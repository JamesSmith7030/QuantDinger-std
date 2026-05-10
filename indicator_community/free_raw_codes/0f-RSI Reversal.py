my_indicator_name = "RSI Reversal"
my_indicator_description = "Buy when RSI crosses above 30 (oversold), sell when crosses below 70 (overbought)."

df = df.copy()

rsi_period = 14
delta = df['close'].diff()
gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
rs = gain / loss
rsi = 100 - (100 / (1 + rs))

buy  = (rsi > 30) & (rsi.shift(1) <= 30)
sell = (rsi < 70) & (rsi.shift(1) >= 70)

df['buy']  = buy.fillna(False).astype(bool)
df['sell'] = sell.fillna(False).astype(bool)

buy_marks  = [df['low'].iloc[i]  * 0.995 if df['buy'].iloc[i]  else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if df['sell'].iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "RSI", "data": rsi.fillna(50).tolist(), "color": "#9C27B0", "overlay": False}
    ],
    "signals": [
        {"type": "buy",  "text": "B", "data": buy_marks,  "color": "#00E676"},
        {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"}
    ]
}
