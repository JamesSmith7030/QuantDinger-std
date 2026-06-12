---
name: quantdinger-std
description: >-
  QuantDinger-std（fork 自 brokermr810/QuantDinger）量化交易平台开发技能：
  项目架构、技术栈、指标/策略编写契约（IndicatorStrategy 四路信号 / ScriptStrategy）、
  回测工作流（Agent Gateway REST + MCP）、安全红线。任何 agent 在本仓库编写指标、
  策略、回测或修改后端代码前必读。
---

# QuantDinger-std 开发技能

## 项目是什么

QuantDinger 是开源的 AI 量化交易自托管平台（Apache 2.0，当前版本 3.0.31）：

> AI 研究 → 策略代码 → 回测 → 模拟盘/实盘执行 → 监控

本仓库 fork 自 [brokermr810/QuantDinger](https://github.com/brokermr810/QuantDinger)。
前端为预构建 Vue 3 SPA（GHCR 镜像，源码在私有 QuantDinger-Vue 仓库），本仓库主要是
**Python 后端 + MCP server + 指标社区示例 + 文档**。

## 仓库地图

| 路径 | 内容 |
|------|------|
| `backend_api_python/` | Flask 后端（核心）。`app/routes/` 薄 HTTP 层 → `app/services/` 业务层 |
| `backend_api_python/app/routes/agent_v1/` | Agent Gateway：`/api/agent/v1` REST 接口（agent 编程主入口） |
| `backend_api_python/app/services/backtest.py` | 回测引擎（信号驱动模拟） |
| `backend_api_python/app/services/strategy_script_runtime.py` | ScriptStrategy 运行时（on_init/on_bar） |
| `backend_api_python/app/services/live_trading/` | 交易所客户端、能力矩阵（`capabilities.py`）、订单契约 |
| `backend_api_python/app/services/trading_executor.py` | 实盘策略循环（遗留热点，改动需谨慎） |
| `backend_api_python/tests/` | pytest 测试；`tests/fixtures/exchanges/` 为免 API key 的交易所契约 |
| `mcp_server/` | Python MCP server，包装 Gateway 的 R/W/B 能力（不含交易） |
| `indicator_community/` | 现成指标策略示例（`free_raw_codes/` 等，可直接参考） |
| `docs/` | 全部文档；`docs/agent/` 为 agent 集成文档（英文） |
| `docker-compose.yml` | 一键部署：postgres:16 + redis:7 + backend(5000) + frontend(8888) |

## 技术栈

- **后端**：Python 3.10+（Docker 镜像 3.12）、Flask 3.1 + flask-smorest（OpenAPI）、gunicorn、PyJWT、bcrypt
- **数据/计算**：pandas、numpy；行情源 ccxt（加密货币）、yfinance、akshare（A 股）、finnhub
- **交易接入**：ccxt（Binance/OKX/Bybit/Bitget/Gate/HTX/Coinbase/Kraken）、alpaca-py、ib_insync（IBKR）、MetaTrader5（Windows）
- **AI**：litellm（多模型网关，策略生成/调参/分析）
- **存储**：PostgreSQL 16（多用户）、Redis 7（缓存）
- **前端**：Vue 3 预构建 SPA（nginx 容器，不在本仓库编译）
- **MCP**：`mcp_server/`（httpx + FastMCP，stdio / sse / streamable-http 三种传输）

## 必读文档（按优先级）

1. [docs/STRATEGY_DEV_GUIDE_CN.md](../../../docs/STRATEGY_DEV_GUIDE_CN.md) — **策略/指标编写教程（核心）**
2. [docs/SIGNAL_EXECUTION_STANDARD_CN.md](../../../docs/SIGNAL_EXECUTION_STANDARD_CN.md) — 信号与执行标准 SSOT（平台级契约）
3. [docs/agent/AGENT_QUICKSTART.md](../../../docs/agent/AGENT_QUICKSTART.md) — Agent Gateway 使用（token、回测 API、四路列契约）
4. [backend_api_python/docs/backend_architecture.md](../../../backend_api_python/docs/backend_architecture.md) — 后端模块边界与重构规则
5. [docs/agent/AI_INTEGRATION_DESIGN.md](../../../docs/agent/AI_INTEGRATION_DESIGN.md) — 新增 agent 端点/工具前必读
6. `docs/CROSS_SECTIONAL_STRATEGY_GUIDE_CN.md`、`docs/API_CONVENTIONS.md` — 按需

本技能附带速查：

- [references/strategy-authoring.md](references/strategy-authoring.md) — 指标/策略编写契约速查（写代码时对照）
- [references/backtest-and-api.md](references/backtest-and-api.md) — 回测与 Agent Gateway / MCP 工作流
- [examples/ema_cross_four_way.py](examples/ema_cross_four_way.py) — 可直接回测的四路信号模板
- [../../docs/策略指标编写新人教程.md](../../docs/策略指标编写新人教程.md) — 零基础通俗教程（K 线/指标/策略概念、第一个双均线策略逐行讲解、三大坑、报错急救表）

## 策略开发 30 秒心智模型

两条 Python 路径：

| 模式 | 形式 | 适用 |
|------|------|------|
| **IndicatorStrategy** | 操作预绑定的 `df`，输出布尔信号列 + `output` 图表字典 | 指标研究、信号型回测、参数调优（**默认从这里开始**） |
| **ScriptStrategy** | `def on_init(ctx)` + `def on_bar(ctx, bar)` 事件驱动 | 有状态逻辑：动态止损、分批、冷却期、bot 执行 |

IndicatorStrategy 强制三层分离：**指标层 → 信号层（布尔列）→ 风险默认配置层（`# @strategy` 注释）**。

最关键的硬性契约（违反即回测失真或被校验拒绝）：

1. **新代码必须输出四路信号列**：`df['open_long']` / `df['close_long']` / `df['open_short']` / `df['close_short']`（bool，与 `len(df)` 等长）。旧式 `buy`/`sell` 两路仅存量兼容。
2. **边缘触发**：禁止每根 bar 连续触发。⚠️ 官方文档的 `s & ~s.shift(1).fillna(False)`
   写法在 pandas 3.x 下**静默失效**（bool 经 shift 变 object，`~` 得到 -1/-2），
   必须用 `prev = s.shift(1).fillna(False).astype(bool); s & ~prev`。
   写完跑 `python examples/_verify_template.py <你的脚本>` 离线自检。
3. **禁止未来函数**：不准 `shift(-1)`；信号在 bar 收盘确认、**下一根开盘价成交**（`next_bar_open`）。
4. **声明退出负责人**：头部注释 `# exit_owner: indicator`（指标信号平仓，须 `trailingEnabled false`）或 `# exit_owner: engine`（引擎止盈止损平仓）。两者窄规则并存会双重平仓。
5. **沙盒限制**：`df/pd/np/params` 已预绑定；import 白名单仅 numpy/pandas/math/json/datetime/time/collections/functools/itertools/statistics/decimal/fractions/copy；禁网络/文件/子进程/eval/exec。
6. **杠杆不写进代码**：`# @strategy` 不支持 `leverage`，杠杆属产品配置层。
7. **数值单位**：`stopLossPct 0.03` = 标的跌 3%；`entryPct 1` = 100% 资金（不是 1%）。

完整规则查 [references/strategy-authoring.md](references/strategy-authoring.md)。

## 回测怎么跑

三条路径，按场景选：

1. **Agent Gateway REST**（推荐给编程 agent）：`POST /api/agent/v1/backtests` 异步任务，
   带 `Idempotency-Key`，轮询 `/jobs/{id}` 或 SSE `/jobs/{id}/stream`。
   代码沙盒额外预绑定内置指标函数 `SMA/EMA/RSI/MACD/BOLL/ATR/CROSSOVER/CROSSUNDER` 和 `call_indicator(...)`。
2. **MCP server**：`validate_indicator_code` → `save_indicator` → `submit_backtest` → `wait_for_job`。
3. **平台 UI**：Indicator IDE 原型 → 保存为策略 → 从持久化策略再跑策略回测（最接近实盘链路）。

需要先有 agent token（人工在 Profile → My Agent Token 签发，scope 至少 `R,B`）。
详见 [references/backtest-and-api.md](references/backtest-and-api.md)。

## 本地开发与验证

```powershell
# 启动全栈（需 Docker；首次复制 env 并设置 SECRET_KEY）
Copy-Item backend_api_python\env.example backend_api_python\.env
docker compose pull; docker compose up -d
# 前端 http://localhost:8888 （默认账号 quantdinger / 123456，登录后改密）

# 后端测试（在 backend_api_python/ 下）
python -m pytest tests/ -q
# Agent Gateway 测试
python -m pytest tests/test_agent_v1.py -q
# 交易所契约冒烟（无需 API key）
python scripts/exchange_smoke_test.py --offline-contracts
python scripts/backend_quality_check.py
```

## 后端改码规则（来自 backend_architecture.md）

- routes 只做 HTTP 解析与 JSON 返回，交易所逻辑禁止写进 routes。
- 新增/删除交易所先改 `live_trading/capabilities.py` 能力矩阵，其它模块从矩阵读取。
- 不要只 patch `pending_order_worker.py` / `trading_executor.py`（遗留热点），优先抽小服务 + 测试。
- 禁止 `except Exception: pass` 吞掉交易核心异常。
- 改实盘路径前先更新 `tests/fixtures/exchanges/` 契约 fixture。

## 安全红线（不可妥协）

- 不提交真实密钥/生产 `.env`/API key/数据库密码；示例一律用占位符。
- Agent 交易默认 **paper-only**；实盘需 token `paper_only=false` **且** 环境变量
  `AGENT_LIVE_TRADING_ENABLED=true` 双重开关，不得绕过或削弱。
- 不添加绕过人工审核的自动实盘下单逻辑，除非用户明确要求并限定范围。
- agent token 仅存哈希（`qd_agent_tokens`），不要记录原始 token；所有调用进 `qd_agent_audit` 审计。
- `docs/agent/` 下新增文档一律英文。
