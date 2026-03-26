import telebot
from telebot import types
import pandas as pd
import os
from flask import Flask
from threading import Thread

# 1. Мини-сервер для Render
app = Flask('')
@app.route('/')
def home(): return "Market Bot is Running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_market_data(category):
    try:
        # Прямые ссылки на разделы Yahoo Finance
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-highs/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-lows/"
        }
        
        # Эмуляция браузера, чтобы Yahoo не выдал ошибку 404/403
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        # Читаем таблицу. [0] - это первая таблица на странице
        dfs = pd.read_html(urls[category], storage_options=headers)
        df = dfs[0].head(10) # Строго ТОП-10

        lines = []
        for _, row in df.iterrows():
            ticker = row['Symbol']
            price = row['Price']
            # Пробуем найти колонку с процентами (она может называться по-разному)
            change = row.get('% Change', row.get('Change', 'N/A'))
            
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            lines.append(f"{emoji} <code>{ticker:5}</code> | <b>${price}</b> (<code>{change}</code>)")

        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (US Market)</b>",
            "losers": "📉 <b>Top 10 Losers (US Market)</b>",
            "high": "📈 <b>New 52W Highs</b>",
            "low": "🧊 <b>New 52W Lows</b>"
        }

        return f"{titles[category]}\n\n" + "\n".join(lines)

    except Exception as e:
        print(f"Ошибка: {e}")
        return "❌ <i>Yahoo временно ограничил доступ к таблицам. Попробуйте через 5 минут.</i>"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 New High", "📉 New Low")
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v3.0</b>\nДанные со всего рынка США:", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 New High": "high",
        "📉 New Low": "low"
    }
    if message.text in mapping:
        # Отправляем временное сообщение, чтобы пользователь видел активность
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Скрейпинг таблиц Yahoo...</i>", parse_mode="HTML")
        
        response = get_market_data(mapping[message.text])
        
        # Удаляем "Загружаю..." и присылаем результат
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML")

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    bot.infinity_polling()
if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    print("Бот запущен...")
    # non_stop=True поможет боту переподключиться, если связь оборвется
    bot.infinity_polling(non_stop=True, skip_pending=True)
