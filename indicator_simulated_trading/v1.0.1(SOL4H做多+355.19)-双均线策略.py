my_indicator_name = "v1.0.1(SOL4H做多+355.19)-双均线策略"
my_indicator_description = "使用指数移动平均线(EMA)的交叉策略：短期EMA(10)上穿长期EMA(30)时买入，下穿时卖出。信号在K线收盘确认"

# --- 参数声明 (Params) ---


# --- 策略风控默认值 (Strategy Defaults) ---
# @strategy entryPct 0.9


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

# 清理 NaN 并确保布尔类型
buy = raw_buy.fillna(False)
sell = raw_sell.fillna(False)

# 赋值给 df 列 (后端执行的关键)
df['buy'] = buy
df['sell'] = sell

# 3. 可视化格式化
# -----------------------
# 计算标记位置
buy_marks = [
    df['low'].iloc[i] * 0.995 if buy.iloc[i] else None
    for i in range(len(df))
]

sell_marks = [
    df['high'].iloc[i] * 1.005 if sell.iloc[i] else None
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
