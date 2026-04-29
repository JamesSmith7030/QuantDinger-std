# Existing code was provided as context.
my_indicator_name = "PowerTower 策略"
my_indicator_description = "### PowerTower 策略  **策略原理**： - 识别价格指数级上涨形态 - 连续3根K线满足幂次增长时触发买入信号 - 连续2根K线满足幂次下跌时触发卖出信号  **公式**： ``` 买入条件: 当前价 > 2根前K线收盘价 × (1 + BUY_POW/100) 且 1根前 > 3根前 × (1 + BUY_POW/100) 且 2根前 > 4根前 × (1 + BUY_POW/"

# @param rsi_len int 14 RSI period

rsi_len = params.get('rsi_len', 14)
df = df.copy()

# Example: robust RSI with edge-triggered buy/sell (no position management, no TP/SL on chart)
delta = df['close'].diff()
gain = delta.clip(lower=0)
loss = (-delta).clip(lower=0)
# Wilder-style smoothing (stable and avoids early NaN explosion)
avg_gain = gain.ewm(alpha=1/rsi_len, adjust=False).mean()
avg_loss = loss.ewm(alpha=1/rsi_len, adjust=False).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))
rsi = rsi.fillna(50)

# Raw conditions (avoid overly strict filters)
raw_buy = (rsi < 30)
raw_sell = (rsi > 70)
# One-shot signals
buy = (raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))).astype(bool)
sell = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)
df['buy'] = buy
df['sell'] = sell

buy_marks = [df['low'].iloc[i] * 0.995 if bool(df['buy'].iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(df['sell'].iloc[i]) else None for i in range(len(df))]

output = {
  'name': my_indicator_name,
  'plots': [
    {'name': 'RSI(14)', 'data': rsi.tolist(), 'color': '#faad14', 'overlay': False}
  ],
  'signals': [
    {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
    {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
  ]
}
