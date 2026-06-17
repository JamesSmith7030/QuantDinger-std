my_indicator_name = "v1.0.5(双向+31.83) PowerTower 策略-BTC/USDT"
my_indicator_description = "保持 RSI 反转逻辑不变，使用更平滑的 RSI 周期与更严格且对称的超买超卖阈值，减少过度交易并提升风险调整收益。"
# 回测参数（开单参数） 标的：BTC K线周期：1H 日期范围：2Y  杠杆：1x  交易方向：双向

# exit_owner: engine （引擎统管退出：固定止损兜底尾部风险 + trailing 锁盈利；反向 RSI 信号仅作 flip 反手）
# @strategy entryPct 0.5
# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.02
# @strategy trailingActivationPct 0.01
# @strategy tradeDirection both

# @param rsi_len int 18 RSI period
# @param buy_threshold float 22 Oversold threshold
# @param sell_threshold float 78 Overbought threshold

# 回退默认与 @param 声明、描述（更平滑周期18 + 更严格阈值22/78）三者对齐，避免漏传参时跑成另一套
rsi_len = params.get('rsi_len', 18)
buy_threshold = params.get('buy_threshold', 22.0)
sell_threshold = params.get('sell_threshold', 78.0)

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

# 仅在“首次进入超买/超卖”的那根触发（RSI 会连续多根处于极值区，去重是必需的）。
# shift(1) 后务必 astype(bool) 再取反——否则 bool 经 shift 变 object，~ 会得到 -1/-2 整数
# 而非布尔（项目已知 pandas 3.x 坑），导致信号静默错乱。
prev_buy = raw_buy.shift(1).fillna(False).astype(bool)
prev_sell = raw_sell.shift(1).fillna(False).astype(bool)

df['buy'] = (raw_buy & ~prev_buy).astype(bool)
df['sell'] = (raw_sell & ~prev_sell).astype(bool)

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
