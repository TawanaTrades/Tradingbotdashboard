import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import requests
from datetime import datetime

# -------------------------------
# 🔧 CONFIG
# -------------------------------
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

st.title("📊 Tawana's Trading Bot Dashboard")
st.markdown("Live market analysis using technical indicators")

# -------------------------------
# 📌 Telegram Setup
# -------------------------------
TELEGRAM_TOKEN = "7725722910:AAECeyZi-nr20QJ5wMGVPsFR5EqLyoIHdCo"
TELEGRAM_CHAT_ID = "7964454145"

def send_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"❌ Telegram failed: {response.text}")
    except Exception as e:
        print(f"❌ Telegram error: {e}")

# -------------------------------
# 📌 Symbol Picker
# -------------------------------
tickers = ["BTC-USD", "ETH-USD", "AAPL", "TSLA"]
symbol = st.selectbox("Choose a symbol:", tickers)

# -------------------------------
# 📅 Date Range Picker
# -------------------------------
start_date = st.date_input("Start Date", value=datetime(2023, 1, 1))
end_date = st.date_input("End Date", value=datetime(2024, 1, 1))

if st.button("🔄 Run Bot"):
    with st.spinner("Fetching market data and running analysis..."):

        # -------------------------------
        # 📈 Download data
        # -------------------------------
        df = yf.download(symbol, start=start_date, end=end_date)

        # ✅ Flatten columns if it's a MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        if df.empty:
            st.error("No data found for selected symbol.")
        else:
            # -------------------------------
            # 📊 Indicators
            # -------------------------------
            close = df["Close"].squeeze()

            df["rsi"] = ta.momentum.RSIIndicator(close=close).rsi()
            df["macd"] = ta.trend.MACD(close=close).macd_diff()
            df["ma50"] = close.rolling(window=50).mean()
            df["ma200"] = close.rolling(window=200).mean()

            df.dropna(inplace=True)

            # -------------------------------
            # 📡 Signal Logic
            # -------------------------------
            def get_signal(row):
                try:
                    ma50 = row["ma50"].item() if hasattr(row["ma50"], 'item') else row["ma50"]
                    ma200 = row["ma200"].item() if hasattr(row["ma200"], 'item') else row["ma200"]
                    rsi = row["rsi"].item() if hasattr(row["rsi"], 'item') else row["rsi"]
                    macd = row["macd"].item() if hasattr(row["macd"], 'item') else row["macd"]
                except:
                    return "HOLD"

                if ma50 > ma200 and rsi < 70 and macd > 0:
                    return "BUY"
                elif macd < 0:
                    return "SELL"
                else:
                    return "HOLD"

            df["signal"] = df.apply(get_signal, axis=1)

            # -------------------------------
            # 💼 Wallet Tracking (Simulated)
            # -------------------------------
            wallet = 10000
            entry_price = None
            position_size = 1
            trade_log = []

            for i, row in df.iterrows():
                if str(row["signal"]) == "BUY" and entry_price is None:
                    entry_price = row["Close"]
                    trade_log.append(f"BUY at {entry_price:.2f} on {i.date()}")
                    send_alert(f"🟢 BOT BUY: {symbol} at ${entry_price:.2f}")
                elif str(row["signal"]) == "SELL" and entry_price:
                    exit_price = row["Close"]
                    profit = (exit_price - entry_price) * position_size
                    wallet += profit
                    trade_log.append(f"SELL at {exit_price:.2f} on {i.date()} | P/L: {profit:.2f}")
                    send_alert(f"🔴 BOT SELL: {symbol} at ${exit_price:.2f} | P/L: {profit:.2f}")
                    entry_price = None

            # -------------------------------
            # 📈 Display Chart + Info
            # -------------------------------
            st.subheader(f"{symbol} Price Chart")
            st.line_chart(df[["Close", "ma50", "ma200"]])

            st.subheader("Last 10 Signals")
            st.dataframe(df[["Close", "rsi", "macd", "ma50", "ma200", "signal"]].tail(10))

            st.subheader("Trade Log")
            st.text("\n".join(trade_log[-10:]))

            st.success(f"Final Wallet Balance: ${wallet:.2f}")
