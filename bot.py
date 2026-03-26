import telebot
from telebot import types
import pandas as pd
import os
from flask import Flask
from threading import Thread

# 1. Мини-сервер
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
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-highs/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-lows/"
        }
        
        headers = {"User-Agent": "Mozilla/5.0"}
        dfs = pd.read_html(urls[category], storage_options=headers)
        df = dfs[0].head(10)

        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            change = row.get('% Change', row.get('Change', 'N/A'))
            
            # Создаем ссылку на профиль акции
            yahoo_link = f"https://finance.yahoo.com/quote/{ticker}"
            
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            # Делаем тикер кликабельным (через HTML)
            lines.append(f"{emoji} <a href='{yahoo_link}'>{ticker:5}</a> | <b>${price}</b> (<code>{change}</code>)")

        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (US)</b>",
            "losers": "📉 <b>Top 10 Losers (US)</b>",
            "high": "📈 <b>52 Week Gainers</b>",
            "low": "🧊 <b>52 Week Losers</b>"
        }

        return f"{titles[category]}\n\n" + "\n".join(lines)

    except Exception as e:
        print(f"Error: {e}")
        return "❌ <i>Данные временно недоступны.</i>"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Новые названия кнопок
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    
    bot.send_message(
        message.chat.id, 
        "📊 <b>Market Terminal v3.5</b>\nНажмите на тикер для перехода в Yahoo Finance:", 
        parse_mode="HTML", 
        reply_markup=markup,
        disable_web_page_preview=True # Чтобы не плодить кучу превью ссылок
    )

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    # Обновленный маппинг под новые названия
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 52 Week Gainers": "high",
        "🧊 52 Week Losers": "low"
    }
    
    text = message.text
    if text in mapping:
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Анализирую сессию...</i>", parse_mode="HTML")
        response = get_market_data(mapping[text])
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.infinity_polling(non_stop=True)
