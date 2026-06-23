my_indicator_name = "v1.0.6 ops(双向+31.83) PowerTower 策略-BTC/USDT"
my_indicator_description = "保持 RSI 反转逻辑不变，使用更平滑的 RSI 周期与更严格且对称的超买超卖阈值，减少过度交易并提升风险调整收益。"
# 回测参数（开单参数） 标的：BTC K线周期：1H 日期范围：2Y  杠杆：1x  交易方向：双向
# 模拟开单参数 标的：BTC K线周期：1H  杠杆：5x  交易方向：双向

# 契约头注释
# exit_owner: engine （它只是给人/校验看的退出归属声明，删掉不影响行为——引擎止损仍由 @strategy stopLossPct 0.05 生效，反向信号平仓照常）

# @strategy entryPct 0.5
# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0
# @strategy trailingEnabled false
# @strategy tradeDirection both

# @param rsi_len int 14 RSI period
# @param buy_threshold float 24 Oversold threshold
# @param sell_threshold float 76 Overbought threshold

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
rsi = rsi.fillna(50.0)

raw_buy = (rsi < safe_buy_threshold).fillna(False)
raw_sell = (rsi > safe_sell_threshold).fillna(False)

def edge(s):
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return (s & ~prev).astype(bool)

buy = edge(raw_buy)
sell = edge(raw_sell)

df['buy'] = buy
df['sell'] = sell

plot_rsi_name = 'RSI(' + str(safe_rsi_len) + ')'

buy_marks = [low.iloc[i] * 0.995 if bool(df['buy'].iloc[i]) else None for i in range(len(df))]
sell_marks = [high.iloc[i] * 1.005 if bool(df['sell'].iloc[i]) else None for i in range(len(df))]

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
