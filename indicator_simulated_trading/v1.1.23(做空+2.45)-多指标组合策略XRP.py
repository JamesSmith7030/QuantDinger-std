my_indicator_name = "v1.1.23(做空+2.45)-多指标组合策略XRP"
my_indicator_description = "Optimized SMA/RSI/MACD composite strategy with unchanged logic but improved default parameters for better risk-adjusted returns via slightly faster trend detection, stricter RSI timing, moderated confirmation, and lower default risk exposure"

# @param sma_short int 20 短期均线周期
# @param sma_long int 84 长期均线周期
# @param rsi_period int 14 RSI周期
# @param rsi_oversold int 34 RSI超卖阈值
# @param rsi_overbought int 60 RSI超买阈值
# @param use_macd bool True 是否使用MACD过滤
# @param use_volume bool True 是否使用成交量过滤
# @param volume_mult float 1.05 成交量放大倍数

# @strategy stopLossPct 0.007
# @strategy takeProfitPct 0.035
# @strategy entryPct 0.20
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.004
# @strategy trailingActivationPct 0.008
# @strategy tradeDirection long

sma_short_period = int(params.get('sma_short', 20))
sma_long_period = int(params.get('sma_long', 84))
rsi_period = int(params.get('rsi_period', 14))
rsi_oversold = float(params.get('rsi_oversold', 34))
rsi_overbought = float(params.get('rsi_overbought', 60))
use_macd = bool(params.get('use_macd', True))
use_volume = bool(params.get('use_volume', True))
volume_mult = float(params.get('volume_mult', 1.05))

df = df.copy()

close = pd.to_numeric(df["close"], errors="coerce")
high = pd.to_numeric(df["high"], errors="coerce")
low = pd.to_numeric(df["low"], errors="coerce")
volume = pd.to_numeric(df["volume"], errors="coerce")

sma_short_period = max(1, sma_short_period)
sma_long_period = max(sma_short_period + 1, sma_long_period)
rsi_period = max(1, rsi_period)
volume_mult = max(0.1, volume_mult)

sma_short = close.rolling(window=sma_short_period, min_periods=sma_short_period).mean()
sma_long = close.rolling(window=sma_long_period, min_periods=sma_long_period).mean()

delta = close.diff()
gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
rs = avg_gain / avg_loss.replace(0, np.nan)
rsi = (100 - (100 / (1 + rs))).fillna(50)

exp1 = close.ewm(span=12, adjust=False, min_periods=12).mean()
exp2 = close.ewm(span=26, adjust=False, min_periods=26).mean()
macd = exp1 - exp2
macd_signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
macd_hist = (macd - macd_signal).fillna(0)

volume_ma = volume.rolling(window=20, min_periods=20).mean()

ma_golden = (sma_short > sma_long) & (sma_short.shift(1) <= sma_long.shift(1))
ma_death = (sma_short < sma_long) & (sma_short.shift(1) >= sma_long.shift(1))

rsi_buy = rsi < rsi_oversold
rsi_sell = rsi > rsi_overbought

macd_golden = (macd > macd_signal) & (macd.shift(1) <= macd_signal.shift(1))
macd_death = (macd < macd_signal) & (macd.shift(1) >= macd_signal.shift(1))

volume_up = volume > (volume_ma * volume_mult)
trend_up = sma_short > sma_long
trend_down = sma_short < sma_long

raw_buy = (ma_golden | (rsi_buy & trend_up))

if use_macd:
    raw_buy = raw_buy & ((macd > macd_signal) | macd_golden) & (macd_hist > -0.001)

if use_volume:
    raw_buy = raw_buy & volume_up.fillna(False)

raw_sell = ma_death | rsi_sell

if use_macd:
    raw_sell = raw_sell | (macd_death & trend_down)

raw_buy = raw_buy.fillna(False)
raw_sell = raw_sell.fillna(False)

df["buy"] = (raw_buy & (~raw_buy.shift(1).fillna(False))).fillna(False).astype(bool)
df["sell"] = (raw_sell & (~raw_sell.shift(1).fillna(False))).fillna(False).astype(bool)

buy_marks = [low.iloc[i] * 0.995 if bool(df["buy"].iloc[i]) and pd.notna(low.iloc[i]) else None for i in range(len(df))]
sell_marks = [high.iloc[i] * 1.005 if bool(df["sell"].iloc[i]) and pd.notna(high.iloc[i]) else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "SMA Short",
            "data": sma_short.fillna(np.nan).tolist(),
            "color": "#f39c12",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "SMA Long",
            "data": sma_long.fillna(np.nan).tolist(),
            "color": "#3498db",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "RSI",
            "data": rsi.fillna(np.nan).tolist(),
            "color": "#9b59b6",
            "overlay": False,
            "type": "line"
        },
        {
            "name": "MACD",
            "data": macd.fillna(np.nan).tolist(),
            "color": "#2ecc71",
            "overlay": False,
            "type": "line"
        },
        {
            "name": "MACD Signal",
            "data": macd_signal.fillna(np.nan).tolist(),
            "color": "#e74c3c",
            "overlay": False,
            "type": "line"
        }
    ],
    "signals": [
        {
            "type": "buy",
            "text": "BUY",
            "color": "#00c853",
            "data": buy_marks
        },
        {
            "type": "sell",
            "text": "SELL",
            "color": "#ff5252",
            "data": sell_marks
        }
    ],
    "calculatedVars": {
        "sma_short_period": sma_short_period,
        "sma_long_period": sma_long_period,
        "rsi_period": rsi_period,
        "rsi_oversold": rsi_oversold,
        "rsi_overbought": rsi_overbought,
        "use_macd": use_macd,
        "use_volume": use_volume,
        "volume_mult": volume_mult
    }
}
