my_indicator_name = "ETH/USDT Short-Term Contract RSI Mean Reversion Strategy v5"
my_indicator_description = "ETH/USDT合约短线均值回归优化参数版：保持RSI+成交量+波动率过滤逻辑，通过更平衡的RSI阈值、更稳健的波动率与趋势过滤、适度放宽量能确认来改善风险调整后表现。"
# @strategy tradeDirection both
# @strategy entryPct 0.10
# @strategy stopLossPct 0.006
# @strategy takeProfitPct 0.014
# @strategy trailingEnabled false
# @strategy trailingStopPct 0.01
# @strategy trailingActivationPct 0.008
# @param rsi_period int 11 RSI period
# @param overbought float 68 RSI overbought threshold
# @param oversold float 32 RSI oversold threshold
# @param atr_period int 16 ATR period
# @param max_volatility_ratio float 0.013 Maximum ATR/close ratio
# @param volume_ma_period int 20 Volume MA period
# @param volume_multiplier float 0.95 Volume confirmation multiplier
# @param ema_short_period int 12 Short EMA period
# @param ema_long_period int 40 Long EMA period
# @param fallback_buy_buffer float 5 Relaxed buy threshold buffer
# @param fallback_sell_buffer float 5 Relaxed sell threshold buffer

df = df.copy()

rsi_period = int(params.get("rsi_period", 11))
overbought = float(params.get("overbought", 68))
oversold = float(params.get("oversold", 32))
atr_period = int(params.get("atr_period", 16))
max_volatility_ratio = float(params.get("max_volatility_ratio", 0.013))
volume_ma_period = int(params.get("volume_ma_period", 20))
volume_multiplier = float(params.get("volume_multiplier", 0.95))
ema_short_period = int(params.get("ema_short_period", 12))
ema_long_period = int(params.get("ema_long_period", 40))
fallback_buy_buffer = float(params.get("fallback_buy_buffer", 5))
fallback_sell_buffer = float(params.get("fallback_sell_buffer", 5))

if df is None or len(df) == 0:
    df["buy"] = pd.Series(dtype=bool)
    df["sell"] = pd.Series(dtype=bool)
    output = {
        "name": my_indicator_name,
        "plots": [],
        "signals": [],
        "calculatedVars": {}
    }
else:
    close = pd.to_numeric(df.get("close"), errors="coerce")
    high = pd.to_numeric(df.get("high"), errors="coerce")
    low = pd.to_numeric(df.get("low"), errors="coerce")
    volume = pd.to_numeric(df.get("volume"), errors="coerce")

    def calculate_atr(high_s, low_s, close_s, period):
        period = max(int(period), 1)
        prev_close = close_s.shift(1)
        high_low = high_s - low_s
        high_close = (high_s - prev_close).abs()
        low_close = (low_s - prev_close).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    def calculate_rsi(series, period):
        period = max(int(period), 1)
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta.clip(upper=0))
        avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi_val = 100 - (100 / (1 + rs))
        return rsi_val.fillna(50.0)

    atr = calculate_atr(high, low, close, atr_period)
    volume_ma = volume.rolling(window=max(volume_ma_period, 1), min_periods=1).mean()
    rsi = calculate_rsi(close, rsi_period)

    ema_short = close.ewm(span=max(ema_short_period, 1), adjust=False, min_periods=1).mean()
    ema_long = close.ewm(span=max(ema_long_period, 1), adjust=False, min_periods=1).mean()
    trend_up = (ema_short > ema_long).fillna(False)
    trend_down = (ema_short < ema_long).fillna(False)

    volatility_ratio = (atr / close.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    volatility_filter = (volatility_ratio < max_volatility_ratio).fillna(False)
    volume_confirm = (volume > (volume_ma * volume_multiplier)).fillna(False)

    raw_buy = ((rsi < oversold) & trend_up & volatility_filter & volume_confirm).fillna(False)
    raw_sell = ((rsi > overbought) & trend_down & volatility_filter & volume_confirm).fillna(False)

    buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
    sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))

    if not bool(buy.any()):
        relaxed_raw_buy = (
            (rsi < (oversold + fallback_buy_buffer)) &
            volatility_filter &
            volume_confirm &
            (trend_up | (rsi < oversold))
        ).fillna(False)
        buy = relaxed_raw_buy.fillna(False) & (~relaxed_raw_buy.shift(1).fillna(False))

    if not bool(sell.any()):
        relaxed_raw_sell = (
            (rsi > (overbought - fallback_sell_buffer)) &
            volatility_filter &
            volume_confirm &
            (trend_down | (rsi > overbought))
        ).fillna(False)
        sell = relaxed_raw_sell.fillna(False) & (~relaxed_raw_sell.shift(1).fillna(False))

    if not bool(buy.any()) and len(df) > 2:
        fallback_raw_buy2 = (
            (rsi < (oversold + fallback_buy_buffer)) &
            volatility_filter &
            trend_up
        ).fillna(False)
        buy = fallback_raw_buy2.fillna(False) & (~fallback_raw_buy2.shift(1).fillna(False))

    if not bool(sell.any()) and len(df) > 2:
        fallback_raw_sell2 = (
            (rsi > (overbought - fallback_sell_buffer)) &
            volatility_filter &
            trend_down
        ).fillna(False)
        sell = fallback_raw_sell2.fillna(False) & (~fallback_raw_sell2.shift(1).fillna(False))

    df["atr"] = atr
    df["volume_ma"] = volume_ma
    df["buy"] = buy.fillna(False).astype(bool)
    df["sell"] = sell.fillna(False).astype(bool)

    rsi_list = rsi.fillna(50.0).astype(float).tolist()
    overbought_line = [float(overbought)] * len(df)
    oversold_line = [float(oversold)] * len(df)
    ema_short_list = ema_short.ffill().bfill().fillna(0.0).astype(float).tolist()
    ema_long_list = ema_long.ffill().bfill().fillna(0.0).astype(float).tolist()
    atr_list = atr.fillna(0.0).astype(float).tolist()

    buy_marks = []
    sell_marks = []
    for i in range(len(df)):
        if bool(df["buy"].iloc[i]):
            if pd.notna(low.iloc[i]):
                buy_marks.append(float(low.iloc[i]) * 0.998)
            elif pd.notna(close.iloc[i]):
                buy_marks.append(float(close.iloc[i]) * 0.998)
            else:
                buy_marks.append(None)
        else:
            buy_marks.append(None)

        if bool(df["sell"].iloc[i]):
            if pd.notna(high.iloc[i]):
                sell_marks.append(float(high.iloc[i]) * 1.002)
            elif pd.notna(close.iloc[i]):
                sell_marks.append(float(close.iloc[i]) * 1.002)
            else:
                sell_marks.append(None)
        else:
            sell_marks.append(None)

    output = {
        "name": my_indicator_name,
        "plots": [
            {"name": "RSI(" + str(rsi_period) + ")", "data": rsi_list, "color": "#9C27B0", "overlay": False, "type": "line"},
            {"name": "Overbought", "data": overbought_line, "color": "#FF5252", "overlay": False, "type": "line"},
            {"name": "Oversold", "data": oversold_line, "color": "#00E676", "overlay": False, "type": "line"},
            {"name": "EMA(" + str(ema_short_period) + ")", "data": ema_short_list, "color": "#2196F3", "overlay": True, "type": "line"},
            {"name": "EMA(" + str(ema_long_period) + ")", "data": ema_long_list, "color": "#FF9800", "overlay": True, "type": "line"},
            {"name": "ATR(" + str(atr_period) + ")", "data": atr_list, "color": "#795548", "overlay": False, "type": "line"}
        ],
        "signals": [
            {"type": "buy", "text": "B", "data": buy_marks, "color": "#00E676"},
            {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"}
        ],
        "calculatedVars": {
            "volatility_ratio": volatility_ratio.fillna(0.0).astype(float).tolist(),
            "volume_confirmation": volume_confirm.fillna(False).astype(bool).tolist(),
            "trend_direction": trend_up.fillna(False).astype(bool).tolist()
        }
    }
