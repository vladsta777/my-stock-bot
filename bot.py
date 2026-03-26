import telebot
from telebot import types
import pandas as pd
import yfinance as yf
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
def home(): return "Market Bot is Active", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск веб-сервера на порту {port}")
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- ФУНКЦИИ ПОЛУЧЕНИЯ ДАННЫХ ---

def get_ticker_info(ticker_symbol):
    """Поиск данных по конкретному тикеру через yfinance"""
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        # Проверка наличия данных
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None
            
        price = info.get('currentPrice', info.get('regularMarketPrice', 'N/A'))
        currency = info.get('currency', 'USD')
        change = info.get('regularMarketChangePercent', 0)
        name = info.get('longName', ticker_symbol)
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')
        
        emoji = "🟢" if (change and change >= 0) else "🔴"
        
        text = (
            f"🔍 <b>{name} ({ticker_symbol})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price: <b>{price} {currency}</b>\n"
            f"{emoji} Day Change: <code>{change:.2f}%</code>\n\n"
            f"🏢 Sector: <i>{sector}</i>\n"
            f"🛠 Industry: <i>{industry}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>View on Yahoo Finance</a>"
        )
        return text
    except Exception as e:
        logger.error(f"Ошибка yfinance для {ticker_symbol}: {e}")
        return None

def get_market_data(category):
    """Парсинг списков лидеров с Yahoo Finance"""
    try:
        urls = {
            "gainers": "https://finance.yahoo.com/markets/stocks/gainers/",
            "losers": "https://finance.yahoo.com/markets/stocks/losers/",
            "high": "https://finance.yahoo.com/markets/stocks/52-week-gainers/",
            "low": "https://finance.yahoo.com/markets/stocks/52-week-losers/"
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        
        dfs = pd.read_html(urls[category], storage_options=headers)
        if not dfs: return "❌ Таблицы не найдены."
        
        df = dfs[0].head(10)
        lines = []
        for _, row in df.iterrows():
            ticker = str(row['Symbol'])
            price = row['Price']
            change = row.get('52 Week % Change', row.get('% Change', row.get('Change', 'N/A')))
            emoji = "🟢" if category in ["gainers", "high"] else "🔴"
            lines.append(f"{emoji} <a href='https://finance.yahoo.com/quote/{ticker}'>{ticker:5}</a> | <b>${price}</b> (<code>{change}</code>)")

        titles = {
            "gainers": "🚀 <b>Top 10 Gainers (Daily)</b>",
            "losers": "📉 <b>Top 10 Losers (Daily)</b>",
            "high": "📈 <b>52 Week Gainers</b>",
            "low": "🧊 <b>52 Week Losers</b>"
        }
        return f"{titles[category]}\n\n" + "\n".join(lines)
    except Exception as e:
        logger.error(f"Ошибка парсинга {category}: {e}")
        return "❌ <i>Данные временно недоступны.</i>"

# --- ЛОГИКА ИНТЕРФЕЙСА ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    markup.row("📈 52 Week Gainers", "🧊 52 Week Losers")
    markup.row("🔍 Поиск по тикеру")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v4.5</b>\n\nИспользуйте меню для анализа рынка США или выполните поиск по тикеру:", 
                     parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    mapping = {
        "🚀 Top Gainers": "gainers",
        "📉 Top Losers": "losers",
        "📈 52 Week Gainers": "high",
        "🧊 52 Week Losers": "low"
    }
    
    if message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ <b>Введите тикер (напр. AAPL, NVDA или TSLA):</b>", parse_mode="HTML")
        # Регистрируем следующий шаг: ждем ввода тикера
        bot.register_next_step_handler(msg, process_ticker_step)
    
    elif message.text in mapping:
        status_msg = bot.send_message(message.chat.id, "⌛ <i>Загрузка данных...</i>", parse_mode="HTML")
        response = get_market_data(mapping[message.text])
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu(), disable_web_page_preview=True)
    
    else:
        bot.send_message(message.chat.id, "🔄 Пожалуйста, используйте кнопки меню:", reply_markup=get_main_menu())

def process_ticker_step(message):
    """Обработка текста после нажатия кнопки Поиск"""
    ticker = message.text.upper().strip()
    
    # Если пользователь передумал и нажал кнопку меню вместо ввода тикера
    menu_commands = ["🚀 TOP GAINERS", "📉 TOP LOSERS", "📈 52 WEEK GAINERS", "🧊 52 WEEK LOSERS", "🔍 ПОИСК ПО ТИКЕРУ"]
    if ticker in menu_commands:
        handle_menu(message) # Перенаправляем обратно в меню
        return

    status_msg = bot.send_message(message.chat.id, f"🔍 <i>Анализирую {ticker}...</i>", parse_mode="HTML")
    response = get_ticker_info(ticker)
    bot.delete_message(message.chat.id, status_msg.message_id)
    
    if response:
        bot.send_message(message.chat.id, response, parse_mode="HTML", reply_markup=get_main_menu(), disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, f"❌ Тикер <b>{ticker}</b> не найден. Попробуйте еще раз или выберите категорию:", 
                         parse_mode="HTML", reply_markup=get_main_menu())

# --- ТОЧКА ВХОДА ---

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    
    logger.info(">>> Очистка сессий Telegram...")
    try:
        bot.remove_webhook(drop_pending_updates=True)
    except:
        bot.remove_webhook()
        bot.get_updates(offset=-1)
    
    time.sleep(3)
    logger.info(">>> Бот запущен!")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("⚠️ Конфликт 409. Ожидание 20 сек...")
                time.sleep(20)
            else:
                logger.error(f"Ошибка Polling: {e}")
                time.sleep(5)
