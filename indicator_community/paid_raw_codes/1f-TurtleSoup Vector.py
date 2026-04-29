import numpy as np

my_indicator_name = "TurtleSoup Vector"
my_indicator_description = "流动性猎杀：捕捉 2.5 STD 极值扫掠与收线拒绝，免疫次根K线滑点"

# ─── 1. 数学统计算法参数 ───
# @param bb_len int 20 基准周期
# @param bb_std float 2.5 极值标准差 (2.5 过滤 99% 的常态波动，仅捕捉极端扫掠)
# @param rsi_len int 14 RSI 周期
# @param rsi_os float 35 恐慌超卖阈值
# @param rsi_ob float 65 狂热超买阈值

# ─── 2. 胜率风控模型 (快进快出，盈亏比 1:1.5) ───
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.03
# @strategy entryPct 0.5
# @strategy tradeDirection both

df = df.copy()

bb_len = int(params.get('bb_len', 20))
bb_std = float(params.get('bb_std', 2.5))
rsi_len = int(params.get('rsi_len', 14))
rsi_os = float(params.get('rsi_os', 35))
rsi_ob = float(params.get('rsi_ob', 65))

# ─── 3. 统计学极值轨道 ───
df['bb_mid'] = df['close'].rolling(bb_len).mean()
df['bb_std_val'] = df['close'].rolling(bb_len).std()
df['bb_upper'] = df['bb_mid'] + bb_std * df['bb_std_val']
df['bb_lower'] = df['bb_mid'] - bb_std * df['bb_std_val']

# ─── 4. 动能衰竭指标 ───
delta = df['close'].diff()
gain = delta.clip(lower=0).ewm(alpha=1/rsi_len, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1/rsi_len, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
df['rsi'] = 100 - (100 / (1 + rs))

# ─── 5. 流动性猎杀 (Sweep & Reject) ───
# 做多：向下插针刺穿下轨 -> 实体收盘拒绝跌破 -> RSI 处于恐慌区
long_sweep = (df['low'] < df['bb_lower']) & (df['close'] > df['bb_lower']) & (df['rsi'] < rsi_os)

# 做空：向上插针刺穿上轨 -> 实体收盘拒绝突破 -> RSI 处于狂热区
short_sweep = (df['high'] > df['bb_upper']) & (df['close'] < df['bb_upper']) & (df['rsi'] > rsi_ob)

# ─── 6. 信号边沿提纯 ───
df['buy'] = (long_sweep.fillna(False) & (~long_sweep.shift(1).fillna(False))).astype(bool)
df['sell'] = (short_sweep.fillna(False) & (~short_sweep.shift(1).fillna(False))).astype(bool)

# ─── 7. UI 极简渲染 ───
buy_marks = [df['low'].iloc[i] * 0.99 if df['buy'].iloc[i] else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.01 if df['sell'].iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": "Upper Envelope", "data": df['bb_upper'].fillna(0).tolist(), "color": "#f5222d", "overlay": True},
        {"name": "Lower Envelope", "data": df['bb_lower'].fillna(0).tolist(), "color": "#52c41a", "overlay": True}
    ],
    "signals": [
        {"type": "buy", "text": "SWEEP", "data": buy_marks, "color": "#00E676"},
        {"type": "sell", "text": "SWEEP", "data": sell_marks, "color": "#FF5252"}
    ]
}
