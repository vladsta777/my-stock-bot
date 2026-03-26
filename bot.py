import telebot
from telebot import types
import yfinance as yf
import os
import pandas as pd
from flask import Flask
from threading import Thread

# 1. Настройка микро-сервера
app = Flask('')

@app.route('/')
def home():
    return "Бот Маркет-Терминал запущен"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_market_data(category):
    try:
        # Прямые ссылки на скринеры Yahoo Finance (весь рынок США)
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-highs/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-lows/"
        }
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # Читаем таблицу
        tables = pd.read_html(urls[category], storage_options={'User-Agent': 'Mozilla/5.0'})
        df = tables[0].head(10) # Берем ТОП-10

        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            # Обработка цены (убираем лишние символы, если есть)
            price = row['Price']
            change = row.get('% Change', row.get('Change', '0%'))
            
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            lines.append(f"{emoji} <code>{ticker:5}</code>: <b>${price}</b> (<code>{change}</code>)")

        title = {
            "gainers": "🚀 <b>Top 10 Gainers (US)</b>",
            "losers": "📉 <b>Top 10 Losers (US)</b>",
            "high": "📈 <b>Top 10 New Highs</b>",
            "low": "🧊 <b>Top 10 New Lows</b>"
        }[category]

        return f"{title}\n\n" + "\n".join(lines)

    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return "❌ <i>Данные временно недоступны (Yahoo обновил структуру). Попробуйте позже.</i>"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🚀 Top Gainers"), types.KeyboardButton("📉 Top Losers"))
    markup.row(types.KeyboardButton("📈 New High"), types.KeyboardButton("📉 New Low"))
    
    bot.send_message(
        message.chat.id, 
        "<b>Market Terminal v2.0</b>\nДанные по всему рынку США (Топ-10):", 
        parse_mode="HTML", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 New High": "high",
        "📉 New Low": "low"
    }
    if message.text in mapping:
        bot.send_message(message.chat.id, "⌛ <i>Запрашиваю биржевые таблицы...</i>", parse_mode="HTML")
        bot.send_message(message.chat.id, get_market_data(mapping[message.text]), parse_mode="HTML")

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    print("Скрипт v2.0 (Scraper) запущен...")
    bot.infinity_polling()
