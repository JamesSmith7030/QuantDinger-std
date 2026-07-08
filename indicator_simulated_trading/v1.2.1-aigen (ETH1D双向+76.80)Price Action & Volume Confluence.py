
"""
Price Action & Volume Confluence
hybin 发布于: 5/13/2026
指标说明：结合均线趋势、裸K价格行为（Pin Bar/吞没形态）与成交量放大的顺势回调策略。

回测表现
综合评分：67 / 100  总收益率：+4.30%  夏普：2.61  最大回撤：-3.33%  盈亏比：439.50  胜率：100.00%
实盘策略：0  实盘交易：0
适用标的：BTC/USDT, ETH/USDT, SOL/USDT
适用周期：1H, 15m, 30m, 4H, 5m
"""

# AI 调优 - AI 生成
# extend v1.0.1-aigen (ETH1D双向+6.29)Price Action & Volume Confluence
my_indicator_name = "v1.2.1-aigen (ETH1D双向+76.80)Price Action & Volume Confluence"
my_indicator_description = "结合均线趋势、裸K价格行为（Pin Bar/吞没形态）与成交量放大的顺势回调策略。"
# 回测参数 标的: ETH, K线周期: 1D, 日期范围: 2Y, 杠杆: 5x, 交易方向: 双向, 回测收益: +76.80%

# --- 1. 参数声明 (Params) ---
# @param fast_ema int 13 快速EMA周期：趋势与价值区间上沿
# @param slow_ema int 55 慢速EMA周期：趋势与价值区间下沿
# @param vol_len int 21 成交量均线周期
# @param vol_mult float 0.62 成交量放大倍数过滤
# @param pin_ratio float 1.05 PinBar影线与实体比例要求

# --- 2. 策略风控默认值 (Strategy Defaults) ---
# @strategy stopLossPct 0.062
# @strategy takeProfitPct 0.041
# @strategy entryPct 0.25
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.011
# @strategy trailingActivationPct 0.025
# @strategy tradeDirection both

# --- 3. 数据准备 ---
df = df.copy()

fast_len = int(params.get('fast_ema', 13))
slow_len = int(params.get('slow_ema', 55))
vol_len = int(params.get('vol_len', 21))
vol_mult = float(params.get('vol_mult', 0.62))
pin_ratio = float(params.get('pin_ratio', 1.05))

fast_len = max(fast_len, 1)
slow_len = max(slow_len, 2)
vol_len = max(vol_len, 1)
vol_mult = max(vol_mult, 0.0)
pin_ratio = max(pin_ratio, 0.0)

open_price = df['open']
high_price = df['high']
low_price = df['low']
close_price = df['close']
volume = df['volume']

ema_fast = close_price.ewm(span=fast_len, adjust=False).mean()
ema_slow = close_price.ewm(span=slow_len, adjust=False).mean()
vol_sma = volume.rolling(vol_len, min_periods=1).mean()

body = (close_price - open_price).abs()
candle_top = df[['open', 'close']].max(axis=1)
candle_bottom = df[['open', 'close']].min(axis=1)
upper_shadow = (high_price - candle_top).clip(lower=0)
lower_shadow = (candle_bottom - low_price).clip(lower=0)

prev_open = open_price.shift(1)
prev_close = close_price.shift(1)
prev_body_net = prev_close - prev_open
curr_body_net = close_price - open_price

bullish_pin = (lower_shadow > (body * pin_ratio)) & (upper_shadow < body) & (body > 0)
bullish_engulfing = (
    (prev_body_net < 0) &
    (curr_body_net > 0) &
    (close_price > prev_open) &
    (open_price < prev_close)
)

bearish_pin = (upper_shadow > (body * pin_ratio)) & (lower_shadow < body) & (body > 0)
bearish_engulfing = (
    (prev_body_net > 0) &
    (curr_body_net < 0) &
    (close_price < prev_open) &
    (open_price > prev_close)
)

long_trend_ok = ema_fast > ema_slow
long_pullback = (low_price < ema_fast) & (close_price > ema_slow)
long_pa_trigger = bullish_pin | bullish_engulfing

short_trend_ok = ema_fast < ema_slow
short_pullback = (high_price > ema_fast) & (close_price < ema_slow)
short_pa_trigger = bearish_pin | bearish_engulfing

vol_ok = volume >= (vol_sma * vol_mult)

raw_long = (long_trend_ok & long_pullback & long_pa_trigger & vol_ok).fillna(False)
raw_short = (short_trend_ok & short_pullback & short_pa_trigger & vol_ok).fillna(False)

def edge(s):
    s = s.fillna(False).astype(bool)
    return (s & ~s.shift(1).fillna(False)).astype(bool)

open_long_signal = edge(raw_long)
open_short_signal = edge(raw_short)

df['open_long'] = open_long_signal.astype(bool)
df['close_long'] = open_short_signal.astype(bool)
df['open_short'] = open_short_signal.astype(bool)
df['close_short'] = open_long_signal.astype(bool)

buy_marks = [
    low_price.iloc[i] * 0.99 if bool(df['open_long'].iloc[i]) else None
    for i in range(len(df))
]
sell_marks = [
    high_price.iloc[i] * 1.01 if bool(df['open_short'].iloc[i]) else None
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
            "name": "Volume SMA",
            "data": vol_sma.fillna(0).tolist(),
            "color": "#9254de",
            "overlay": False,
            "type": "line"
        }
    ],
    "signals": [
        {
            "type": "buy",
            "text": "PA Long",
            "data": buy_marks,
            "color": "#00E676"
        },
        {
            "type": "sell",
            "text": "PA Short",
            "data": sell_marks,
            "color": "#FF5252"
        }
    ],
    "calculatedVars": {}
}
