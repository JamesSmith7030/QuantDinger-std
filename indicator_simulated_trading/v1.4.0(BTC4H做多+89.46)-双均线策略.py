# extend v1.0.1(SOL4H做多+355.19)-双均线策略
# signal_form: four_way
# exit_owner: engine
# flip_mode: R1
my_indicator_name = "v1.4.0(BTC4H做多+89.46)-双均线策略"
my_indicator_description = "EMA双均线做多策略(参数优化):短期EMA上穿长期EMA且价格位于长期趋势线上方时开多,死叉平多;引擎管理固定止损/止盈+移动止损压制回撤。信号收盘确认,次开盘成交"
# 回测 标的: BNB, K线周期: 4H, 日期范围: 2Y, 杠杆: 3x, 交易方向: 做多
# 总收益 +46.34% / 最大回撤 -30.07% / 夏普比率 0.53 / 胜率 +54.55% / 盈亏比 1.58 / 交易次数 22

# 回测 标的: SOL, K线周期: 4H, 日期范围: 2Y, 杠杆: 3x, 交易方向: 做多
# 总收益 +66.03% / 最大回撤 -20.62% / 夏普比率 0.81 / 胜率 +75.00% / 盈亏比 2.00 / 交易次数 16

# 回测 标的: BTC, K线周期: 4H, 日期范围: 2Y, 杠杆: 3x, 交易方向: 做多
# 总收益 +89.46% / 最大回撤 -26.52% / 夏普比率 1.08 / 胜率 +71.43% / 盈亏比 3.74 / 交易次数 14


# 回测基线 标的: SOL, K线周期: 4H, 日期范围: 2Y, 杠杆: 3x, 交易方向: 做多
# 基线表现: +90.22% / 最大回撤 -30.06% / Sharpe 0.76 / 胜率 45.45% / 盈亏比 1.70 / 33笔


# --- 1. 参数声明 (Params) ---
# @param ema_short_len int 21 短期EMA周期
# @param ema_long_len int 55 长期EMA周期
# @param trend_len int 200 趋势过滤EMA周期
# @param use_trend_filter bool true 是否启用趋势过滤(仅在长期趋势向上时做多)

# --- 2. 策略风控默认值 (Strategy Defaults) ---
# @strategy entryPct 0.8
# @strategy stopLossPct 0.05
# @strategy takeProfitPct 0.2
# @strategy trailingEnabled true
# @strategy trailingActivationPct 0.05
# @strategy trailingStopPct 0.03
# @strategy tradeDirection long
#
# 参数优化思路(保持双均线交叉核心逻辑不变,仅调参改善风险调整后收益):
#   1) 短/长均线由 20/50 微调到 21/55,进一步过滤高波动区假突破,减少低质量交叉。
#   2) 趋势过滤保持 EMA200,只在长期趋势向上时做多,规避下跌段反复止损。
#   3) 风控收紧:止损 6%->5%、止盈 18%->20%、移动止损 3.5%->3.0%、仓位 0.85->0.8,
#      目标是在维持收益的同时压低最大回撤,提升 Sharpe 与盈亏比。

df = df.copy()

# ---- 读取参数 ----
ema_short_len = int(params.get('ema_short_len', 21))
ema_long_len = int(params.get('ema_long_len', 55))
trend_len = int(params.get('trend_len', 200))
use_trend_filter = bool(params.get('use_trend_filter', True))

# ---- 1. 指标计算 ----
close = df['close']
ema_short = close.ewm(span=ema_short_len, adjust=False).mean()
ema_long = close.ewm(span=ema_long_len, adjust=False).mean()
ema_trend = close.ewm(span=trend_len, adjust=False).mean()

# ---- 2. 信号逻辑 ----
# 金叉:短期EMA上穿长期EMA
golden_cross = (ema_short > ema_long) & (ema_short.shift(1) <= ema_long.shift(1))
# 死叉:短期EMA下穿长期EMA
death_cross = (ema_short < ema_long) & (ema_short.shift(1) >= ema_long.shift(1))

# 趋势过滤:价格位于长期趋势线上方
if use_trend_filter:
    trend_ok = close > ema_trend
else:
    trend_ok = pd.Series(True, index=df.index)

raw_open_long = (golden_cross & trend_ok).fillna(False)
raw_close_long = death_cross.fillna(False)


# 边缘触发助手:只在状态由 False->True 的那根K线触发
def edge(s):
    s = s.fillna(False).astype(bool)
    return s & ~s.shift(1).fillna(False)


open_long = edge(raw_open_long)
close_long = edge(raw_close_long)
# 长期做多策略,不做空
open_short = pd.Series(False, index=df.index)
close_short = pd.Series(False, index=df.index)

# ---- 四路执行列 ----
df['open_long'] = open_long.astype(bool)
df['close_long'] = close_long.astype(bool)
df['open_short'] = open_short.astype(bool)
df['close_short'] = close_short.astype(bool)

# ---- 3. 可视化 ----
buy_marks = [
    df['low'].iloc[i] * 0.995 if bool(df['open_long'].iloc[i]) else None
    for i in range(len(df))
]
sell_marks = [
    df['high'].iloc[i] * 1.005 if bool(df['close_long'].iloc[i]) else None
    for i in range(len(df))
]

ema_short_data = [None if pd.isna(x) else float(x) for x in ema_short]
ema_long_data = [None if pd.isna(x) else float(x) for x in ema_long]
ema_trend_data = [None if pd.isna(x) else float(x) for x in ema_trend]

# ---- 4. 输出 ----
output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "EMA %d" % ema_short_len,
            "data": ema_short_data,
            "color": "#1890ff",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "EMA %d" % ema_long_len,
            "data": ema_long_data,
            "color": "#faad14",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "EMA %d (趋势)" % trend_len,
            "data": ema_trend_data,
            "color": "#8e44ad",
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
