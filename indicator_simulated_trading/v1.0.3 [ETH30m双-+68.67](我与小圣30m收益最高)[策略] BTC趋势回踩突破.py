my_indicator_name = "v1.0.3 [ETH30m双-+68.67](我与小圣30m收益最高)[策略] BTC趋势回踩突破"
my_indicator_description = "BTC永续合约趋势策略：EMA判断方向，回踩/突破触发入场，RSI确认动量，ATR过滤极端波动。止损、止盈、移动止盈和仓位由QuantDinger策略引擎管理。"
# ETH，30M级别，15倍杠杆，年化4000000000%

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

ema_fast = close.ewm(span=fast_len, adjust=False).mean()
ema_slow = close.ewm(span=slow_len, adjust=False).mean()

trend_up = ema_fast > ema_slow
price_above_slow = close > ema_slow

delta = close.diff()
gain = delta.clip(lower=0).ewm(alpha=1 / rsi_len, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_len, adjust=False).mean()
rs = (gain / loss.replace(0, np.nan)).fillna(0)
rsi = (100 - (100 / (1 + rs))).fillna(0)
rsi_ok = rsi > rsi_floor

high_low = high - low
high_close = (high - close.shift(1)).abs()
low_close = (low - close.shift(1)).abs()

tr_df = pd.concat([high_low, high_close, low_close], axis=1)
tr = tr_df.max(axis=1)
atr = tr.rolling(atr_len, min_periods=1).mean()
atr_pct = (atr / close.replace(0, np.nan)).fillna(0)
atr_pct_ma = atr_pct.rolling(atr_len * 3, min_periods=1).mean()

vol_ok = atr_pct < (atr_pct_ma * atr_filter_mult).fillna(0)

range_high = high.rolling(breakout_len, min_periods=1).max().shift(1)
range_low = low.rolling(breakout_len, min_periods=1).min().shift(1)

breakout_buy = close > range_high.fillna(close)

near_ema_fast = low <= ema_fast * (1 + pullback_buffer)
recover_above_ema = close > ema_fast

pullback_buy = (
    trend_up &
    price_above_slow &
    near_ema_fast &
    recover_above_ema
)

raw_buy = (
    trend_up &
    price_above_slow &
    rsi_ok &
    vol_ok &
    (breakout_buy | pullback_buy)
)

buy = (
    raw_buy.fillna(False) &
    (~raw_buy.shift(1).fillna(False))
).astype(bool)

trend_fail = ema_fast < ema_slow
weak_momentum = rsi < 44
structure_fail = close < range_low.fillna(close)

raw_sell = (
    trend_fail |
    weak_momentum |
    structure_fail
)

sell = (
    raw_sell.fillna(False) &
    (~raw_sell.shift(1).fillna(False))
).astype(bool)

df["buy"] = buy
df["sell"] = sell

buy_marks = [
    low.iloc[i] * 0.995 if bool(buy.iloc[i]) else None
    for i in range(len(df))
]

sell_marks = [
    high.iloc[i] * 1.005 if bool(sell.iloc[i]) else None
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
            "data": rsi.fillna(0).tolist(),
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
