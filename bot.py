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
        if not info or 'currentPrice' not in info: return None

        # Расчет изменения за день (%)
        day_change = info.get('regularMarketChangePercent', 0)
        change_emoji = "🟢" if day_change >= 0 else "🔴"

        # Расчет ATR (упрощенно за 14 дней)
        hist = stock.history(period="20d")
        atr = (hist['High'] - hist['Low']).tail(14).mean() if len(hist) > 0 else 0

        # Данные по Earnings
        calendar = stock.calendar
        next_report = "N/A"
        if calendar and 'Earnings Date' in calendar:
            next_report = calendar['Earnings Date'][0].strftime('%d.%m')
        
        last_eps = info.get('trailingEps', 'N/A')

        text = (
            f"🔍 <b>{info.get('longName', ticker_symbol)} ({ticker_symbol})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: <b>{info.get('currentPrice')} {info.get('currency', 'USD')}</b> | {change_emoji} <b>{day_change:+.2f}%</b>\n"
            f"📊 Volume: <b>{info.get('volume', 0):,}</b>\n"
            f"📈 Avg Vol: <b>{info.get('averageVolume', 0):,}</b>\n"
            f"🎈 Float: <b>{info.get('floatShares', 0)/1e6:.2f}M</b>\n"
            f"🏢 Market Cap: <b>{info.get('marketCap', 0)/1e9:.2f}B</b>\n"
            f"📏 ATR: <b>{atr:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>EARNINGS:</b>\n"
            f"• Ожидаем: <b>{next_report}</b> | Тек: <b>{last_eps} (last)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>Open in Yahoo</a>"
        )
        return text
    except: return None

def get_market_data(category):
    try:
        url = f"https://finance.yahoo.com/markets/stocks/{category}/"
        headers = {"User-Agent": "Mozilla/5.0"}
        dfs = pd.read_html(url, storage_options=headers)
        df = dfs[0].head(10)
        
        emoji = "🟢" if category == "gainers" else "🔴"
        lines = [f"📊 <b>TOP {category.upper()}:</b>\n"]
        
        for _, row in df.iterrows():
            sym = row['Symbol']
            price = row['Price']
            chg = row.get('% Change', row.get('Change', '0%'))
            lines.append(f"{emoji} <a href='https://finance.yahoo.com/quote/{sym}'>{sym:5}</a> | <b>${price}</b> (<code>{chg}</code>)")
        
        return "\n".join(lines)
    except: return "❌ Ошибка данных."

# --- ОБРАБОТКА ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📰 Обзор на сегодня", "🔍 Поиск по тикеру")
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v8.0</b>", parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_all_messages(message):
    text = message.text
    
    if text == "📰 Обзор на сегодня":
        bot.send_message(message.chat.id, get_daily_digest(), parse_mode="HTML", disable_web_page_preview=True)
    
    elif text == "🔍 Поиск по тикеру":
        bot.send_message(message.chat.id, "✍️ Введите тикер (например, AAPL):")
    
    elif "Top" in text:
        cat = "gainers" if "Gainers" in text else "losers"
        bot.send_message(message.chat.id, get_market_data(cat), parse_mode="HTML", disable_web_page_preview=True)
    
    elif re.fullmatch(r'[A-Za-z]{1,5}', text):
        res = get_ticker_info(text)
        if res: bot.send_message(message.chat.id, res, parse_mode="HTML", disable_web_page_preview=True)
        else: bot.send_message(message.chat.id, "❌ Тикер не найден.")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
