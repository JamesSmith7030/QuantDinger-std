# Vibe-Trading MCP 测试方案

> 创建：2026-07-02（任务 202607021049）｜ 对象：HKUDS/Vibe-Trading v0.1.10 的 MCP 服务器（54 工具）
> 安装状态：`vibe-trading-ai` 已 pip 安装（anaconda Python 3.13），`claude mcp add --scope user vibe-trading -- vibe-trading-mcp` 已注册，健康检查 √ Connected。
> 来源核验：PyPI 发布者 `HKUDS <hkuds@connect.hku.hk>`，与仓库 pyproject.toml 双向吻合。

## 前提

- ⚠️ MCP 工具需**新会话**加载（工具名形如 `mcp__vibe-trading__*`）。注册当时的旧会话看不到。
- L1–L5 全免凭证（OKX/CCXT/yfinance/Eastmoney/FRED 免费源）；仅 L6 swarm 需在 `.env` 配 LLM key。
- 🔒 红线（不可妥协）：全程不在对话提供任何 API key；trading_* 连接器仅验证"未配置时优雅拒绝"；即便日后配置也只走 paper/只读。

## 工具清单速查（实测 54 个，按类）

- **研究**：list_skills / load_skill / start_research_goal / get_research_goal / add_goal_evidence / update_research_goal_status
- **分析**：backtest（文件驱动）/ factor_analysis / analyze_options / pattern_recognition
- **通用**：read_url / read_document / web_search / write_file / read_file
- **数据**：get_market_data / get_fund_flow / get_dragon_tiger / get_northbound_flow / get_margin_trading / get_block_trades / get_shareholder_count / get_lockup_expiry / get_sector_info / get_research_reports / get_stock_news / get_sec_filings / get_financial_statements / get_options_chain / get_stock_profile / screen_market / search_symbol / get_macro_series / iwencai_search
- **交易连接器（只读/受限）**：trading_connections / trading_select_connection / trading_check / trading_account / trading_positions / trading_orders / trading_quote / trading_history
- **Swarm**：list_swarm_presets / run_swarm / get_swarm_status / get_run_result / list_runs

## L0 · 进程冒烟（无需 Claude，已于 2026-07-02 通过 ✅）

```powershell
vibe-trading-mcp --help        # 出 usage 即通过
claude mcp list                # vibe-trading √ Connected 即通过
```

## L1 · 工具发现

> **提示词**：用 vibe-trading MCP 的 list_skills 列出它的金融技能，并告诉我一共有多少个 MCP 工具可用

**通过**：技能清单可列、工具总数 54。
**失败排查**：会话未重启 / anaconda PATH 未生效（`where.exe vibe-trading-mcp` 应指向 anaconda3\Scripts）。

## L2 · 数据层（三市场 + 宏观，各一条）

| # | 提示词 | 测什么 | 通过标准 |
|---|--------|--------|----------|
| 2a | 用 vibe-trading 的 get_market_data 拉 BTC-USDT 最近 30 天日线 OHLCV，给我最新收盘价 | 加密路由（OKX/CCXT） | 与 `okx market ticker BTC-USDT` 偏差 <0.5% |
| 2b | 用 get_fund_flow 查贵州茅台（600519）最近 5 天主力资金净流入，再用 get_northbound_flow 看最近北向资金 | A 股特色数据（现有工具链空白） | 结构化数据非报错；日期为最近交易日 |
| 2c | 用 get_macro_series 拉 FRED 的 10 年期美债收益率（DGS10）最近 10 个观测值 | 宏观源 | 与 datahub `rates_yields` 的 t10y 交叉吻合 |
| 2d | 用 search_symbol 搜 "特斯拉"，再用 get_stock_profile 给我 TSLA 的公司概况 | 符号解析 + 美股 | 正确解析出 TSLA |

## L3 · 回测层（核心）

回测为**文件驱动**：`write_file` 生成 `config.json` + `signal_engine.py` → 调 `backtest`。

> **提示词**：用 vibe-trading MCP 跑一个回测：BTC-USDT 日线，最近 180 天，策略是 MA5/MA20 双均线金叉做多、死叉平仓，初始资金 10000 USDT。先用 write_file 写好 config.json 和 signal_engine.py，再调 backtest，给我总收益率、最大回撤、交易次数

**通过**：产出完整绩效指标；180 天双均线交易次数应为个位数到十几次的合理量级。

## L4 · 交叉验证（对本仓库最有价值）

> **提示词**：把刚才这个 MA5/MA20 双均线策略，按 QuantDinger 的四路信号契约（open_long/close_long/open_short/close_short + 边缘触发 + next_bar_open 成交）改写，通过 QuantDinger Agent Gateway 提交回测，对比两边的收益率和交易次数差异，解释口径差异来源（成交价假设/手续费/信号触发时点）

**通过**：交易**次数**接近（±1~2 次）；收益率差异可被口径解释（vibe-trading 向量化 vs QuantDinger next_bar_open 信号驱动）。
**注意**：差异过大 = 有一方存在前视偏差，属重要发现而非测试失败。QuantDinger 侧记得遵守 pandas 3.x 边缘触发写法（`shift(1).fillna(False).astype(bool)` 后取反）。

## L5 · 安全边界（必测）

| # | 提示词 | 预期 |
|---|--------|------|
| 5a | 用 trading_connections 列出可用券商连接器，再用 trading_check 检查 okx 配置状态 | 列出 ~10 个 profile；check 返回"未配置"且优雅报错，**不得索要密钥** |
| 5b | 用 trading_account 读账户 | 无凭证时明确拒绝，**不产生任何下单行为** |

## L6 · 可选：Swarm 多智能体（需 LLM key）

> **提示词**：用 list_swarm_presets 看有哪些多智能体团队预设，选一个研究型 preset 对 BTC 当前市况跑 run_swarm，用 get_run_result 取最终报告

不配 key 时优雅报错本身也是测试点。配置方式：`.env` 中 `LANGCHAIN_PROVIDER` + 对应 `*_API_KEY`（勿在对话中粘贴 key）。

## 建议执行顺序与预算

L1 → 2a → 2c → L3 → L4 → L5，约 20–30 分钟，L1–L5 零成本；L6 才消耗 LLM token。

## 结果记录

| 级别 | 日期 | 结果 | 备注 |
|------|------|------|------|
| L0 | 2026-07-02 | ✅ | 安装当日通过 |
| L1 | 2026-07-02 | ⚠️ 部分通过 | list_skills 正常（77 个技能）；但会话实际暴露 **36** 个工具而非 54——实装版本是 **0.1.9**（计划针对 0.1.10），缺 get_fund_flow/get_macro_series/search_symbol/get_stock_profile 等全部独立数据工具，多出 shadow-account 系 7 工具 |
| L2 | 2026-07-02 | ⚠️ 2a✅ 其余 N/A | 2a：BTC-USDT 30d 日线正常，最新完整日线收盘 60147.9 vs okx ticker 60360.2，偏差 0.35%<0.5% ✅；替代测试 get_market_data TSLA.US（yfinance 路由）✅ 最新收盘 425.30(7/1)；2b/2c/2d 所需工具在 0.1.9 不存在，N/A |
| L3 | 2026-07-02 | ✅（排障后） | BTC-USDT 180d MA5/MA20：总收益 -3.22%，最大回撤 -9.31%，交易 3 次，胜率 33%，基准 -34.1%/超额 +30.9%。排障 3 项见下方「实测勘误与环境修复记录」 |
| L4 | | | |
| L5 | 2026-07-02 | ✅ | 5a：0.1.9 列出 **4** 个 profile（非计划的 ~10，无 okx 连接器——版本差异）：ibkr-paper-local（默认）/ibkr-live-local-readonly/ibkr-live-official-mcp-readonly/robinhood-live-mcp，全部 readonly 或 mandate 门禁；trading_check 优雅报"127.0.0.1:7497 无 TWS socket、ib_async 未装"，**未索要密钥** ✅。5b：trading_account 明确拒绝（同错误），无任何下单行为 ✅ |
| L6 | | | |

## 实测勘误与环境修复记录（2026-07-02）

1. **版本勘误**：本机实装 vibe-trading-ai **0.1.9**（计划头部写 0.1.10 有误）。0.1.9 无独立数据工具层（get_fund_flow 等 18 个），L2b/2c/2d、工具总数 54 的验收口径仅适用 0.1.10+。
2. **pathlib backport 冲突（已修复）**：anaconda 里遗留 PyPI `pathlib 1.0.1`（py2 backport）遮蔽 stdlib，backtest 子进程直接崩溃。已 `pip uninstall pathlib`。
3. **fastmcp 版本要求错误（上游 bug，已绕过）**：包声明 `fastmcp>=2.14.0`，但代码 `from fastmcp.client.transports.http import ...` 只在 fastmcp 3.x 存在（2.14.7 是 2.x 末版）。已升级 fastmcp 3.4.2（伴随 code-review-graph<3、fastapi/starlette 两条依赖冲突警告，暂未见破坏）。
4. **升级被运行中 MCP 锁死**：pip 升级 0.1.10 时 `vibe-trading-mcp.exe` 被占用，升级中断且旧目录被改名为 `~rc/~acktest/~li` 残留在 site-packages（待清理）。已用「下载 wheel + zipfile 解压」铺上 0.1.10 的 Python 文件；**本会话服务器进程仍是 0.1.9（36 工具），重启会话后才是完整 0.1.10**。
5. **write_file 工具**：0.1.9 直接报 "run_dir is required for write_file"，不可独立使用；用 agent 自己写文件 + backtest 传绝对路径替代。
6. **run_dir 白名单**：backtest 仅接受白名单目录；0.1.9 服务器与 0.1.10 子进程默认白名单的交集是 `~\.vibe-trading\shadow_runs`（0.1.10 起另有 `~\.vibe-trading\runs`）。L3 实际 run_dir：`~\.vibe-trading\shadow_runs\vt_l3_ma_cross`。
7. **成交口径实证**（对 L4 关键）：vibe 回测 = 信号 bar 收盘确认 + **下一根开盘成交**，0.001 手续费按半边 0.0005 嵌入成交价（买 = open×1.0005，卖 = open×0.9995），与 QuantDinger strictMode `next_bar_open` 同口径。L3 三笔交易：3/4 买 73428.7 → 3/22 卖 68809.6（-6.29%）；4/8 买 71342.3 → 5/17 卖 78002.8（+9.34%）；6/19 买 63252.1 → 6/24 卖 60249.8（-4.75%）。
