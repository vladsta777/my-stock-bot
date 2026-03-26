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
    return "Market Bot is Active and Healthy", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Запуск веб-сервера на порту {port}")
    serve(app, host='0.0.0.0', port=port)

# 3. Настройка бота
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# --- СПИСКИ ДЛЯ ОБЗОРА ---
DIGEST_TICKERS = {
    "Crude Oil": "CL=F",
    "Natural Gas": "NG=F",
    "Gold": "GC=F",
    "Dow Jones": "YM=F",
    "S&P 500": "ES=F",
    "Nasdaq 100": "NQ=F",
    "Russell 2000": "RTY=F"
}

# --- ФУНКЦИИ ДАННЫХ ---

def get_daily_digest():
    """Сводка по рынкам с актуальной макроэкономикой 2026"""
    try:
        lines = [f"📅 <b>Обзор рынка на {datetime.now().strftime('%d.%m.%Y')}</b>\n"]
        lines.append("📊 <b>Фьючерсы и Индексы:</b>")
        
        for name, ticker in DIGEST_TICKERS.items():
            try:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if not hist.empty and len(hist) >= 2:
                    price = hist['Close'].iloc[-1]
                    prev_price = hist['Close'].iloc[-2]
                    change = ((price - prev_price) / prev_price) * 100
                    emoji = "🟢" if change >= 0 else "🔴"
                    change_str = f"<code>{change:+.2f}%</code>"
                    p_val = f"{price:.2f}"
                    lines.append(f"{emoji} <a href='https://finance.yahoo.com/quote/{ticker}'>{name:12}</a>: <b>{p_val}</b> ({change_str})")
            except: continue
        
        lines.append("\n🗓 <b>Ключевые события (NY Time):</b>")
        lines.append("• <b>Ставка ФРС:</b> 29.04 | <i>Тек: 3.75%</i>")
        lines.append("• <b>CPI (Инфляция):</b> 15.04 | <i>Тек: 2.4%</i>")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Digest error: {e}")
        return "❌ Ошибка загрузки дайджеста."

def get_ticker_info(ticker_symbol):
    """Математический скоринг на основе цифр отчета и тех. данных"""
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None

        # --- 1. СБОР ПОКАЗАТЕЛЕЙ ---
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        change = info.get('regularMarketChangePercent', 0) or 0
        rev_growth = info.get('revenueGrowth', 0) or 0
        eps_growth = info.get('earningsGrowth', 0) or 0
        debt_to_eq = info.get('debtToEquity', 150) or 150
        margin = info.get('profitMargins', 0) or 0
        vol_ratio = (info.get('volume', 0) / info.get('averageVolume', 1)) if info.get('averageVolume') else 1

        # --- 2. МАТЕМАТИЧЕСКИЙ РАСЧЕТ БАЛЛОВ (Max 10) ---
        score = 0
        calc_steps = []

        # Выручка (Вес 3)
        if rev_growth > 0.20: 
            score += 3
            calc_steps.append(f"📈 Выручка > 20% ({rev_growth*100:.1f}%) [+3]")
        elif rev_growth > 0.05:
            score += 1
            calc_steps.append(f"✅ Рост выручки ({rev_growth*100:.1f}%) [+1]")
        else:
            score -= 2
            calc_steps.append(f"❌ Слабая выручка ({rev_growth*100:.1f}%) [-2]")

        # Прибыль (Вес 3)
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

        # Техника/Объем (Вес 2)
        if vol_ratio > 1.3:
            score += 2
            calc_steps.append(f"📊 Аномальный объем ({vol_ratio:.2f}x) [+2]")

        # --- 3. ФИНАЛЬНОЕ РЕШЕНИЕ ---
        if score >= 6: verdict, reason = "🟢 STRONG LONG", "Фундаментал сильный, риск низкий."
        elif score >= 2: verdict, reason = "🟡 NEUTRAL / HOLD", "Смешанные цифры, ждем подтверждения."
        else: verdict, reason = "🔴 STRONG SHORT", "Бизнес деградирует или перегружен долгами."

        # Формирование отчета
        emoji = "🟢" if change >= 0 else "🔴"
        text = (
            f"🔍 <b>{info.get('longName', ticker_symbol)} ({ticker_symbol})</b>\n"
            f"💰 Цена: <b>{price} {info.get('currency', 'USD')}</b> ({emoji} <code>{change:+.2f}%</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ <b>РАСЧЕТ ЛОГИКИ (Score: {score}/10):</b>\n"
            f"{chr(10).join(calc_steps)}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>РЕШЕНИЕ: {verdict}</b>\n"
            f"🧠 <i>{reason}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📑 <b>ПОДРОБНЫЕ ДАННЫЕ (нажми):</b>\n"
            f"<tg-spoiler>• Rev Growth: {rev_growth:.2%}\n• EPS Growth: {eps_growth:.2%}\n• Debt/Equity: {debt_to_eq}\n• Profit Margin: {margin:.2%}\n• Short Float: {info.get('shortPercentOfFloat', 0)*100:.2f}%</tg-spoiler>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>Yahoo Finance Terminal</a>"
        )
        return text
    except Exception as e:
        logger.error(f"Scoring error: {e}")
        return None

def get_market_data(category):
    try:
        urls = {"gainers": "https://finance.yahoo.com/markets/stocks/gainers/", 
                "losers": "https://finance.yahoo.com/markets/stocks/losers/"}
        headers = {"User-Agent": "Mozilla/5.0"}
        dfs = pd.read_html(urls[category], storage_options=headers)
        df = dfs[0].head(10)
        lines = [f"{ticker:5} | ${price} ({change})" for ticker, price, change in zip(df['Symbol'], df['Price'], df.get('% Change', df.get('Change', '')))]
        return f"📊 <b>{category.upper()}</b>\n\n" + "\n".join(lines)
    except: return "❌ Ошибка данных."

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📰 Обзор на сегодня", "🔍 Поиск по тикеру")
    markup.row("🚀 Top Gainers", "📉 Top Losers")
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v7.0</b>\nМатематический анализ отчетов активен.", 
                     parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    if message.text == "📰 Обзор на сегодня":
        bot.send_message(message.chat.id, get_daily_digest(), parse_mode="HTML", disable_web_page_preview=True)
    elif message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ Введите тикер (напр. TSLA):", parse_mode="HTML")
        bot.register_next_step_handler(msg, process_ticker_step)
    elif "Top" in message.text:
        cat = "gainers" if "Gainers" in message.text else "losers"
        bot.send_message(message.chat.id, get_market_data(cat), parse_mode="HTML")

def process_ticker_step(message):
    ticker = message.text.upper().strip()
    res = get_ticker_info(ticker)
    if res: bot.send_message(message.chat.id, res, parse_mode="HTML", disable_web_page_preview=True)
    else: bot.send_message(message.chat.id, f"❌ Тикер {ticker} не найден.")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
