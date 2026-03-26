import telebot
from telebot import types
import pandas as pd
import os
from flask import Flask
from threading import Thread
from waitress import serve
import requests

# 1. Мини-сервер для Render
app = Flask('')

@app.route('/')
def home():
    return "Market Bot is Running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    # Waitress обеспечивает стабильную работу 24/7
    serve(app, host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_market_data(category):
    try:
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-highs/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-lows/"
        }
        
        # Расширенные заголовки, чтобы Yahoo не блокировал запросы
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        # Читаем таблицу
        dfs = pd.read_html(urls[category], storage_options=headers)
        if not dfs:
            return "❌ Таблицы на странице не найдены."
            
        df = dfs[0].head(10)

        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            # Пытаемся достать процент изменения, пробуя разные имена колонок
            change = row.get('% Change', row.get('Change', 'N/A'))
            
            yahoo_link = f"https://finance.yahoo.com/quote/{ticker}"
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            
            lines.append(f"{emoji} <a href='{yahoo_link}'>{ticker:5}</a> | <b>${price}</b> (<code>{change}</code>)")

        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (US)</b>",
            "losers": "📉 <b>Top 10 Losers (US)</b>",
            "high": "📈 <b>52 Week Gainers</b>",
            "low": "🧊 <b>52 Week Losers</b>"
        }

        return f"{titles[category]}\n\n" + "\n".join(lines)

    except Exception as e:
        print(f"Ошибка получения данных: {e}")
        return "❌ <i>Yahoo временно ограничил доступ. Попробуйте через пару минут.</i>"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    
    bot.send_message(
        message.chat.id, 
        "📊 <b>Market Terminal v3.6</b>\n\nВыберите категорию для анализа рынка США:", 
        parse_mode="HTML", 
        reply_markup=markup,
        disable_web_page_preview=True
    )

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 52 Week Gainers": "high",
        "🧊 52 Week Losers": "low"
    }
    
    if message.text in mapping:
        # Отправляем уведомление о загрузке
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Запрашиваю биржевые данные...</i>", parse_mode="HTML")
        
        response = get_market_data(mapping[message.text])
        
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True)

if __name__ == "__main__":
    # 1. Запуск веб-сервера в фоне
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print(">>> Сервер Waitress запущен. Начинаю опрос Telegram...")
    
    # 2. Бесконечный цикл опроса с защитой от вылетов
    while True:
        try:
            # skip_pending=True игнорирует сообщения, присланные пока бот был выключен
            bot.infinity_polling(non_stop=True, skip_pending=True, timeout=90)
        except Exception as e:
            print(f" Ошибка поллинга: {e}. Перезапуск через 5 секунд...")
            import time
            time.sleep(5)
