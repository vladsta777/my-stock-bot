import telebot
from telebot import types
import pandas as pd
import yfinance as yf
import os
import requests
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
from waitress import serve
import logging
import re
from datetime import datetime

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Мини-сервер
app = Flask('')
@app.route('/')
def home(): return "Market Bot is Active", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

DIGEST_TICKERS = {
    "Crude Oil": "CL=F", "Natural Gas": "NG=F", "Gold": "GC=F",
    "Dow Jones": "YM=F", "S&P 500": "ES=F", "Nasdaq 100": "NQ=F", "Russell 2000": "RTY=F"
}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_volume(volume):
    """Исправлено: берет число до и одну цифру после запятой/точки, добавляя M или K."""
    try:
        val_str = str(volume).upper()
        # Если Yahoo уже прислал с буквой, оставляем
        if 'M' in val_str or 'K' in val_str:
            return val_str
            
        # Очищаем от запятых и прочего
        clean_val = re.sub(r'[^\d.]', '', val_str)
        if not clean_val: return str(volume)
        
        val = float(clean_val)
        if val >= 1_000_000:
            return f"{val/1_000_000:.1f}M"
        if val >= 1_000:
            return f"{val/1_000:.1f}K"
        return str(int(val))
    except:
        return str(volume)

# --- ФУНКЦИИ ---

def get_daily_digest():
    try:
        lines = [f"📅 <b>Обзор рынка на {datetime.now().strftime('%d.%m.%Y')}</b>\n"]
        lines.append("📊 <b>Фьючерсы и Индексы:</b>")
        for name, ticker in DIGEST_TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="2d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    change = ((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                    emoji = "🟢" if change >= 0 else "🔴"
                    lines.append(f"{emoji} <a href='https://finance.yahoo.com/quote/{ticker}'>{name:12}</a>: <b>{price:.2f}</b> (<code>{change:+.2f}%</code>)")
            except: continue
        
        lines.append("\n🗓 <b>Ключевые события (NY Time):</b>")
        lines.append("• <b>Ставка ФРС:</b> 29.04 | <i>Тек: 3.75% (18.03)</i>")
        lines.append("• <b>CPI (Инфляция):</b> 15.04 | <i>Тек: 2.4% (12.03)</i>")
        lines.append("• <b>NFP/Безработица:</b> 03.04 | <i>Тек: 4.4% (06.03)</i>")
        return "\n".join(lines)
    except: return "❌ Ошибка загрузки дайджеста."

def get_ticker_info(ticker_symbol):
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        if not info or ('currentPrice' not in info and 'regularMarketPrice' not in info): return None

        day_change = info.get('regularMarketChangePercent', 0)
        change_emoji = "🟢" if day_change >= 0 else "🔴"

        hist = stock.history(period="20d")
        atr = (hist['High'] - hist['Low']).tail(14).mean() if len(hist) > 0 else 0

        calendar = stock.calendar
        next_report = "N/A"
        if calendar and 'Earnings Date' in calendar:
            next_report = calendar['Earnings Date'][0].strftime('%d.%m')
        
        forecast = info.get('earningsEstimateNextQuarter') or "N/A"
        forecast_str = f"{forecast:.2f}" if isinstance(forecast, (int, float)) else "N/A"

        prev_actual_str = "N/A"
        try:
            earn_hist = stock.earnings_history
            if not earn_hist.empty:
                last_row = earn_hist.dropna(subset=['EPS Actual']).iloc[-1]
                prev_actual_str = f"{last_row['EPS Actual']:.2f}"
        except:
            prev_actual = info.get('trailingEps', "N/A")
            prev_actual_str = f"{prev_actual:.2f}" if isinstance(prev_actual, (int, float)) else "N/A"

        # --- НОВОСТИ С MARKETWATCH ---
        news_lines = ["🗞 <b>MarketWatch News:</b>"]
        try:
            mw_url = f"https://www.marketwatch.com/investing/stock/{ticker_symbol}"
            mw_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            resp = requests.get(mw_url, headers=mw_headers, timeout=5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                headlines = soup.find_all('h3', class_='article__headline', limit=3)
                if headlines:
                    for hl in headlines:
                        title = hl.get_text(strip=True)
                        link_tag = hl.find('a')
                        link = link_tag['href'] if link_tag else "#"
                        if link.startswith('/'): link = "https://www.marketwatch.com" + link
                        news_lines.append(f"• <a href='{link}'>{title}</a>")
                else:
                    news_lines.append("<i>Новостей не найдено</i>")
            else:
                news_lines.append("<i>Источник недоступен</i>")
        except:
            news_lines.append("<i>Ошибка загрузки новостей</i>")
        
        last_news_text = "\n".join(news_lines)

        text = (
            f"🔍 <b>{info.get('longName', ticker_symbol)} ({ticker_symbol})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: <b>{info.get('currentPrice') or info.get('regularMarketPrice')} {info.get('currency', 'USD')}</b> | {change_emoji} <b>{day_change:+.2f}%</b>\n"
            f"📊 Volume: <b>{info.get('volume', 0):,}</b>\n"
            f"📈 Avg Vol: <b>{info.get('averageVolume', 0):,}</b>\n"
            f"🎈 Float: <b>{info.get('floatShares', 0)/1e6:.2f}M</b>\n"
            f"🏢 Market Cap: <b>{info.get('marketCap', 0)/1e9:.2f}B</b>\n"
            f"📏 ATR: <b>{atr:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>EARNINGS:</b>\n"
            f"• Ожидаем: <b>{next_report}</b> | Прогноз: <b>{forecast_str}</b> (Прошлый факт: <b>{prev_actual_str}</b>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{last_news_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>Open in Yahoo</a>"
        )
        return text
    except: return None

def send_market_data(message, category):
    try:
        url = f"https://finance.yahoo.com/markets/stocks/{category}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        dfs = pd.read_html(url, storage_options=headers)
        df = dfs[0].head(10)
        
        is_gainers = category == "gainers"
        cat_label = "GAINERS 🚀" if is_gainers else "LOSERS 📉"
        title = f"📊 <b>TOP {cat_label}:</b>\n<i>Нажми для быстрого анализа:</i>"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for _, row in df.iterrows():
            sym = str(row['Symbol'])
            price_raw = str(row['Price']).split('+')[0].split('-')[0].replace('$', '').strip()
            full_row_str = " ".join(map(str, row.values))
            change_match = re.search(r'([+-]\d+\.\d+\s\([+-]?\d+\.?\d*%\))', full_row_str)
            change_display = change_match.group(1) if change_match else "0.00 (0%)"
            
            # Применяем новое форматирование объема
            vol_formatted = format_volume(row.get('Volume', '-'))
            
            emoji = "🟢" if is_gainers else "🔴"
            btn_text = f"{emoji} {sym:5} | ${price_raw} {change_display} | Vol: {vol_formatted}"
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"t_info_{sym}")
            markup.add(btn)
        
        bot.send_message(message.chat.id, title, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        logger.error(f"Market data error: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка данных.")

# --- ОБРАБОТКА ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📰 Обзор на сегодня", "🔍 Поиск по тикеру")
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    return markup

@bot.callback_query_handler(func=lambda call: call.data.startswith('t_info_'))
def handle_ticker_callback(call):
    ticker = call.data.replace('t_info_', '')
    res = get_ticker_info(ticker)
    if res:
        bot.send_message(call.message.chat.id, res, parse_mode="HTML", disable_web_page_preview=True)
    else:
        bot.answer_callback_query(call.id, "❌ Ошибка загрузки.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v16.0</b>", parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    text = message.text
    if text == "📰 Обзор на сегодня":
        bot.send_message(message.chat.id, get_daily_digest(), parse_mode="HTML", disable_web_page_preview=True)
    elif text == "🔍 Поиск по тикеру":
        bot.send_message(message.chat.id, "✍️ Введите тикер (например, AAPL):")
    elif "Top" in text:
        cat = "gainers" if "Gainers" in text else "losers"
        send_market_data(message, cat)
    elif re.fullmatch(r'[A-Za-z0-9.=]{1,10}', text):
        res = get_ticker_info(text)
        if res: bot.send_message(message.chat.id, res, parse_mode="HTML", disable_web_page_preview=True)
        else: bot.send_message(message.chat.id, "❌ Тикер не найден.")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=10)
