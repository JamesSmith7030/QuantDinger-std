my_indicator_name = "v1.0.6 self(双向+31.83) PowerTower 策略-BTC/USDT"
my_indicator_description = "保持 RSI 反转逻辑不变，使用更平滑的 RSI 周期与更严格且对称的超买超卖阈值，减少过度交易并提升风险调整收益。"
# extend v1.0.5(双向+31.83) PowerTower 策略-BTC/USDT
# 历史基线（旧止损参数） 标的：BTC K线周期：1H 日期范围：2Y  杠杆：1x  交易方向：双向  回测收益：+22.30%
# 模拟开单参数 标的：BTC K线周期：1H  杠杆：5x  交易方向：双向

# signal_form: four_way
# exit_owner: engine
# flip_mode: R2

# --- 参数声明 (Params) ---
# @param rsi_len int 14 RSI period
# @param buy_threshold float 24 Oversold threshold
# @param sell_threshold float 76 Overbought threshold

# --- 策略风控默认值 (Strategy Defaults) ---
# @strategy entryPct 0.9
# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0
# @strategy trailingEnabled false
# @strategy trailingStopPct 0
# @strategy trailingActivationPct 0
# @strategy tradeDirection both

rsi_len = params.get('rsi_len', 14)
buy_threshold = params.get('buy_threshold', 24)
sell_threshold = params.get('sell_threshold', 76)

df = df.copy()

close = df['close']
low = df['low']
high = df['high']

safe_rsi_len = max(int(rsi_len), 1)
safe_buy_threshold = float(buy_threshold)
safe_sell_threshold = float(sell_threshold)

delta = close.diff()
gain = delta.clip(lower=0)
loss = (-delta).clip(lower=0)

avg_gain = gain.ewm(alpha=1.0 / safe_rsi_len, adjust=False).mean()
avg_loss = loss.ewm(alpha=1.0 / safe_rsi_len, adjust=False).mean()

rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))
rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
rsi = rsi.fillna(50.0)

raw_buy = (rsi < safe_buy_threshold).fillna(False)
raw_sell = (rsi > safe_sell_threshold).fillna(False)

def edge(s):
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return (s & ~prev).astype(bool)


open_long = edge(raw_buy)
open_short = edge(raw_sell)

df['open_long'] = open_long
df['close_long'] = open_short
df['open_short'] = open_short
df['close_short'] = open_long

plot_rsi_name = 'RSI(' + str(safe_rsi_len) + ')'

buy_marks = [low.iloc[i] * 0.995 if bool(df['open_long'].iloc[i]) else None for i in range(len(df))]
sell_marks = [high.iloc[i] * 1.005 if bool(df['open_short'].iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': plot_rsi_name, 'data': rsi.tolist(), 'color': '#faad14', 'overlay': False, 'type': 'line'},
        {'name': 'Buy Threshold', 'data': [safe_buy_threshold] * len(df), 'color': '#00E676', 'overlay': False, 'type': 'line'},
        {'name': 'Sell Threshold', 'data': [safe_sell_threshold] * len(df), 'color': '#FF5252', 'overlay': False, 'type': 'line'}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ],
    'calculatedVars': {}
}
