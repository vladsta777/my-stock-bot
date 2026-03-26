import telebot
from telebot import types
import pandas as pd
import yfinance as yf
import os
from flask import Flask
from threading import Thread
from waitress import serve
import logging
import time
from datetime import datetime

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Мини-сервер для UptimeRobot и Health Check
app = Flask('')

@app.route('/')
def home():
    return "Market Bot is Active and Healthy", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск веб-сервера на порту {port}")
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- СПИСКИ ДЛЯ ОБЗОРА ---
DIGEST_TICKERS = {
    "Crude Oil": "CL=F",
    "Natural Gas": "NG=F",
    "Gold": "GC=F",
    "Dow Jones": "YM=F",
    "S&P 500": "ES=F",
    "Nasdaq 100": "NQ=F",
    "Russell 2000": "RTY=F"
}

# --- ФУНКЦИИ ДАННЫХ ---

def get_daily_digest():
    """Сводка по рынкам с макроэкономикой на русском (NY Time)"""
    try:
        lines = [f"📅 <b>Обзор рынка на {datetime.now().strftime('%d.%m.%Y')}</b>\n"]
        lines.append("📊 <b>Фьючерсы и Индексы:</b>")
        
        for name, ticker in DIGEST_TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                
                if not hist.empty and len(hist) >= 2:
                    price = hist['Close'].iloc[-1]
                    prev_price = hist['Close'].iloc[-2]
                    change = ((price - prev_price) / prev_price) * 100
                    emoji = "🟢" if change >= 0 else "🔴"
                    change_str = f"<code>{change:+.2f}%</code>"
                else:
                    price = t.info.get('regularMarketPrice') or t.info.get('currentPrice', 'N/A')
                    emoji = "⚪️"
                    change_str = "<code>нет данных</code>"
                
                link = f"https://finance.yahoo.com/quote/{ticker}"
                p_val = f"{price:.2f}" if isinstance(price, (int, float)) else price
                lines.append(f"{emoji} <a href='{link}'>{name:12}</a>: <b>{p_val}</b> ({change_str})")
            except Exception:
                continue
        
        lines.append("\n🗓 <b>Ключевые события (New York Time):</b>")
        # Данные актуализированы на весну 2026 года
        lines.append("• <b>Решение по ставке ФРС:</b> 29 апреля, 14:00 ET")
        lines.append("• <b>Инфляция (CPI):</b> 15 апреля, 08:30 ET")
        lines.append("• <b>Занятость (NFP):</b> 3 апреля, 08:30 ET")
        lines.append("• <b>Уровень безработицы:</b> 3 апреля, 08:30 ET")
        
        lines.append("\n🗞 <b>Главные новости:</b>")
        try:
            spy = yf.Ticker("SPY")
            news = spy.news[:3]
            for n in news:
                lines.append(f"🔹 <a href='{n.get('link')}'>{n.get('title')[:75]}...</a>")
        except:
            lines.append("<i>Новости временно недоступны</i>")
            
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Ошибка дайджеста: {e}")
        return "❌ <i>Не удалось собрать сводку. Попробуйте еще раз.</i>"

def get_ticker_info(ticker_symbol):
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None
            
        price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
        currency = info.get('currency', 'USD')
        change = info.get('regularMarketChangePercent', 0)
        name = info.get('longName', ticker_symbol)
        
        emoji = "🟢" if (change and change >= 0) else "🔴"
        
        text = (
            f"🔍 <b>{name} ({ticker_symbol})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: <b>{price} {currency}</b>\n"
            f"{emoji} Day Change: <code>{change:.2f}%</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>View on Yahoo Finance</a>"
        )
        return text
    except Exception:
        return None

def get_market_data(category):
    try:
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-gainers/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-losers/"
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        dfs = pd.read_html(urls[category], storage_options=headers)
        df = dfs[0].head(10)
        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            change = row.get('% Change', row.get('Change', 'N/A'))
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            lines.append(f"{emoji} <a href='https://finance.yahoo.com/quote/{ticker}'>{ticker:5}</a> | <b>${price}</b> (<code>{change}</code>)")

        titles = {"gainers": "🚀 <b>Top 10 Gainers</b>", "losers": "📉 <b>Top 10 Losers</b>", "high": "📈 <b>52W High</b>", "low": "🧊 <b>52W Low</b>"}
        return f"{titles[category]}\n\n" + "\n".join(lines)
    except Exception:
        return "❌ <i>Данные временно недоступны.</i>"

# --- ЛОГИКА ИНТЕРФЕЙСА ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Сводка и Поиск сверху в один ряд
    markup.row("📰 Обзор на сегодня", "🔍 Поиск по тикеру")
    # Остальные кнопки ниже
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v5.1</b>\n\nВыберите раздел в меню:", 
                     parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 52 Week Gainers": "high",
        "🧊 52 Week Losers": "low"
    }
    
    if message.text == "📰 Обзор на сегодня":
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Загрузка сводки...</i>", parse_mode="HTML")
        response = get_daily_digest()
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True)
    
    elif message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ <b>Введите тикер (напр. AAPL):</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_ticker_step)
    
    elif message.text in mapping:
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Получаю данные...</i>", parse_mode="HTML")
        response = get_market_data(mapping[message.text])
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True)
    
    else:
        process_ticker_step(message)

def process_ticker_step(message):
    ticker = message.text.upper().strip()
    if any(cmd in ticker for cmd in ["ОБЗОР", "ПОИСК", "TOP", "WEEK"]):
        return

    status_msg = bot.send_message(message.chat.id, f"🔍 <i>Ищу {ticker}...</i>", parse_mode="HTML")
    response = get_ticker_info(ticker)
    bot.delete_message(message.chat.id, status_msg.message_id)
    
    if response:
        bot.send_message(message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, f"❌ Тикер <b>{ticker}</b> не найден.", parse_mode="HTML")

# --- ЗАПУСК ---

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    try:
        bot.remove_webhook(drop_pending_updates=True)
    except:
        pass
    
    logger.info(">>> Бот запущен!")
    bot.infinity_polling(timeout=20, long_polling_timeout=20)
