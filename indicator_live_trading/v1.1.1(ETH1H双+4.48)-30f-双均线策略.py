my_indicator_name = "v1.1.1(ETH1H双+4.48)-30f-双均线策略"
my_indicator_description = "优化参数版双均线交叉策略：短期8/长期34均线，降低过度交易并改善风险调整收益"

# 实盘开单参数 标的: ETH, K线周期: 1H, 杠杆: 5x, 交易方向: 双向, +AI 决策

# @param sma_short int 6 短期均线周期
# @param sma_long int 24 长期均线周期

# @strategy stopLossPct 0.012
# @strategy takeProfitPct 0.024
# @strategy entryPct 0.35
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.008
# @strategy trailingActivationPct 0.012
# @strategy tradeDirection both

sma_short_period = int(params.get('sma_short', 8))
sma_long_period = int(params.get('sma_long', 34))

if sma_short_period < 1:
    sma_short_period = 1
if sma_long_period < 2:
    sma_long_period = 2
if sma_short_period >= sma_long_period:
    sma_long_period = sma_short_period + 1

df = df.copy()

close = pd.to_numeric(df["close"], errors="coerce")
low = pd.to_numeric(df["low"], errors="coerce")
high = pd.to_numeric(df["high"], errors="coerce")

sma_short = close.rolling(window=sma_short_period, min_periods=sma_short_period).mean()
sma_long = close.rolling(window=sma_long_period, min_periods=sma_long_period).mean()

raw_buy = (sma_short > sma_long) & (sma_short.shift(1) <= sma_long.shift(1))
raw_sell = (sma_short < sma_long) & (sma_short.shift(1) >= sma_long.shift(1))

buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))

df["buy"] = buy.fillna(False).astype(bool)
df["sell"] = sell.fillna(False).astype(bool)

buy_marks = [low.iloc[i] * 0.995 if bool(df["buy"].iloc[i]) and pd.notna(low.iloc[i]) else None for i in range(len(df))]
sell_marks = [high.iloc[i] * 1.005 if bool(df["sell"].iloc[i]) and pd.notna(high.iloc[i]) else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": f"SMA{sma_short_period}",
            "data": sma_short.tolist(),
            "color": "#FF9800",
            "overlay": True,
            "type": "line"
        },
        {
            "name": f"SMA{sma_long_period}",
            "data": sma_long.tolist(),
            "color": "#3F51B5",
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
    ],
    "calculatedVars": {}
}
