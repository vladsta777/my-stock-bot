import telebot
from telebot import types
import yfinance as yf
import os

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
bot = telebot.TeleBot(TOKEN)

# Функция для получения данных (Gainers/Losers имитируем через выборку волатильных акций, 
# так как yfinance не дает готовый топ пре-маркета одной командой бесплатно)
def get_market_movers(category):
    # Список популярных акций для анализа
    tickers = ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "COIN"]
    data_list = []
    
    for t in tickers:
        s = yf.Ticker(t)
        hist = s.history(period="2d")
        if len(hist) >= 2:
            change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            data_list.append({"ticker": t, "change": change, "price": hist['Close'].iloc[-1]})
    
    if category == "gainers":
        data_list.sort(key=lambda x: x['change'], reverse=True)
        title = "🚀 Top Gainers (Pre-market est.)"
    else:
        data_list.sort(key=lambda x: x['change'])
        title = "📉 Top Losers (Pre-market est.)"
        
    res = f"<b>{title}</b>\n\n"
    for item in data_list[:5]:
        emoji = "🟢" if item['change'] > 0 else "🔴"
        res += f"{emoji} {item['ticker']}: {item['price']:.2f}$ ({item['change']:+.2f}%)\n"
    return res

# Создание кнопок
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🚀 Top Gainers", callback_data="gainers")
    btn2 = types.InlineKeyboardButton("📉 Top Losers", callback_data="losers")
    btn3 = types.InlineKeyboardButton("📈 New High", callback_data="high")
    btn4 = types.InlineKeyboardButton("📉 New Low", callback_data="low")
    markup.add(btn1, btn2, btn3, btn4)
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "gainers":
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text=get_market_movers("gainers"), parse_mode="HTML", reply_markup=main_menu())
    elif call.data == "losers":
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text=get_market_movers("losers"), parse_mode="HTML", reply_markup=main_menu())
    # Для New High/Low логика аналогична, можно расширить

if __name__ == "__main__":
    # Отправляем сообщение с кнопками при запуске
    bot.send_message(CHAT_ID, "📊 Выберите категорию для анализа пре-маркета США:", reply_markup=main_menu())
