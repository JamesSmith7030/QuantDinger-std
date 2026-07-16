# 修复 SOL 与 BTC 策略 P1 问题

## 1. 文档信息

- **任务类型**：策略缺陷修复
- **优先级**：P1
- **范围**：两份 IndicatorStrategy
- **原则**：只修复审查确认的 P1，P2/P3 不改

## 2. 背景

前序审查确认两份修改后策略仍存在会导致重复信号、无法通过当前策略校验、
风险无上限或止损晚于清算风险的 P1 问题，需要在重新发布或继续实盘前修复。

## 3. 修复目标

1. 将两份策略迁移为 QuantDinger 当前四路信号契约。
2. 修复 BTC PowerTower 在 pandas 3.x 下的边缘触发错误。
3. 为 SOL 策略增加明确的引擎硬止损，消除零止损裸跑。
4. 将 BTC 策略的 30% 极宽止损恢复为可实际保护仓位的 5% 硬止损。
5. 保持策略原有入场条件、交易方向及用户已有的 90% 仓位修改。

## 4. 修改范围

### 4.1 SOL 双均线做多策略

`indicator_simulated_trading/v1.0.1(SOL4H做多+355.19)-双均线策略.py`

- 增加 `signal_form: four_way`、`exit_owner: engine`、`flip_mode: R1`。
- 增加 `stopLossPct 0.05`、`tradeDirection long`，其余风险参数保持最小明确配置。
- 金叉映射为 `open_long`，死叉映射为 `close_long`。
- `open_short`、`close_short` 固定为 False。
- 四路信号全部为边缘触发布尔列。
- 图表信号改为引用四路执行列。

### 4.2 BTC PowerTower 双向策略

`indicator_simulated_trading/v1.0.6 self(双向+31.83) PowerTower 策略-BTC.py`

- 保留用户已修改的 `entryPct 0.9`。
- 增加 `signal_form: four_way`、`exit_owner: engine`、`flip_mode: R2`。
- 将 `stopLossPct 0.3` 改为 `0.05`。
- 用 pandas 3.x 安全写法修复 RSI 状态边缘触发。
- 超卖边缘同时映射为 `close_short` 与 `open_long`。
- 超买边缘同时映射为 `close_long` 与 `open_short`。
- R2 使用显式四路“先平后开”反手，引擎硬止损负责异常行情退出。
- 图表信号改为引用四路执行列。

## 5. 约束

- 不修改 RSI 计算公式及其 P3 极端值处理。
- 不增加止盈或追踪止损，不重新优化参数。
- 不修改交易所、账户、资金、杠杆或运行实例。
- 不执行实盘交易，不自动重新发布策略。
- 不修改两份策略以外的业务代码。

## 6. 验收标准

- [x] 两份策略均通过 Python 编译。
- [x] 两份策略均通过 `validate_indicator_code`。
- [x] 四路执行列存在、为 bool、长度等于 `len(df)`。
- [x] PowerTower 连续超卖/超买状态只在首次进入时触发一次。
- [x] SOL 只产生多头开仓和平仓信号，不产生空头信号。
- [x] 两份策略均无 `shift(-1)` 未来函数。
- [x] `entryPct 0.9` 在两份策略中保持不变。
- [x] SOL 与 BTC 的引擎硬止损均为 5%。
- [x] 未修改 P2/P3 范围及其他业务文件。

## 7. 非目标

- 不重新跑历史收益回测或声称原收益仍然成立。
- 不解决 BTC 价格高于约 90,000 USDT 后可能再次低于 Binance 最小数量的问题。
- 不同步已运行实例中的策略代码和配置。
- 不修复 PowerTower RSI 在单边上涨时可能填充为 50 的 P3 问题。
