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
        lines.append("• <b>Ставка ФРС:</b> 29.04 | <i>Тек: 3.75% (18.03)</i>")
        lines.append("• <b>CPI (Инфляция):</b> 15.04 | <i>Тек: 2.4% (12.03)</i>")
        lines.append("• <b>NFP/Безработица:</b> 03.04 | <i>Тек: 4.4% (06.03)</i>")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Digest error: {e}")
        return "❌ Ошибка загрузки дайджеста."

def get_ticker_info(ticker_symbol):
    """Глубокий анализ тикера с системой баллов и логикой Long/Short"""
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None
            
        # Сбор параметров
        price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        change = info.get('regularMarketChangePercent', 0)
        vol_ratio = info.get('volume', 0) / info.get('averageVolume', 1)
        
        rev_growth = info.get('revenueGrowth', 0)
        eps_growth = info.get('earningsGrowth', 0)
        debt_to_eq = info.get('debtToEquity', 100)
        fcf = info.get('freeCashflow', 0)
        margin = info.get('profitMargins', 0)
        
        float_sh = info.get('floatShares', 0)
        out_sh = info.get('sharesOutstanding', 1)
        short_pct = info.get('shortPercentOfFloat', 0) * 100

        # --- SCORING ENGINE ---
        checks = []
        total_score = 0

        # Техника
        if vol_ratio > 1.2:
            checks.append("✅ Объём ↑ (Сила) [+1]")
            total_score += 1
        if change > 0:
            total_score += 1
        else:
            total_score -= 1
        if float_sh and (float_sh / out_sh) < 0.4:
            checks.append("✅ Low Float (Легкий ход) [+1]")
            total_score += 1

        # Фундаментал
        if rev_growth > 0.1:
            checks.append(f"✅ Growth: {rev_growth*100:.1f}% [+1]")
            total_score += 1
        elif rev_growth < 0:
            checks.append("❌ Выручка падает [-2]")
            total_score -= 2

        if fcf > 0:
            checks.append("✅ Positive FCF [+1]")
            total_score += 1
        else:
            checks.append("❌ Negative FCF [-1]")
            total_score -= 1

        if debt_to_eq < 70:
            checks.append("✅ Low Debt [+1]")
            total_score += 1
        elif debt_to_eq > 150:
            checks.append("⚠️ High Debt [-1]")
            total_score -= 1

        # Вердикт
        if total_score >= 4:
            verdict, signal_text = "🟢 STRONG LONG", "👉 Деньги заходят + бизнес растёт"
        elif total_score <= -2:
            verdict, signal_text = "🔴 STRONG SHORT", "👉 Слабый отчет + долги + слив"
        else:
            verdict, signal_text = "🟡 NEUTRAL", "👉 Смешанные сигналы"

        emoji = "🟢" if change >= 0 else "🔴"
        text = (
            f"🔍 <b>{info.get('longName', ticker_symbol)}</b>\n"
            f"💰 Цена: <b>{price} {info.get('currency', 'USD')}</b> ({emoji} <code>{change:+.2f}%</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>АНАЛИЗ ПАРАМЕТРОВ:</b>\n"
            f"{chr(10).join(checks)}\n"
            f"• Short Float: <b>{short_pct:.2f}%</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>ИТОГ: {total_score}/10 — {verdict}</b>\n"
            f"🧠 <i>{signal_text}</i>\n\n"
            f"📅 <b>EARNINGS LOGIC:</b>\n"
            f"• Beat + Raise → 🚀 | Miss → 📉\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>Открыть в Terminal</a>"
        )
        return text
    except: return None

# [get_market_data, get_main_menu, handle_menu и process_ticker_step остаются прежними]
def get_market_data(category):
    try:
        urls = {"gainers": "https://finance.yahoo.com/markets/stocks/gainers/", "losers": "https://finance.yahoo.com/markets/stocks/losers/", "high": "https://finance.yahoo.com/markets/stocks/52-week-gainers/", "low": "https://finance.yahoo.com/markets/stocks/52-week-losers/"}
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
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v6.0</b>", parse_mode="HTML", reply_markup=get_main_menu())

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
    res = get_ticker_info(message.text)
    if res: bot.send_message(message.chat.id, res, parse_mode="HTML", disable_web_page_preview=True)
    else: bot.send_message(message.chat.id, "❌ Тикер не найден.")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
