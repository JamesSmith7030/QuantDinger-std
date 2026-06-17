my_indicator_name = "v2.0.5(ETH4H双+253.20)-30f-双均线策略"
my_indicator_description = "优化参数版双均线交叉策略：短期25/长期40均线，降低过度交易并改善风险调整收益"
# 回测参数（开单参数） 标的：ETH  K 线周期：4H  日期范围：3Y  杠杆：3x  交易方向：双向

# @param sma_short int 25 短期均线周期
# @param sma_long int 40 长期均线周期

# exit_owner: engine  （引擎统一管 SL/TP/trailing；buy/sell 仅作双向反手触发，避免与指标平仓双重平仓）
# @strategy stopLossPct 0.018
# @strategy takeProfitPct 0.018
# @strategy entryPct 0.3419
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.01
# @strategy trailingActivationPct 0.008
# @strategy tradeDirection both

# 回退默认对齐声明/描述的 25/40（原为 8/34，与 @param 和回测口径不符，会导致漏传参时跑成另一套策略）
sma_short_period = int(params.get('sma_short', 25))
sma_long_period = int(params.get('sma_long', 40))

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

# 金叉/死叉本身就是单根边缘事件，无需再做 ~shift(1) 去重；
# 且原写法 ~raw.shift(1).fillna(False) 在 pandas 3.x 下 bool 经 shift 变 object，
# ~ 会得到 -1/-2 整数而非布尔（项目已知坑），故直接 astype(bool) 取交叉信号。
raw_buy = (sma_short > sma_long) & (sma_short.shift(1) <= sma_long.shift(1))
raw_sell = (sma_short < sma_long) & (sma_short.shift(1) >= sma_long.shift(1))

df["buy"] = raw_buy.fillna(False).astype(bool)
df["sell"] = raw_sell.fillna(False).astype(bool)

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
