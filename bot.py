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
    """Сборка ежедневной сводки по рынкам"""
    try:
        lines = [f"📅 <b>Обзор рынка на {datetime.now().strftime('%d.%m.%Y')}</b>\n"]
        lines.append("📊 <b>Фьючерсы и Индексы:</b>")
        
        for name, ticker in DIGEST_TICKERS.items():
            t = yf.Ticker(ticker)
            # Пытаемся получить данные за сегодня
            hist = t.history(period="2d")
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change = ((price - prev_price) / prev_price) * 100
                emoji = "🟢" if change >= 0 else "🔴"
                
                link = f"https://finance.yahoo.com/quote/{ticker}"
                lines.append(f"{emoji} <a href='{link}'>{name:12}</a>: <b>{price:.2f}</b> (<code>{change:+.2f}%</code>)")
        
        lines.append("\n🗓 <b>Экономический календарь:</b>")
        lines.append("• <b>Ставка ФРС:</b> Следующее решение 29 апреля 2026 г.")
        lines.append("• <b>Безработица:</b> Данные Jobless Claims — каждый четверг в 15:30 МСК.")
        
        lines.append("\n🗞 <b>Главные новости (Digest):</b>")
        # Парсим новости через тикер S&P 500 (SPY)
        spy = yf.Ticker("SPY")
        news = spy.news[:3]
        for n in news:
            title = n.get('title')
            url = n.get('link')
            lines.append(f"🔹 <a href='{url}'>{title[:75]}...</a>")
            
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Ошибка дайджеста: {e}")
        return "❌ <i>Не удалось собрать сводку данных.</i>"

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
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')
        
        emoji = "🟢" if (change and change >= 0) else "🔴"
        
        text = (
            f"🔍 <b>{name} ({ticker_symbol})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: <b>{price} {currency}</b>\n"
            f"{emoji} Day Change: <code>{change:.2f}%</code>\n\n"
            f"🏢 Sector: <i>{sector}</i>\n"
            f"🛠 Industry: <i>{industry}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>View on Yahoo Finance</a>"
        )
        return text
    except Exception as e:
        logger.error(f"Ошибка yfinance для {ticker_symbol}: {e}")
        return None

def get_market_data(category):
    try:
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-gainers/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-losers/"
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        
        dfs = pd.read_html(urls[category], storage_options=headers)
        if not dfs: return "❌ Таблицы не найдены."
        
        df = dfs[0].head(10)
        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            change = row.get('52 Week % Change', row.get('% Change', row.get('Change', 'N/A')))
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            lines.append(f"{emoji} <a href='https://finance.yahoo.com/quote/{ticker}'>{ticker:5}</a> | <b>${price}</b> (<code>{change}</code>)")

        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (Daily)</b>",
            "losers": "📉 <b>Top 10 Losers (Daily)</b>",
            "high": "📈 <b>52 Week Gainers</b>",
            "low": "🧊 <b>52 Week Losers</b>"
        }
        return f"{titles[category]}\n\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"Ошибка парсинга {category}: {e}")
        return "❌ <i>Данные временно недоступны.</i>"

# --- ЛОГИКА ИНТЕРФЕЙСА ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    markup.row("📰 Обзор на сегодня")
    markup.row("🔍 Поиск по тикеру")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v4.8</b>\n\nВыберите категорию, получите сводку дня или введите тикер:", 
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
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Формирую сводку рынка...</i>", parse_mode="HTML")
        response = get_daily_digest()
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu(), disable_web_page_preview=True)
    
    elif message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ <b>Введите тикер акции (напр. AAPL, NVDA, TSLA):</b>", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_ticker_step)
    
    elif message.text in mapping:
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Загрузка данных...</i>", parse_mode="HTML")
        response = get_market_data(mapping[message.text])
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu(), disable_web_page_preview=True)
    
    else:
        bot.send_message(message.chat.id, "🔄 Используйте кнопки меню:", reply_markup=get_main_menu())

def process_ticker_step(message):
    ticker = message.text.upper().strip()
    menu_cmds = ["🚀 TOP GAINERS", "📉 TOP LOSERS", "📈 52 WEEK GAINERS", "🧊 52 WEEK LOSERS", "🔍 ПОИСК ПО ТИКЕРУ", "📰 ОБЗОР НА СЕГОДНЯ"]
    if ticker in menu_cmds:
        handle_menu(message)
        return

    status_msg = bot.send_message(message.chat.id, f"🔍 <i>Анализируем {ticker}...</i>", parse_mode="HTML")
    response = get_ticker_info(ticker)
    bot.delete_message(message.chat.id, status_msg.message_id)
    
    if response:
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu(), disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, f"❌ Тикер <b>{ticker}</b> не найден.", 
                         parse_mode="HTML", reply_markup=get_main_menu())

# --- ЗАПУСК ---

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    
    try:
        bot.remove_webhook(drop_pending_updates=True)
    except:
        bot.remove_webhook()
    
    time.sleep(2)
    logger.info(">>> Бот запущен!")
    
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception as e:
            if "Conflict" in str(e):
                time.sleep(20)
            else:
                logger.error(f"Ошибка Polling: {e}")
                time.sleep(5)
