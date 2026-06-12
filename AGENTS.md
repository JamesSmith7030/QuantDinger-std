# Agent 入口（QuantDinger-std）

在本仓库开发（写指标/策略、跑回测、改后端）前，先读：

1. **[.agents/skills/quantdinger-std/SKILL.md](.agents/skills/quantdinger-std/SKILL.md)** —
   项目地图、技术栈、策略编写契约、回测工作流、安全红线（本仓库技能入口）。
2. [.cursor/skills/quantdinger-agent-workflow/SKILL.md](.cursor/skills/quantdinger-agent-workflow/SKILL.md) —
   上游官方 agent 工作流（后端改码规则、Agent Gateway 实现真相）。
3. 零基础者：[.agents/docs/策略指标编写新人教程.md](.agents/docs/策略指标编写新人教程.md)。
4. 策略开发 agent 人设：[.agents/agents/crypto-quant-strategist.md](.agents/agents/crypto-quant-strategist.md) —
   加密货币量化策略专家角色（已绑定平台契约与交付物格式）。

硬性约束速记：

- 新策略信号一律四路布尔列 `open_long / close_long / open_short / close_short` + 边缘触发；
  禁止 `shift(-1)` 未来函数；头部声明 `# exit_owner: indicator|engine`。
- 边缘触发注意 pandas 3.x 陷阱：`shift(1)` 后必须 `astype(bool)` 再取反。
- 不提交密钥/生产 `.env`；agent 交易默认 paper-only，实盘双重开关不得绕过。
- 后端：routes 只做 HTTP，交易所逻辑进 `app/services/live_trading/`；测试
  `cd backend_api_python && python -m pytest tests/ -q`。
