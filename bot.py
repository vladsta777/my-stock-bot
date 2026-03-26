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
    """Глубокий анализ тикера с системой баллов и детализацией данных"""
    try:
        ticker_symbol = ticker_symbol.upper().strip()
        stock = yf.Ticker(ticker_symbol)
        info = stock.info
        
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None
            
        # 1. Сбор всех необходимых полей
        raw_fields = {
            "Price": info.get('currentPrice') or info.get('regularMarketPrice'),
            "Revenue Growth": info.get('revenueGrowth'),
            "EPS Growth": info.get('earningsGrowth'),
            "Debt to Equity": info.get('debtToEquity'),
            "Free Cash Flow": info.get('freeCashflow'),
            "Profit Margin": info.get('profitMargins'),
            "Short Float %": info.get('shortPercentOfFloat'),
            "Float Shares": info.get('floatShares'),
            "Avg Volume": info.get('averageVolume'),
            "Volume": info.get('volume'),
            "Market Cap": info.get('marketCap'),
            "Shares Outstanding": info.get('sharesOutstanding'),
            "Insider Own %": info.get('heldPercentInsiders'),
            "Inst. Own %": info.get('heldPercentInstitutions')
        }

        # Разделяем на найденные и пропущенные
        found = {k: v for k, v in raw_fields.items() if v is not None}
        missing = [k for k, v in raw_fields.items() if v is None]

        # 2. SCORING ENGINE
        checks = []
        score = 0
        
        # Техника
        change = info.get('regularMarketChangePercent', 0)
        if change > 0: score += 1
        else: score -= 1

        if "Volume" in found and "Avg Volume" in found:
            ratio = found["Volume"] / found["Avg Volume"]
            if ratio > 1.2:
                score += 1
                checks.append(f"✅ Объём выше среднего ({ratio:.2f}x) [+1]")

        # Фундаментал
        rev_g = found.get("Revenue Growth", 0)
        if rev_g > 0.1:
            score += 1
            checks.append(f"✅ Рост выручки ({rev_g*100:.1f}%) [+1]")
        elif rev_g < 0:
            score -= 2
            checks.append("❌ Падение выручки [-2]")

        if found.get("Free Cash Flow", 0) > 0:
            score += 1
            checks.append("✅ Положительный FCF [+1]")

        if found.get("Debt to Equity", 200) < 80:
            score += 1
            checks.append("✅ Низкий долг [+1]")

        # 3. Вердикт
        if score >= 4: verdict, signal = "🟢 STRONG LONG", "👉 Деньги заходят + бизнес растёт"
        elif score <= -2: verdict, signal = "🔴 STRONG SHORT", "👉 Слабый отчет + долги + слив"
        else: verdict, signal = "🟡 NEUTRAL", "👉 Смешанные сигналы"

        # 4. Составление подробного лога для спойлера
        detailed_log = "<b>📋 ПОЛНЫЙ ТЕХНИЧЕСКИЙ ОТЧЕТ:</b>\n\n"
        detailed_log += "<b>✅ ПОЛУЧЕННЫЕ ДАННЫЕ:</b>\n"
        for k, v in found.items():
            if isinstance(v, (int, float)) and v > 1000000: val = f"{v/1e6:.2f}M"
            elif "Growth" in k or "Margin" in k or "%" in k: val = f"{v*100:.2f}%" if isinstance(v, float) else str(v)
            else: val = str(v)
            detailed_log += f"• {k}: <code>{val}</code>\n"

        if missing:
            detailed_log += "\n<b>⚠️ НЕ НАЙДЕНО (N/A):</b>\n"
            detailed_log += f"<i>{', '.join(missing)}</i>\n"

        # Итоговое сообщение
        emoji = "🟢" if change >= 0 else "🔴"
        text = (
            f"🔍 <b>{info.get('longName', ticker_symbol)} ({ticker_symbol})</b>\n"
            f"💰 Цена: <b>{found.get('Price', 'N/A')} {info.get('currency', 'USD')}</b> ({emoji} <code>{change:+.2f}%</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>ИТОГ: {score} БАЛЛОВ — {verdict}</b>\n\n"
            f"<b>АКТИВНЫЕ ФАКТОРЫ:</b>\n"
            f"{chr(10).join(checks) if checks else 'Нет данных для анализа'}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📑 <b>ПОДРОБНЕЕ (нажми):</b>\n"
            f"<tg-spoiler>{detailed_log}</tg-spoiler>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 <b>Beat + Raise → 🚀 | Miss → 📉</b>\n"
            f"🔗 <a href='https://finance.yahoo.com/quote/{ticker_symbol}'>Terminal</a>"
        )
        return text
    except Exception as e:
        logger.error(f"Scoring error: {e}")
        return None

# Оставшиеся функции без изменений
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
    bot.send_message(message.chat.id, "📊 <b>Market Terminal v6.5</b>", parse_mode="HTML", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: True)
def handle_menu(message):
    if message.text == "📰 Обзор на сегодня":
        bot.send_message(message.chat.id, get_daily_digest(), parse_mode="HTML", disable_web_page_preview=True)
    elif message.text == "🔍 Поиск по тикеру":
        msg = bot.send_message(message.chat.id, "✍️ Введите тикер (напр. NVDA):", parse_mode="HTML")
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
