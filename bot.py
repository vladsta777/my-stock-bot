import telebot
from telebot import types
import pandas as pd
import os
from flask import Flask
from threading import Thread
from waitress import serve
import logging
import time

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Мини-сервер для UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Market Bot is Active"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск веб-сервера на порту {port}")
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def get_market_data(category):
    try:
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-gainers/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-losers/"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        
        # Загрузка данных
        dfs = pd.read_html(urls[category], storage_options=headers)
        if not dfs:
            return "❌ Таблицы не найдены."
            
        df = dfs[0].head(10)

        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            # Проверка разных вариантов имен колонок Yahoo
            change = row.get('52 Week % Change', row.get('% Change', row.get('Change', 'N/A')))
            
            yahoo_link = f"https://finance.yahoo.com/quote/{ticker}"
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

# Функция формирования клавиатуры
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"Команда /start от {message.chat.id}")
    bot.send_message(
        message.chat.id, 
        "📊 <b>Market Terminal v4.0</b>\n\nВыберите категорию для анализа рынка США:", 
        parse_mode="HTML", 
        reply_markup=get_main_menu(),
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
        # Принудительно обновляем клавиатуру при каждом ответе (лечение залипания)
        bot.send_message(message.chat.id, response, parse_mode="HTML", 
                         reply_markup=get_main_menu(), disable_web_page_preview=True)
    else:
        # Если пришла кнопка со старым текстом (например, "New High") или просто текст
        logger.warning(f"Неизвестный текст: {message.text}. Исправляю кнопки.")
        bot.send_message(
            message.chat.id, 
            "🔄 <b>Кнопки обновлены!</b>\nПожалуйста, используйте актуальное меню:", 
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )

# 4. Точка входа
if __name__ == "__main__":
    # Запуск сервера
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logger.info(">>> Очистка сессий Telegram...")
    try:
        # Попытка удалить вебхук с очисткой очереди (для новых версий библиотеки)
        bot.remove_webhook(drop_pending_updates=True)
    except TypeError:
        # Если библиотека старая и не знает про drop_pending_updates
        bot.remove_webhook()
        bot.get_updates(offset=-1) # Ручная очистка очереди
    
    time.sleep(3) # Пауза перед стартом, чтобы избежать 409 Conflict
    
    logger.info(">>> Бот запущен и готов к работе!")
    
    while True:
        try:
            # Используем infinity_polling как более современный аналог polling
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("⚠️ Конфликт 409. Жду 20 сек пока Render закроет старую копию...")
                time.sleep(20)
            else:
                logger.error(f"Ошибка Polling: {e}")
                time.sleep(5)
