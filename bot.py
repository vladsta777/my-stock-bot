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
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# 2. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Список акций для мониторинга
TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMD", "GOOGL", "AMZN", "META", "NFLX", "COIN"]

def get_market_data(category):
    results = []
    
    for t in TICKERS:
        try:
            stock = yf.Ticker(t)
            if category in ["gainers", "losers"]:
                df = stock.history(period="2d")
                if len(df) >= 2:
                    last = df['Close'].iloc[-1]
                    prev = df['Close'].iloc[-2]
                    pct = ((last - prev) / prev) * 100
                    results.append({"ticker": t, "price": last, "change": pct})
            
            elif category in ["high", "low"]:
                info = stock.info
                current = info.get('currentPrice') or info.get('regularMarketPrice')
                if category == "high":
                    h52 = info.get('fiftyTwoWeekHigh')
                    if current and h52 and current >= h52 * 0.98:
                        results.append(f"🔥 <code>{t:5}</code>: <b>${current:.2f}</b> (Пик: ${h52:.2f})")
                else:
                    l52 = info.get('fiftyTwoWeekLow')
                    if current and l52 and current <= l52 * 1.02:
                        results.append(f"🧊 <code>{t:5}</code>: <b>${current:.2f}</b> (Дно: ${l52:.2f})")
        except:
            continue

    if category == "gainers":
        results.sort(key=lambda x: x['change'], reverse=True)
        lines = [f"🟢 <code>{item['ticker']:5}</code>: <b>${item['price']:.2f}</b> (<code>{item['change']:+.2f}%</code>)" for item in results[:5]]
        title = "🚀 <b>Top Gainers</b>"
    elif category == "losers":
        results.sort(key=lambda x: x['change'])
        lines = [f"🔴 <code>{item['ticker']:5}</code>: <b>${item['price']:.2f}</b> (<code>{item['change']:+.2f}%</code>)" for item in results[:5]]
        title = "📉 <b>Top Losers</b>"
    elif category == "high":
        title = "📈 <b>New 52W High</b>"
        lines = results[:5]
    else:
        title = "📉 <b>New 52W Low</b>"
        lines = results[:5]

    if not lines:
        return f"{title}\n\n<i>Нет данных по списку наблюдения</i>"
    
    return f"{title}\n\n" + "\n".join(lines)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Явно задаем структуру рядов
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    
    btn1 = types.KeyboardButton("🚀 Top Gainers")
    btn2 = types.KeyboardButton("📉 Top Losers")
    btn3 = types.KeyboardButton("📈 New High")
    btn4 = types.KeyboardButton("📉 New Low")
    
    # Добавляем по две кнопки в ряд
    markup.row(btn1, btn2)
    markup.row(btn3, btn4)
    
    bot.send_message(
        message.chat.id, 
        "<b>Ассистент фондового рынка США</b>\n\nВыберите категорию данных:", 
        parse_mode="HTML", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    chat_id = message.chat.id
    text = message.text.strip() # Убираем лишние пробелы
    
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 New High": "high",
        "📉 New Low": "low"
    }
    
    if text in mapping:
        bot.send_message(chat_id, "⌛ <i>Загружаю данные...</i>", parse_mode="HTML")
        response = get_market_data(mapping[text])
        bot.send_message(chat_id, response, parse_mode="HTML")

if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.start()
    print("Бот запущен...")
    bot.infinity_polling()
