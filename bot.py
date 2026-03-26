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

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask('')
@app.route('/')
def home(): return "Market Bot is Active", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    serve(app, host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_ticker_info(ticker_symbol):
    """Функция для поиска расширенных данных по тикеру"""
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
        
        emoji = "🟢" if change >= 0 else "🔴"
        
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
        logger.error(f"Ошибка поиска тикера {ticker_symbol}: {e}")
        return None

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    markup.row("🔍 Поиск по тикеру") # НОВАЯ КНОПКА
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id, 
        "📊 <b>Market Terminal v4.2</b>\n\nВыберите категорию анализа:", 
        parse_mode="HTML", 
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 52 Week Gainers": "high",
        "🧊 52 Week Losers": "low"
    }
    
    # 1. Если нажали "Поиск"
    if message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ <b>Введите тикер акции (например: AAPL, TSLA или NVDA):</b>", parse_mode="HTML")
        # Регистрируем следующий шаг: бот будет ждать текст от юзера и передаст его в функцию process_ticker
        bot.register_next_step_handler(msg, process_ticker)
        
    # 2. Если нажали одну из стандартных кнопок
    elif message.text in mapping:
        from bot_logic import get_market_data # предполагаем, что функция парсинга там или в этом же файле
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Загрузка данных...</i>", parse_mode="HTML")
        # Для краткости здесь использую заглушку, вставьте вашу функцию get_market_data сюда
        response = "Данные обновляются..." 
        # (Используйте вашу функцию get_market_data как раньше)
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu())

    else:
        bot.send_message(message.chat.id, "🔄 Пожалуйста, используйте кнопки меню:", reply_markup=get_main_menu())

def process_ticker(message):
    """Обработка введенного тикера после нажатия кнопки Поиск"""
    ticker = message.text.upper().strip()
    
    # Если пользователь передумал и нажал другую кнопку меню вместо ввода тикера
    if ticker in ["🚀 TOP GAINERS", "📉 TOP LOSERS", "📈 52 WEEK GAINERS", "🧊 52 WEEK LOSERS", "🔍 ПОИСК ПО ТИКЕРУ"]:
        handle_menu(message)
        return

    status_msg = bot.send_message(message.chat.id, f"🔍 <i>Анализируем {ticker}...</i>", parse_mode="HTML")
    response = get_ticker_info(ticker)
    bot.delete_message(message.chat.id, status_msg.message_id)
    
    if response:
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu(), disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, f"❌ Тикер <b>{ticker}</b> не найден. Попробуйте еще раз или выберите категорию:", 
                         parse_mode="HTML", reply_markup=get_main_menu())

# --- Запуск ---
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    try:
        bot.remove_webhook(drop_pending_updates=True)
    except:
        bot.remove_webhook()
    time.sleep(2)
    bot.infinity_polling(timeout=60)
