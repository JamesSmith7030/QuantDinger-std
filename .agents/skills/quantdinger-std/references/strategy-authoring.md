# 指标 / 策略编写契约速查

> 权威来源：`docs/STRATEGY_DEV_GUIDE_CN.md`（教程）与 `docs/SIGNAL_EXECUTION_STANDARD_CN.md`（SSOT）。
> 本页是写代码时的对照表，冲突时以上述两份文档为准。

## 1. 形态选型（必须先选）

| 形态 | 信号列 | 适用 |
|------|--------|------|
| A 两路 | `df['buy']` / `df['sell']` | 金叉死叉、对称反转（存量兼容；新代码不推荐） |
| **B 四路（新代码标准）** | `open_long` / `close_long` / `open_short` / `close_short` | 多空分离、触及型 tp/sl、状态机 |
| C ScriptStrategy | `on_init` + `on_bar` | 强依赖持仓状态、分批、冷却、bot |

两路 `tradeDirection` 语义（极易踩坑）：

| `tradeDirection` | `buy=True` | `sell=True` |
|---|---|---|
| `long` | 开多 | 平多 |
| `short` | 平空 | 开空 |
| `both` | 开多（持空则**先平空再开多**） | 开空（持多则**先平多再开空**） |

`both` 下 `buy` 不存在「仅平空」语义——只想平仓不反手必须用四路 `close_*` 或 ScriptStrategy。

## 2. IndicatorStrategy 脚本骨架

```python
my_indicator_name = "Strategy Name"
my_indicator_description = "One-line description."

# signal_form: four_way          # two_way | four_way
# exit_owner: engine             # indicator | engine（没有 layered！）
# flip_mode: R2                  # R1 下一根再开 | R2 同 bar 先平后开

# @param fast_len int 20 Fast EMA length
# @param slow_len int 50 Slow EMA length

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.25
# @strategy tradeDirection both

df = df.copy()                   # 首行可变操作 MUST

fast_len = int(params.get('fast_len', 20))   # 声明了 @param 就必须用 params.get 读取

# ... 指标计算（向量化，pandas 原生） ...

def edge(s):
    # 注意：bool Series 经 shift(1) 会退化成 object dtype，必须再 astype(bool) 才能 ~
    # 官方文档里 `s & ~s.shift(1).fillna(False)` 的写法在 pandas 3.x 下会静默失效（信号不去重）
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return s & ~prev

df['open_long']   = edge(raw_open_long)
df['close_long']  = edge(raw_close_long)
df['open_short']  = edge(raw_open_short)
df['close_short'] = edge(raw_close_short)

output = {
    "name": my_indicator_name,
    "plots":  [ {"name": "...", "data": series.fillna(0).tolist(),  # len == len(df)
                 "color": "#1890ff", "overlay": True} ],
    "signals": [ {"type": "buy", "text": "L", "color": "#00E676",
                  "data": marks} ],   # 无信号位置用 None；仅图表展示，不参与成交
}
```

## 3. 沙盒环境

- 预绑定：`df`（列 `time/open/high/low/close/volume`）、`pd`、`np`、`params`。
- Agent Gateway 回测沙盒额外预绑定：`open/high/low/close/volume` Series、
  `SMA EMA RSI MACD BOLL ATR CROSSOVER CROSSUNDER`、`call_indicator(...)`。
- import 白名单：numpy pandas math json datetime time collections functools
  itertools statistics decimal fractions copy。
- 禁止：网络、文件 IO、子进程、`eval/exec/open/__import__/getattr/setattr`、
  dunder 绕过（`__class__`/`__globals__`）、`import operator`。

## 4. `# @strategy` 支持的 key（仅此 7 个）

| Key | 含义 | 注意 |
|-----|------|------|
| `stopLossPct` | 止损（标的涨跌幅，0–1 小数） | `0.03` = 跌 3%；**不除杠杆** |
| `takeProfitPct` | 止盈 | 同上 |
| `entryPct` | 开仓资金占比 | **`1` = 100%**，`0.25` = 25% |
| `trailingEnabled` | 跟踪止损开关 | `exit_owner: indicator` 时必须 `false` |
| `trailingStopPct` | 跟踪回撤比例 | |
| `trailingActivationPct` | 跟踪激活盈利阈值 | |
| `tradeDirection` | `long` / `short` / `both` | 与信号列语义联动 |

**禁止 `leverage`** —— 杠杆、交易所、标的、凭证、成交时机都在产品配置层。

`# @param` 格式：`# @param <name> <int|float|bool|str> <default> <描述>`，
声明后必须 `params.get('name', default)` 读取，否则代码质量检查告警。

## 5. 退出负责人（防双重平仓的核心）

| 声明 | 含义 | 配套要求 |
|------|------|----------|
| `# exit_owner: indicator` | 退出全部由指标信号（`close_*` 或信号内 tp/sl）负责；服务端固定止损/止盈/追踪全部不平仓 | `# @strategy trailingEnabled false` |
| `# exit_owner: engine` | 服务端价格风控（stopLoss/takeProfit/trailing）负责退出 | 指标内只留结构性反转 `close_*`，**不要**再写窄 tp/sl 布尔列 |

- 不存在 `exit_owner: layered`，不要生成。
- 双重退出的典型病征：实盘日志 `server_trailing_stop` 之后紧跟 `close_*`
  → `invalid amount (0.0) for close_*` 拒单。

## 6. 执行语义（回测 = 实盘对齐基准）

- 信号：bar **收盘确认**（`signal_mode` / `exit_signal_mode` = `confirmed`）。
- 成交：**下一根 bar 开盘价** ± 滑点（`signalTiming = next_bar_open`）。
- 同 bar 优先级：`close_*` > `open_*`；同 bar 不要同时 `open_long` 和 `open_short`。
- 反手：R1 = 同 bar 只平、下一根再开；R2 = 同 bar 先平后开（与历史 both 回测一致）。
- 仓位大小由规范化配置 `entryPct` 决定，不是脚本里的 amount。
- 实盘依赖「盘中触及」（`high >= 线`）的逻辑，会比 confirmed 回测更早触发——对齐就用 confirmed。

## 7. ScriptStrategy API

必须同时定义 `on_init(ctx)` 与 `on_bar(ctx, bar)`（校验器两个都查）。

| `ctx` | 说明 |
|-------|------|
| `ctx.param(name, default)` | 脚本级默认参数 |
| `ctx.bars(n)` | 最近 n 根已收盘 bar 列表 |
| `ctx.position` | 持仓；支持 `if not ctx.position` / `> 0` / `["side"|"size"|"entry_price"|"direction"|"amount"]` |
| `ctx.balance` / `ctx.equity` | 余额 / 权益快照 |
| `ctx.buy(price, amount)` / `ctx.sell(price, amount)` | 方向性意图（持反向仓可能解释为先平后反手） |
| `ctx.close_position()` | **全部平仓用这个**，别用 buy/sell 表达 |
| `ctx.log(msg)` | 策略日志 |

`bar`：`open/high/low/close/volume/timestamp`。

- 回测语义：脚本标准回测 · 逐 bar · 下一根开盘成交（没有指标 IDE 的严格/非严格开关）。
- `amount` 是运行时下单意图，保存后策略回测仓位仍以 `entryPct` 为主——上线前用保存后的策略回测核对暴露。
- bot 模式（网格/DCA）会用类 tick 伪 bar 反复调 `on_bar`，与标准 bar-close 策略分开测试。

## 8. 高频错误清单（自检）

1. **`# @param` 声明的默认值 ≠ 代码 `params.get(name, X)` 的回退默认 X**。两处必须一致，
   否则漏传参时实盘静默跑成另一套参数（与回测/描述不符）。这是最隐蔽的一类 bug。
2. **边缘触发反模式 `~s.shift(1).fillna(False)`**：bool 经 `shift` 变 object，`~` 得到
   `-1/-2` 整数而非布尔（pandas 3.x 坑），信号静默错乱。固定写法：
   `prev = s.shift(1).fillna(False).astype(bool); edge = (s & ~prev).astype(bool)`。
   （交叉信号本就是单根、可不去重；`rsi<阈值` 这类会连续多根为真，去重必需。）
3. **沙盒禁 `pd.api` / `.core` / `.io` 等属性**（`safe_exec` 黑名单）：用了
   `pd.api.types.is_datetime64_any_dtype` / `is_numeric_dtype` 会被校验拒 →
   `indicator execution failed` 自动停。改用 `s.dtype.kind`：`'M'`=datetime、
   `'i'/'u'/'f'/'b'`=数值。离线自检无此校验，**只在实盘沙箱暴露**。
4. `shift(-1)` 未来函数 → 回测虚高。
5. `# @strategy leverage 10` → 非法 key（杠杆属产品配置层）。
6. `both` 模式把空侧 tp/sl 塞进 `buy` 列，期待「仅平空」→ 实际会反手开多。
7. 指标内窄 tp/sl + `trailingEnabled true` 并存 → 双重平仓（用 `# exit_owner` 声明归属）。
8. **零止损裸跑**：`stopLossPct 0` + `takeProfitPct 0` + `trailingEnabled false` 且仅靠
   反向信号离场 → 趋势行情可无限亏。至少给一道引擎硬止损或启用 trailing 兜底。
9. plot/signal 的 `data` 长度 ≠ `len(df)` → 渲染报错。
10. ScriptStrategy 想全平却写 `ctx.sell()`。
11. NaN 未清理（rolling/ewm 前导 NaN）就比较。

> 注：1/2/3/8 是 2026-06-17 review v1.3.4 / v2.0.5 / PowerTower 三个实盘策略时反复发现的真实坑。
> 改完务必 `python examples/_verify_template.py <脚本>` 离线自检——但注意它**不含沙箱校验**，
> 第 3 条（pd.api）需在实盘沙箱才暴露，编写时主动避开。

## 9. 现成示例

`indicator_community/free_raw_codes/`：

- `0f-双均线策略.py` — 最小两路 EMA 交叉（含完整 output 结构）
- `0f-【四合一】通道买卖点.py` — Pine Script 翻译的复杂多模块指标
- `0f-RSI Reversal.py`、`0f-Triple EMA Ribbon.py` 等

本技能 `examples/ema_cross_four_way.py` 是符合最新四路标准的可回测模板。
