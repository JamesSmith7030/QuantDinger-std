my_indicator_name = "Drawdown & BIAS Direction Strategy"
my_indicator_description = "Buy when max drawdown < 3% and BIAS is falling; sell when max drawdown > 8% and BIAS is rising."

# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0.10
# @strategy entryPct 0.25
# @strategy trailingEnabled false
# @strategy tradeDirection both

# @param lookback int 20 Rolling window for max drawdown calculation
# @param bias_len int 20 Period for BIAS (close vs SMA)
# @param buy_dd_threshold float 0.03 Max drawdown below this triggers buy (3%)
# @param sell_dd_threshold float 0.08 Max drawdown above this triggers sell (8%)

lookback = int(params.get('lookback', 20))
bias_len = int(params.get('bias_len', 20))
buy_dd_threshold = float(params.get('buy_dd_threshold', 0.03))
sell_dd_threshold = float(params.get('sell_dd_threshold', 0.08))

df = df.copy()
close = pd.to_numeric(df['close'], errors='coerce')

# 1. 计算滚动最大回撤率 (drawdown)
# 滚动最高价 (前 lookback 根 K 线的最高值)
rolling_high = close.rolling(window=lookback, min_periods=1).max()
drawdown = (rolling_high - close) / rolling_high  # 回撤率，范围 0~1
drawdown = drawdown.fillna(0)

# 2. 计算乖离率 BIAS = (close - SMA) / SMA
sma = close.rolling(window=bias_len, min_periods=1).mean()
bias = (close - sma) / sma
bias = bias.fillna(0)

# 3. 计算方向变化：当前期 vs 上一期
bias_falling = bias < bias.shift(1)   # 下移（当前 < 前一期）
bias_rising = bias > bias.shift(1)    # 上移（当前 > 前一期）

# 4. 原始信号条件
raw_buy = (drawdown < buy_dd_threshold) & bias_falling
raw_sell = (drawdown > sell_dd_threshold) & bias_rising

# 5. 边缘触发：只在条件从 false 变为 true 时产生信号
buy = (raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))).astype(bool)
sell = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)

df['buy'] = buy
df['sell'] = sell

# 6. 图表标记：在信号位置画标记
buy_marks = [float(df['low'].iloc[i]) * 0.995 if buy.iloc[i] else None for i in range(len(df))]
sell_marks = [float(df['high'].iloc[i]) * 1.005 if sell.iloc[i] else None for i in range(len(df))]

# 7. 准备输出
output = {
    'name': my_indicator_name,
    'plots': [
        {
            'name': 'Drawdown',
            'data': drawdown.tolist(),
            'color': '#FF6B6B',
            'overlay': False,
            'type': 'line'
        },
        {
            'name': 'BIAS',
            'data': bias.tolist(),
            'color': '#4ECDC4',
            'overlay': False,
            'type': 'line'
        },
        {
            'name': 'SMA',
            'data': sma.tolist(),
            'color': '#F9CA4B',
            'overlay': True,
            'type': 'line'
        }
    ],
    'signals': [
        {
            'type': 'buy',
            'text': 'B',
            'color': '#00E676',
            'data': buy_marks
        },
        {
            'type': 'sell',
            'text': 'S',
            'color': '#FF5252',
            'data': sell_marks
        }
    ],
    'calculatedVars': {
        'lookback': lookback,
        'bias_len': bias_len,
        'buy_dd_threshold': buy_dd_threshold,
        'sell_dd_threshold': sell_dd_threshold
    }
}
