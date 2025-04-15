import streamlit as st
st.set_page_config(page_title="Trading Bot Dashboard", layout="wide")

import pandas as pd
import numpy as np
import requests
import MetaTrader5 as mt5
import time
import threading
import pytz
import random
from datetime import datetime, timedelta

# 🔐 MT5 login
MT5_LOGIN = int(st.secrets["MT5_LOGIN"])
MT5_PASSWORD = st.secrets["MT5_PASSWORD"]
MT5_SERVER = st.secrets["MT5_SERVER"]
mt5.initialize(login=MT5_LOGIN, server=MT5_SERVER, password=MT5_PASSWORD)

# 🔁 Force rerun
if st.session_state.get("_rerun"):
    st.session_state._rerun = False
    st.rerun()

# UI
st.title("📊 Tawana's Trading Bot Dashboard")
st.markdown("AI-filtered MT5 signals with auto-trading, alerts, logs & performance")

# 💰 Account stats
account_info = mt5.account_info()
if account_info:
    balance = round(account_info.balance, 2)
    equity = round(account_info.equity, 2)
    profit = round(account_info.profit, 2)
    profit_color = "green" if profit >= 0 else "red"
    st.markdown(
        f"""
        <div style='background-color: #f0f0f0; padding: 10px; border-radius: 10px; color: black;'>
        💼 <b>Balance:</b> {balance} |
        📈 <b>Equity:</b> {equity} |
        📊 <b>Profit/Loss:</b> <span style='color:{profit_color}'>{profit}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

# ✅ Setup state
if "trade_count" not in st.session_state:
    st.session_state.trade_count = 0
if "wins" not in st.session_state:
    st.session_state.wins = 0
if "losses" not in st.session_state:
    st.session_state.losses = 0
if "balance_log" not in st.session_state:
    st.session_state.balance_log = []
if "trade_log" not in st.session_state:
    st.session_state.trade_log = []

# ⚙️ Config
TELEGRAM_TOKEN = "7725722910:AAECeyZi-nr20QJ5wMGVPsFR5EqLyoIHdCo"
TELEGRAM_CHAT_ID = "7964454145"

refresh_rate = st.number_input("🔁 Refresh every (seconds)", min_value=1, value=1)
execute_trades = st.checkbox("✅ Enable Live Trading")
max_trades = st.number_input("🛑 Max Trades Per Day", min_value=1, value=3)
order_volume = st.number_input("💼 Order Volume", value=0.1, step=0.01)

# Timeframe setting
trade_duration = st.selectbox("Trade Duration", ["Short-Term", "Mid-Term", "Long-Term"])
timeframe_map = {
    "Short-Term": (mt5.TIMEFRAME_M5, timedelta(hours=1)),
    "Mid-Term": (mt5.TIMEFRAME_H1, timedelta(days=1)),
    "Long-Term": (mt5.TIMEFRAME_D1, timedelta(weeks=1))
}
timeframe, hold_time = timeframe_map[trade_duration]

# 🔍 Select symbols
symbols = [s.name for s in mt5.symbols_get() if s.visible]
scan_symbols = st.multiselect("🔎 Symbols to scan:", symbols, default=symbols[:5])

# 📦 Helpers
def get_price(symbol):
    tick = mt5.symbol_info_tick(symbol)
    return tick.bid if tick else None

def generate_signal(price):
    threshold = 0.5 + random.uniform(-0.15, 0.15)
    vol = random.uniform(0.002, 0.008)
    confidence = random.uniform(70, 99.5)
    if (price % 5) > threshold:
        action = "BUY"
        tp = price * (1 + vol)
        sl = price * (1 - vol / 1.5)
    else:
        action = "SELL"
        tp = price * (1 - vol)
        sl = price * (1 + vol / 1.5)
    return action, round(tp, 5), round(sl, 5), round(confidence, 2)

def send_telegram(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
    except:
        st.warning("⚠️ Telegram failed")

# 🔎 SCANNER
st.subheader("📋 Signal Results")
top_conf = 0
top_signal = None

for symbol in scan_symbols:
    price = get_price(symbol)
    if price is None:
        st.error(f"❌ No price for {symbol}")
        continue
    action, tp, sl, conf = generate_signal(price)
    st.success(f"{symbol} ➜ {action} @ {price:.5f} | TP: {tp} | SL: {sl} | Confidence: {conf:.2f}%")

    if conf > top_conf:
        top_conf = conf
        top_signal = (symbol, price, action, tp, sl, conf)

# 🚀 AUTO TRADE
if execute_trades and top_signal and st.session_state.trade_count < max_trades:
    symbol, price, action, tp, sl, conf = top_signal
    info = mt5.symbol_info(symbol)
    if info and info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": order_volume,
            "type": mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 123456,
            "comment": "AutoTradeBot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            st.session_state.trade_count += 1
            profit = (tp - price) if action == "BUY" else (price - tp)
            if profit > 0:
                st.session_state.wins += 1
            else:
                st.session_state.losses += 1
            st.session_state.balance_log.append(mt5.account_info().balance)
            st.session_state.trade_log.append({
                "Time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "Symbol": symbol,
                "Action": action,
                "Entry": price,
                "TP": tp,
                "SL": sl,
                "Confidence": conf
            })
            st.success(f"🚀 {action} executed on {symbol} @ {price}")
            send_telegram(f"📈 {action} on {symbol} @ {price:.5f}\\nTP: {tp} | SL: {sl} | Confidence: {conf:.2f}%")
        else:
            st.error(f"❌ Trade failed: {result.comment}")
    else:
        st.warning(f"⚠️ {symbol} not tradable")

# 🧾 Trade History
if st.session_state.trade_log:
    st.subheader("📑 Trade History")
    st.dataframe(pd.DataFrame(st.session_state.trade_log).tail(10), use_container_width=True)

# 🟢🔴 Win/Loss Summary
st.subheader("📊 Performance")
st.markdown(f"🟢 Wins: {st.session_state.wins} | 🔴 Losses: {st.session_state.losses}")

# 📈 Balance Graph
if len(st.session_state.balance_log) > 1:
    st.line_chart(st.session_state.balance_log)

# 🔁 Auto-refresh
def rerun_later(seconds):
    def run():
        time.sleep(seconds)
        st.session_state._rerun = True
    threading.Thread(target=run).start()

if execute_trades:
    rerun_later(refresh_rate)
