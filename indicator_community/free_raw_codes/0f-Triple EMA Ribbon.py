my_indicator_name = "Triple EMA Ribbon"
my_indicator_description = "Buy when EMA8 > EMA21 > EMA55 (all aligned bullish); sell when EMA8 < EMA21 < EMA55."

df = df.copy()

ema8  = df['close'].ewm(span=8,  adjust=False).mean()
ema21 = df['close'].ewm(span=21, adjust=False).mean()
ema55 = df['close'].ewm(span=55, adjust=False).mean()

bull = (ema8 > ema21) & (ema21 > ema55)
bear = (ema8 < ema21) & (ema21 < ema55)

buy  = bull & ~bull.shift(1).fillna(False)
sell = bear & ~bear.shift(1).fillna(False)

df['buy']  = buy.fillna(False).astype(bool)
df['sell'] = sell.fillna(False).astype(bool)

buy_marks  = [df['low'].iloc[i]  * 0.995 if df['buy'].iloc[i]  else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if df['sell'].iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "EMA 8",  "data": ema8.fillna(0).tolist(),  "color": "#4CAF50", "overlay": True},
        {"name": "EMA 21", "data": ema21.fillna(0).tolist(), "color": "#FFC107", "overlay": True},
        {"name": "EMA 55", "data": ema55.fillna(0).tolist(), "color": "#F44336", "overlay": True}
    ],
    "signals": [
        {"type": "buy",  "text": "B", "data": buy_marks,  "color": "#00E676"},
        {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"}
    ]
}
