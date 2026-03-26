import telebot
from telebot import types
import pandas as pd
import yfinance as yf
import os
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

        # --- ЛОГИКА EARNINGS ---
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

        # --- ОБНОВЛЕННАЯ ЛОГИКА: 3 ПОСЛЕДНИЕ НОВОСТИ (БЕЗ ВРЕМЕНИ) ---
        news_lines = ["🗞 <b>Последние новости:</b>"]
        try:
            news = stock.news
            if news and len(news) > 0:
                for item in news[:3]: # Берем 3 новости
                    n_title = item.get('title', 'Новость без заголовка')
                    n_link = item.get('link', '#')
                    news_lines.append(f"• <a href='{n_link}'>{n_title}</a>")
            else:
                news_lines.append("<i>Новостей не найдено</i>")
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
    """Парсинг данных и отправка сообщения с информативными кнопками в один столбец"""
    try:
        url = f"https://finance.yahoo.com/markets/stocks/{category}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        dfs = pd.read_html(url, storage_options=headers)
        df = dfs[0].head(10)
        
        title = f"📊 <b>TOP {category.upper()}:</b>\n<i>Нажми для быстрого анализа:</i>"
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        for _, row in df.iterrows():
            sym = row['Symbol']
            price = row['Price']
            chg = row.get('% Change', row.get('Change', '0%'))
            vol = row.get('Volume', '-')
            
            # Эмодзи направления
            emoji = "🟢" if "-" not in str(chg) else "🔴"
            
            # Текст кнопки: Тикер | Цена | Изменение | Объем
            btn_text = f"{emoji} {sym:5} | ${price} | {chg} | Vol: {vol}"
            
            btn = types.InlineKeyboardButton(btn_text, callback_data=f"t_info_{sym}")
            markup.add(btn)
        
        bot.send_message(message.chat.id, title, parse_mode="HTML", reply_markup=markup)
    except:
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
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v13.0</b>", parse_mode="HTML", reply_markup=get_main_menu())

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
    bot.infinity_polling()
