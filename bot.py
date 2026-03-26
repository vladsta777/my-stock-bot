import yfinance as yf
import requests
import os

# Вставьте ваши данные здесь для теста (но для постоянной работы лучше через Secrets)
TOKEN = "8760265107:AAHdcj9Ls_2-c27OFkqV67MRhI2E9SBYxUs"
CHAT_ID = "154150415" # Сюда вставьте свой цифровой ID (например, 12345678)
STOCKS = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]

def get_stock_report(tickers):
    message = "🔔 **Пре-маркет США (Обновление):**\n\n"
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # Получаем данные за последние 2 дня, чтобы сравнить цены
            data = stock.history(period="2d")
            if len(data) >= 2:
                prev_close = data['Close'].iloc[-2]
                current_price = data['Close'].iloc[-1]
                diff = ((current_price - prev_close) / prev_close) * 100
                emoji = "🟢" if diff >= 0 else "🔴"
                message += f"{emoji} **{ticker}**: ${current_price:.2f} ({diff:+.2f}%)\n"
        except Exception as e:
            print(f"Ошибка по {ticker}: {e}")
    return message

def send_to_tg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})

if __name__ == "__main__":
    report = get_stock_report(STOCKS)
    send_to_tg(report)
    print("Сообщение отправлено!")
