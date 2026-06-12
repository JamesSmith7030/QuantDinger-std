my_indicator_name = "v1.0.4 [ETH30m] 趋势回踩突破（四路标准修复版）"
my_indicator_description = "v1.0.3 的四路标准重写：EMA判断方向，回踩/突破触发入场，RSI确认动量，ATR过滤极端波动。方向语义锁定为只做多（open_short/close_short 恒为 False），退出由引擎风控负责（固定止损/止盈/移动止盈），指标侧 close_long 仅做趋势/动量/结构破位的结构性离场。"

# signal_form: four_way
# exit_owner: engine
# flip_mode: R1

# @param fast_len int 34 Fast EMA length
# @param slow_len int 96 Slow EMA length
# @param rsi_len int 18 RSI length
# @param rsi_floor float 55 Minimum RSI for long entry
# @param atr_len int 20 ATR length
# @param atr_filter_mult float 1.8 Max ATR expansion multiplier
# @param breakout_len int 20 Breakout lookback bars
# @param pullback_buffer float 0.004 Pullback tolerance around EMA fast

# @strategy stopLossPct 0.028
# @strategy takeProfitPct 0.065
# @strategy entryPct 0.1
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.005
# @strategy trailingActivationPct 0.009
# @strategy tradeDirection long

df = df.copy()

fast_len = int(params.get("fast_len", 34))
slow_len = int(params.get("slow_len", 96))
rsi_len = int(params.get("rsi_len", 18))
rsi_floor = float(params.get("rsi_floor", 55.0))
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

trend_up = ema_fast > ema_slow
price_above_slow = close > ema_slow

# RSI（P3 修复：loss==0 的连续上涨期应为 100 而不是被算成 0；
# 前导未成熟期填 50 中性值，避免既误触发 rsi_ok 也误触发 weak_momentum）
delta = close.diff()
gain = delta.clip(lower=0).ewm(alpha=1 / rsi_len, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_len, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))
rsi = rsi.where(~((loss == 0) & (gain > 0)), 100.0)
rsi = rsi.fillna(50.0)
rsi_ok = rsi > rsi_floor

# ATR 波动过滤
high_low = high - low
high_close = (high - close.shift(1)).abs()
low_close = (low - close.shift(1)).abs()
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
atr = tr.rolling(atr_len, min_periods=1).mean()
atr_pct = (atr / close.replace(0, np.nan)).fillna(0)
atr_pct_ma = atr_pct.rolling(atr_len * 3, min_periods=1).mean()
vol_ok = atr_pct < (atr_pct_ma * atr_filter_mult).fillna(0)

# 突破 / 回踩
range_high = high.rolling(breakout_len, min_periods=1).max().shift(1)
range_low = low.rolling(breakout_len, min_periods=1).min().shift(1)

breakout_buy = close > range_high.fillna(close)

near_ema_fast = low <= ema_fast * (1 + pullback_buffer)
recover_above_ema = close > ema_fast
pullback_buy = trend_up & price_above_slow & near_ema_fast & recover_above_ema

# ---------- 信号层 ----------
raw_open_long = (
    trend_up &
    price_above_slow &
    rsi_ok &
    vol_ok &
    (breakout_buy | pullback_buy)
)

# 结构性离场（趋势破位 / 动量走弱 / 结构破位）。窄止盈止损归引擎（exit_owner: engine）。
trend_fail = ema_fast < ema_slow
weak_momentum = rsi < 44
structure_fail = close < range_low.fillna(close)
raw_close_long = trend_fail | weak_momentum | structure_fail


def edge(s):
    """边缘触发（P1 修复：shift 后必须 astype(bool)，否则 pandas 3.x 下 ~ 取反静默失效）"""
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return (s & ~prev).astype(bool)


open_long = edge(raw_open_long)
close_long = edge(raw_close_long)
false_col = pd.Series(False, index=df.index)

# P0 修复：四路执行列把方向语义锁死在代码里——空头两列恒为 False，
# 即使部署配置误设为 both，也不会把离场条件解释成开空信号。
df["open_long"] = open_long
df["close_long"] = close_long
df["open_short"] = false_col
df["close_short"] = false_col

# ---------- 图表输出 ----------
buy_marks = [
    low.iloc[i] * 0.995 if bool(open_long.iloc[i]) else None
    for i in range(len(df))
]
sell_marks = [
    high.iloc[i] * 1.005 if bool(close_long.iloc[i]) else None
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
    ],
    "calculatedVars": {}
}
