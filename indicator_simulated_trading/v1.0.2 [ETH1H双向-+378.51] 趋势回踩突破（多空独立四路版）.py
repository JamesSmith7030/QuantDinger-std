my_indicator_name = "v1.0.2 [ETH1H双向-+378.51] 趋势回踩突破（多空独立四路版）"
my_indicator_description = "双向扩展：多头沿用趋势回踩/突破入场；空头为独立镜像建模（下跌趋势 + RSI 弱势 + 向下突破或反弹受阻），不再复用多头离场条件作为开空信号。四路信号显式表达，退出由引擎风控负责，指标侧 close_* 仅做结构性离场。"
# 初始资金：$10000.00 杠杆：4x 交易方向：双向

# signal_form: four_way
# exit_owner: engine
# flip_mode: R2

# @param fast_len int 56 快线 EMA 周期
# @param slow_len int 277 慢线 EMA 周期
# @param rsi_len int 26 RSI 周期
# @param rsi_floor float 1.359558 开多所需的最低 RSI（动量确认）
# @param rsi_ceiling float 60.562135 开空所需的最高 RSI（弱势确认）
# @param rsi_long_exit float 93.994141 多头动量衰竭离场阈值（RSI 跌破）
# @param rsi_short_exit float 410.327149 空头动量恢复离场阈值（RSI 升破）
# @param atr_len int 1 ATR 周期
# @param atr_filter_mult float 2.636719 ATR 极端波动过滤倍数
# @param breakout_len int 5 突破回看根数
# @param pullback_buffer float 0.015312 回踩/反弹至快线的容差比例

# @strategy stopLossPct 0.063
# @strategy takeProfitPct 0.061
# @strategy entryPct 0.122
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.0003
# @strategy trailingActivationPct 0.0024
# @strategy tradeDirection both

df = df.copy()

fast_len = int(params.get("fast_len", 34))
slow_len = int(params.get("slow_len", 96))
rsi_len = int(params.get("rsi_len", 18))
rsi_floor = float(params.get("rsi_floor", 55.0))
rsi_ceiling = float(params.get("rsi_ceiling", 45.0))
rsi_long_exit = float(params.get("rsi_long_exit", 44.0))
rsi_short_exit = float(params.get("rsi_short_exit", 56.0))
atr_len = int(params.get("atr_len", 20))
atr_filter_mult = float(params.get("atr_filter_mult", 1.8))
breakout_len = int(params.get("breakout_len", 20))
pullback_buffer = float(params.get("pullback_buffer", 0.004))

close = df["close"]
high = df["high"]
low = df["low"]

# ---------- 指标层 ----------
ema_fast = close.ewm(span=fast_len, adjust=False).mean()
ema_slow = close.ewm(span=slow_len, adjust=False).mean()

trend_up = ema_fast > ema_slow        # 多头趋势：快线在慢线上方
trend_down = ema_fast < ema_slow      # 空头趋势：快线在慢线下方
price_above_slow = close > ema_slow   # 价格站上慢线（多头环境确认）
price_below_slow = close < ema_slow   # 价格跌破慢线（空头环境确认）

# RSI（连续上涨期 loss==0 时应为 100，而非被除零逻辑算成 0；
# 前导未成熟期填 50 中性值，避免误触发任何一侧的动量条件）
delta = close.diff()
gain = delta.clip(lower=0).ewm(alpha=1 / rsi_len, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_len, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))
rsi = rsi.where(~((loss == 0) & (gain > 0)), 100.0)
rsi = rsi.fillna(50.0)

# ATR 波动过滤：极端放量行情两侧都不入场（插针、消息行情）
high_low = high - low
high_close = (high - close.shift(1)).abs()
low_close = (low - close.shift(1)).abs()
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
atr = tr.rolling(atr_len, min_periods=1).mean()
atr_pct = (atr / close.replace(0, np.nan)).fillna(0)
atr_pct_ma = atr_pct.rolling(atr_len * 3, min_periods=1).mean()
vol_ok = atr_pct < (atr_pct_ma * atr_filter_mult).fillna(0)

# 区间上下轨（用昨日为止的滚动极值，避免引用当根 K 的未来信息）
range_high = high.rolling(breakout_len, min_periods=1).max().shift(1)
range_low = low.rolling(breakout_len, min_periods=1).min().shift(1)

# ---------- 信号层：多头（与 v1.0.4 一致）----------
# 入场方式一：收盘向上突破区间上轨
breakout_buy = close > range_high.fillna(close)
# 入场方式二：回踩快线后收复（low 触及快线容差带，收盘重新站上快线）
near_ema_fast_long = low <= ema_fast * (1 + pullback_buffer)
recover_above_ema = close > ema_fast
pullback_buy = trend_up & price_above_slow & near_ema_fast_long & recover_above_ema

raw_open_long = (
    trend_up &
    price_above_slow &
    (rsi > rsi_floor) &
    vol_ok &
    (breakout_buy | pullback_buy)
)

# 多头结构性离场：趋势破位 / 动量衰竭 / 跌破区间下轨（窄止盈止损归引擎）
raw_close_long = (
    trend_down |
    (rsi < rsi_long_exit) |
    (close < range_low.fillna(close))
)

# ---------- 信号层：空头（独立镜像建模，不复用多头离场条件）----------
# 入场方式一：收盘向下突破区间下轨
breakdown_sell = close < range_low.fillna(close)
# 入场方式二：反弹至快线受阻（high 触及快线容差带，收盘仍被压在快线下方）
near_ema_fast_short = high >= ema_fast * (1 - pullback_buffer)
reject_below_ema = close < ema_fast
rally_reject = trend_down & price_below_slow & near_ema_fast_short & reject_below_ema

raw_open_short = (
    trend_down &
    price_below_slow &
    (rsi < rsi_ceiling) &
    vol_ok &
    (breakdown_sell | rally_reject)
)

# 空头结构性离场：趋势恢复 / 动量回升 / 收复区间上轨
raw_close_short = (
    trend_up |
    (rsi > rsi_short_exit) |
    (close > range_high.fillna(close))
)


def edge(s):
    """边缘触发：仅在条件由 False 变 True 的那根 K 触发一次。
    注意 shift 后必须显式 astype(bool)——pandas 3.x 下布尔列经 shift
    退化为 object 类型，直接 ~ 取反会静默失效（信号变成连续触发且不报错）。"""
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return (s & ~prev).astype(bool)


open_long = edge(raw_open_long)
close_long = edge(raw_close_long)
open_short = edge(raw_open_short)
close_short = edge(raw_close_short)

# 同根 K 冲突消解：持仓状态由引擎管理，脚本只保证信号自洽——
# 1) 同根 K 不允许同时开多和开空（趋势过滤下几乎不可能，双保险置空）；
# 2) close_* 与对侧 open_* 同根出现属正常反手语义（R2：先平后开），保留。
conflict = open_long & open_short
open_long = open_long & ~conflict
open_short = open_short & ~conflict

df["open_long"] = open_long
df["close_long"] = close_long
df["open_short"] = open_short
df["close_short"] = close_short

# ---------- 图表输出（仅展示，不参与成交）----------
buy_marks = [
    low.iloc[i] * 0.995 if bool(open_long.iloc[i]) else None
    for i in range(len(df))
]
sell_marks = [
    high.iloc[i] * 1.005 if bool(open_short.iloc[i]) else None
    for i in range(len(df))
]

output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "EMA Fast",
            "data": ema_fast.fillna(0).tolist(),
            "color": "#1890ff",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "EMA Slow",
            "data": ema_slow.fillna(0).tolist(),
            "color": "#faad14",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "Range High",
            "data": range_high.fillna(0).tolist(),
            "color": "#52c41a",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "Range Low",
            "data": range_low.fillna(0).tolist(),
            "color": "#f5222d",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "RSI",
            "data": rsi.fillna(50).tolist(),
            "color": "#722ed1",
            "overlay": False,
            "type": "line"
        },
        {
            "name": "ATR%",
            "data": atr_pct.fillna(0).tolist(),
            "color": "#13c2c2",
            "overlay": False,
            "type": "line"
        }
    ],
    "signals": [
        {
            "type": "buy",
            "text": "L",
            "data": buy_marks,
            "color": "#00E676"
        },
        {
            "type": "sell",
            "text": "S",
            "data": sell_marks,
            "color": "#FF5252"
        }
    ],
    "calculatedVars": {}
}
