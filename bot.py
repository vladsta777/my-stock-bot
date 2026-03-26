import telebot
from telebot import types
import yfinance as yf
import os
from flask import Flask
from threading import Thread

# --- МИНИ-СЕРВЕР ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

def keep_alive():
    t = Thread(target=run)
    t.start()
# ------------------------------

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_data(category):
    tickers = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META"]
    results = []
    for t in tickers:
        try:
            stock = yf.Ticker(t)
            hist = stock.history(period="2d")
            if len(hist) >= 2:
                price = hist['Close'].iloc[-1]
                change = ((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                results.append({"ticker": t, "price": price, "change": change})
        except: continue

    if category == "gainers":
        results.sort(key=lambda x: x['change'], reverse=True)
        title = "🚀 Top Gainers"
    else:
        results.sort(key=lambda x: x['change'])
        title = "📉 Top Losers"

    msg = f"<b>{title}:</b>\n\n"
    for item in results[:5]:
        emoji = "🟢" if item['change'] >= 0 else "🔴"
        msg += f"{emoji} {item['ticker']}: ${item['price']:.2f} ({item['change']:+.2f}%)\n"
    return msg

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚀 Top Gainers"), types.KeyboardButton("📉 Top Losers"))
    markup.add(types.KeyboardButton("📈 New High"), types.KeyboardButton("📉 New Low"))
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Бот готов к работе!", reply_markup=main_keyboard())

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🚀 Top Gainers":
        bot.send_message(message.chat.id, get_data("gainers"), parse_mode="HTML")
    elif message.text == "📉 Top Losers":
        bot.send_message(message.chat.id, get_data("losers"), parse_mode="HTML")

if __name__ == "__main__":
    keep_alive() # Запускаем микро-сервер для Render
    print("Бот запущен...")
    bot.infinity_polling()
