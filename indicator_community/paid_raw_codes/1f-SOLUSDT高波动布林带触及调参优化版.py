my_indicator_name = "SOLUSDT高波动布林带触及调参优化版"
my_indicator_description = "简单布林带反转思路示例；实盘请结合趋势过滤与风控。"

# @strategy stopLossPct 0
# @strategy takeProfitPct 0.1
# @strategy entryPct 0.3
# @strategy tradeDirection long
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.03
# @strategy trailingActivationPct 0.06

df = df.copy()
period = 20
mult = 2.0
mid = df['close'].rolling(period, min_periods=1).mean()
std = df['close'].rolling(period, min_periods=1).std()
upper = mid + mult * std
lower = mid - mult * std

raw_buy = df['close'] < lower
raw_sell = df['close'] > upper
buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))
df['buy'] = buy.astype(bool)
df['sell'] = sell.astype(bool)

buy_marks = [df['low'].iloc[i] * 0.995 if bool(buy.iloc[i]) else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if bool(sell.iloc[i]) else None for i in range(len(df))]

output = {
    'name': my_indicator_name,
    'plots': [
        {'name': 'BOLL 上', 'data': upper.tolist(), 'color': '#69c0ff', 'overlay': True},
        {'name': 'BOLL 中', 'data': mid.tolist(), 'color': '#d9d9d9', 'overlay': True},
        {'name': 'BOLL 下', 'data': lower.tolist(), 'color': '#69c0ff', 'overlay': True}
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00E676'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}
