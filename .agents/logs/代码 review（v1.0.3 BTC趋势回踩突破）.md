1.2 策略代码 review（v1.0.3 BTC趋势回踩突破）
按严重程度排序：

🔴 P0 — 方向配置错位，这是空头仓位的来源。代码声明 # @strategy tradeDirection long（只做多），但日志里出现 close_short / Flip open_long，说明部署时的 trading_config 被改成了 both。后果致命：你的 sell 信号（趋势破位 trend_fail、动量走弱 rsi < 44、结构破位 structure_fail）是按"多头离场条件"设计的，在 both 模式下它们全部变成了开空信号——策略在每次"该离场"的时候反手做空，这不是策略本意。本次 0.002 ETH 空单就是这么来的。修复：在平台界面把该策略的交易方向改回 long，或者升级代码为四路信号（open_short/close_short 全 False），让方向语义锁死在代码里。

🔴 P1 — 边缘触发在 pandas 3.x 下会静默失效。第 85–88、100–103 行用的是 ~raw.shift(1).fillna(False)——布尔列经 shift 后变 object 类型，新版 pandas 直接 ~ 取反结果错误且不报错，信号会退化成每根 bar 连续触发。安全写法（与教程一致）：

prev = raw_buy.shift(1).fillna(False).astype(bool)
buy = (raw_buy.fillna(False).astype(bool) & ~prev)
🟡 P2 — 退出负责人未声明，存在双重退出。头部没有 # exit_owner 契约；同时启用了引擎侧 stopLossPct/takeProfitPct/trailing（且 trailing 很窄：0.5% 回撤/0.9% 激活）和指标内的 sell 退出条件。两者并存会出现"server_trailing_stop 平完仓、指标 close_* 又来一单数量为 0"的拒单。建议补 # exit_owner: engine，并接受 sell 仅作结构性反转退出（前提是 P0 修掉、sell 不再开空）。

🟡 P3 — RSI 计算边界 bug。第 46 行 rs = (gain / loss.replace(0, np.nan)).fillna(0)：连续上涨使 loss=0 时，RSI 应为 100（最强），却被算成 0（最弱），rsi_ok 把最强势的入场机会反向过滤掉了。应改为 rs 保持 NaN、最后 rsi.fillna(50) 或显式把 loss==0 映射成 RSI=100。

🟢 P4 — 杂项：第 3 行注释"15倍杠杆，年化4000000000%"与实际运行的 3x 杠杆不符，纯误导建议删除；# signal_form / # flip_mode 契约头缺失；entryPct 0.1 配小资金必撞最小下单量（本次事故的另一半原因）。

如需我把 v1.0.3 按四路标准重写成 v1.0.4（修掉 P0–P3）并跑回测对比，说一声即可。



docker compose build backend 和 docker compose up -d backend ，都要执行吗？可执行一个吗？有什么区别？
