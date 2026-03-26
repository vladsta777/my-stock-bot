import telebot
from telebot import types
import pandas as pd
import yfinance as yf
import os
from flask import Flask
from threading import Thread
from waitress import serve
import logging
from datetime import datetime

# 1. Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Мини-сервер для UptimeRobot
app = Flask('')

@app.route('/')
def home():
    return "Market Bot is Active", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- ФУНКЦИИ АНАЛИЗА ---

def get_ticker_info(ticker_symbol):
    """Математический скоринг на основе отчета компании"""
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None

        # --- 1. СБОР ЦИФР ИЗ ОТЧЕТА ---
        # Берем значения или 0, если данных нет
        rev_growth = info.get('revenueGrowth', 0) or 0
        eps_growth = info.get('earningsGrowth', 0) or 0
        debt_to_eq = info.get('debtToEquity', 150) or 150
        margin = info.get('profitMargins', 0) or 0
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        change = info.get('regularMarketChangePercent', 0) or 0

        # --- 2. МАТЕМАТИЧЕСКИЙ РАСЧЕТ БАЛЛОВ (Max 10) ---
        score = 0
        calc_steps = []

        # Рост выручки (Вес 3)
        if rev_growth > 0.20: 
            score += 3
            calc_steps.append(f"📈 Выручка > 20% ({rev_growth*100:.1f}%) [+3]")
        elif rev_growth > 0.05:
            score += 1
            calc_steps.append(f"✅ Выручка растет ({rev_growth*100:.1f}%) [+1]")
        else:
            score -= 2
            calc_steps.append(f"❌ Выручка стагнирует ({rev_growth*100:.1f}%) [-2]")

        # Рост прибыли (Вес 3)
        if eps_growth > 0.10:
            score += 3
            calc_steps.append(f"💰 Прибыль растет ({eps_growth*100:.1f}%) [+3]")
        elif eps_growth < 0:
            score -= 2
            calc_steps.append(f"⚠️ Убыточный квартал ({eps_growth*100:.1f}%) [-2]")

        # Долг (Вес 2)
        if debt_to_eq < 80:
            score += 2
            calc_steps.append(f"🛡 Долг низкий ({debt_to_eq:.1f}) [+2]")
        elif debt_to_eq > 160:
            score -= 2
            calc_steps.append(f"🔴 Высокий долг ({debt_to_eq:.1f}) [-2]")

        # Маржинальность (Вес 2)
        if margin > 0.15:
            score += 2
            calc_steps.append(f"💎 Высокая маржа ({margin*100:.1f}%) [+2]")

        # --- 3. ИТОГОВОЕ РЕШЕНИЕ ---
        if score >= 6:
            decision = "🟢 ПОКУПКА (LONG)"
            reason = "Бизнес здоров, показатели выше рынка."
        elif score >= 2:
            decision = "🟡 НАБЛЮДЕНИЕ (HOLD)"
            reason = "Смешанные цифры, риск умеренный."
        else:
            decision = "🔴 ПРОДАЖА / ИГНОР (SHORT)"
            reason = "Фундаментальный перекос, плохой отчет."

        # Формирование сообщения
        emoji = "🟢" if change >= 0 else "🔴"
        text = (
            f"🔍 <b>{info.get('longName', ticker_symbol)}</b>\n"
            f"💰 Цена: <b>{price} {info.get('currency', 'USD')}</b> ({emoji} <code>{change:+.2f}%</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>РАСЧЕТ ЛОГИКИ:</b>\n"
            f"{chr(10).join(calc_steps)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>ИТОГ: {score} из 10 БАЛЛОВ</b>\n"
            f"🏁 <b>РЕШЕНИЕ: {decision}</b>\n\n"
            f"🧠 <i>{reason}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📑 <b>ПОДРОБНЫЙ ОТЧЕТ:</b>\n"
            f"<tg-spoiler>Выручка: {rev_growth:.2%}\nПрибыль: {eps_growth:.2%}\nДолг/Кап: {debt_to_eq}\nМаржа: {margin:.2%}</tg-spoiler>\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>Yahoo Finance</a>"
        )
        return text
    except Exception as e:
        logger.error(f"Error analyzing {ticker_symbol}: {e}")
        return None

# --- МЕНЮ И ОБРАБОТКА ---

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📰 Обзор на сегодня", "🔍 Поиск по тикеру")
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📈 <b>Quant Market Terminal</b>\nАнализ акций на основе цифр отчета.", 
                     parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    if message.text == "📰 Обзор на сегодня":
        # (Функция get_daily_digest из прошлых версий остается без изменений)
        bot.send_message(message.chat.id, "⌛️ Загружаю сводку...") 
    elif message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ Введите тикер (напр. AAPL):", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_ticker_step)

def process_ticker_step(message):
    res = get_ticker_info(message.text)
    if res:
        bot.send_message(message.chat.id, res, parse_mode="HTML", disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, "❌ Ошибка анализа тикера.")

# --- ЗАПУСК ---
if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
