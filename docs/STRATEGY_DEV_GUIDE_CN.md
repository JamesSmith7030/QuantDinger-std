# QuantDinger Python v3 策略开发指南

这份指南不是单纯罗列接口，而是站在**策略开发者**视角，回答一个更实际的问题：

**到底应该怎么写一个结构清晰、能回测、能落地成平台策略的指标策略？**

QuantDinger 当前支持两条 Python 开发路径：

- **IndicatorStrategy**：基于 `df` 的指标/信号脚本，用于 Indicator IDE、图表渲染和信号型回测。
- **ScriptStrategy**：基于 `on_init / on_bar` 的事件驱动脚本，用于策略运行时、策略回测与实盘执行。

如果你要从零开始开发一个策略，默认建议是：

1. 先用 `IndicatorStrategy` 把信号逻辑跑通。
2. 先验证图表、信号和回测语义。
3. 只有当你需要运行时状态、动态仓位管理或执行控制时，再升级为 `ScriptStrategy`。

---

## 1. 先建立正确心智模型

很多开发者会把**信号逻辑**、**止盈止损**、**仓位管理**、**执行逻辑**混在一起写，结果文档看不懂、代码也不好维护。

### 1.1 IndicatorStrategy 是什么

可以把 `IndicatorStrategy` 理解成：

- 基于 `df` 计算指标序列
- 生成布尔型 `buy` / `sell` 信号
- 通过元数据声明默认策略配置
- 返回 `output` 供图表展示

它最适合：

- 指标研究
- 策略原型验证
- 参数调优
- 信号型回测
- 先做信号、后保存成平台策略的工作流

### 1.2 ScriptStrategy 是什么

可以把 `ScriptStrategy` 理解成：

- 按 bar 逐根执行的运行时逻辑
- 通过 `ctx.position` 读取当前持仓状态
- 用 `ctx.buy()`、`ctx.sell()`、`ctx.close_position()` 发出动作
- 把退出、仓位、执行节奏写进代码

它最适合：

- 有状态的执行逻辑
- 动态止盈止损
- 分批加仓、减仓、部分止盈
- 冷却期、重入限制、bot 型执行策略

### 1.3 最重要的分层

对于 `IndicatorStrategy`，请强制把逻辑拆成三层：

1. **指标层**：均线、RSI、ATR、布林带、过滤条件。
2. **信号层**：`df['buy']` 和 `df['sell']`。
3. **风险默认配置层**：`# @strategy stopLossPct ...`、`takeProfitPct`、`entryPct` 等。

不要把这三层混成一团。

尤其要明确：

- `buy` / `sell` 负责表达**什么时候进出场**
- `# @strategy` 负责表达**引擎默认如何控风险、如何设仓位**
- 杠杆属于产品配置，不属于指标脚本

---

## 2. 应该选哪种模式？

| 使用场景 | 推荐模式 |
|----------|----------|
| 写指标、叠加图表、画买卖点 | `IndicatorStrategy` |
| 研究 dataframe 上的进出场信号 | `IndicatorStrategy` |
| 只想给策略补固定止损、止盈、仓位默认值 | `IndicatorStrategy` |
| 需要逐根读取持仓状态做判断 | `ScriptStrategy` |
| 止损止盈依赖当前持仓状态动态变化 | `ScriptStrategy` |
| 需要分批开平仓、状态机、bot 风格执行 | `ScriptStrategy` |

一个简单判断方法：

- 如果你的逻辑可以表述成“条件 A 出现就买，条件 B 出现就卖”，先用 `IndicatorStrategy`
- 如果你的逻辑更像“开仓后要持续盯着当前持仓，并根据状态做不同反应”，那就应该用 `ScriptStrategy`

---

## 3. 如何开发一个 IndicatorStrategy

这是大多数新策略最推荐的开发路径。

### 3.1 第一步：先把元数据和默认配置写清楚

脚本开头先定义名称、描述、可调参数、默认策略配置。

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

`# @param` 用来定义用户经常调的参数。

`# @strategy` 用来定义策略默认配置，比如：

- `stopLossPct`：止损比例，例如 `0.03` 表示 3%
- `takeProfitPct`：止盈比例，例如 `0.06` 表示 6%
- `entryPct`：开仓资金占比
- `trailingEnabled`
- `trailingStopPct`
- `trailingActivationPct`
- `tradeDirection`：`long`、`short` 或 `both`

这里有个非常关键的边界：

- 这些是**引擎读取的默认配置**
- 不是让你再去 dataframe 里造一列 `stop_loss`
- 不要在这里写 `leverage`

### 3.2 第二步：复制 dataframe，再算指标

Indicator 代码运行在沙盒里，`pd` 和 `np` 已预置。

推荐开头固定写：

```python
df = df.copy()
```

通常可用列包括：

- `open`
- `high`
- `low`
- `close`
- `volume`

`time` 列可能存在，但不要假设其类型永远一致。

避免这些写法：

- 网络请求
- 文件读写
- 子进程
- `eval`、`exec`、`open`、`__import__` 这类破坏沙盒边界的模式

### 3.3 第三步：把原始条件变成干净的 `buy` / `sell`

回测引擎读取的是两列**布尔信号**：

- `df['buy']`
- `df['sell']`

它们应满足：

- 与 dataframe 长度完全一致
- `fillna(False)` 后为布尔值
- 除非你明确要连续触发，否则应尽量做成边缘触发

推荐模式：

```python
raw_buy = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
raw_sell = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

df['buy'] = (raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))).astype(bool)
df['sell'] = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)
```

这样可以避免同一段趋势里每根 bar 都重复发信号。

### 3.4 第四步：先决定“谁负责退出”

止盈止损和仓位管理最容易在这里写乱。

在 `IndicatorStrategy` 里，退出逻辑通常有两种合法写法。

#### 写法 A：信号自己负责退出

也就是由你的指标逻辑直接生成 `df['sell']`。

典型例子：

- 均线死叉
- RSI 跌破阈值
- 收盘价跌破 ATR 止损线
- 均值回归到目标位后离场

如果退出本身就是策略思想的一部分，用这种写法最自然。

#### 写法 B：引擎负责固定止盈止损

也就是你只定义默认配置，由引擎按固定规则处理：

- `stopLossPct`
- `takeProfitPct`
- `entryPct`
- trailing 系列参数

如果你的信号逻辑想保持简洁，而保护性规则是固定的，就用这种写法。

#### 最佳实践

尽量明确一个“主退出来源”。

例如：

- 如果你的核心逻辑是“金叉进，死叉出”，那退出就主要由 `sell` 信号负责
- 如果你的逻辑是“信号进场，固定 3% 止损 + 6% 止盈管理交易”，那退出主要由 `# @strategy` 负责

两者可以同时存在，但一定要在注释或描述里写清楚，否则别的开发者不知道到底是**信号退出**还是**引擎退出**在起主要作用。

### 3.5 第五步：最后再组装 `output`

脚本最后必须赋值 `output`：

```python
output = {
    "name": "My Strategy",
    "plots": [],
    "signals": []
}
```

主要支持键：

- `name`
- `plots`
- `signals`
- `calculatedVars`：可选元数据

每个 `plot` 项通常包含：

- `name`
- `data`，长度必须等于 `len(df)`
- `color`
- `overlay`
- 可选 `type`

每个 `signal` 项通常包含：

- `type`：`buy` 或 `sell`
- `text`
- `color`
- `data`：无信号的 bar 用 `None`

### 3.6 第六步：校验回测语义

指标回测是典型的信号驱动：

- 引擎读取 `df['buy']` 和 `df['sell']`
- 信号按 bar close 确认
- 通常在**下一根 bar 开盘价**成交

这件事非常重要，因为：

- 你在当前 K 线上画出来的“止损线”不等于系统一定按这根 K 线内部价格成交
- 一旦用了 `shift(-1)`，就基本等于引入未来函数

---

## 4. 止盈止损和仓位管理到底怎么写

这一节就是给开发者的直接答案。

### 4.1 在 IndicatorStrategy 里写固定止损、止盈、仓位

如果你想要的是固定默认配置，就写成 `# @strategy`：

```python
# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 0.25
# @strategy tradeDirection long
```

含义分别是：

- `stopLossPct 0.03`：默认 3% 止损
- `takeProfitPct 0.06`：默认 6% 止盈
- `entryPct 0.25`：默认用 25% 资金开仓
- `tradeDirection long`：默认只做多

这种写法适合：

- 信号代码尽量简单
- 希望回测时能直接读懂默认风险参数
- 希望 UI 和引擎都能直接识别这些默认值

### 4.2 在 IndicatorStrategy 里写“指标驱动型止损”

如果你的“止损”本质上是策略逻辑的一部分，那就不要假装成外部配置，而是直接写进 `sell` 信号。

例如：跌破 ATR 风格止损线就卖出。

```python
atr = (df['high'] - df['low']).rolling(14).mean()
stop_line = df['close'].rolling(20).max() - atr * 2.0

raw_sell = df['close'] < stop_line.shift(1)
df['sell'] = (raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))).astype(bool)
```

这种写法表示：

- 退出属于你的指标逻辑
- 引擎不是替你“发明”一个止损
- 你最好在描述或注释里说明这一点

### 4.3 IndicatorStrategy 里的仓位管理边界

对 `IndicatorStrategy` 来说，仓位管理应该尽量保持简单：

- 用 `entryPct` 管默认开仓资金占比
- 用 `tradeDirection` 管做多 / 做空 / 双向
- 用固定的止损止盈或 trailing 默认值做保护

如果你需要下面这些能力：

- 分批加仓、减仓
- 部分止盈
- 开仓前后用不同逻辑
- 止损线会跟随当前持仓状态动态变化
- 止损后冷却一段时间再重入

那就说明这套逻辑已经超出 `IndicatorStrategy` 该承担的范围，应该迁移到 `ScriptStrategy`。

---

## 5. 完整的 IndicatorStrategy 示例

下面这个例子展示了一个更符合开发者思维的完整结构：元数据、默认配置、指标计算、信号生成、图表输出分层清楚。

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

这个例子刻意强调了几件事：

- 先算指标，再出信号
- 进出场逻辑通过布尔列表达
- 固定风险默认值通过 `# @strategy` 单独声明
- 图表输出是最后一步，不要和信号逻辑搅在一起

---

## 6. 什么时候该切到 ScriptStrategy

当策略需要“运行时状态”而不是“纯 dataframe 信号”时，就该迁移到 `ScriptStrategy`。

典型信号包括：

- 止损止盈依赖当前持仓，而不是仅依赖历史序列
- 开仓后要动态移动止损
- 需要部分平仓或加仓
- 首次开仓和再次开仓逻辑不同
- 需要冷却期、节流、bot 风格执行规则

### 6.1 必需函数

当前产品侧校验默认要求：

- `def on_init(ctx): ...`
- `def on_bar(ctx, bar): ...`

即使某些内部路径可能允许缺少 `on_init`，面向产品的策略代码也建议两个都写。

### 6.2 可用对象

`bar` 通常提供：

- `bar.open`
- `bar.high`
- `bar.low`
- `bar.close`
- `bar.volume`
- `bar.timestamp`

`ctx` 当前通常提供：

- `ctx.param(name, default=None)`
- `ctx.bars(n=1)`
- `ctx.position`
- `ctx.balance`
- `ctx.equity`
- `ctx.log(message)`
- `ctx.buy(price=None, amount=None)`
- `ctx.sell(price=None, amount=None)`
- `ctx.close_position()`

`ctx.position` 同时支持数值判断和字段访问，例如：

```python
if not ctx.position:
    ...

if ctx.position > 0:
    ...

if ctx.position["side"] == "long":
    ...
```

### 6.3 一个带运行时退出的 ScriptStrategy 示例

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

这种写法适合“止盈止损属于运行时持仓管理”的场景，而不是单纯图表信号输出。

---

## 7. 回测、持久化与当前限制

保存后的策略会被后端解析成统一快照，再进入回测或执行链路。常见字段包括：

- `strategy_type`
- `strategy_mode`
- `strategy_code`
- `indicator_config`
- `trading_config`

当前常见 `run_type` 包括：

- `indicator`
- `strategy_indicator`
- `strategy_script`

当前限制包括：

- `cross_sectional` 在当前策略快照链路中还未完全打通
- `ScriptStrategy` 当前不支持 `cross_sectional` 实盘运行
- 策略回测要求 symbol 合法且代码非空

---

## 8. 最佳实践

### 8.1 始终避免未来函数

- 只使用已完成 bar 的信息
- 优先使用 `shift(1)` 做确认
- 不要在信号逻辑中使用 `shift(-1)`

### 8.2 显式处理 NaN

滚动窗口和 EWM 都会产生前导 NaN，生成信号前必须先清理。

### 8.3 保持所有序列长度一致

所有 `plot['data']` 和 `signal['data']` 都必须与 `len(df)` 完全一致。

### 8.4 IndicatorStrategy 尽量保持向量化

核心指标计算优先用 pandas 原生向量化逻辑，不要把主逻辑写成逐行循环。

### 8.5 ScriptStrategy 保持确定性

`ScriptStrategy` 尽量避免 `ctx` 外部的隐式状态、随机行为，以及含糊不清的下单意图。

### 8.6 把配置放在正确层级

- 指标型默认值用 `# @param` 和 `# @strategy`
- 脚本型默认值优先用 `ctx.param()`
- 杠杆、交易所、账户凭证放在产品配置层，不要硬编码

---

## 9. 故障排除

### 9.1 `column "strategy_mode" does not exist`

说明数据库结构版本落后于当前代码，需要对 `qd_strategies_trading` 执行对应迁移。

### 9.2 `Strategy script must define on_bar(ctx, bar)`

说明 `ScriptStrategy` 缺少必需的 `on_bar`。

### 9.3 `Missing required functions: on_init, on_bar`

说明当前 UI 校验器要求源码里同时存在这两个函数。

### 9.4 `Strategy code is empty and cannot be backtested`

说明保存后的策略在当前模式下没有有效代码。

### 9.5 图表长度不一致

说明某个 plot 或 signal 的数组长度没有和 `df` 对齐。

### 9.6 回测结果很奇怪

优先检查这几件事：

- 有没有误用未来数据
- `buy` / `sell` 是否做成了边缘触发
- 是否同时混用了“信号退出”和“引擎退出”却没有说明清楚
- `# @strategy` 默认值是否真的符合策略风格

### 9.7 后端日志排查

如果策略创建、校验、回测或执行失败，请优先查后端日志。常见问题包括：

- 数据库结构不匹配
- JSON / 配置载荷格式错误
- 代码校验失败
- 市场 / symbol 不匹配
- 交易所凭证或配置异常

---

## 10. 推荐开发流程

1. 先用 `IndicatorStrategy` 把想法原型化。
2. 先验证图表、信号密度和 next-bar-open 的回测语义。
3. 把 `# @param` 和 `# @strategy` 元数据补完整。
4. 明确写清楚：退出到底是“信号负责”还是“引擎负责”。
5. 保存策略后，再从持久化记录跑策略回测。
6. 只有在确实需要运行时仓位管理时，再迁移到 `ScriptStrategy`。
7. 确认配置、凭证和市场语义都正确后，再进入模拟盘或实盘。

