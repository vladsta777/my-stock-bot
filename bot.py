import telebot
from telebot import types
import yfinance as yf
import os
import pandas as pd
from flask import Flask
from threading import Thread

# 1. Настройка микро-сервера для Render
app = Flask('')

@app.route('/')
def home():
    return "Бот активен"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_market_data(category):
    try:
        # Ссылки на актуальные скринеры Yahoo Finance
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-highs/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-lows/"
        }
        
        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (US Market)</b>",
            "losers": "📉 <b>Top 10 Losers (US Market)</b>",
            "high": "📈 <b>Top 10 New 52W Highs</b>",
            "low": "🧊 <b>Top 10 New 52W Lows</b>"
        }

        # Читаем таблицу с сайта (pandas делает это за один запрос)
        tables = pd.read_html(urls[category])
        df = tables[0].head(10) # Берем топ-10 актуальных акций

        lines = []
        for _, row in df.iterrows():
            ticker = row['Symbol']
            price = f"{row['Price']:.2f}" if isinstance(row['Price'], (int, float)) else row['Price']
            
            # Определяем изменение (для разных таблиц колонки могут чуть отличаться)
            change = row.get('% Change', row.get('Change', ''))
            
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            lines.append(f"{emoji} <code>{ticker:5}</code>: <b>${price}</b> (<code>{change}</code>)")

        return f"{titles[category]}\n\n" + "\n".join(lines)

    except Exception as e:
        print(f"Error: {e}")
        return "❌ <i>Не удалось получить данные с биржи. Попробуйте позже.</i>"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🚀 Top Gainers")
    btn2 = types.KeyboardButton("📉 Top Losers")
    btn3 = types.KeyboardButton("📈 New High")
    btn4 = types.KeyboardButton("📉 New Low")
    
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    
    bot.send_message(
        message.chat.id, 
        "<b>Market Terminal США</b>\n\nАктуальные данные по всему рынку:", 
        parse_mode="HTML", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 New High": "high",
        "📉 New Low": "low"
    }
    
    if text in mapping:
        bot.send_message(chat_id, "⌛ <i>Анализирую рынок
