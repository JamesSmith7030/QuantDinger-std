my_indicator_name = "v1.0.1(SOL4H做多+355.19)-双均线策略"
my_indicator_description = "使用指数移动平均线(EMA)的交叉策略：短期EMA(10)上穿长期EMA(30)时买入，下穿时卖出。信号在K线收盘确认"
# 回测 标的: SOL, K线周期: 4H, 日期范围: 2Y, 杠杆: 3x, 交易方向: 做多

# signal_form: four_way
# exit_owner: engine
# flip_mode: R1

# --- 策略风控默认值 (Strategy Defaults) ---
# @strategy entryPct 0.9
# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0
# @strategy trailingEnabled false
# @strategy trailingStopPct 0
# @strategy trailingActivationPct 0
# @strategy tradeDirection long

df = df.copy()

# 1. 指标计算
# -----------------------
# 计算短期和长期 EMA
ema_short = df['close'].ewm(span=10).mean()
ema_long = df['close'].ewm(span=30).mean()

# 2. 信号逻辑
# -----------------------
# 买入：短期 EMA 上穿 长期 EMA
raw_buy = (ema_short > ema_long) & (ema_short.shift(1) <= ema_long.shift(1))

# 卖出：短期 EMA 下穿 长期 EMA
raw_sell = (ema_short < ema_long) & (ema_short.shift(1) >= ema_long.shift(1))

def edge(s):
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return (s & ~prev).astype(bool)


# 四路执行信号：只做多
df['open_long'] = edge(raw_buy)
df['close_long'] = edge(raw_sell)
df['open_short'] = pd.Series(False, index=df.index, dtype=bool)
df['close_short'] = pd.Series(False, index=df.index, dtype=bool)

# 3. 可视化格式化
# -----------------------
# 计算标记位置
buy_marks = [
    df['low'].iloc[i] * 0.995 if df['open_long'].iloc[i] else None
    for i in range(len(df))
]

sell_marks = [
    df['high'].iloc[i] * 1.005 if df['close_long'].iloc[i] else None
    for i in range(len(df))
]

# 准备绘图数据，使用 None 替换 NaN
ema_short_data = [None if pd.isna(x) else x for x in ema_short]
ema_long_data = [None if pd.isna(x) else x for x in ema_long]

# 4. 最终输出
# -----------------------
output = {
  "name": my_indicator_name,
  "plots": [
    {
        "name": "EMA 10",
        "data": ema_short_data,
        "color": "#1890ff",
        "overlay": True,
        "type": "line"
    },
    {
        "name": "EMA 30",
        "data": ema_long_data,
        "color": "#faad14",
        "overlay": True,
        "type": "line"
    }
  ],
  "signals": [
    {
        "type": "buy",
        "text": "B",
        "data": buy_marks,
        "color": "#00E676"
    },
    {
        "type": "sell",
        "text": "S",
        "data": sell_marks,
        "color": "#FF5252"
    }
  ]
}
