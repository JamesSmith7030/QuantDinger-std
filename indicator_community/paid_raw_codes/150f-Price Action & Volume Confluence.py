
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

my_indicator_name = "150f-Price Action & Volume Confluence"
my_indicator_description = "结合均线趋势、裸K价格行为（Pin Bar/吞没形态）与成交量放大的顺势回调策略。"

# --- 1. 参数声明 (Params) ---
# @param fast_ema int 12 快速均线周期 (价值区间上限)
# @param slow_ema int 30 慢速均线周期 (价值区间下限)
# @param vol_len int 12 成交量均线周期
# @param vol_mult float 1.05 成交量放大倍数
# @param pin_ratio float 1.6 PinBar影线与实体的比例要求

# --- 2. 策略风控默认值 (Strategy Defaults) ---
# 使用引擎管理退出逻辑，避免代码过于复杂
# @strategy stopLossPct 0.018
# @strategy takeProfitPct 0.04
# @strategy entryPct 0.18
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.01
# @strategy trailingActivationPct 0.018
# @strategy tradeDirection both

# --- 3. 数据准备 ---
df = df.copy()

fast_len = int(params.get('fast_ema', 20))
slow_len = int(params.get('slow_ema', 50))
vol_len = int(params.get('vol_len', 20))
vol_mult = float(params.get('vol_mult', 1.2))
pin_ratio = float(params.get('pin_ratio', 2.0))

# 计算均线与成交量基准
ema_fast = df['close'].ewm(span=fast_len, adjust=False).mean()
ema_slow = df['close'].ewm(span=slow_len, adjust=False).mean()
vol_sma = df['volume'].rolling(vol_len).mean()

# --- 4. 价格行为 (Price Action) 模式识别 ---
# 基础 K 线元素
body = abs(df['close'] - df['open'])
upper_shadow = df['high'] - df[['open', 'close']].max(axis=1)
lower_shadow = df[['open', 'close']].min(axis=1) - df['low']

# 模式 A: Bullish Pin Bar (长下影线，实体较小)
bullish_pin = (lower_shadow > (body * pin_ratio)) & (upper_shadow < body) & (body > 0)
# 模式 B: Bullish Engulfing (看涨吞没)
prev_body_net = df['close'].shift(1) - df['open'].shift(1)
curr_body_net = df['close'] - df['open']
bullish_engulfing = (prev_body_net < 0) & (curr_body_net > 0) & (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))

# 模式 C: Bearish Pin Bar (长上影线)
bearish_pin = (upper_shadow > (body * pin_ratio)) & (lower_shadow < body) & (body > 0)
# 模式 D: Bearish Engulfing (看跌吞没)
bearish_engulfing = (prev_body_net > 0) & (curr_body_net < 0) & (df['close'] < df['open'].shift(1)) & (df['open'] > df['close'].shift(1))

# --- 5. 综合信号逻辑 ---
# 多头逻辑：大趋势向上 + 回调到价值区间 + 出现看涨价格行为 + 成交量放大
long_trend_ok = ema_fast > ema_slow
long_pullback = (df['low'] < ema_fast) & (df['close'] > ema_slow)
long_pa_trigger = bullish_pin | bullish_engulfing
vol_ok = df['volume'] >= (vol_sma * vol_mult)

raw_buy = long_trend_ok & long_pullback & long_pa_trigger & vol_ok

# 空头逻辑：大趋势向下 + 反弹到价值区间 + 出现看跌价格行为 + 成交量放大
short_trend_ok = ema_fast < ema_slow
short_pullback = (df['high'] > ema_fast) & (df['close'] < ema_slow)
short_pa_trigger = bearish_pin | bearish_engulfing

raw_sell = short_trend_ok & short_pullback & short_pa_trigger & vol_ok

# 边缘触发 (Edge-trigger) 处理，避免连续触发
buy = (raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))).astype(bool)
sell = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)

df['buy'] = buy
df['sell'] = sell

# --- 6. 图表输出组装 ---
buy_marks = [df['low'].iloc[i] * 0.99 if buy.iloc[i] else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.01 if sell.iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "EMA Fast (Value High)",
            "data": ema_fast.fillna(0).tolist(),
            "color": "#1890ff",
            "overlay": True
        },
        {
            "name": "EMA Slow (Value Low)",
            "data": ema_slow.fillna(0).tolist(),
            "color": "#faad14",
            "overlay": True
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
    ]
}
