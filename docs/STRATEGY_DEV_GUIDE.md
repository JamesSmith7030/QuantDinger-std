# QuantDinger v3 Python Strategy Development Guide

This guide is written from a **developer** point of view. Its goal is not only to list the current contracts, but to answer the practical question:

**How do I build an indicator strategy that is clear, backtestable, and ready to become a saved trading strategy?**

QuantDinger currently supports two Python authoring models:

- **IndicatorStrategy**: dataframe-based code for indicator research, chart rendering, and signal-style backtests.
- **ScriptStrategy**: event-driven code for runtime execution, strategy backtests, and live trading.

If you are starting a new strategy, the default recommendation is:

1. Start with `IndicatorStrategy`.
2. Prove the signal logic visually and in backtests.
3. Move to `ScriptStrategy` only if you need bar-by-bar state, dynamic position management, or execution control.

---

## 1. Start With the Right Mental Model

The most common source of confusion is mixing up **signal logic**, **risk defaults**, and **runtime execution**.

### 1.1 IndicatorStrategy

Think of `IndicatorStrategy` as:

- compute indicator series from `df`
- generate boolean `buy` / `sell` signals
- declare default strategy settings through metadata comments
- return chart-friendly `output`

This is the best fit for:

- indicator research
- strategy prototyping
- parameter tuning
- signal-based backtests
- saved strategies that still follow a signal-first workflow

### 1.2 ScriptStrategy

Think of `ScriptStrategy` as:

- maintain runtime logic bar by bar
- inspect current position state through `ctx.position`
- place explicit actions with `ctx.buy()`, `ctx.sell()`, and `ctx.close_position()`
- manage exits and sizing in code when needed

This is the best fit for:

- stateful execution logic
- dynamic stop-loss or take-profit handling
- partial exits, scale-ins, cooldowns, or other runtime rules
- strategies that behave more like trading bots than pure indicators

### 1.3 The Most Important Separation

For `IndicatorStrategy`, you usually have **three layers**:

1. **Indicator layer**: moving averages, RSI, ATR, bands, filters.
2. **Signal layer**: `df['buy']` and `df['sell']`.
3. **Risk defaults layer**: `# @strategy stopLossPct ...`, `takeProfitPct`, `entryPct`, and related defaults.

Do not mix these into one thing.

In particular:

- `buy` / `sell` decide **when the strategy wants to enter or exit**
- `# @strategy` decides **how the engine should size and protect positions by default**
- leverage belongs in product configuration, not in indicator code

---

## 2. Which Mode Should You Use?

| Use Case | Recommended Mode |
|----------|------------------|
| Build indicators, overlays, and signal markers | `IndicatorStrategy` |
| Research entry and exit rules on a dataframe | `IndicatorStrategy` |
| Add fixed stop-loss, take-profit, or entry sizing defaults | `IndicatorStrategy` |
| Need runtime position state and bar-by-bar control | `ScriptStrategy` |
| Need dynamic exits based on current open position | `ScriptStrategy` |
| Need partial close, scale-in/out, or bot-like logic | `ScriptStrategy` |

Rule of thumb:

- If your logic can be described as "when condition A happens, buy; when condition B happens, sell", start with `IndicatorStrategy`.
- If your logic sounds like "after entry, keep watching the open position and react differently depending on state", you probably need `ScriptStrategy`.

---

## 3. How To Develop an IndicatorStrategy

This is the recommended workflow for most new strategy development.

### 3.1 Step 1: Declare metadata and defaults first

At the top of the script, define name, description, tunable params, and strategy defaults.

```python
my_indicator_name = "Trend Pullback Strategy"
my_indicator_description = "Buy pullbacks in an uptrend and exit on weakness."

# @param fast_len int 20 Fast EMA length
# @param slow_len int 50 Slow EMA length
# @param rsi_len int 14 RSI length
# @param rsi_floor float 45 Minimum RSI for long entries

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.25
# @strategy trailingEnabled true
# @strategy trailingStopPct 0.02
# @strategy trailingActivationPct 0.04
# @strategy tradeDirection long
```

Use `# @param` for values the user may tune often.

Use `# @strategy` for strategy defaults such as:

- `stopLossPct`: stop-loss ratio, for example `0.03` = 3%
- `takeProfitPct`: take-profit ratio, for example `0.06` = 6%
- `entryPct`: fraction of capital to allocate on entry
- `trailingEnabled`
- `trailingStopPct`
- `trailingActivationPct`
- `tradeDirection`: `long`, `short`, or `both`

Important:

- These are **defaults consumed by the engine**.
- They are not extra dataframe columns.
- Do not put `leverage` here.

### 3.2 Step 2: Copy the dataframe and compute indicators

Indicator code runs in a sandbox. `pd` and `np` are already available.

Recommended baseline:

```python
df = df.copy()
```

Expected columns usually include:

- `open`
- `high`
- `low`
- `close`
- `volume`

A `time` column may exist, but do not rely on a fixed type.

Avoid:

- network access
- file I/O
- subprocesses
- unsafe metaprogramming such as `eval`, `exec`, `open`, or `__import__`

### 3.3 Step 3: Turn raw conditions into clean `buy` / `sell` signals

The backtest engine reads **boolean** columns:

- `df['buy']`
- `df['sell']`

They should:

- match the dataframe length exactly
- be boolean after `fillna(False)`
- usually be edge-triggered, unless repeated signals are intentional

Recommended pattern:

```python
raw_buy = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
raw_sell = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

df['buy'] = (raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))).astype(bool)
df['sell'] = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)
```

This keeps your signals from firing on every bar of the same regime.

### 3.4 Step 4: Decide who owns the exit logic

This is where stop-loss, take-profit, and position management usually become confusing.

There are **two valid exit styles** in `IndicatorStrategy`.

#### Style A: Signal-managed exits

Your indicator logic itself decides when to exit by setting `df['sell']`.

Examples:

- moving-average bearish crossover
- RSI falling below a threshold
- close dropping below an ATR-based stop line
- mean reversion target hit

Use this style when the exit is part of the strategy idea itself.

#### Style B: Engine-managed exits

You let the strategy engine apply fixed defaults declared with `# @strategy`, such as:

- `stopLossPct`
- `takeProfitPct`
- `entryPct`
- trailing settings

Use this style when the signal logic should stay simple, and you want the engine to handle fixed protective rules.

#### Best practice

Pick one primary owner for exits whenever possible.

For example:

- if your edge is "enter on crossover, exit on reverse crossover", keep that in `buy` / `sell`
- if your edge is "enter on signal and let a fixed 3% stop + 6% target manage the trade", use `# @strategy`

You *can* combine them, but document it clearly so other developers know whether an exit is signal-driven, engine-driven, or both.

### 3.5 Step 5: Build the `output` object

Your script must assign a final `output` dictionary:

```python
output = {
    "name": "My Strategy",
    "plots": [],
    "signals": []
}
```

Supported keys:

- `name`
- `plots`
- `signals`
- `calculatedVars` as optional metadata

Each plot item should contain:

- `name`
- `data` with length exactly `len(df)`
- `color`
- `overlay`
- optional `type`

Each signal item should contain:

- `type`: `buy` or `sell`
- `text`
- `color`
- `data`: list with `None` on bars without a marker

### 3.6 Step 6: Validate backtest semantics

Indicator backtests are signal-driven:

- the engine reads `df['buy']` and `df['sell']`
- signals are treated as bar-close confirmation
- fills are typically on the **next bar open**

This matters because:

- an intrabar-looking stop drawn on the current candle is not the same as a next-bar-open fill
- using `shift(-1)` in signal logic introduces look-ahead bias

---

## 4. How To Write Stop-Loss, Take-Profit, and Position Sizing

This section is the practical answer to the most common implementation question.

### 4.1 Fixed stop-loss, take-profit, and entry sizing in IndicatorStrategy

If you want fixed risk defaults, write them as `# @strategy` lines:

```python
# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.25
# @strategy tradeDirection long
```

Meaning:

- `stopLossPct 0.03`: use a 3% stop-loss default
- `takeProfitPct 0.06`: use a 6% take-profit default
- `entryPct 0.25`: allocate 25% of capital on entry
- `tradeDirection long`: long-only by default

This is the correct choice when you want:

- simple signal code
- consistent defaults in backtests
- strategy settings that the UI and engine can understand directly

### 4.2 Indicator-driven exits in IndicatorStrategy

If your "stop-loss" is actually part of the indicator model, write it as a `sell` signal.

Example: exit a long when close falls below an ATR-style stop line.

```python
atr = (df['high'] - df['low']).rolling(14).mean()
stop_line = df['close'].rolling(20).max() - atr * 2.0

raw_sell = df['close'] < stop_line.shift(1)
df['sell'] = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)
```

In this style:

- the exit belongs to your indicator logic
- the engine is not inventing the stop for you
- you should explain this in the strategy description or comments

### 4.3 How position management works in IndicatorStrategy

For indicator strategies, position management is intentionally simple:

- use `entryPct` for default entry sizing
- use `tradeDirection` to limit long, short, or both
- use engine-managed stop, take-profit, or trailing defaults if they are fixed

If you need:

- scale-in / scale-out
- partial exits
- different logic before and after entry
- stop movement that depends on the current live position state
- cooldowns after a stop

then the strategy has outgrown `IndicatorStrategy` and should move to `ScriptStrategy`.

---

## 5. Full IndicatorStrategy Example

This example shows a complete developer-oriented pattern: metadata, defaults, indicator calculation, signal generation, and chart output.

```python
my_indicator_name = "EMA Pullback Strategy"
my_indicator_description = "Buy pullbacks above the slow EMA and exit on trend failure."

# @param fast_len int 20 Fast EMA length
# @param slow_len int 50 Slow EMA length
# @param rsi_len int 14 RSI length
# @param rsi_floor float 50 Minimum RSI for entry

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.25
# @strategy tradeDirection long

df = df.copy()

fast_len = 20
slow_len = 50
rsi_len = 14
rsi_floor = 50.0

ema_fast = df['close'].ewm(span=fast_len, adjust=False).mean()
ema_slow = df['close'].ewm(span=slow_len, adjust=False).mean()

delta = df['close'].diff()
gain = delta.clip(lower=0).ewm(alpha=1 / rsi_len, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_len, adjust=False).mean()
rs = gain / loss.replace(0, np.nan)
rsi = 100 - (100 / (1 + rs))

trend_up = ema_fast > ema_slow
pullback_done = df['close'] > ema_fast
rsi_ok = rsi > rsi_floor

raw_buy = trend_up & pullback_done & rsi_ok & (~trend_up.shift(1).fillna(False))
raw_sell = (ema_fast < ema_slow) | (rsi < 45)

buy = (raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))).astype(bool)
sell = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)

df['buy'] = buy
df['sell'] = sell

buy_marks = [df['low'].iloc[i] * 0.995 if buy.iloc[i] else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if sell.iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "EMA Fast",
            "data": ema_fast.fillna(0).tolist(),
            "color": "#1890ff",
            "overlay": True
        },
        {
            "name": "EMA Slow",
            "data": ema_slow.fillna(0).tolist(),
            "color": "#faad14",
            "overlay": True
        },
        {
            "name": "RSI",
            "data": rsi.fillna(0).tolist(),
            "color": "#722ed1",
            "overlay": False
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
    ]
}
```

What this example teaches:

- indicators are computed first
- entries and exits are expressed as boolean signals
- fixed risk defaults are declared separately through `# @strategy`
- chart output is treated as a final rendering step, not mixed into signal logic

---

## 6. When You Should Switch to ScriptStrategy

Move to `ScriptStrategy` when the strategy needs runtime state rather than pure dataframe signals.

Typical triggers:

- the stop-loss depends on the current open position rather than only on historical series
- you want to adjust stops after entry
- you need partial close or pyramiding
- you want different logic for first entry versus re-entry
- you need cooldown logic, execution throttling, or bot-style workflows

### 6.1 Required functions

Current product-facing verification expects:

- `def on_init(ctx): ...`
- `def on_bar(ctx, bar): ...`

Even if some internal runtime paths can tolerate a missing `on_init`, you should define both.

### 6.2 Available objects

`bar` typically exposes:

- `bar.open`
- `bar.high`
- `bar.low`
- `bar.close`
- `bar.volume`
- `bar.timestamp`

`ctx` currently exposes:

- `ctx.param(name, default=None)`
- `ctx.bars(n=1)`
- `ctx.position`
- `ctx.balance`
- `ctx.equity`
- `ctx.log(message)`
- `ctx.buy(price=None, amount=None)`
- `ctx.sell(price=None, amount=None)`
- `ctx.close_position()`

`ctx.position` supports both numeric checks and field access patterns such as:

```python
if not ctx.position:
    ...

if ctx.position > 0:
    ...

if ctx.position["side"] == "long":
    ...
```

### 6.3 Script example with runtime exits

```python
def on_init(ctx):
    ctx.log("strategy initialized")


def on_bar(ctx, bar):
    stop_loss_pct = ctx.param("stop_loss_pct", 0.03)
    take_profit_pct = ctx.param("take_profit_pct", 0.06)
    order_amount = ctx.param("order_amount", 1)

    bars = ctx.bars(30)
    if len(bars) < 20:
        return

    closes = [b.close for b in bars]
    ma_fast = sum(closes[-10:]) / 10
    ma_slow = sum(closes[-20:]) / 20

    if not ctx.position and ma_fast > ma_slow:
        ctx.buy(price=bar.close, amount=order_amount)
        return

    if not ctx.position:
        return

    if ctx.position["side"] != "long":
        return

    entry_price = ctx.position["entry_price"]

    if bar.close <= entry_price * (1 - stop_loss_pct):
        ctx.close_position()
        return

    if bar.close >= entry_price * (1 + take_profit_pct):
        ctx.close_position()
        return

    if ma_fast < ma_slow:
        ctx.close_position()
```

Use this style when stop-loss and take-profit truly belong to runtime position management instead of pure indicator output.

---

## 7. Backtesting, Persistence, and Current Limits

Saved strategies are resolved by the backend into a normalized snapshot for backtesting and execution. Common fields include:

- `strategy_type`
- `strategy_mode`
- `strategy_code`
- `indicator_config`
- `trading_config`

Current run types include:

- `indicator`
- `strategy_indicator`
- `strategy_script`

Current limitations:

- cross-sectional strategies are not fully supported in the current strategy snapshot flow
- `ScriptStrategy` does not support `cross_sectional` live execution mode
- strategy backtests expect a valid symbol and non-empty code

---

## 8. Best Practices

### 8.1 Avoid look-ahead bias

- use completed-bar information only
- prefer `shift(1)` for confirmation
- do not use `shift(-1)` in signal logic

### 8.2 Handle NaNs explicitly

Rolling and EWM calculations create leading NaNs. Clean them before signal generation.

### 8.3 Keep all series aligned

Every `plot['data']` and `signal['data']` list must match `len(df)` exactly.

### 8.4 Prefer vectorized indicator logic

For `IndicatorStrategy`, core calculations should be pandas-native whenever possible.

### 8.5 Keep runtime scripts deterministic

For `ScriptStrategy`, avoid hidden state outside `ctx`, avoid randomness, and make order intent explicit.

### 8.6 Put configuration in the right layer

- use `# @param` and `# @strategy` for indicator defaults
- use `ctx.param()` for script defaults
- keep leverage, venue configuration, and credentials outside the strategy code

---

## 9. Troubleshooting

### 9.1 `column "strategy_mode" does not exist`

Your database schema is older than the running code. Apply the required migration on `qd_strategies_trading`.

### 9.2 `Strategy script must define on_bar(ctx, bar)`

Your `ScriptStrategy` code is missing the required handler.

### 9.3 `Missing required functions: on_init, on_bar`

The current UI verifier expects both functions to exist in the source text.

### 9.4 `Strategy code is empty and cannot be backtested`

The saved strategy does not contain valid code for the selected mode.

### 9.5 Marker or plot length mismatch

All chart output arrays must align exactly with the dataframe length.

### 9.6 Strategy behaves strangely in backtest

Check these first:

- did you accidentally use future data?
- are your `buy` / `sell` signals edge-triggered?
- are you mixing signal-driven exits with engine-driven exits without documenting it?
- are your `# @strategy` defaults aligned with the strategy idea?

### 9.7 Backend logs

If strategy creation, verification, backtest, or execution fails, check backend logs first. Common issue classes:

- schema mismatch
- invalid JSON or config payloads
- code verification failure
- market or symbol mismatch
- credential or exchange configuration issues

---

## 10. Recommended Development Workflow

1. Prototype the idea as an `IndicatorStrategy`.
2. Validate plots, signal density, and next-bar-open backtest behavior.
3. Add clear `# @param` and `# @strategy` metadata.
4. Decide explicitly whether exits are signal-managed or engine-managed.
5. Save the strategy and run strategy backtests from the persisted record.
6. Promote to `ScriptStrategy` only when you truly need runtime position logic.
7. Move to paper or live trading only after configuration, credentials, and market semantics are verified.

