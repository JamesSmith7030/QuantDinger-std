# 技术设计

## 1. 设计原则

采用最小修改：保留指标计算和交易思想，只替换执行信号契约、修复边缘触发，
并补齐引擎硬止损。仓位、参数周期和图表样式不做重构。

## 2. SOL 信号映射

| 原始条件 | 四路信号 | 行为 |
|---|---|---|
| EMA10 上穿 EMA30 | `open_long` | 空仓时开多 |
| EMA10 下穿 EMA30 | `close_long` | 持有多仓时平多 |
| 无 | `open_short` | 永远 False |
| 无 | `close_short` | 永远 False |

退出负责人使用 `engine`：EMA 死叉是结构性退出，5% 固定止损是价格风险兜底。

## 3. BTC 信号映射

| 原始条件 | 四路信号 | 行为 |
|---|---|---|
| RSI 首次进入 `< 24` | `close_short` + `open_long` | 空仓开多；持空时 R2 先平空再开多 |
| RSI 首次进入 `> 76` | `close_long` + `open_short` | 空仓开空；持多时 R2 先平多再开空 |

退出负责人使用 `engine`：反向开仓信号负责结构性反手，5% 固定止损负责异常行情退出。

## 4. 边缘触发契约

```python
def edge(s):
    s = s.fillna(False).astype(bool)
    prev = s.shift(1).fillna(False).astype(bool)
    return (s & ~prev).astype(bool)
```

必须在 `~prev` 前执行 `astype(bool)`，避免 pandas 3.x 将 object 值取反为整数。

## 5. 兼容性

- 使用当前平台要求的四路执行列。
- `output['signals']` 只负责图表显示，数据来自对应执行列。
- 不保留旧 `df['buy']` / `df['sell']`，避免新旧契约并存造成语义不清。
- 只修改本地策略文件，不改变已运行实例。

## 6. 回滚

每份策略是独立文件。若验证失败，可按文件恢复本任务改动；不得恢复用户在任务开始前
已经暂存的 PowerTower `entryPct 0.9` 修改。
