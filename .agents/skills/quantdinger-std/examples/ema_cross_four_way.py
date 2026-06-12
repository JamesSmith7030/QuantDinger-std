# QuantDinger IndicatorStrategy 模板 — 四路信号标准（signal_form: four_way）
# 用法：作为 Indicator IDE / POST /api/agent/v1/backtests 的 code 提交。
# 契约速查见 ../references/strategy-authoring.md

my_indicator_name = "EMA Cross Four-Way Template"
my_indicator_description = "EMA fast/slow cross, long on golden cross, short on death cross; engine-managed exits."

# signal_form: four_way
# exit_owner: engine
# flip_mode: R2

# @param fast_len int 10 Fast EMA length
# @param slow_len int 30 Slow EMA length

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.25
# @strategy trailingEnabled false
# @strategy tradeDirection both

df = df.copy()

fast_len = int(params.get('fast_len', 10))
slow_len = int(params.get('slow_len', 30))

ema_fast = df['close'].ewm(span=fast_len, adjust=False).mean()
ema_slow = df['close'].ewm(span=slow_len, adjust=False).mean()

# 原始条件（持续态）
raw_long = ema_fast > ema_slow
raw_short = ema_fast < ema_slow


def edge(s):
    """边缘触发：false→true 的那一根才发信号。
    注意：bool Series 经 shift(1) 会变 object dtype，取反前必须 astype(bool)，
    否则 ~ 得到 -1/-2 整数，pandas 3.x 下过滤会静默失效（每根 bar 都触发）。"""
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return s & ~prev


golden_cross = edge(raw_long)
death_cross = edge(raw_short)

# 四路执行列：金叉 = 平空 + 开多；死叉 = 平多 + 开空（flip_mode R2 同 bar 先平后开）
df['open_long'] = golden_cross
df['close_short'] = golden_cross
df['open_short'] = death_cross
df['close_long'] = death_cross

# 图表标记（仅展示，不参与成交）
buy_marks = [df['low'].iloc[i] * 0.995 if golden_cross.iloc[i] else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if death_cross.iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {
            "name": "EMA Fast",
            "data": [None if pd.isna(x) else float(x) for x in ema_fast],
            "color": "#1890ff",
            "overlay": True,
            "type": "line"
        },
        {
            "name": "EMA Slow",
            "data": [None if pd.isna(x) else float(x) for x in ema_slow],
            "color": "#faad14",
            "overlay": True,
            "type": "line"
        }
    ],
    "signals": [
        {"type": "buy", "text": "L", "data": buy_marks, "color": "#00E676"},
        {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"}
    ]
}
