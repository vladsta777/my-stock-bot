import telebot
from telebot import types
import yfinance as yf
import os
from flask import Flask
from threading import Thread

# 1. Настройка микро-сервера для Render
app = Flask('')

@app.route('/')
def home():
    return "Бот активен"

def run_flask():
    # Render сам подставит нужный порт в переменную PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_stock_data(category):
    # Список для теста
    tickers = ["AAPL", "TSLA", "NVDA", "MSFT", "AMD"]
    results = []
    for t in tickers:
        try:
            s = yf.Ticker(t)
            df = s.history(period="2d")
            if len(df) >= 2:
                last = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                pct = ((last - prev) / prev) * 100
                results.append(f"{'🟢' if pct >= 0 else '🔴'} {t}: ${last:.2f} ({pct:+.2f}%)")
        except: continue
    return "\n".join(results) if results else "Нет данных"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Top Gainers", "📉 Top Losers")
    bot.send_message(message.chat.id, "Выбери категорию:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def echo_all(message):
    if "Gainers" in message.text:
        bot.send_message(message.chat.id, get_data_simulated("gainers"))
    elif "Losers" in message.text:
        bot.send_message(message.chat.id, get_data_simulated("losers"))

def get_data_simulated(cat):
    # Упрощенная заглушка для проверки
    return f"Данные по {cat}:\n" + get_stock_data(cat)

# 3. ЗАПУСК
if __name__ == "__main__":
    # Сначала запускаем Flask в отдельном потоке
    t = Thread(target=run_flask)
    t.start()
    
    print("Порт открыт, запускаю бота...")
    # Теперь запускаем самого бота
    bot.infinity_polling()
