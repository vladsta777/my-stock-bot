import telebot
from telebot import types
import pandas as pd
import os
from flask import Flask
from threading import Thread
from waitress import serve
import logging

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Мини-сервер для UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "OK"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск Waitress на порту {port}")
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_market_data(category):
    try:
        # ОБНОВЛЕННЫЕ ССЫЛКИ: теперь ведут на разделы Gainers/Losers за 52 недели
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-gainers/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-losers/"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        
        # Читаем таблицу
        dfs = pd.read_html(urls[category], storage_options=headers)
        if not dfs:
            return "❌ Таблицы не найдены."
            
        df = dfs[0].head(10)

        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            
            # Проверяем разные варианты названия колонки с процентами
            change = row.get('52 Week % Change', row.get('% Change', row.get('Change', 'N/A')))
            
            yahoo_link = f"https://finance.yahoo.com/quote/{ticker}"
            
            # Эмодзи: для лидеров роста за год тоже ставим зеленый
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            
            lines.append(f"{emoji} <a href='{yahoo_link}'>{ticker:5}</a> | <b>${price}</b> (<code>{change}</code>)")

        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (Daily)</b>",
            "losers": "📉 <b>Top 10 Losers (Daily)</b>",
            "high": "📈 <b>52 Week Gainers</b>",
            "low": "🧊 <b>52 Week Losers</b>"
        }

        return f"{titles[category]}\n\n" + "\n".join(lines)

    except Exception as e:
        logger.error(f"Ошибка Yahoo: {e}")
        return "❌ <i>Данные временно недоступны.</i>"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"Команда /start от {message.chat.id}")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    
    bot.send_message(
        message.chat.id, 
        "📊 <b>Market Terminal v3.7</b>\n\nВыберите категорию:", 
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
        logger.info(f"Запрос {message.text} от {message.chat.id}")
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Сборка данных Yahoo...</i>", parse_mode="HTML")
        
        response = get_market_data(mapping[message.text])
        
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", disable_web_page_preview=True)

# 4. Точка входа
if __name__ == "__main__":
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    logger.info(">>> Бот запускает Polling...")
    
    while True:
        try:
            # skip_pending=True обязателен, чтобы бот не «захлебнулся» старыми сообщениями
            bot.polling(none_stop=True, interval=0, timeout=20, skip_pending=True)
        except Exception as e:
            logger.error(f"Ошибка Polling: {e}")
            import time
            time.sleep(5)
