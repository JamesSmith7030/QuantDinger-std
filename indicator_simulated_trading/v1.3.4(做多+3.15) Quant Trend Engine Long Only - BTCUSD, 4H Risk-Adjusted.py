my_indicator_name = "v1.3.4(做多+3.15) Quant Trend Engine Long Only - BTC/USD, 4H Risk-Adjusted"
my_indicator_description = (
    "Long-only trend strategy with unchanged core logic, retuned for better risk-adjusted returns "
    "via moderately earlier entries, slightly looser trend qualification, and faster protective exits."
)

# @param start_year int 2019 Backtest start year
# @param fast_len int 18 Fast EMA length
# @param mid_len int 50 Mid EMA length
# @param slow_len int 140 Slow EMA length
# @param smooth_len int 5 EMA smoothing length
# @param pullback_len int 10 Pullback lookback bars
# @param breakout_len int 30 Breakout lookback bars
# @param eff_len int 20 Efficiency lookback bars
# @param persist_len int 8 Momentum persistence bars
# @param mom_len int 14 Momentum lookback bars
# @param slope_len int 12 EMA slope lookback bars
# @param atr_len int 14 ATR length
# @param atr_base_len int 48 ATR baseline length
# @param min_score float 5.6 Minimum entry score
# @param exit_score_thresh float 3.5 Weak-trend exit score
# @param min_sep_perc float 0.55 Minimum EMA separation percent
# @param min_slow_slope_perc float 0.05 Minimum slow EMA slope percent
# @param min_eff float 0.46 Minimum path efficiency
# @param min_atr_regime float 0.88 Minimum ATR regime ratio
# @param min_breakout_atr float 0.22 Minimum breakout ATR strength
# @param pullback_atr_mult float 0.95 Pullback distance in ATR
# @param reclaim_atr_mult float 0.12 Reclaim distance in ATR
# @param cooldown_bars int 8 Cooldown bars after exit
# @param hard_stop_perc float 0.75 Hard stop percent
# @param trail_atr_mult float 1.45 ATR trailing multiplier
# @param profit_lock_atr_mult float 4.2 Profit lock ATR multiplier
# @param resample_to_4h bool True Build 4H candles from lower timeframes

# @strategy stopLossPct 0.0075
# @strategy entryPct 0.25
# @strategy tradeDirection long
# @strategy takeProfitPct 0.05
# @strategy trailingEnabled false
# @strategy trailingStopPct 0.011
# @strategy trailingActivationPct 0.005


def _bounded_int(raw_params, name, default, minimum, maximum):
    try:
        value = int(raw_params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


def _bounded_float(raw_params, name, default, minimum, maximum):
    try:
        value = float(raw_params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


def _bounded_bool(raw_params, name, default):
    value = raw_params.get(name, default)
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


def get_strategy_params(raw_params=None):
    raw_params = raw_params or {}
    settings = {
        "start_year": _bounded_int(raw_params, "start_year", 2019, 2000, 2100),
        "fast_len": _bounded_int(raw_params, "fast_len", 18, 2, 200),
        "mid_len": _bounded_int(raw_params, "mid_len", 50, 2, 200),
        "slow_len": _bounded_int(raw_params, "slow_len", 140, 2, 500),
        "smooth_len": _bounded_int(raw_params, "smooth_len", 5, 1, 50),
        "pullback_len": _bounded_int(raw_params, "pullback_len", 10, 1, 100),
        "breakout_len": _bounded_int(raw_params, "breakout_len", 30, 2, 200),
        "eff_len": _bounded_int(raw_params, "eff_len", 20, 2, 200),
        "persist_len": _bounded_int(raw_params, "persist_len", 8, 2, 100),
        "mom_len": _bounded_int(raw_params, "mom_len", 14, 2, 200),
        "slope_len": _bounded_int(raw_params, "slope_len", 12, 2, 100),
        "atr_len": _bounded_int(raw_params, "atr_len", 14, 2, 200),
        "atr_base_len": _bounded_int(raw_params, "atr_base_len", 48, 2, 500),
        "min_score": _bounded_float(raw_params, "min_score", 5.6, 0.0, 10.0),
        "exit_score_thresh": _bounded_float(raw_params, "exit_score_thresh", 3.5, 0.0, 10.0),
        "min_sep_perc": _bounded_float(raw_params, "min_sep_perc", 0.55, 0.01, 5.0),
        "min_slow_slope_perc": _bounded_float(raw_params, "min_slow_slope_perc", 0.05, 0.0, 2.0),
        "min_eff": _bounded_float(raw_params, "min_eff", 0.46, 0.0, 1.0),
        "min_atr_regime": _bounded_float(raw_params, "min_atr_regime", 0.88, 0.1, 5.0),
        "min_breakout_atr": _bounded_float(raw_params, "min_breakout_atr", 0.22, 0.0, 5.0),
        "pullback_atr_mult": _bounded_float(raw_params, "pullback_atr_mult", 0.95, 0.1, 10.0),
        "reclaim_atr_mult": _bounded_float(raw_params, "reclaim_atr_mult", 0.12, 0.0, 5.0),
        "cooldown_bars": _bounded_int(raw_params, "cooldown_bars", 8, 0, 100),
        "hard_stop_perc": _bounded_float(raw_params, "hard_stop_perc", 0.75, 0.1, 20.0),
        "trail_atr_mult": _bounded_float(raw_params, "trail_atr_mult", 1.45, 0.5, 10.0),
        "profit_lock_atr_mult": _bounded_float(raw_params, "profit_lock_atr_mult", 4.2, 0.5, 50.0),
        "resample_to_4h": _bounded_bool(raw_params, "resample_to_4h", True),
    }
    return settings


# 沙箱兼容：实盘沙箱(safe_exec)把 pandas 的 api 子模块列为禁止访问属性，故不能再用
# “pandas api types”里的 is_datetime64_any_dtype / is_numeric_dtype。改用 numpy dtype
# 的 kind 码自判：'M'=datetime64，'i/u/f/b'=整型/无符号/浮点/布尔，等价且不触发校验拒绝。
def _is_datetime_like(obj):
    try:
        return obj.dtype.kind == "M"
    except AttributeError:
        return False


def _is_numeric_like(obj):
    try:
        return obj.dtype.kind in ("i", "u", "f", "b")
    except AttributeError:
        return False


def _ema(series, length):
    return series.astype(float).ewm(span=length, adjust=False).mean()


def _rma(series, length):
    values = series.astype(float).to_numpy()
    result = np.full(len(values), np.nan, dtype=float)
    if len(values) < length or length <= 0:
        return pd.Series(result, index=series.index, dtype="float64")
    seed = np.nanmean(values[:length])
    result[length - 1] = seed
    for i in range(length, len(values)):
        prev = result[i - 1]
        curr = values[i]
        if np.isnan(curr):
            result[i] = prev
        else:
            result[i] = (prev * (length - 1) + curr) / length
    return pd.Series(result, index=series.index, dtype="float64")


def _atr(high, low, close, length):
    prev_close = close.shift(1)
    tr = np.maximum.reduce(
        [
            (high - low).astype(float).to_numpy(),
            (high - prev_close).abs().fillna(0.0).astype(float).to_numpy(),
            (low - prev_close).abs().fillna(0.0).astype(float).to_numpy(),
        ]
    )
    tr_series = pd.Series(tr, index=close.index, dtype="float64")
    return _rma(tr_series, length)


def _safe_divide(numerator, denominator):
    if hasattr(denominator, "replace"):
        denominator = denominator.replace(0, np.nan)
    else:
        denominator = np.where(np.asarray(denominator) == 0, np.nan, denominator)
    out = numerator / denominator
    if hasattr(out, "replace"):
        return out.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    out = np.where(np.isfinite(out), out, np.nan)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def _pct_change(old, new):
    return _safe_divide(new - old, old) * 100.0


def _plot_values(series):
    if isinstance(series, pd.Series):
        return series.replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float).tolist()
    return pd.Series(series).replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(float).tolist()


def _same_index_bool_series(values, index):
    return pd.Series(values, index=index).fillna(False).astype(bool)


def _same_index_float_series(values, index):
    return pd.Series(values, index=index, dtype="float64")


def _allow_trade_series(result_df, start_year):
    if "timestamp" in result_df.columns:
        timestamps = result_df["timestamp"]
    elif "time" in result_df.columns:
        timestamps = result_df["time"]
    else:
        return _same_index_bool_series(np.ones(len(result_df), dtype=bool), result_df.index)

    if _is_datetime_like(timestamps):
        allowed = timestamps.dt.year >= start_year
    elif _is_numeric_like(timestamps):
        numeric_timestamps = pd.to_numeric(timestamps, errors="coerce")
        median_timestamp = numeric_timestamps.dropna().median()
        unit = "ms" if pd.notna(median_timestamp) and abs(float(median_timestamp)) > 100000000000 else "s"
        dt = pd.to_datetime(numeric_timestamps, unit=unit, errors="coerce", utc=True)
        allowed = dt.dt.year >= start_year
        allowed = allowed.fillna(True)
    else:
        years = timestamps.astype(str).str.slice(0, 4)
        numeric_years = pd.to_numeric(years, errors="coerce")
        allowed = (numeric_years >= float(start_year)).fillna(True)
    return allowed.astype(bool)


def _source_timestamp_series(source_df):
    if "timestamp" in source_df.columns:
        raw_timestamps = source_df["timestamp"]
    elif "time" in source_df.columns:
        raw_timestamps = source_df["time"]
    elif _is_datetime_like(source_df.index):
        raw_timestamps = pd.Series(source_df.index, index=source_df.index)
    else:
        return None

    if _is_numeric_like(raw_timestamps):
        numeric_timestamps = pd.to_numeric(raw_timestamps, errors="coerce")
        median_timestamp = numeric_timestamps.dropna().median()
        unit = "ms" if pd.notna(median_timestamp) and abs(float(median_timestamp)) > 100000000000 else "s"
        return pd.to_datetime(numeric_timestamps, unit=unit, errors="coerce", utc=True)
    return pd.to_datetime(raw_timestamps, errors="coerce", utc=True)


def _resample_ohlcv_to_4h(source_df):
    required_columns = {"open", "high", "low", "close"}
    if not required_columns.issubset(set(source_df.columns)):
        return None

    timestamps = _source_timestamp_series(source_df)
    if timestamps is None or timestamps.notna().sum() < 2:
        return None

    working = source_df.copy()
    if "volume" not in working.columns:
        working["volume"] = 0.0
    working["_qte_timestamp"] = timestamps
    working["_qte_source_pos"] = np.arange(len(working))
    working = working.dropna(subset=["_qte_timestamp", "open", "high", "low", "close"])
    working = working.sort_values("_qte_timestamp")

    median_delta = working["_qte_timestamp"].diff().dropna().median()
    if pd.isna(median_delta) or median_delta <= pd.Timedelta(0):
        return None
    if median_delta >= pd.Timedelta(hours=4):
        return None

    working["_qte_4h_bucket"] = working["_qte_timestamp"].dt.floor("4h")
    grouped = working.groupby("_qte_4h_bucket", sort=True)
    resampled = grouped.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "_qte_timestamp": "last",
            "_qte_source_pos": "last",
        }
    )
    resampled["timestamp"] = resampled["_qte_timestamp"]
    return resampled.drop(columns=["_qte_timestamp"]).reset_index(drop=True)


def _map_bool_signal_to_source(signal_values, source_positions, source_index, forward_fill=False):
    raw_values = list(signal_values)
    if forward_fill:
        mapped = pd.Series(np.nan, index=source_index, dtype="object")
        for signal_index, source_position in enumerate(source_positions):
            if 0 <= source_position < len(source_index):
                mapped.iloc[source_position] = bool(raw_values[signal_index])
        return mapped.ffill().fillna(False).astype(bool)

    mapped = pd.Series(False, index=source_index, dtype=bool)
    for signal_index, source_position in enumerate(source_positions):
        if 0 <= source_position < len(source_index):
            mapped.iloc[source_position] = bool(raw_values[signal_index])
    return mapped.astype(bool)


def _map_numeric_signal_to_source(signal_values, source_positions, source_index, forward_fill=False):
    mapped = pd.Series(np.nan, index=source_index, dtype="float64")
    raw_values = list(signal_values)
    for signal_index, source_position in enumerate(source_positions):
        if 0 <= source_position < len(source_index):
            try:
                mapped.iloc[source_position] = float(raw_values[signal_index])
            except (TypeError, ValueError):
                mapped.iloc[source_position] = np.nan
    return mapped.ffill() if forward_fill else mapped


def _simulate_position_state(
    close,
    high,
    low,
    atr,
    allow_trade,
    candidate_long_entry,
    signal_exit,
    settings,
    min_valid_index,
):
    buy = np.zeros(len(close), dtype=bool)
    sell = np.zeros(len(close), dtype=bool)
    in_position = np.zeros(len(close), dtype=bool)
    trail_stop = np.full(len(close), np.nan, dtype=float)

    last_exit_bar = None
    has_position = False
    entry_bar_index = None
    entry_price = None
    high_since_entry = None
    current_trail_stop = None

    for index in range(len(close)):
        close_value = float(close.iloc[index]) if pd.notna(close.iloc[index]) else np.nan
        high_value = float(high.iloc[index]) if pd.notna(high.iloc[index]) else np.nan
        low_value = float(low.iloc[index]) if pd.notna(low.iloc[index]) else np.nan
        atr_value = float(atr.iloc[index]) if pd.notna(atr.iloc[index]) else np.nan

        if index < min_valid_index or np.isnan(close_value) or np.isnan(high_value) or np.isnan(low_value) or np.isnan(atr_value):
            in_position[index] = has_position
            continue

        if has_position:
            high_since_entry = high_value if high_since_entry is None else max(high_since_entry, high_value)
            raw_trail = close_value - atr_value * settings["trail_atr_mult"]
            profit_lock = high_since_entry - atr_value * settings["profit_lock_atr_mult"]
            combined_trail = max(raw_trail, profit_lock)
            current_trail_stop = combined_trail if current_trail_stop is None else max(current_trail_stop, combined_trail)
            trail_stop[index] = current_trail_stop

            can_exit_now = entry_bar_index is not None and index > entry_bar_index
            hard_stop = entry_price * (1.0 - settings["hard_stop_perc"] / 100.0)
            stop_price = max(hard_stop, current_trail_stop)
            risk_exit = low_value <= stop_price

            if can_exit_now and (risk_exit or bool(signal_exit.iloc[index])):
                sell[index] = True
                has_position = False
                last_exit_bar = index
                entry_bar_index = None
                entry_price = None
                high_since_entry = None
                current_trail_stop = None
                in_position[index] = False
                continue

            in_position[index] = True
            continue

        cooldown_ok = last_exit_bar is None or index - last_exit_bar > settings["cooldown_bars"]
        if bool(allow_trade.iloc[index]) and cooldown_ok and bool(candidate_long_entry.iloc[index]):
            buy[index] = True
            has_position = True
            entry_bar_index = index
            entry_price = close_value
            high_since_entry = high_value
            current_trail_stop = close_value - atr_value * settings["trail_atr_mult"]
            in_position[index] = True

    return (
        _same_index_bool_series(buy, close.index),
        _same_index_bool_series(sell, close.index),
        _same_index_float_series(trail_stop, close.index),
        _same_index_bool_series(in_position, close.index),
    )


def _build_strategy_output_direct(source_df, settings):
    result_df = source_df.copy()

    close = result_df["close"].astype(float)
    high = result_df["high"].astype(float)
    low = result_df["low"].astype(float)

    fast_inner = _ema(close, settings["fast_len"])
    fast = _ema(fast_inner, settings["smooth_len"])
    mid_inner = _ema(close, settings["mid_len"])
    mid = _ema(mid_inner, settings["smooth_len"])
    slow_inner = _ema(close, settings["slow_len"])
    slow = _ema(slow_inner, settings["smooth_len"])

    atr = _atr(high, low, close, settings["atr_len"])
    atr_base = atr.rolling(settings["atr_base_len"], min_periods=settings["atr_base_len"]).mean()

    bull_stack = (fast > mid) & (mid > slow)
    sep_perc = _safe_divide((fast - slow).abs(), slow) * 100.0
    sep_ok = sep_perc >= settings["min_sep_perc"]

    fast_slope = _pct_change(fast.shift(settings["slope_len"]), fast)
    mid_slope = _pct_change(mid.shift(settings["slope_len"]), mid)
    slow_slope = _pct_change(slow.shift(settings["slope_len"]), slow)
    slope_ok = (slow_slope >= settings["min_slow_slope_perc"]) & (mid_slope > 0) & (fast_slope > 0)

    net_move = (close - close.shift(settings["eff_len"])).abs()
    step_move = close.diff().abs().rolling(settings["eff_len"], min_periods=settings["eff_len"]).sum()
    efficiency = _safe_divide(net_move, step_move)
    eff_ok = efficiency >= settings["min_eff"]

    up_bar = close > close.shift(1)
    up_bars = up_bar.astype(float).rolling(settings["persist_len"], min_periods=settings["persist_len"]).sum()
    persist_ratio = _safe_divide(up_bars, float(settings["persist_len"]))
    mom_raw = _pct_change(close.shift(settings["mom_len"]), close)
    mom_ok = (mom_raw > 0) & (persist_ratio >= 0.60)

    atr_regime = _safe_divide(atr, atr_base)
    atr_ok = atr_regime >= settings["min_atr_regime"]

    hh = high.rolling(settings["breakout_len"], min_periods=settings["breakout_len"]).max().shift(1)
    breakout_dist = close - hh
    breakout_strength = _safe_divide(breakout_dist, atr)
    breakout_ok = (close > hh) & (breakout_strength >= settings["min_breakout_atr"])

    pullback_low = low.rolling(settings["pullback_len"], min_periods=settings["pullback_len"]).min()
    dist_from_fast_atr = _safe_divide(fast - pullback_low, atr)
    deep_enough_pullback = dist_from_fast_atr >= settings["pullback_atr_mult"]

    reclaim_fast = (close > fast) & (close.shift(1) <= fast.shift(1))
    reclaim_mid = (close > mid) & (close.shift(1) <= mid.shift(1))
    reclaim_strength = _safe_divide(close - fast, atr)
    reclaim_ok = (reclaim_fast | reclaim_mid) & (reclaim_strength >= settings["reclaim_atr_mult"])

    bull_cross = (
        ((fast > mid) & (fast.shift(1) <= mid.shift(1)))
        | ((fast > slow) & (fast.shift(1) <= slow.shift(1)))
        | ((mid > slow) & (mid.shift(1) <= slow.shift(1)))
    )
    recent_trend_birth = bull_cross.astype(float).rolling(15, min_periods=1).max().fillna(0).astype(bool)

    trend_score = (
        bull_stack.astype(float) * 1.50
        + sep_ok.astype(float) * 0.90
        + slope_ok.astype(float) * 1.10
        + eff_ok.astype(float) * 1.00
        + atr_ok.astype(float) * 0.80
        + mom_ok.astype(float) * 1.00
        + breakout_ok.astype(float) * 1.25
        + reclaim_ok.astype(float) * 1.10
    )

    trend_continuation_entry = bull_stack & breakout_ok & slope_ok & eff_ok & mom_ok
    pullback_reentry = bull_stack & sep_ok & slope_ok & deep_enough_pullback & reclaim_ok & eff_ok
    early_trend_entry = recent_trend_birth & bull_stack & sep_ok & slope_ok & atr_ok & mom_ok

    raw_candidate_long_entry = (
        (trend_score >= settings["min_score"])
        & (close > slow)
        & (trend_continuation_entry | pullback_reentry | early_trend_entry)
    ).fillna(False)

    raw_candidate_long_entry = raw_candidate_long_entry.fillna(False)
    candidate_long_entry = raw_candidate_long_entry & (~raw_candidate_long_entry.shift(1).fillna(False))

    bear_cross = ((fast < mid) & (fast.shift(1) >= mid.shift(1))) | ((fast < slow) & (fast.shift(1) >= slow.shift(1)))
    structure_break = (close < mid) & (fast < mid)
    score_weak = trend_score <= settings["exit_score_thresh"]
    momentum_failure = (persist_ratio < 0.45) & (mom_raw < 0)
    regime_failure = (atr_regime < 0.85) & (efficiency < 0.30)
    raw_signal_exit = (bear_cross | structure_break | score_weak | momentum_failure | regime_failure).fillna(False)
    signal_exit = raw_signal_exit & (~raw_signal_exit.shift(1).fillna(False))

    allow_trade = _allow_trade_series(result_df, settings["start_year"])
    min_valid_index = settings["slow_len"] + settings["smooth_len"] + settings["slope_len"] + settings["atr_base_len"]

    buy, sell, trail_stop, in_position = _simulate_position_state(
        close=close,
        high=high,
        low=low,
        atr=atr,
        allow_trade=allow_trade,
        candidate_long_entry=candidate_long_entry,
        signal_exit=signal_exit,
        settings=settings,
        min_valid_index=min_valid_index,
    )

    result_df["buy"] = buy.fillna(False).astype(bool)
    result_df["sell"] = sell.fillna(False).astype(bool)
    result_df["qte_trend_score"] = trend_score.fillna(0.0).astype(float)
    result_df["qte_trail_stop"] = trail_stop.astype(float)
    result_df["qte_in_position"] = in_position.fillna(False).astype(bool)

    buy_marks = [float(low.iloc[i]) * 0.995 if bool(result_df["buy"].iloc[i]) else None for i in range(len(result_df))]
    sell_marks = [float(high.iloc[i]) * 1.005 if bool(result_df["sell"].iloc[i]) else None for i in range(len(result_df))]

    output = {
        "name": my_indicator_name,
        "plots": [
            {"name": "EMA Fast", "data": _plot_values(fast), "color": "#1890ff", "overlay": True, "type": "line"},
            {"name": "EMA Mid", "data": _plot_values(mid), "color": "#faad14", "overlay": True, "type": "line"},
            {"name": "EMA Slow", "data": _plot_values(slow), "color": "#722ed1", "overlay": True, "type": "line"},
            {"name": "ATR Trail Stop", "data": _plot_values(trail_stop), "color": "#f5222d", "overlay": True, "type": "line"},
            {"name": "Trend Score", "data": _plot_values(trend_score), "color": "#13c2c2", "overlay": False, "type": "line"},
        ],
        "signals": [
            {"type": "buy", "text": "B", "data": buy_marks, "color": "#00E676"},
            {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"},
        ],
        "calculatedVars": {
            "description": my_indicator_description,
            "entry_model": "trend continuation / pullback reclaim / early trend birth",
            "exit_model": "hard stop / ATR trail / weak trend signal",
            "optimization_bias": "more opportunities, lower threshold, tighter risk control",
        },
    }

    return result_df, output


def _map_4h_output_to_source(source_df, signal_df, signal_output):
    result_df = source_df.copy()
    source_positions = signal_df["_qte_source_pos"].astype(int).to_numpy()

    result_df["buy"] = _map_bool_signal_to_source(signal_df["buy"], source_positions, result_df.index).fillna(False).astype(bool)
    result_df["sell"] = _map_bool_signal_to_source(signal_df["sell"], source_positions, result_df.index).fillna(False).astype(bool)
    result_df["qte_trend_score"] = _map_numeric_signal_to_source(
        signal_df["qte_trend_score"], source_positions, result_df.index, forward_fill=True
    ).fillna(0.0)
    result_df["qte_trail_stop"] = _map_numeric_signal_to_source(
        signal_df["qte_trail_stop"], source_positions, result_df.index, forward_fill=True
    )
    result_df["qte_in_position"] = _map_bool_signal_to_source(
        signal_df["qte_in_position"], source_positions, result_df.index, forward_fill=True
    ).fillna(False).astype(bool)

    low = result_df["low"].astype(float)
    high = result_df["high"].astype(float)
    buy_marks = [float(low.iloc[i]) * 0.995 if bool(result_df["buy"].iloc[i]) else None for i in range(len(result_df))]
    sell_marks = [float(high.iloc[i]) * 1.005 if bool(result_df["sell"].iloc[i]) else None for i in range(len(result_df))]

    mapped_plots = []
    for plot in signal_output["plots"]:
        mapped_series = _map_numeric_signal_to_source(plot["data"], source_positions, result_df.index, forward_fill=True).fillna(0.0)
        mapped_plot = dict(plot)
        mapped_plot["data"] = mapped_series.astype(float).tolist()
        mapped_plots.append(mapped_plot)

    calculated_vars = dict(signal_output.get("calculatedVars", {}))
    calculated_vars["timeframe_handling"] = "lower timeframe OHLCV resampled to 4H"

    output = {
        "name": signal_output["name"],
        "plots": mapped_plots,
        "signals": [
            {"type": "buy", "text": "B", "data": buy_marks, "color": "#00E676"},
            {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"},
        ],
        "calculatedVars": calculated_vars,
    }
    return result_df, output


def build_strategy_output(source_df, raw_params=None):
    settings = get_strategy_params(raw_params)
    original_df = source_df.copy()

    if settings["resample_to_4h"]:
        four_hour_df = _resample_ohlcv_to_4h(original_df)
        if four_hour_df is not None and len(four_hour_df) > 0:
            signal_df, signal_output = _build_strategy_output_direct(four_hour_df, settings)
            return _map_4h_output_to_source(original_df, signal_df, signal_output)

    return _build_strategy_output_direct(original_df, settings)


try:
    active_params = params
except NameError:
    active_params = {}

_ = active_params.get("start_year", 2019)
_ = active_params.get("fast_len", 18)
_ = active_params.get("mid_len", 50)
_ = active_params.get("slow_len", 140)
_ = active_params.get("smooth_len", 5)
_ = active_params.get("pullback_len", 10)
_ = active_params.get("breakout_len", 30)
_ = active_params.get("eff_len", 20)
_ = active_params.get("persist_len", 8)
_ = active_params.get("mom_len", 14)
_ = active_params.get("slope_len", 12)
_ = active_params.get("atr_len", 14)
_ = active_params.get("atr_base_len", 48)
_ = active_params.get("min_score", 5.6)
_ = active_params.get("exit_score_thresh", 3.5)
_ = active_params.get("min_sep_perc", 0.55)
_ = active_params.get("min_slow_slope_perc", 0.05)
_ = active_params.get("min_eff", 0.46)
_ = active_params.get("min_atr_regime", 0.88)
_ = active_params.get("min_breakout_atr", 0.22)
_ = active_params.get("pullback_atr_mult", 0.95)
_ = active_params.get("reclaim_atr_mult", 0.12)
_ = active_params.get("cooldown_bars", 8)
_ = active_params.get("hard_stop_perc", 0.75)
_ = active_params.get("trail_atr_mult", 1.45)
_ = active_params.get("profit_lock_atr_mult", 4.2)
_ = active_params.get("resample_to_4h", True)

try:
    df = df.copy()
    df, output = build_strategy_output(df, active_params)
    df["buy"] = df["buy"].fillna(False).astype(bool)
    df["sell"] = df["sell"].fillna(False).astype(bool)
except NameError:
    output = {"name": my_indicator_name, "plots": [], "signals": [], "calculatedVars": {}}
