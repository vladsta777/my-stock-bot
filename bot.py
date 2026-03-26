import telebot
from telebot import types
import yfinance as yf
import os

# Берем токен из переменных среды (настроим в Render)
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_data(category):
    # Список для примера (можно расширить)
    tickers = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META"]
    results = []
    
    for t in tickers:
        stock = yf.Ticker(t)
        hist = stock.history(period="2d")
        if len(hist) >= 2:
            price = hist['Close'].iloc[-1]
            change = ((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            results.append({"ticker": t, "price": price, "change": change})

    if category == "gainers":
        results.sort(key=lambda x: x['change'], reverse=True)
        title = "🚀 Top Gainers"
    elif category == "losers":
        results.sort(key=lambda x: x['change'])
        title = "📉 Top Losers"
    else:
        title = "📊 Market Data"

    msg = f"<b>{title} (Pre-market est.):</b>\n\n"
    for item in results[:5]:
        emoji = "🟢" if item['change'] >= 0 else "🔴"
        msg += f"{emoji} {item['ticker']}: ${item['price']:.2f} ({item['change']:+.2f}%)\n"
    return msg

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🚀 Top Gainers")
    btn2 = types.KeyboardButton("📉 Top Losers")
    btn3 = types.KeyboardButton("📈 New High")
    btn4 = types.KeyboardButton("📉 New Low")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    return markup

# Реакция на команду /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, 
        "Привет! Я твой финансовый ассистент. Выбери категорию:", 
        reply_markup=main_keyboard()
    )

# Реакция на нажатие кнопок (текстовых)
@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text == "🚀 Top Gainers":
        bot.send_message(message.chat.id, get_data("gainers"), parse_mode="HTML")
    elif message.text == "📉 Top Losers":
        bot.send_message(message.chat.id, get_data("losers"), parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "Используйте кнопки в меню 👇")

# Запуск бота в режиме бесконечного прослушивания
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
