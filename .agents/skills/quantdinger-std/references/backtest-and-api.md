# 回测与 Agent Gateway / MCP 工作流

> 权威来源：`docs/agent/AGENT_QUICKSTART.md`、`docs/agent/agent-openapi.json`、`mcp_server/README.md`。

## 0. 前置：拿到 agent token

Token 由**人工**签发（agent 不能给自己发 token）：

- UI：Profile → My Agent Token；或
- API：先 `/api/auth/login` 拿用户 JWT，再 `POST /api/agent/v1/me/tokens`
  （body：`name / scopes / markets / instruments / rate_limit_per_min / expires_in_days`）。

完整 token（`qd_agent_...`）只展示一次，服务端仅存哈希。

| Scope | 能力 | 默认 |
|-------|------|------|
| `R` | 读：行情、策略、任务 | 有 |
| `W` | 写工作区：创建/修改指标与策略 | 无 |
| `B` | 回测/实验（异步任务） | 无 |
| `N` | 通知类副作用 | 无 |
| `T` | 交易（默认 paper-only） | 无 |
| `C` | 凭证（仅 admin，不给 agent） | 无 |

写策略 + 回测的标准组合：`R,W,B`。

## 1. REST 回测（推荐路径）

基址：`http://localhost:8888/api/agent/v1`（经前端 nginx 代理）或直连后端 `:5000`。

```bash
# 1) 冒烟
curl -s $BASE/health
curl -s $BASE/whoami -H "Authorization: Bearer $TOKEN"

# 2) 行情
curl -s "$BASE/markets" -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/markets/Crypto/symbols?keyword=BTC&limit=5" -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/klines?market=Crypto&symbol=BTC/USDT&timeframe=1D&limit=10" -H "Authorization: Bearer $TOKEN"

# 3) 提交回测（异步）
curl -s -X POST $BASE/backtests \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key-001" \
  -d '{
        "code": "<IndicatorStrategy Python，见 strategy-authoring.md>",
        "market": "Crypto", "symbol": "BTC/USDT", "timeframe": "1D",
        "start_date": "2024-01-01", "end_date": "2024-03-31",
        "strictMode": true
      }'
# → { job_id, status: "queued" }

# 4) 取结果：轮询或 SSE
curl -s "$BASE/jobs/<job_id>" -H "Authorization: Bearer $TOKEN"
curl -N "$BASE/jobs/<job_id>/stream" -H "Authorization: Bearer $TOKEN"
# SSE 帧：snapshot → progress* → ping* → result；断线用 ?since=<seq> 续传
```

要点：

- `strictMode: true`（默认）= 与实盘对齐的 next-bar-open 路径；`false` = IDE 非严格 MTF 路径。
- `Idempotency-Key` 使重试安全（相同 key 返回原任务）。
- `code` 是**脚本**不是函数：直接改写预绑定 `df`，新增四路布尔列。
- 回测沙盒预绑定：`df / open / high / low / close / volume / np / pd / params /
  call_indicator / SMA EMA RSI MACD BOLL ATR CROSSOVER CROSSUNDER`。

最小可用示例：

```python
fast = SMA(close, 10)
slow = SMA(close, 30)
open_long = CROSSOVER(fast, slow).fillna(False).astype(bool)
open_short = CROSSUNDER(fast, slow).fillna(False).astype(bool)
df['open_long'] = open_long
df['close_short'] = open_long
df['open_short'] = open_short
df['close_long'] = open_short
```

## 2. 指标与策略持久化

```bash
# 编写契约（机器可读）
curl -s $BASE/indicators/authoring-contract -H "Authorization: Bearer $TOKEN"

# 校验不保存（R）
curl -s -X POST $BASE/indicators/validate -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{ "code": "..." }'

# 保存进租户库（W；≤512KiB）
curl -s -X POST $BASE/indicators -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{ "name": "my-ind", "code": "..." }'

# 创建策略（W）——永不自动运行，status 默认 stopped；切 running 需 T scope
curl -s -X POST $BASE/strategies -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "strategy_name": "ma-cross-bot", "strategy_type": "IndicatorStrategy",
        "market_category": "Crypto",
        "trading_config": { "symbol": "BTC/USDT", "timeframe": "1D",
                            "initial_capital": 10000, "leverage": 1 } }'
```

## 3. MCP server 路径

`mcp_server/`（环境变量：`QUANTDINGER_API_BASE`、`QUANTDINGER_AGENT_TOKEN`、
`QUANTDINGER_MCP_TRANSPORT=stdio|sse|streamable-http`）。

工具清单（按工作流排序）：

| 阶段 | 工具 |
|------|------|
| 探查 | `check_health` `whoami` `list_markets` `search_symbols` `get_klines` `get_price` |
| 编写 | `get_indicator_authoring_contract` `validate_indicator_code` `save_indicator` `list_indicators` `get_indicator` |
| 策略 | `list_strategies` `get_strategy` `create_strategy` `update_strategy` |
| 回测 | `submit_backtest` → `wait_for_job` / `stream_job_until_done` / `get_job` `list_jobs` |
| 进阶 | `regime_detect` `submit_experiment_pipeline` `submit_structured_tune` `submit_ai_optimize`（需 `confirm_llm_usage=True`） |
| 持仓 | `list_portfolio_positions` `list_paper_orders` |

MCP **不暴露**：实盘/纸面下单（quick-trade）、token 管理、凭证库——按设计如此，需要时走 REST + 对应 scope。

## 4. 交易（T scope，了解即可，默认别碰）

- 双重门禁：token `paper_only=false` **且** env `AGENT_LIVE_TRADING_ENABLED=true`，否则全部记入
  `qd_agent_paper_orders` 纸面单。
- `POST $BASE/quick-trade/orders`；一键撤纸面单：`POST $BASE/quick-trade/kill-switch`。

## 5. 错误处理

统一信封：`{ code, message, details, retriable }`。

| HTTP | 含义 | 重试 |
|------|------|------|
| 401 | token 无效/过期 | 否（重新签发） |
| 403 | scope/allowlist 不足 | 否 |
| 429 | 每 token 限流 | 60s 后重试 |
| 502 | 上游行情源故障 | 可重试 |
| 501 | 实盘未启用 | 否 |

## 6. 推荐闭环（agent 标准作业流程）

1. `get_indicator_authoring_contract`（或读 `references/strategy-authoring.md`）确认契约。
2. 写 IndicatorStrategy（四路 + 边缘触发 + exit_owner 声明）。
3. `validate_indicator_code` 校验。
4. `submit_backtest`（strictMode=true）→ `wait_for_job`。
5. 检查结果：胜率/回撤/成交明细；信号过密查边缘触发，收益离谱查未来函数。
6. 调参迭代；定稿参数写回源码（代码是单一真相）。
7. `save_indicator` / `create_strategy` 持久化，再从持久化策略跑一次回测核对仓位与成交语义。
