# QuantDinger Changelog

This document records version updates, new features, bug fixes, and database migration instructions.

---

## V3.0.7 (2026-05-13) — 代码瘦身：Polymarket 预测市场模块全量下线（含前端）

历史遗留的 **Polymarket 预测市场** 模块整套下线。本次一次性清干净：删 5 个后端文件（worker / batch analyzer / single analyzer / route / data_source）+ 2 个后端测试 + 2 个前端文件（API 客户端 + 弹框组件）+ 计费项 + 3 张数据表 + AI 分析里那段「相关预测市场」prompt 上下文 + AI 资产分析页面的「预测市场 tab」+ 10 个 locales 文件里所有翻译条目，**共减少 ≈ 160 KB / 5600+ 行**。

### 🧹 Frontend Removed

- **`ai-asset-analysis` 页面里的「预测市场」tab**：整段 `<a-tab-pane key="polymarket">` 删除，下面挂载的 `<PolymarketAnalysisModal>` 一并删除
- **粘贴 polymarket.com URL 让 AI 单市场分析**的对话框：`components/PolymarketAnalysisModal/index.vue`（24.8 KB）删除 + 配套 API 客户端 `api/polymarket.js` 删除（之前页面打开时 `/api/polymarket/history?page=1&page_size=20` 报 404 就是源自此处）
- **`PredictionMarket` 市场枚举**：从 `ai-asset-analysis` 卡片样式、`indicator-ide` 自选标的列表 / 颜色映射 / CSS 类中全部移除
- **AI 交易雷达**轮播卡片里的 PredictionMarket 分支（`is-prediction` 卡片宽 290px 变体 / `rc-prediction-title` 双行截断标题 / 概率+评分+建议三件套指标项 / 相关 CSS）整段删除，统一回归到「价格 / 24h 涨跌 / 信号」三件套
- **i18n 多语言翻译**：10 个 locales 文件（ar / de / en / fr / ja / ko / th / vi / zh-CN / zh-TW）共 **1087 行** `polymarket.*` / `PredictionMarket` / `predictionmarket` 翻译条目一次性脚本清除，`node --check` 全部语法 OK

### 🧹 Backend Removed

- **后台 LLM worker**：`polymarket_worker.py`（每 30min 调用 OpenAI 批量分析市场）、`polymarket_batch_analyzer.py`、`polymarket_analyzer.py` 全部删除，启动钩子 `start_polymarket_worker()` 移除
- **API 路由**：`/api/polymarket/*`（含 `/analyze`、`/history`）全部下线，`routes/polymarket.py` 删除 + blueprint 注销
- **数据源**：`app/data_sources/polymarket.py`（67 KB，CLOB/Gamma API 客户端 + 本地缓存读写）删除
- **AI 资产分析的 polymarket 上下文段**：`fast_analysis.py` 的 prompt 模板里去掉 `🎯 PREDICTION MARKETS` 段，`market_data_collector.py` 去掉 `include_polymarket` 参数和 `_get_polymarket_events` / `_extract_polymarket_keywords` 私有方法（主分析功能不受影响，只是 prompt 里少一段 30~80 token 的预测市场背景）
- **计费项**：`billing_service.py` 删除 `cost_polymarket_deep_analysis` 单价、`polymarket_deep_analysis` feature 名映射、`feature_costs` 输出
- **未消费的孤儿函数**：`data_providers/opportunities.py::analyze_opportunities_polymarket`
- **测试**：`tests/test_polymarket_slug_lookup.py`、`tests/test_polymarket_url_parsing.py`

### 🗄️ Database

`migrations/init.sql` 删除 3 张相关表的 `CREATE TABLE` 与索引，并加入老库一次性清理迁移（全新部署是 no-op）：

```sql
DROP TABLE IF EXISTS qd_polymarket_asset_opportunities CASCADE;
DROP TABLE IF EXISTS qd_polymarket_ai_analysis CASCADE;
DROP TABLE IF EXISTS qd_polymarket_markets CASCADE;
```

### ⚠️ Upgrade Notes

- **不需要任何手动迁移**：重启后端时 `init_database()` 会自动跑 init.sql，三张 `qd_polymarket_*` 表会被自动清理；如果你之前没有这三张表（新库），DROP 语句是空操作
- **前端缓存**：升级后请用户硬刷一次（Ctrl+Shift+R）清掉 `chunk-vendors.*.js` 旧 bundle，否则浏览器加载缓存的旧 JS 还会去请求 `/api/polymarket/history` 报 404
- **AI 分析效果**：原本 prompt 末尾「相关预测市场事件」段被去掉。该段对最终决策影响很弱（多数标的根本搜不到对应预测市场，且预测市场≠基本面），删除后 LLM 调用平均省 30-80 token，速度略增
- **AI 交易雷达**：后端 `trading_opportunities` 接口不再返回 `market: 'PredictionMarket'` 的卡片（孤儿扫描器已删），前端轮播只剩股票 / 加密 / 外汇三类机会
- **第三方 Adanos 情绪 API 的 `polymarket` 情绪源不受影响** —— 那是 Adanos 提供的舆情数据通道，跟本次下线的 Polymarket 模块是完全独立的两件事，保留

### 💡 Why

后台 LLM 持续在跑但无任何用户出口 = 纯成本：DB 行数、OpenAI token、Python 内存、日志噪声都在白白增长。trim 掉之后，启动日志安静 / 后台线程数 -1 / OpenAI 月账单 -X / DB 体积 -Y（具体取决于历史数据量）。

---

## V3.0.6 (2026-05-13) — USDT 支付重写：单地址 + 金额尾数 + 四链（TRC20 / BEP20 / ERC20 / SOL）

本版只动了一处但动得很彻底：**USDT 收款系统**。原先是每张订单派生一个独立 TRC20 地址（xpub HD 派生），上线后两个痛点暴露得很猛 —— **(1)** 几十个派生地址的资金归集要逐个发 TRC20 转账，每次烧掉的 Energy/Bandwidth 折合 ≈ 1.5 USDT/笔，月度归集成本 = 订单数 × 1.5 USDT；**(2)** 派生地址只能 TRC20，跨链扩展（用户喊了很久要 BSC / ETH / SOL）改造工作量巨大。本版用「**单地址 + 金额尾数识别**」一次性解了这两个坑，并顺手把链扩展到 4 条。

### 🚀 New Features

#### USDT 支付：单地址 + 金额尾数模型（替换原 xpub 派生）
核心想法很简单 —— **不再为每张订单造新地址，所有人都付到同一个主钱包地址；订单的唯一身份藏在「金额尾数」里**。比如基础价 $19.9 的月卡，订单 #A 算出来要付 19.901234 USDT，订单 #B 要付 19.905678 USDT，两笔都到主钱包后我们通过尾数把它们认回原订单：
- **零归集成本**：钱直接进主钱包，再也不需要扫描数十个派生地址做归集转账
- **额外成本 ≤ 0.01 USDT/单**：尾数最大被夹到 0.01 USDT 以内（默认 6 位精度，slot 空间 10000+），用户视觉上「就是普通付款」
- **碰撞防御**：`qd_usdt_orders` 上的 `UNIQUE(chain, amount_usdt) WHERE status IN ('pending','paid')` 偏序唯一索引保证活动订单不会撞到同金额；INSERT 触发碰撞时自动重试不同 seed（默认 10 次）
- **环境变量**：`USDT_AMOUNT_SUFFIX_DECIMALS=6`（建议默认）

#### 4 条链一次性全开：TRC20 / BEP20 / ERC20 / SOL
每条链只需一行环境变量，未配置的链前端自动隐藏：
- `USDT_TRC20_ADDRESS=Txxx...`、`USDT_BEP20_ADDRESS=0x...`、`USDT_ERC20_ADDRESS=0x...`、`USDT_SOL_ADDRESS=base58...`
- 总开关 `USDT_PAY_ENABLED_CHAINS=TRC20,BEP20,ERC20,SOL`（任一项不在白名单内的链下单时被拒）
- 新增 `GET /api/billing/usdt/chains`：返回当前实际可用的链列表（带 `recommended` 徽标 + 典型手续费），UI 据此渲染选择器
- 推荐链：**BSC（≈$0.30/笔）+ Solana（≈$0.0005/笔）** —— 比 TRC20 还省钱

#### 钱包深链 URI 二维码（imToken / MetaMask / TokenPocket / Phantom 一扫即填金额）
每条链生成对应协议的标准 URI 并把它编进二维码，主流钱包扫码后会自动把地址+金额都填好，用户不用手输：
- **EVM (BEP20/ERC20)**：`ethereum:<contract>@<chain_id>/transfer?address=<recipient>&uint256=<raw>` (EIP-681)
- **Solana**：`solana:<recipient>?amount=...&spl-token=<mint>&label=...&message=...` (Solana Pay)
- **TRON**：`tron:<recipient>?asset=USDT&amount=<human>` (TP / imToken 支持，旧版 TronLink 退化为读地址)
- 钱包不识别 URI 时退化为「读地址 + 用户手动填金额」 —— 此时金额复制按钮 + 高亮尾数让用户不会少付

#### 订单页 UI 改造
- 选链 modal：列出每条链 + 典型手续费 + 推荐徽标 + 一键继续
- 支付 modal：二维码大字号显示金额，**末几位尾数高亮成红色**（用户最容易漏看的部分），一键复制金额/地址
- 钱包兼容性 tooltip：根据链类型给出钱包扫码兼容性提示
- 没配置任何链时弹「请联系管理员配置 USDT_*_ADDRESS」的指引，而不是 500

### 🛠️ 工程改进

#### 后端 `app/services/usdt_payment/` 包重构
原 830 行单文件 `usdt_payment_service.py` 拆为分层包：
- `chains.py`：链元数据 / URI 构造 / 金额尾数生成（纯函数，100% 单测覆盖）
- `watchers/`：`tron.py` (TronGrid) / `evm.py` (Etherscan + BscScan 同 endpoint) / `solana.py` (官方 RPC，`getSignaturesForAddress` + `getTransaction` 解析 SPL `preTokenBalances`/`postTokenBalances`)
- `service.py`：订单创建 + 入账匹配 + worker
- 旧路径 `app.services.usdt_payment_service` 保留为 shim，所有现有 import 兼容

#### Watcher 通用约定
四条链共用同一接口 `find_incoming(address, amount, created_at) -> (IncomingTransfer | None, debug_note)`。**精确金额匹配**（±1 微单位容忍 wallets 的尾零截断）是匹配方案 A 的关键 —— 不再像旧版那样接受过付为匹配，否则尾数识别会失效。

#### DB Schema 演进（向后兼容 + 一次性自愈）
`migrations/init.sql` 中的 `qd_usdt_orders` 表加 4 列（`currency` / `amount_suffix` / `payment_uri` / `matched_via`）+ 偏序唯一索引；老库通过 `DO $$ ... ALTER TABLE ADD COLUMN IF NOT EXISTS ...` 自愈，不需要任何停机/手工迁移命令。`address_index` 列保留不删，老订单可继续查看。

#### 15 个新单测 + 130/130 全套绿
- `tests/test_usdt_payment_chains.py`：金额尾数精度 / 重试发散 / URI 构造（4 条链每条断言独立）/ 链选择器 env 解析（缺地址自动隐藏）

### 🐛 修复与清理
- **删除 xpub HD 派生路径**：`bip_utils` 依赖在 USDT 域已无引用（其他场景仍用），新订单完全不走派生
- **TRC20 USDT 合约硬编码地址修正**：之前 `env.example` 默认值 `TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj` 是一个无效占位地址（TronGrid 永远返回空 result），改成 TRC20 USDT 官方合约 `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`

### 🐞 上线后 hotfix（v3.0.6 内）

实战截图发现两个真实痛点，**同版本内**修复：

1. **金额总小数位漂移**（`19.9 → 19.90670000` 八位）
   `qd_usdt_orders.amount_usdt` 列宽 `NUMERIC(20,8)`，比 `USDT_AMOUNT_SUFFIX_DECIMALS=6` 宽 2 位。`Decimal('19.901234')` 量化到 6 位写入后，Postgres 回填成 `19.90123400`（DB 列宽决定的零填充），前端拆字符串就出来 `19.90 + 123400` 的 8 位显示，与第一次创单时返回的 6 位 `19.901234` 不一致。
   - 新增 `chains.format_amount_display()`：统一在 API 出口量化到 `suffix_decimals()` 位
   - `_row_to_dict` / `create_order` 返回值 / `build_payment_uri` 的 URI 金额段全部走这层，前后端永远见到一致的 6 位小数
   - DB 列宽保留 `(20,8)` 作为未来扩展 `USDT_AMOUNT_SUFFIX_DECIMALS=8` 的余量，不做 schema 迁移
2. **关闭支付窗口再打开 = 报错**
   原实现每次点「立即购买」都创建新订单，老 pending 订单留在 DB 里没人管，前端再次开窗时如果偶发后端慢会让用户看到 toast 报错。
   - `create_order` 加幂等性：先查 `(user_id, plan, chain, status='pending', expires_at > now)` 的活跃订单，存在就**复用同一条**返回（同样金额、同样地址、同样剩余过期时间），不创建新行
   - 返回结构加 `reused: bool` 字段；前端 confirmChain 看到 `reused=true` 弹一行轻量 toast「检测到您还有一笔未支付订单，已为您继续展示」
   - 4 个新单测（`test_usdt_payment_idempotency.py`）覆盖：同请求复用 / 不同链不复用 / 不同用户不复用 / 已过期订单不阻塞新建

### 📋 升级须知
1. **重启即可**：DB schema 自治迁移已合入 `init.sql`，不需要手工跑 SQL
2. **配 env 才生效**：把 `USDT_TRC20_ADDRESS=` 等四个变量改成你的主钱包地址；空着的链前端自动隐藏，不会出现在用户的选项里
3. **API Key 可选但强烈建议**：Etherscan / BscScan 不配 Key 时走匿名通道（200 次/天），少量订单可用；Solana 默认走官方公开 RPC（足够小流量），高流量建议换 Helius / QuickNode 私有 RPC（`SOLANA_RPC_URL`）
4. **TRON 合约地址默认值变更**：升级后请用 `env.example` 里的新默认 `TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t`，旧 `.env` 里如果显式配了无效占位务必更新

### 📂 关键文件
| 文件 | 用途 |
|---|---|
| `backend_api_python/app/services/usdt_payment/chains.py` | 4 条链元数据 / URI 构造 / 金额尾数 |
| `backend_api_python/app/services/usdt_payment/watchers/*.py` | 4 条链入账扫描器 |
| `backend_api_python/app/services/usdt_payment/service.py` | 订单流程 + worker |
| `backend_api_python/app/services/usdt_payment_service.py` | 向后兼容 shim |
| `backend_api_python/migrations/init.sql` | `qd_usdt_orders` 新列 + 偏序唯一索引 + 自愈 migration |
| `backend_api_python/env.example` | 新 env 变量（4 链地址 / 浏览器 Key / 尾数精度） |
| `backend_api_python/app/routes/billing.py` | 新增 `/usdt/chains`，`/usdt/create` 接收 `chain` 参数 |
| `QuantDinger-Vue-src/src/views/billing/index.vue` | 选链 modal + URI 二维码 + 尾数高亮 |
| `QuantDinger-Vue-src/src/api/billing.js` | `listUsdtChains()` / `createUsdtOrder(plan, chain)` |
| `backend_api_python/tests/test_usdt_payment_chains.py` | 15 个新单测 |

---

## V3.0.5 (2026-05-13) — Alpaca / Smart Tuning v2 / IS-OOS 双面板 / 经纪商统一面板 / DB 启动自愈

本版合并了过去两周累积的「让回测更科学、让多券商管理更顺手、让本地部署更不容易踩坑」的改动。其中**回测科学性**是这次最值得说的事——之前智能调参在训练段（IS）上给出 +36% 头条数字，用户把参数应用回完整窗口跑出 -24%，这种沉默过拟合是本次重点修复对象。同时新增 **Alpaca Markets** 作为第三家「传统经纪商」适配器，与 IBKR / MT5 平级。

### 🚀 New Features

#### Alpaca Markets 适配器（美股 / ETF / 加密货币 · paper + live）
作为第三种「传统经纪商」并入 QuantDinger，与 IBKR / MT5 平级（来源 [PR #101](https://github.com/brokermr810/QuantDinger/pull/101)）：
- **覆盖**：US 股票、ETF、加密货币现货；纸面 (`paper-api.alpaca.markets`) 和真实 (`api.alpaca.markets`) 账户均可
- **adapter**：`backend_api_python/app/services/alpaca_trading/`（client / symbols / 错误规范化 / OHLCV）
- **路由**：`/api/alpaca/connect|status|account|positions|orders|symbols`
- **多租户**：与 IBKR 一起接入新的 `BrokerSessionRegistry`，每个用户独立 client，不再共享全局连接
- **零 referral 干扰**：审过整个适配器代码，无 referral / partner code 类隐藏标识

#### 统一经纪商账户页面（`/broker-accounts`）
原先 IBKR / MT5 / Alpaca / 加密货币交易所的连接入口散落在不同位置，现合并为一个统一管理页：
- 头部摘要 + Alpaca / IBKR / MT5 三个 panel（连接表单 + 账户 KPI + 持仓表 + 挂单表 + 一键撤单）
- 加密货币交易所凭据作为一张独立卡片列出，复用现有 `ExchangeAccountModal`
- 前端通过 `src/api/broker.js` 统一各家不一致的端点结构

#### 智能调参 v2（Smart Tuning）—— 多参数策略真正可用
之前的「智能调参」实际只扫止盈 / 止损 / 杠杆 3 个维度，RSI / MACD / EMA / ATR 这种多参数策略基本无法调参。本版把它做成真正的多维寻优：
- **P1 · 自动推断 sweep 范围**：指标里写 `# @param rsi_len int 14 RSI period` 就够，不用手写 `range=`，前端基于 default × `[0.5, 0.75, 1, 1.25, 1.75]` 自动生成扫参网格（int 类型自动取整、去重）
- **P2 ·「可调维度」面板**：在结构化调参卡片里一目了然列出所有维度（带 risk / position / leverage / `@param` declared / `@param` inferred 五色徽标），实时显示完整笛卡尔积大小与候选预算，每个维度都可勾选取消
- **P3 · 维度爆炸自动切 DE**：完整笛卡尔积 > 候选预算 × 10 时（默认 480），grid 自动切换到 Differential Evolution，避免「扫了等于没扫」，UI 显示蓝色提示「已自动切换到 DE」
- **P4 · trailing 维度自动加入**：策略 `@strategy trailingEnabled=true` 时，自动追加 `trailing.pct` 和 `trailing.activationPct` 两个扫参维度

#### IS-OOS 双面板 + 应用按钮分流
解决了一个长期沉默的过拟合陷阱（智能调参在 70% 训练段上给 +36% 头条数字，应用到完整窗口含 30% 验证段后跑出 -24%，但 UI 上完全看不出来）：
- **最佳候选卡片** 改成 IS / OOS 并排展示，红框警示「OOS 退化 X%，疑似过拟合」
- **原来的「应用最佳参数」按钮拆成三个动作**：
  - 应用并在训练段验证（复现 +36% 头条数字）
  - 应用并在完整窗口跑（含 OOS 段，看真实表现）
  - 只应用参数（不立即跑回测）
- 后端 `ExperimentRunnerService._build_best_output` 暴露 `oosSummary` / `oosScore` / `oosDegradation` / `oosOverfit` 给前端

#### Crypto 行情时间框架后端 resample
当交易所原生不提供某个时间框架（如 OKX 没有 30m）时，后端自动取更细粒度的 OHLCV 数据并按交易所对齐 resample。前端无需关心，13 个新单测覆盖（来源 [PR #104](https://github.com/brokermr810/QuantDinger/pull/104)）。

### 🛠️ 工程改进

#### 数据库启动自治（解决「本地 PG 部署 `relation does not exist` / `权限不够` 满屏」）
之前本地 PostgreSQL（非 docker）部署必须手工 `psql -f migrations/init.sql` 才能建表，否则 worker 起来满屏 `relation "pending_orders" does not exist` / `qd_strategy_positions 权限不够`；docker 部署不会踩这个坑（容器 entrypoint 自动跑 init.sql）。现在：
- `init_database()` 每次启动**自动 apply** `migrations/init.sql`（全幂等 `CREATE TABLE IF NOT EXISTS`，docker 二次跑无害）
- 启动后做一次轻量**权限自检**：对 `qd_users` / `pending_orders` / `qd_strategy_positions` / `qd_strategies_trading` / `qd_analysis_memory` 五个关键表跑 `SELECT 1 LIMIT 0`，任何 `InsufficientPrivilege` 失败立刻打头条 banner 给出 `ALTER TABLE OWNER` 修复配方，而不是让权限错误淹在每秒的 worker 日志里
- 新 env: `SKIP_AUTO_MIGRATE=true` 作为外部 schema 管理（Flyway / Liquibase / DBA 手工）的逃生口

#### 多租户经纪商会话（`BrokerSessionRegistry`）
`backend_api_python/app/utils/broker_session.py` 提供按 `(user_id, broker_name)` 缓存的 client 注册表，加 `threading.Lock` 保护。把原本 IBKR / Alpaca 共用全局 `_client` 改为按用户隔离，避免「一个用户重连把所有用户踢下线」。

#### OAuth `FRONTEND_URL` 支持多前端
`backend_api_python/app/services/oauth_service.py` 现在把 `FRONTEND_URL` 解析为逗号分隔列表：第一个作为默认登录后重定向 origin，全部作为 OAuth 重定向白名单。便于一套后端同时给 `ai.quantdinger.com` + `m.quantdinger.com` 两个域提供服务。

#### 默认指标精简 + SuperTrend 示例国际化
新用户注册原本默认塞 4 个内置指标，现简化为 **1 个高质量 SuperTrend 示例**：全英文注释 + `@param` 范围标注 + Wilder ATR 平滑、路径依赖 SuperTrend 计算的标准实现，开箱即跑且展示推荐的多参数策略写法。

### 🐛 Bug 修复

- **指标市场综合评分全为 0**（V3.0.4，已合并入本版）：`community_service.py` 读字段拼错（`'overall'` 实际字段是 `'overallScore'`），所有上架策略综合分都显示 0；4 个回归测试补齐
- **风险-收益分布坐标轴单位错误**：散点图坐标轴单位把已经是百分比的 `totalReturn` / `maxDrawdown` 再乘 100，显示为「百分之好几千」，已修
- **`runBacktest` 时间窗口覆盖**：方法签名加入 `options.dateRangeOverride`，允许「应用并在训练段验证」这种行为复用完整 `runBacktest` 路径
- **i18n key 漏写**：调参维度面板部分 label 直接显示 `indicatorIde.stopLossPct` 而不是「止损 (%)」—— 补齐 4 个缺失 key × 10 locale (`stopLossPct` / `takeProfitPct` / `trailingStopPct` / `trailingActivationPct`)，并把 label 解析改用 `$te()`（translation exists 检查）防御未来再有遗漏
- **Smart Tuning 12 个 IS/OOS 相关 i18n key** 同步铺到 10 个 locale

### ⚙️ 配置变化

| 变量 | 默认 | 作用 |
|---|---|---|
| `SKIP_AUTO_MIGRATE` | `false` | 启动时不自动 apply `migrations/init.sql`（外部 schema 管理时设 true） |
| `FRONTEND_URL` | `http://localhost:8080` | 现支持逗号分隔多个 origin，全部进 OAuth 白名单；第一个作默认重定向 |

### ✅ 测试

新增 14 个回归测试，全套 **115/115 通过**：
- `tests/test_db_bootstrap.py` —— 6 个（auto-migrate 幂等 / `init.sql` 缺失兜底 / SQL 失败不崩 / `_verify_table_access` 全绿 / 多个权限失败汇总 banner / `SKIP_AUTO_MIGRATE` 逃生口）
- `tests/test_experiment_services.py::test_evolution_sweeps_indicator_level_params` —— 1 个（确认 `indicator_params.atr_period` 路径走通 snapshot + overrides）
- `tests/test_experiment_best_output.py` —— 3 个（OOS metrics surfacing：`oosSummary` / `oosScore` / `oosDegradation` / `oosOverfit`）
- `tests/test_market_indicator_score.py` —— 4 个（综合评分 `'overall'` → `'overallScore'` 拼写错误回归）

ESLint 对所有触及的 `.vue` / `.js` 文件全绿。

### 📦 兼容性 / 升级建议

- **零破坏性升级**：所有 backend 路由、env 变量、数据库表 schema 全部向后兼容
- **数据库**：首次启动会自动 apply `migrations/init.sql`；如果你的 PG 用户不是表 owner，启动日志里会出 banner 指引你跑一次 `ALTER TABLE ... OWNER TO <user>;` 一键修好
- **前端**：需要 build `QuantDinger-Vue-src` 并替换 `frontend/dist`（仓库内 `frontend/dist` 已经包含本次构建产物）
- **Alpaca**：需要在生产 `requirements.txt` 加 `alpaca-py>=0.30.0`，或本地 `pip install alpaca-py`（已在 `backend_api_python/requirements.txt` 中加好）

### 🗂️ 文件改动概览

- 后端：`app/services/alpaca_trading/*`、`app/routes/alpaca.py`、`app/services/experiment/runner.py`、`app/services/builtin_indicators.py`、`app/services/oauth_service.py`、`app/utils/db.py`、`app/utils/broker_session.py`、`app/services/community_service.py`
- 前端：`src/views/indicator-ide/index.vue`、`src/views/broker-accounts/*`、`src/api/broker.js`、`src/locales/lang/*.js`（10 个 locale + 16 个新 key）
- 文档：`README.md` + 6 个 `docs/README_*.md`（badge → 3.0.5 / 加入 Alpaca）、`env.example`（新 `SKIP_AUTO_MIGRATE`）

---

## V3.1.0 (2026-05-02) — AI Agent Gateway / MCP HTTP / SSE 进度流 / Admin UI

把 QuantDinger 从「只服务人类用户的 Web 产品」扩展成「同时面向人类和 AI Agent 的两栈产品」。给 OpenClaw / NanoBot / Claude Code / Cursor / Codex 这类 Agent 运行时配齐了：受控的 HTTP 网关、按 Scope 的细粒度授权、异步任务 + 实时进度、MCP 接入、Admin 后台运维面板，以及一份机器可读的契约（OpenAPI 3.0）。**所有 Agent 入口默认拒绝实盘交易**——T 类（Trading）即便给到 Agent，也走纸面订单簿，需要管理员显式开启服务器级开关后才可能走真实交易所。

### 🚀 New Features

#### Agent Gateway（`/api/agent/v1`）
全新的、与人类 JWT 完全隔离的机器对机器 API：
- **Token 模型**：管理员一次性签发 `qd_agent_xxxx` 令牌，存库时只保留 SHA-256 哈希；支持自定义 scopes (`R / W / B / N / C / T`)、市场白名单、品种白名单、`paper_only`、速率上限、过期时间。
- **Capability Classes**：每个端点声明唯一一个 risk class —— **R**(Read) / **W**(Workspace write) / **B**(Backtest) / **N**(Notify) / **C**(Credentials, admin only) / **T**(Trading, paper-only by default)。
- **审计日志**：每一次 Agent 调用（成功、被拒、429）都追加到 `qd_agent_audit`，含路由、scope class、状态码、耗时与脱敏后的请求/响应摘要。
- **速率限制 + 幂等**：基于 token 的进程内滑动窗口；W/B/T 类支持 `Idempotency-Key` 头，重复 key 直接返回原始 job，不再重复执行。
- **异步任务**：长任务（回测、实验流水线、AI 优化）通过进程内 `ThreadPoolExecutor` 入队，写入 `qd_agent_jobs`，客户端走「提交 → 轮询 / SSE」模式；workers 数和实盘开关都走 env 控制。
- **Tenant 隔离**：`token → user_id → 资源`；任何 Agent 都看不到其他用户的策略、订单、审计或任务。

实现的端点（与 `docs/agent/agent-openapi.json` 一一对应）：
| 类别 | 路径 | Class | 说明 |
|---|---|---|---|
| Health | `GET /health` · `GET /whoami` | – / R | 公开存活 / token 自省 |
| Markets | `GET /markets` · `/markets/{m}/symbols` · `/klines` · `/price` | R | 行情 |
| Strategies | `GET /strategies` · `GET/POST/PATCH /strategies/{id}` | R / W | 状态切到 `running` 需 T |
| Backtests | `POST /backtests` | B | 异步，返回 `job_id` |
| Experiments | `POST /experiments/{regime/detect, pipeline, structured-tune, ai-optimize}` | B | regime 同步、其余异步 |
| Jobs | `GET /jobs` · `GET /jobs/{id}` · `GET /jobs/{id}/stream` | R | 列表 / 单查 / **SSE 实时流** |
| Portfolio | `GET /portfolio/positions` · `/portfolio/paper-orders` | R | 持仓 / 纸面成交 |
| Quick-Trade | `POST /quick-trade/orders` · `POST /quick-trade/kill-switch` | T | 默认走纸面簿 |
| Admin | `POST/GET /admin/tokens` · `DELETE /admin/tokens/{id}` · `GET /admin/audit` | – | 仅人类 JWT |

#### SSE 实时进度（`GET /api/agent/v1/jobs/{id}/stream`）
长任务（`ai-optimize` / `structured-tune` / 多轮回测流水线）现在能让 LLM 客户端「边跑边看」：
- 帧类型：`snapshot`（首帧给基线）→ `progress`（每次 runner `on_progress` 触发）→ `ping`（~15s 心跳，防代理掐线）→ `result`（终态后立刻收尾）。
- 断点续传：`?since=<seq>` 或标准 `Last-Event-ID` 头。
- 任务已结束时直接给 `snapshot + result` 后关闭，客户端无需写两套逻辑。
- Runner 接入约定：`runner(payload, on_progress)` 第二参数自动被探测到，事件同时投递给 SSE 订阅者并写入 `qd_agent_jobs.progress` JSONB（断线重连可读取最新快照）。

#### MCP Server（`mcp_server/` —— 已发布到 PyPI: [`quantdinger-mcp`](https://pypi.org/project/quantdinger-mcp/)）
独立 Python 包，把 Agent Gateway 的 R / B 子集包成 Model Context Protocol 工具：
- 一行装好（任意机器，不用 clone 仓库）：`uvx quantdinger-mcp` / `pipx install quantdinger-mcp` / `pip install quantdinger-mcp`。
- 三种 transport，由环境变量 `QUANTDINGER_MCP_TRANSPORT` 选：
  - `stdio`（默认）—— 桌面 IDE（Cursor / Claude Code）以子进程启动
  - `sse` —— 仅支持 SSE 的客户端
  - `streamable-http` —— 新版 MCP HTTP 协议，云端 Agent / 远程 IDE 直连
- HTTP 模式额外读 `QUANTDINGER_MCP_HOST` / `QUANTDINGER_MCP_PORT`。
- 永远只接 Agent token，**绝不要写人类 JWT 或交易所 Key**。

#### 前端 Admin UI：Agent Tokens 面板（仅 admin）
集成进现有 Vue 后台（与「用户管理」「系统设置」并列）：
- 路由 `/agent-tokens`，权限 `permission: ['admin']`。
- **Tokens 标签**：列表（含彩色 scope tag、market 白名单、paper-only / live-eligible 状态、最后使用时间）+ 撤销按钮。
- **签发弹窗**：scope 多选、市场/品种白名单、速率、过期天数、`paper_only` 开关；勾 T 但关 paper-only 时给红色警告提示需要服务器端 `AGENT_LIVE_TRADING_ENABLED=true`。
- **Reveal 弹窗**：完整 token **只显示一次**，自带复制到剪贴板。
- **Audit 标签**：method / route / scope class / status / 耗时；status 用色阶（5xx 红、429 橙、4xx 火、2xx 绿）。
- i18n：`en-US` + `zh-CN` 各加约 30 个 `agentTokens.*` key，其它语言走英文 fallback。

#### 系统架构图
README 顶部插入了一张端到端架构图（`docs/screenshots/architecture.png`），中英两份 README 同步。

### 🛠️ Tooling / Docs

- `docs/agent/AGENT_ENVIRONMENT_DESIGN.md` —— 三层契约（Documentation → Command → Machine Interface）总览，约束 Cursor / Claude Code / Codex 这类**写代码**的 Agent。
- `docs/agent/AI_INTEGRATION_DESIGN.md` —— 把 QuantDinger 当**产品**消费的 Agent 设计文档（personas、capability classes、安全、Roadmap、实施进度表）。当前进到 v0.3。
- `docs/agent/AGENT_QUICKSTART.md` —— 操作手册：从签 token、`/whoami`、读行情、跑回测、SSE 监听到 MCP 接入的逐步 `curl` 例子。
- `docs/agent/agent-openapi.json` —— OpenAPI 3.0 契约，含所有 `/api/agent/v1/...` 路径 + `x-scope-class` 自定义扩展。
- `.cursor/skills/quantdinger-agent-workflow/SKILL.md` —— 给 Cursor / Claude Code 用的 Skill，告诉 Agent 在本仓库改代码时的红线、入口、验证方式。
- `mcp_server/README.md` —— MCP 三种 transport 的部署示例。

### ⚙️ Configuration

新增（全部可选）环境变量，默认即安全：

| 变量 | 默认 | 作用 |
|---|---|---|
| `AGENT_JOBS_MAX_WORKERS` | `4` | Agent 异步任务线程池大小 |
| `AGENT_LIVE_TRADING_ENABLED` | `false` | **服务器级实盘开关**。即使某个 token `paper_only=false`，没开这个开关也只走纸面 |
| `QUANTDINGER_MCP_TRANSPORT` | `stdio` | MCP 客户端连接方式 (`stdio` / `sse` / `streamable-http`) |
| `QUANTDINGER_MCP_HOST` | `127.0.0.1` | MCP HTTP 模式 bind host |
| `QUANTDINGER_MCP_PORT` | `8000` | MCP HTTP 模式 bind port |

### ✅ Tests

- `backend_api_python/tests/test_agent_v1.py` —— 9 个用例：缺 token / 未知 token / inactive / expired token / scope 不足 / 速率限制 / token 生成格式等。
- `backend_api_python/tests/test_agent_jobs_progress.py` —— 5 个用例：runner 签名探测、有序累积、`since_seq` 续传、idle 超时、跨线程实时投递。
- `mcp_server/tests/test_transport_resolution.py` —— 4 个用例：默认 transport、别名解析、未知值优雅退出、HTTP settings shim。安装 `mcp` 包后才会跑，否则 `importorskip` 跳过。

后端跑出 **58 passed**（53 个 Gateway 测试 + 5 个 SSE 测试）。

### 🗄️ Database Migration

本版新增 4 张表 + 1 个 JSONB 列，全部由 `agent_auth._ensure_schema` 在第一次接到 Agent 请求时**自动幂等创建**，所以**已运行的部署什么都不做也能正常用**。但建议在升级时统一显式执行下面的 SQL，确保索引齐全：

```sql
-- ============================================================
-- QuantDinger V3.1.0 Database Migration
-- Agent Gateway: tokens / async jobs / audit / paper orders
-- ============================================================

-- 1. Agent tokens (one row per issued token; only the SHA-256 hash is stored)
CREATE TABLE IF NOT EXISTS qd_agent_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    name VARCHAR(80) NOT NULL,
    token_prefix VARCHAR(24) NOT NULL,
    token_hash VARCHAR(128) NOT NULL,
    scopes TEXT NOT NULL DEFAULT 'R',
    markets TEXT NOT NULL DEFAULT '*',
    instruments TEXT NOT NULL DEFAULT '*',
    paper_only BOOLEAN NOT NULL DEFAULT TRUE,
    rate_limit_per_min INTEGER NOT NULL DEFAULT 60,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_tokens_hash   ON qd_agent_tokens(token_hash);
CREATE INDEX        IF NOT EXISTS idx_agent_tokens_user   ON qd_agent_tokens(user_id);
CREATE INDEX        IF NOT EXISTS idx_agent_tokens_status ON qd_agent_tokens(status);

-- 2. Agent async jobs (backtests / experiments / ai-optimize / ...)
CREATE TABLE IF NOT EXISTS qd_agent_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_id VARCHAR(40) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    agent_token_id INTEGER REFERENCES qd_agent_tokens(id) ON DELETE SET NULL,
    kind VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    request JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    error TEXT,
    progress JSONB,                      -- NEW in V3.1.0: latest snapshot for SSE cold reconnects
    idempotency_key VARCHAR(120),
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);
-- Safe to run even if the table existed (e.g. _ensure_schema already created
-- the V3.0 shape without `progress`):
ALTER TABLE qd_agent_jobs ADD COLUMN IF NOT EXISTS progress JSONB;

CREATE INDEX        IF NOT EXISTS idx_agent_jobs_user   ON qd_agent_jobs(user_id);
CREATE INDEX        IF NOT EXISTS idx_agent_jobs_status ON qd_agent_jobs(status);
CREATE INDEX        IF NOT EXISTS idx_agent_jobs_kind   ON qd_agent_jobs(kind);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_jobs_idem
    ON qd_agent_jobs(agent_token_id, kind, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- 3. Append-only audit log (every agent call, including denials)
CREATE TABLE IF NOT EXISTS qd_agent_audit (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    agent_token_id INTEGER,
    agent_name VARCHAR(80),
    route VARCHAR(160) NOT NULL,
    method VARCHAR(8) NOT NULL,
    scope_class VARCHAR(4) NOT NULL,
    status_code INTEGER NOT NULL,
    idempotency_key VARCHAR(120),
    request_summary JSONB,               -- redacted by _redact() before insert
    response_summary JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_audit_user  ON qd_agent_audit(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_audit_token ON qd_agent_audit(agent_token_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_audit_class ON qd_agent_audit(scope_class);

-- 4. Paper-only ledger so T-class tokens can simulate without ever
--    touching live exchange credentials.
CREATE TABLE IF NOT EXISTS qd_agent_paper_orders (
    id BIGSERIAL PRIMARY KEY,
    order_uid VARCHAR(40) NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    agent_token_id INTEGER REFERENCES qd_agent_tokens(id) ON DELETE SET NULL,
    market VARCHAR(40) NOT NULL,
    symbol VARCHAR(60) NOT NULL,
    side VARCHAR(8) NOT NULL,
    order_type VARCHAR(16) NOT NULL DEFAULT 'market',
    qty DECIMAL(28,10) NOT NULL,
    limit_price DECIMAL(28,10),
    fill_price DECIMAL(28,10),
    fill_value DECIMAL(28,10),
    status VARCHAR(16) NOT NULL DEFAULT 'filled',
    note TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agent_paper_orders_user  ON qd_agent_paper_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_paper_orders_token ON qd_agent_paper_orders(agent_token_id);

DO $$ BEGIN RAISE NOTICE '✅ QuantDinger V3.1.0 agent gateway schema migration completed!'; END $$;
```

**Docker 一行示例：**

```bash
docker compose exec -T postgres psql -U quantdinger -d quantdinger \
  -f /app/migrations/init.sql   # 全 idempotent，可重复执行
```

或者把上面的 SQL 单独存盘后：

```bash
docker cp /path/to/v3.1.0_agent_gateway.sql quantdinger-db:/tmp/migrate.sql
docker compose exec -T postgres psql -U quantdinger -d quantdinger -f /tmp/migrate.sql
```

**Migration Notes：**
- 所有语句都用了 `IF NOT EXISTS`，**重复执行安全**。
- 不修改、不删除任何已有数据。
- 没设置 `AGENT_LIVE_TRADING_ENABLED=true` 之前，T 类调用永远只写 `qd_agent_paper_orders`，不会触发 `TradingExecutor`。
- 4 张表都按 `user_id` 做 tenant 隔离；删除用户会级联清理对应的 token / job / paper-order，audit 因为有可能要事后追责，是软关联（`agent_token_id INTEGER`，无外键级联）。

### 📦 Files Changed

**Backend (`backend_api_python/`):**
- `migrations/init.sql` — 新增 Section 30「Agent Gateway」，4 张表 + `progress` JSONB 列 + 索引
- `app/utils/agent_auth.py` — token 鉴权、scope/allowlist 校验、速率限制、`_audit + _redact`、`with_idempotency`、`_ensure_schema` 运行时建表
- `app/utils/agent_jobs.py` — 异步 job runner、`on_progress` 探测、SSE 事件环（`deque(maxlen=200)` + `threading.Event`）、`stream_progress(...)` 生成器、`progress` 列持久化
- `app/routes/agent_v1/__init__.py` + `_helpers.py` + `health.py` + `markets.py` + `strategies.py` + `backtests.py` + `experiments.py` + `jobs.py`(含 SSE) + `portfolio.py` + `quick_trade.py` + `admin.py`
- `app/routes/__init__.py` — 注册 `agent_v1_bp`
- `env.example` — 新增 `AGENT_JOBS_MAX_WORKERS`、`AGENT_LIVE_TRADING_ENABLED`
- `tests/test_agent_v1.py`、`tests/test_agent_jobs_progress.py`

**MCP server（新增包）：**
- `mcp_server/pyproject.toml`、`mcp_server/README.md`
- `mcp_server/src/quantdinger_mcp/{__init__.py, server.py}` — `FastMCP` + `httpx`，三种 transport via env
- `mcp_server/tests/test_transport_resolution.py`

**前端（`QuantDinger-Vue-src/` + 同步打包到 `frontend/dist/`）：**
- `src/api/agent.js` — Agent admin API client
- `src/views/agent-tokens/index.vue` — Tokens / Audit 双标签页面
- `src/config/router.config.js` — 新路由 `/agent-tokens`，`permission: ['admin']`
- `src/locales/lang/{en-US,zh-CN}.js` — `menu.agentTokens` + 约 30 个 `agentTokens.*` key
- `frontend/dist/` — 重新打包并替换（101 个文件，约 18.9 MB；含 agent-tokens 路由代码与 zh-CN i18n）

**文档：**
- `docs/agent/AGENT_ENVIRONMENT_DESIGN.md`、`docs/agent/AI_INTEGRATION_DESIGN.md`（v0.3）、`docs/agent/AGENT_QUICKSTART.md`、`docs/agent/agent-openapi.json`、`docs/agent/README.md`
- `.cursor/skills/quantdinger-agent-workflow/SKILL.md`
- `README.md` + `docs/README_CN.md` — 顶部插入架构图 + 文档导航补充 Agent 相关链接
- `docs/screenshots/architecture.png` — 端到端架构图

### 🗑️ Removed

- `.github/dependabot.yml` — 关闭 Dependabot，避免每周冒出 11 个噪音分支（大量 npm `vue-cli` v6 / webpack v5 升级会和当前 Vue 2 + webpack 4 链路硬冲）。

### ⚠️ Operational notes

1. **第一次启动可以不跑 SQL**：Agent Gateway 第一次接到请求时会自动建表（`_ensure_schema`）。但建议升级时统一执行上面的迁移以保证索引齐全。
2. **实盘开关默认关**：`AGENT_LIVE_TRADING_ENABLED` 不设或非 `true`，T 类 token 即便配置了 `paper_only=false` 也只走 `qd_agent_paper_orders`。这是产品级红线，请勿在文档/代码里弱化。
3. **签发的 token 不可恢复**：库里只存 SHA-256 hash，前端 reveal 弹窗关掉就找不回了，丢了只能撤销重签。
4. **MCP HTTP 模式生产部署**：`streamable-http` 默认 bind 到 `127.0.0.1`，对外暴露请显式设 `QUANTDINGER_MCP_HOST=0.0.0.0` 并放到 nginx / 反代后面，**只让带 Agent token 的客户端访问**。

---

## V3.0.2 (2026-04-11) — 多语言文件全量补齐(AI 自动翻译)

### 🌍 i18n

此前除 `zh-CN` / `en-US` 外,其余 7 个语言文件只有约 2000/4240 条(约 48% 覆盖),大量界面字段会回退到英文或 key 名。这次用 DeepSeek 把全部缺失 key 一次性批量翻译、写回源文件:

| 语言 | 修复前 | 修复后 | 新增条目 |
|---|---|---|---|
| `ar-SA` Arabic  | 2029 | **4573** | 2541 |
| `de-DE` German  | 2077 | **4573** | 2491 (+patch) |
| `en-US` English | 4424 | **4498** | 72 |
| `fr-FR` French  | 2029 | **4573** | 2539 (+patch) |
| `ja-JP` Japanese| 2033 | **4573** | 2537 (+patch) |
| `ko-KR` Korean  | 2034 | **4573** | 2537 (+patch) |
| `th-TH` Thai    | 2029 | **4573** | 2541 (+patch) |
| `vi-VN` Vietnamese | 1759 | **4495** | 2734 (+patch) |
| `zh-TW` Traditional | 3741 | **4499** | 758 |

全部 9 个语言文件相对 `zh-CN` 基准 **missing = 0** ✅

### 🛠️ Tooling (新增)

- **`scripts/i18n-diff.js`** — 扫描所有 locale 文件,以 `zh-CN` 为基准报告 missing / extra keys;支持 `--detail`、`--lang=xx-YY` 查看具体缺失。
- **`scripts/i18n-fill-ai.js`** — 增量 AI 翻译工具。支持 DeepSeek / Anthropic / OpenAI / OpenRouter 四家 provider,批量(默认 80/batch)+ 并发(默认 6)+ 本地缓存(`scripts/.i18n-cache/`)+ 自动备份(`*.js.bak`),字符串值按安全追加方式写回文件。失败批次 3 次重试 + 部分保留策略。保护占位符 `{foo}`、`<code>…</code>`、换行符 `\n`、HTML 标签、`BTC/ETH/USDT/AI/MT5` 等专有名词。
- **`scripts/i18n-patch-specials.js`** — 一次性补齐 AI 脚本无法覆盖的特殊 key:空字符串值、嵌套对象值(`trading-assistant.brokerNames`)、中文量词单字(`dashboard.unit.trades` / `.strategies` 等在西语/泰/越留空)。
- **`scripts/README.md`** — 工具链说明,含典型用法、API Key 配置、成本估算、质量提示。
- **`.gitignore`** — 忽略 `scripts/.i18n-cache/` 与 `QuantDinger-Vue-src/src/locales/lang/*.bak`。

### 翻译质量

专用术语已落地行业译法:网格(`neutral/long/short`)、Maker/Taker 指值/市价、加仓/平仓、止盈/止损、浮动盈亏、权益、仓位、挂单、成交等。占位符 / `<code>` 标签 / 代码示例全部保留。单次批量失败率 < 0.2%,失败 key 已由 specials 脚本兜底。

### ⚠️ 已知事项(后续改进)

- **`ja-JP` / `zh-TW` 等部分"已存在但值是英文"的 key 未被重译**:脚本只填「完全缺失」的 key,不覆写已有值。若要纠正这部分"占位英文",需要单独一次「识别非目标语言内容并重译」的增强扫描。

### 🗄️ Database Migration

无。

### 📦 Files Changed

- `QuantDinger-Vue-src/src/locales/lang/{ar-SA,de-DE,en-US,fr-FR,ja-JP,ko-KR,th-TH,vi-VN,zh-TW}.js`
- `scripts/i18n-diff.js`、`scripts/i18n-fill-ai.js`、`scripts/i18n-patch-specials.js`、`scripts/README.md`
- `.gitignore`

---

## V3.0.2 (2026-04-11) — 交易机器人全链路修复(Grid / Martingale / Trend / DCA)

### 🐛 Bug Fixes — 交易机器人

针对四类机器人(网格 / 马丁 / 趋势 / 定投)做了从前端配置、脚本模板、后端执行到列表/详情页数据的端到端审计与修复:

- **[P0-1] 编辑机器人会清空运行时状态**:`StrategyService.update_strategy` 此前直接用 payload 里的 `trading_config` 整体替换老记录,导致 `script_runtime_state`(马丁 `layer`/`total_cost`、网格 `bp/sp/prev_price`、DCA `total_qty` 等)被一把抹掉,改完参数重启就像换了台新机器人。改为 `{**existing, **incoming}` 浅合并,并保护 `script_runtime_state`、`last_signal_time`、`last_execution_time`、`bot_runtime_stats` 等后端维护的运行时字段。
- **[P0-2] 网格空头不受预算控制**:旧 `total_spent` 只在买入时累加,卖出开空(中性/做空模式)既不检查也不累加,合约下可以把空头无限放大直至爆仓。重写网格脚本改为 `long_exposure` / `short_exposure` 双路独立核算,BUY 先抵扣空头再开多(做多侧过预算就跳过),SELL 同理。
- **[P0-3] 马丁/趋势默认 `maker` 限价挂单导致漏触发和重复下单**:马丁每层加仓依赖上一单「已成交」才会更新 `last_entry_price`,挂单未成交时脚本在下一根 K 线用同一价格重新发单,出现一次开仓就下两笔甚至多笔的现象。向导 `buildPayload` 对 `bot_type` 为 `martingale` / `trend` 强制 `order_mode='market'`,网格/DCA 保留用户选择(默认 maker 更省费)。
- **[P0-4] 网格/DCA 在同一 tick 多笔减仓的本地持仓跟踪错误**:`_script_orders_to_execution_signals` 把脚本传来的 USDT 名义金额直接丢给 `ctx.position.reduce_position/add_position/open_position`(这些方法内部以 qty 单位计数),导致同一 tick 内若先后发 sell + sell,第二笔会被误判为「开空」而不是「继续平多」,发出错误的 `open_short` 信号。修复:把 USDT 金额按 `usdt * leverage / ref_price` 换算成近似 qty 再更新本地 ctx.position(真实下单数量依旧由 `_execute_signal` 按杠杆/市场类型重算,完全不变)。
- **[P0-5] DCA 频率被 K 线周期吞掉**:`intervalBars = round(freqMin / tfMin)` 当 `freq<tf`(比如 4h 线上选 hourly)会取整到 0,再 `max(1,0)=1`,结果变成「每根 K 线都买」(等于 4 小时 1 次)。把 DCA 脚本改成 **基于真实时间戳** 的 `INTERVAL_SEC = freqMin * 60`,用 `now - last_buy_ts >= INTERVAL_SEC` 判断,彻底与 K 线周期解耦。

### 🔧 Improvements

- **[P1] 机器人列表/详情返回运行时指标**:`list_strategies` / `get_strategy` 通过一次 GROUP BY 批量查 `qd_strategy_trades.profit-commission` 和 `qd_strategy_positions.unrealized_pnl`,在响应里附带 `realized_pnl` / `unrealized_pnl` / `total_pnl` / `current_equity`,前端 KPI 和卡片不再需要自己拼。
- **[P1] 趋势机器人仓位按实时权益计算**:`_hydrate_script_ctx_from_positions` 在 hydrate 持仓的同时把 `ctx.balance` / `ctx.equity` 刷新为 `initial_capital + 已实现 + 未实现` 的最新值,趋势脚本里 `amt = ctx.balance * POS_PCT` 终于能跟着账户净值走,而不是始终停在初始资金。
- **[P1] DCA 仓位被外部平掉后自动重置**:DCA 脚本每根 bar 检查 `buy_count>0 且 total_qty>0 但 ctx.position 为空` 的情况,判定为手动/止损平仓并清零累计状态,下一轮定投正常重新开始。
- **[P1] 网格/DCA 前端参数校验**:`GridConfig` 新增上下限大小校验、等比网格下限>0 校验、以及「每格金额 × 网格数 ≤ 初始资金」校验;`DCAConfig` 新增「单次金额 ≤ 总预算」校验。多语言已补齐 10 种。

### 🗄️ Database Migration

本次无新增列/表,仅代码层修复。已有部署**不需要**执行任何 SQL。

### 📦 Files Changed

- `backend_api_python/app/services/strategy.py` — `update_strategy` 合并逻辑、`_compute_runtime_metrics`、列表/详情附带运行时指标
- `backend_api_python/app/services/trading_executor.py` — `_script_orders_to_execution_signals` USDT→qty 换算、`_hydrate_script_ctx_from_positions` 刷新 balance/equity
- `QuantDinger-Vue-src/src/views/trading-bot/components/BotCreateWizard.vue` — 马丁/趋势强制市价
- `QuantDinger-Vue-src/src/views/trading-bot/components/botScriptTemplates.js` — 网格双路预算、DCA 时间制间隔与外部平仓重置
- `QuantDinger-Vue-src/src/views/trading-bot/components/configs/GridConfig.vue`、`DCAConfig.vue` — 参数校验
- `QuantDinger-Vue-src/src/locales/lang/*.js` — 4 条新校验文案 × 10 语言

---

## V3.0.2 (2026-04-17) — 指标社区「同步代码」+ Martingale / 回测稳定性

### 🚀 New Features

- **指标社区 · 同步代码**：指标详情弹窗为已购用户在「立即使用」旁新增「同步代码」按钮。发布者更新并重新上架后，已购用户可一键把最新代码拉到自己的本地副本；前端带 `Tooltip`、确认弹窗与「有更新」橙色标记，暗色主题单独适配。
  - 新接口：`POST /api/community/indicators/<id>/sync`
  - 详情接口 `GET /api/community/indicators/<id>` 新增字段：`has_update`、`local_copy_id`
  - 本地副本与原始指标通过新增的 `qd_indicator_codes.source_indicator_id` 建立持久关联；老数据按名称兜底匹配并在首次同步时回填该字段。
- **交易机器人 · 参数标准化**：Martingale / Grid / Trend / DCA 四类机器人参数统一语义，创建确认页、列表页、详情页展示完全对齐，后端 `bot_display` 统一结构，前端映射大幅简化。
- **Martingale 重复开仓修复**：策略启动瞬间会立即下两笔单的问题修复（信号去重 + 当次循环内的市值/持仓校验）。

### 🐛 Bug Fixes

- **回测日期范围失效**：调整回测起止日期但结果不变的严重问题修复。根因为 `_fetch_kline_data` 在上游数据覆盖不全时会退化为 `df.tail(N)`，忽略 `start_date` 约束。改为严格按「请求区间 ∩ 可用区间」过滤；无交集时直接报错；确需兜底时打印 `WARNING` 并标记 `fallback=True`。新增 `[BacktestRequest]`、`[Backtest] … requested/upstream/effective`、`[CryptoKline] …` 等诊断日志，便于排查数据源覆盖问题。
- **回测后 K 线 Buy/Sell 标记错位**：指标 IDE 运行回测后，K 线上的 B / S 标记可能整体往后偏移一根 K 线（多时间框架 MTF 模式下尤为明显）。根因有两点：
  1. 开启 MTF 后，后端执行时间框架（exec_tf）会自动切换到 `1m` 或 `5m`，`trade.time` 记录的是 exec_tf 级时间戳；但前端 K 线显示的是用户选择的信号 TF（如 `1h`）。
  2. 前端使用「就近」对齐（nearest-snap），当 SL / TP / Trailing 等触发发生在信号 TF 柱的后半段时，会被吸附到**下一根**柱，造成整根柱的错位。

  修复：
  - 后端 `_simulate_trading_mtf` 对每笔 trade 新增 `bar_time` 字段 —— 把 exec_tf 时间戳 floor 到信号 TF，得到 trade 实际所属的**图表柱**起点时间（UTC，`'%Y-%m-%d %H:%M'`）。
  - 前端 `renderBacktestSignals` 改为**优先使用 `trade.bar_time`**（已经是图表柱对齐），并把「就近」改为 **floor-snap**（定位到包含该时间的最后一根 K 线），彻底消除 ±1 根柱的偏移。
  - 非 MTF 路径无需改动：`trade.time` 本身就等于信号 TF 柱时间，前端回退到 `trade.time` 后依旧正确对齐。
  - 改动文件：`backend_api_python/app/services/backtest.py`、`QuantDinger-Vue-src/src/views/indicator-ide/index.vue`。

### 🗄️ Database Migration

本次新增一列 + 一个索引，用于指标社区「同步代码」定位买家本地副本：

```sql
-- 1. 新列：买家本地副本 -> 市场原始指标 的外键关联（软外键，NULL 兼容老数据）
ALTER TABLE qd_indicator_codes
    ADD COLUMN IF NOT EXISTS source_indicator_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_indicator_codes_source
    ON qd_indicator_codes USING btree (source_indicator_id);

-- 2. 可选回填：给已有的已购副本按名称回写 source_indicator_id
--    安全条件：仅写 is_buy=1 且 source_indicator_id IS NULL 的行，按 (买家ID, 原指标名) 匹配
UPDATE qd_indicator_codes lc
SET    source_indicator_id = p.indicator_id
FROM   qd_indicator_purchases p
JOIN   qd_indicator_codes orig ON orig.id = p.indicator_id
WHERE  lc.user_id = p.buyer_id
  AND  lc.is_buy = 1
  AND  lc.source_indicator_id IS NULL
  AND  lc.name = orig.name;
```

**已在开发环境 Docker 中执行完毕**（`ALTER TABLE` + `CREATE INDEX` 均返回成功，回填 `UPDATE 4`）。新库使用当前仓库中的 `migrations/init.sql` 初始化已包含该列定义，无需重复执行。

**在已有库上手动执行（Docker 一行示例）：**

```bash
docker compose exec -T postgres psql -U quantdinger -d quantdinger <<'SQL'
ALTER TABLE qd_indicator_codes ADD COLUMN IF NOT EXISTS source_indicator_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_indicator_codes_source ON qd_indicator_codes USING btree (source_indicator_id);
UPDATE qd_indicator_codes lc
SET source_indicator_id = p.indicator_id
FROM qd_indicator_purchases p
JOIN qd_indicator_codes orig ON orig.id = p.indicator_id
WHERE lc.user_id = p.buyer_id
  AND lc.is_buy = 1
  AND lc.source_indicator_id IS NULL
  AND lc.name = orig.name;
SQL
```

> 服务启动时 `CommunityService.__init__` 亦带 `ADD COLUMN IF NOT EXISTS`，作为冗余保障（向后兼容）。

### 🎨 Frontend / i18n

- `QuantDinger-Vue-src/package.json`、`src/config/defaultSettings.js`、`src/layouts/BasicLayout.vue` 版本号 `3.0.1 → 3.0.2`；`README.md` 与 `docs/README_CN.md` 版本徽章同步。
- `zh-CN / zh-TW / en-US` 新增 12 条 `community.sync*` / `community.hasUpdate` / `community.already_latest` 等 i18n key；其他语言沿用英文 fallback。
- 重新执行 `npm run build` 并同步 `dist/` 至 `frontend/dist/`，`docker compose build frontend` 已重打镜像。
- **补丁**：回测 Buy/Sell 标记错位修复后再次 `npm run build` + 同步 `frontend/dist/` + `docker compose build backend frontend && up -d backend frontend`，无需额外数据库变更。

---

## 2026-04-07 — 数据库：`qd_market_symbols` 补充 A股 / H股热门标的

已在 **Docker** 内对运行中的 PostgreSQL 执行完毕（`INSERT 0 20`）。**新库**若使用当前仓库中的 `migrations/init.sql` 初始化，已包含同批种子数据，无需重复执行。

**在已有库上手动执行（等价 SQL，可重复执行，`ON CONFLICT DO NOTHING`）：**

```sql
INSERT INTO qd_market_symbols (market, symbol, name, exchange, currency, is_active, is_hot, sort_order) VALUES
('CNStock', '600519', '贵州茅台', 'SSE', 'CNY', 1, 1, 100),
('CNStock', '600036', '招商银行', 'SSE', 'CNY', 1, 1, 99),
('CNStock', '601318', '中国平安', 'SSE', 'CNY', 1, 1, 98),
('CNStock', '600900', '长江电力', 'SSE', 'CNY', 1, 1, 97),
('CNStock', '601899', '紫金矿业', 'SSE', 'CNY', 1, 1, 96),
('CNStock', '000858', '五粮液', 'SZSE', 'CNY', 1, 1, 95),
('CNStock', '000333', '美的集团', 'SZSE', 'CNY', 1, 1, 94),
('CNStock', '002594', '比亚迪', 'SZSE', 'CNY', 1, 1, 93),
('CNStock', '300750', '宁德时代', 'SZSE', 'CNY', 1, 1, 92),
('CNStock', '000001', '平安银行', 'SZSE', 'CNY', 1, 1, 91),
('HKStock', '00700', '腾讯控股', 'HKEX', 'HKD', 1, 1, 100),
('HKStock', '09988', '阿里巴巴-W', 'HKEX', 'HKD', 1, 1, 99),
('HKStock', '03690', '美团-W', 'HKEX', 'HKD', 1, 1, 98),
('HKStock', '01810', '小米集团-W', 'HKEX', 'HKD', 1, 1, 97),
('HKStock', '00939', '建设银行', 'HKEX', 'HKD', 1, 1, 96),
('HKStock', '01299', '友邦保险', 'HKEX', 'HKD', 1, 1, 95),
('HKStock', '02318', '中国平安', 'HKEX', 'HKD', 1, 1, 94),
('HKStock', '00388', '香港交易所', 'HKEX', 'HKD', 1, 1, 93),
('HKStock', '00883', '中国海洋石油', 'HKEX', 'HKD', 1, 1, 92),
('HKStock', '01398', '工商银行', 'HKEX', 'HKD', 1, 1, 91)
ON CONFLICT (market, symbol) DO NOTHING;
```

**Docker 一行示例（文件需 UTF-8）：**

```bash
docker cp backend_api_python/migrations/<your>.sql quantdinger-db:/tmp/migrate.sql
docker compose exec -T postgres psql -U quantdinger -d quantdinger -f /tmp/migrate.sql
```

---

## V3.0.1 (2026-04-05) — Frontend / docs

- **前端版本**：私有 Vue 仓库 `package.json`、页脚展示与 `frontend/VERSION` 统一为 **3.0.1**。
- **文档**：根目录 `README.md` 与 `docs/README_CN.md` 补充 QuantDinger 专属交易所邀请注册链接表（与个人中心「开户」一致），版本徽章更新为 3.0.1。
- **回测中心**：暗黑主题下图标与「添加标的」等弹窗样式对齐（`a-icon`、图表标题区、Modal 挂载层）。

---

## V2.2.4 (2026-04-05)

### 🚀 New Features

- **真实策略回测主链路**: 新增基于 `strategyId` 的策略回测入口，支持已保存的 `IndicatorStrategy` 与 `ScriptStrategy`，不再只是“取指标再跑一次指标回测”。
- **策略快照解析层**: 后端新增统一策略快照解析逻辑，把 `indicator_config`、`trading_config`、`strategy_code` 解析为可回测的标准输入。
- **策略回测历史与详情**: 回测记录现在可区分 `indicator` / `strategy_indicator` / `strategy_script`，并支持策略回测历史、详情查看和 AI 修正建议链路。
- **交易助手联动回测中心**: 交易助手中的策略项新增回测跳转入口，可直接带 `strategy_id` 进入回测中心。

### 🐛 Bug Fixes

- Fixed the previous “策略回测” pseudo-flow that only reused `/api/indicator/backtest` and could not faithfully replay stored strategies.
- Fixed strategy backtest history semantics so records can be linked to concrete strategies instead of only relying on `indicator_id`.
- Fixed strategy backtest UI entry restoration in Backtest Center and wired the strategy selector/history drawer to real backend endpoints.

### 🎨 UI/UX Improvements

- Restored the `回测中心 -> 策略回测` tab with strategy summary cards and environment override controls.
- Unified strategy backtest history display with the existing run viewer and AI suggestion modal.

### 📋 Database Migration

**在已有 PostgreSQL 库上执行（新库若已通过更新后的 `migrations/init.sql` 初始化则无需再执行）：**

```sql
-- ============================================================
-- QuantDinger V2.2.4 Database Migration
-- Strategy Backtest Persistence Upgrade
-- ============================================================

ALTER TABLE qd_backtest_runs ADD COLUMN IF NOT EXISTS strategy_id INTEGER;
ALTER TABLE qd_backtest_runs ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(255) DEFAULT '';
ALTER TABLE qd_backtest_runs ADD COLUMN IF NOT EXISTS run_type VARCHAR(50) DEFAULT 'indicator';
ALTER TABLE qd_backtest_runs ADD COLUMN IF NOT EXISTS config_snapshot TEXT DEFAULT '';
ALTER TABLE qd_backtest_runs ADD COLUMN IF NOT EXISTS engine_version VARCHAR(50) DEFAULT '';
ALTER TABLE qd_backtest_runs ADD COLUMN IF NOT EXISTS code_hash VARCHAR(128) DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy_id ON qd_backtest_runs(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_run_type ON qd_backtest_runs(run_type);

CREATE TABLE IF NOT EXISTS qd_backtest_trades (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL DEFAULT 1 REFERENCES qd_users(id) ON DELETE CASCADE,
    strategy_id INTEGER,
    trade_index INTEGER DEFAULT 0,
    trade_time VARCHAR(64) DEFAULT '',
    trade_type VARCHAR(64) DEFAULT '',
    side VARCHAR(32) DEFAULT '',
    price DOUBLE PRECISION DEFAULT 0,
    amount DOUBLE PRECISION DEFAULT 0,
    profit DOUBLE PRECISION DEFAULT 0,
    balance DOUBLE PRECISION DEFAULT 0,
    reason VARCHAR(64) DEFAULT '',
    payload_json TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_id ON qd_backtest_trades(run_id);

CREATE TABLE IF NOT EXISTS qd_backtest_equity_points (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    point_index INTEGER DEFAULT 0,
    point_time VARCHAR(64) DEFAULT '',
    point_value DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_equity_points_run_id ON qd_backtest_equity_points(run_id);
```

### 📝 Migration Notes

- All statements are idempotent and safe to run multiple times.
- Existing backtest data is preserved.
- Existing `indicator` backtest records remain compatible; new strategy backtests will write `run_type`, `strategy_id`, `strategy_name`, `config_snapshot`, `engine_version`, and `code_hash`.
- `qd_backtest_trades` and `qd_backtest_equity_points` are introduced for future strategy-level analytics and debugging.

---

## V2.2.3 (2026-03-24)

### 🚀 New Features

- **User profile IANA timezone (`qd_users.timezone`)**: 个人资料可保存时区（IANA 标识，如 `Asia/Shanghai`）；为空表示跟随浏览器。登录态 `/api/auth/info`、资料接口与前端 AI 分析页等时间展示会按该时区调用 `toLocaleString(..., { timeZone })`（非法或空则回退本机时区）。

### 📋 Database Migration

**在已有 PostgreSQL 库上执行（新库若已通过更新后的 `migrations/init.sql` 初始化则无需再执行）：**

```sql
-- ============================================================
-- QuantDinger V2.2.3 — qd_users.timezone（用户资料时区）
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'qd_users'
          AND column_name = 'timezone'
    ) THEN
        ALTER TABLE qd_users ADD COLUMN timezone VARCHAR(64) DEFAULT '';
        RAISE NOTICE 'Added timezone column to qd_users table';
    END IF;
END $$;
```

**仅当列不存在时的一行式写法（自行确认无列后再执行）：**

```sql
ALTER TABLE qd_users ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) DEFAULT '';
```

> 说明：`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 需 **PostgreSQL 11+**（本仓库 Docker 默认 `postgres:16` 可用）；与上面 `DO` 块二选一即可。

---

## V2.2.2 (2026-02-28)

### 🚀 New Features

#### Polymarket Prediction Markets Integration 🔮
- **Prediction Market Analysis**: Integrated Polymarket prediction markets as a new data source for AI analysis
- **AI-Driven Insights**: AI analyzes prediction market events and compares AI predictions with market consensus
- **Opportunity Discovery**: Identifies undervalued prediction opportunities with AI vs market divergence analysis
- **Asset Trading Recommendations**: Links prediction market events to related asset trading opportunities (e.g., BTC/USDT, ETH/USDT)
- **Data Analysis Only**: Focuses on data analysis and trading opportunity recommendations without live trading
- **Frontend Pages**: New `/polymarket` page with market listings, filtering, sorting, and search functionality
- **Market Detail View**: Comprehensive analysis view showing market info, AI analysis results, and related asset opportunities
- **AI Trading Radar Integration**: Prediction market opportunities appear in the AI Trading Radar alongside Crypto, US Stocks, and Forex

### 🐛 Bug Fixes
- Fixed duplicate `common.refresh` key in internationalization files (`zh-CN.js` and `en-US.js`)
- Fixed OKX position `entry_price` extraction (now correctly reads `avgPx`, `avgPxEp`, or `last` from position data)
- Improved symbol normalization across all exchanges to handle edge cases (e.g., PI, TRX without quote currency)
- Enhanced LLM provider fallback mechanism to handle 403/402/404/429 errors automatically

### 🎨 UI/UX Improvements
- Added Polymarket market cards with AI analysis summaries and opportunity scores
- Enhanced AI Trading Radar to display prediction market opportunities with distinct styling
- Improved symbol selector in Quick Trade panel with watchlist integration

### 📋 Database Migration

**Run the following SQL on your PostgreSQL database before deploying V2.2.2:**

```sql
-- ============================================================
-- QuantDinger V2.2.2 Database Migration
-- Polymarket Prediction Markets Integration
-- ============================================================

-- 预测市场表（缓存）
CREATE TABLE IF NOT EXISTS qd_polymarket_markets (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(255) UNIQUE NOT NULL,
    question TEXT,
    category VARCHAR(100),  -- crypto, politics, economics, sports
    current_probability DECIMAL(5,2),  -- YES概率（0-100）
    volume_24h DECIMAL(20,2),
    liquidity DECIMAL(20,2),
    end_date_iso TIMESTAMP,
    status VARCHAR(50),  -- active, closed, resolved
    outcome_tokens JSONB,  -- YES/NO价格和交易量
    slug VARCHAR(255),  -- Polymarket事件slug，用于构建URL
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 添加slug字段（如果表已存在但字段不存在）
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_polymarket_markets' AND column_name = 'slug'
    ) THEN
        ALTER TABLE qd_polymarket_markets ADD COLUMN slug VARCHAR(255);
        RAISE NOTICE 'Added slug column to qd_polymarket_markets';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_polymarket_category ON qd_polymarket_markets(category);
CREATE INDEX IF NOT EXISTS idx_polymarket_status ON qd_polymarket_markets(status);
CREATE INDEX IF NOT EXISTS idx_polymarket_updated ON qd_polymarket_markets(updated_at DESC);

-- AI分析记录表
CREATE TABLE IF NOT EXISTS qd_polymarket_ai_analysis (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(255) NOT NULL,
    user_id INTEGER,  -- 可选：用户特定的分析
    ai_predicted_probability DECIMAL(5,2),
    market_probability DECIMAL(5,2),
    divergence DECIMAL(5,2),  -- AI - 市场
    recommendation VARCHAR(20),  -- YES/NO/HOLD
    confidence_score DECIMAL(5,2),
    opportunity_score DECIMAL(5,2),
    reasoning TEXT,
    key_factors JSONB,
    related_assets TEXT[],  -- 相关资产列表
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polymarket_analysis_market ON qd_polymarket_ai_analysis(market_id);
CREATE INDEX IF NOT EXISTS idx_polymarket_analysis_opportunity ON qd_polymarket_ai_analysis(opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_polymarket_analysis_user ON qd_polymarket_ai_analysis(user_id);

-- 资产交易机会表（基于预测市场生成）
CREATE TABLE IF NOT EXISTS qd_polymarket_asset_opportunities (
    id SERIAL PRIMARY KEY,
    market_id VARCHAR(255) NOT NULL,
    asset_symbol VARCHAR(100),
    asset_market VARCHAR(50),
    signal VARCHAR(20),  -- BUY/SELL/HOLD
    confidence DECIMAL(5,2),
    reasoning TEXT,
    entry_suggestion JSONB,  -- 入场建议
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_polymarket_opp_market ON qd_polymarket_asset_opportunities(market_id);
CREATE INDEX IF NOT EXISTS idx_polymarket_opp_asset ON qd_polymarket_asset_opportunities(asset_symbol, asset_market);

-- Migration Complete
DO $$
BEGIN
    RAISE NOTICE '✅ QuantDinger V2.2.2 database migration completed!';
END $$;
```

**Migration Notes:**
- All statements use `IF NOT EXISTS` — safe to run multiple times
- No existing data is modified or deleted
- New tables are created for Polymarket data caching and AI analysis
- Polymarket integration is read-only (data analysis only, no live trading)

### 📝 Configuration Notes
- No new environment variables required for basic Polymarket integration
- Polymarket data source uses placeholder/dummy data by default (can be extended with actual API integration)
- AI analysis leverages existing LLM configuration from System Settings

---

## V2.2.1 (2026-02-27)

### 🚀 New Features

#### Membership & Billing System
- **Subscription Plans**: Monthly / Yearly / Lifetime tiers with configurable pricing and credit bundles
- **Credit System**: Each plan includes credits; lifetime members receive recurring monthly credit bonuses
- **Plan Management**: All plan prices, credits, and bonus amounts configurable via System Settings → Billing Configuration
- **Membership Orders**: Order tracking with status management (paid / pending / failed / refunded)

#### USDT On-Chain Payment (TRC20)
- **HD Wallet Integration**: Per-order unique receiving address derived from xpub (BIP-32/44) — no private key on server
- **Automatic Reconciliation**: Background polling via TronGrid API detects incoming payments and confirms orders
- **Depth-Flexible xpub**: Supports both account-level (depth=3) and change-level (depth=4) xpub keys
- **Configurable Expiry**: Order expiration time and confirmation delay configurable in System Settings
- **Scan-to-Pay Modal**: Professional checkout UI with QR code, step indicator, real-time status, copy-to-clipboard, dark theme support

#### VIP Free Indicators
- **VIP Free Tag**: Admins can mark community indicators as "VIP Free" when publishing
- **Zero-Credit Access**: VIP members can use VIP-free indicators without spending credits
- **Visual Badge**: VIP Free indicators display a distinct badge in the Indicator Market

#### AI Trading Opportunities Radar
- **Multi-Market Scanning**: Auto-scans Crypto, US Stocks, and Forex markets every hour
- **Rolling Carousel**: Opportunities displayed in a rotating carousel with market-specific styling
- **Signal Classification**: BUY / SELL signals with percentage change and reason text
- **Multi-Language**: All radar card content fully internationalized

#### Simplified Strategy Creation
- **Simple / Advanced Mode Toggle**: New users start with simplified mode, power users can switch to advanced
- **Smart Defaults**: 15-minute K-line period, 5x leverage, market order, sensible TP/SL percentages
- **Live Trading Disclaimer**: Mandatory risk acknowledgment checkbox before enabling live trading

#### System Settings Simplification
- **Streamlined Configuration**: Removed redundant config groups (server, strategy); consolidated into essential categories
- **Market Order Default**: Changed default order mode to market order for reliable execution
- **Billing Config i18n**: All billing configuration items fully multi-language supported

#### Quick Trade Panel (闪电交易) 🆕
- **Side-Sliding Drawer**: Professional trading panel slides in from the right, allowing instant order placement without leaving the analysis page
- **Multi-Exchange Support**: Select from saved exchange credentials (Binance, OKX, Bitget, Bybit, etc.) with real-time balance display
- **Long/Short Toggle**: Color-coded direction buttons with one-click switching
- **Market / Limit Orders**: Toggle between market and limit order types; limit orders accept a specific price
- **Leverage Slider**: Interactive 1x–125x leverage control for futures trading
- **TP/SL Price Setting**: Optional take-profit and stop-loss by **absolute price** (not percentage)
- **Current Position Display**: Shows open position with side, size, entry price, unrealized PnL, and one-click close button
- **Recent Trade History**: Displays last 5 quick trades with status tags
- **AI Radar Integration**: "Trade Now" button on each AI Trading Opportunities card pre-fills symbol, direction, and price
- **Indicator Analysis Integration**: Quick Trade button in chart header and floating ⚡ button pre-fills current symbol and price
- **Auto-Polling**: Balance and position data refresh every 10 seconds
- **Full Dark Theme**: Complete dark mode support for all panel elements
- **Multi-Language**: All labels and messages fully internationalized (zh-CN / en-US)

#### Indicator Market Performance Tracking
- **Live Performance Data**: Fixed aggregation to correctly parse backtest `result_json` and include live trade data
- **Combined Metrics**: Backtest return, live PnL, and win rate now properly displayed on indicator cards

### 🐛 Bug Fixes
- Fixed `quick_trade.py` importing from non-existent `auth_utils` module (corrected to `auth`)
- Fixed "Live Performance" data showing all zeros in Indicator Market (incorrect SQL query referencing non-existent columns)
- Fixed incorrect entry price display in Position Records (was falling back to current price)
- Fixed inaccurate System Overview statistics for running strategies, total capital, and total PnL
- Fixed multiple duplicate i18n key issues in `zh-CN.js` and `en-US.js` causing ESLint build failures
- Fixed exposed i18n keys (`common.loading`, `common.noData`, `systemOverview.*`) not configured
- Fixed HTML nesting issues in trading assistant strategy creation form
- Fixed `ed25519-blake2b` build failure in Docker by adding temporary build dependencies
- Fixed "Current depth (3) is not suitable for deriving address" error for xpub — now compatible with both depth 3 and depth 4

### 🎨 UI/UX Improvements
- Removed "Total Analyses" / "Accuracy Rate" row from homepage AI Analysis section
- Removed "Search" and "Portfolio Checkup" features from AI Asset Analysis page
- Professional USDT checkout modal with custom header, step indicator, dual-column layout
- Dark theme and mobile responsive support for payment modal
- Trading Opportunities Radar carousel with smooth scrolling animation

### 📋 Database Migration

**Run the following SQL on your PostgreSQL database before deploying V2.2.1:**

```sql
-- ============================================================
-- QuantDinger V2.2.1 Database Migration
-- Membership, USDT Payment, VIP Free Indicators
-- ============================================================

-- 1. User Table: Add membership columns
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'qd_users' AND column_name = 'vip_plan'
    ) THEN
        ALTER TABLE qd_users ADD COLUMN vip_plan VARCHAR(20) DEFAULT '';
        RAISE NOTICE 'Added vip_plan column to qd_users';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'qd_users' AND column_name = 'vip_is_lifetime'
    ) THEN
        ALTER TABLE qd_users ADD COLUMN vip_is_lifetime BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added vip_is_lifetime column to qd_users';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'qd_users' AND column_name = 'vip_monthly_credits_last_grant'
    ) THEN
        ALTER TABLE qd_users ADD COLUMN vip_monthly_credits_last_grant TIMESTAMP;
        RAISE NOTICE 'Added vip_monthly_credits_last_grant column to qd_users';
    END IF;
END $$;

-- 2. Indicator Codes: Add VIP Free flag
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'vip_free'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN vip_free BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added vip_free column to qd_indicator_codes';
    END IF;
END $$;

-- 3. Membership Orders table
CREATE TABLE IF NOT EXISTS qd_membership_orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    plan VARCHAR(20) NOT NULL,
    price_usd DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'paid',
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_membership_orders_user_id ON qd_membership_orders(user_id);

-- 4. USDT Orders table (on-chain payment tracking)
CREATE TABLE IF NOT EXISTS qd_usdt_orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    plan VARCHAR(20) NOT NULL,
    chain VARCHAR(20) NOT NULL DEFAULT 'TRC20',
    amount_usdt DECIMAL(20,6) NOT NULL DEFAULT 0,
    address_index INTEGER NOT NULL DEFAULT 0,
    address VARCHAR(80) NOT NULL DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    tx_hash VARCHAR(120) DEFAULT '',
    paid_at TIMESTAMP,
    confirmed_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_usdt_orders_address_unique ON qd_usdt_orders(chain, address);
CREATE INDEX IF NOT EXISTS idx_usdt_orders_user_id ON qd_usdt_orders(user_id);
CREATE INDEX IF NOT EXISTS idx_usdt_orders_status ON qd_usdt_orders(status);

-- 5. Quick Trades table (manual / discretionary orders from Quick Trade Panel)
CREATE TABLE IF NOT EXISTS qd_quick_trades (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    credential_id   INTEGER DEFAULT 0,
    exchange_id     VARCHAR(40) NOT NULL DEFAULT '',
    symbol          VARCHAR(60) NOT NULL DEFAULT '',
    side            VARCHAR(10) NOT NULL DEFAULT '',       -- buy / sell
    order_type      VARCHAR(20) NOT NULL DEFAULT 'market', -- market / limit
    amount          DECIMAL(24, 8) DEFAULT 0,
    price           DECIMAL(24, 8) DEFAULT 0,
    leverage        INTEGER DEFAULT 1,
    market_type     VARCHAR(20) DEFAULT 'swap',            -- swap / spot
    tp_price        DECIMAL(24, 8) DEFAULT 0,
    sl_price        DECIMAL(24, 8) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'submitted',       -- submitted / filled / failed / cancelled
    exchange_order_id VARCHAR(120) DEFAULT '',
    filled_amount   DECIMAL(24, 8) DEFAULT 0,
    avg_fill_price  DECIMAL(24, 8) DEFAULT 0,
    error_msg       TEXT DEFAULT '',
    source          VARCHAR(40) DEFAULT 'manual',          -- ai_radar / ai_analysis / indicator / manual
    raw_result      JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quick_trades_user    ON qd_quick_trades(user_id);
CREATE INDEX IF NOT EXISTS idx_quick_trades_created ON qd_quick_trades(created_at DESC);

-- Migration Complete
DO $$
BEGIN
    RAISE NOTICE '✅ QuantDinger V2.2.1 database migration completed!';
END $$;
```

**Migration Notes:**
- All statements use `IF NOT EXISTS` — safe to run multiple times
- No existing data is modified or deleted
- New `.env` variables required for USDT payment: `USDT_PAY_ENABLED`, `USDT_TRC20_XPUB`, `TRONGRID_API_KEY`
- New `.env` variables for membership pricing: `MEMBERSHIP_MONTHLY_PRICE_USD`, `MEMBERSHIP_MONTHLY_CREDITS`, etc.
- See `backend_api_python/env.example` for all new configuration options

### 📝 Configuration Notes

New environment variables (all optional, with defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `MEMBERSHIP_MONTHLY_PRICE_USD` | `19.9` | Monthly plan price |
| `MEMBERSHIP_MONTHLY_CREDITS` | `500` | Credits included in monthly plan |
| `MEMBERSHIP_YEARLY_PRICE_USD` | `169` | Yearly plan price |
| `MEMBERSHIP_YEARLY_CREDITS` | `8000` | Credits included in yearly plan |
| `MEMBERSHIP_LIFETIME_PRICE_USD` | `499` | Lifetime plan price |
| `MEMBERSHIP_LIFETIME_CREDITS` | `30000` | Initial credits for lifetime plan |
| `MEMBERSHIP_LIFETIME_MONTHLY_BONUS` | `500` | Monthly bonus credits for lifetime members |
| `USDT_PAY_ENABLED` | `false` | Enable USDT TRC20 payment |
| `USDT_TRC20_XPUB` | _(empty)_ | TRC20 HD wallet xpub for address derivation |
| `TRONGRID_API_KEY` | _(empty)_ | TronGrid API key for on-chain monitoring |
| `USDT_ORDER_EXPIRE_MINUTES` | `30` | USDT order expiration time |

---

## V2.1.3 (2026-02-XX)

### 🚀 New Features

#### Cross-Sectional Strategy Support
- **Multi-Symbol Portfolio Management** - Added support for cross-sectional strategies that manage a portfolio of multiple symbols simultaneously
  - Strategy type selection: Single Symbol vs Cross-Sectional
  - Symbol list configuration: Select multiple symbols for portfolio management
  - Portfolio size: Configure the number of symbols to hold simultaneously
  - Long/Short ratio: Set the proportion of long vs short positions (0-1)
  - Rebalance frequency: Daily, Weekly, or Monthly portfolio rebalancing
  - Indicator execution: Indicators receive a `data` dictionary (symbol -> DataFrame) for cross-symbol analysis
  - Signal generation: Automatic buy/sell/close signals based on indicator rankings
  - Parallel execution: Multiple orders executed concurrently for efficiency
- **Backend Implementation**
  - Cross-sectional configurations stored in `trading_config` JSON field
  - New `_run_cross_sectional_strategy_loop` method in TradingExecutor
  - Automatic rebalancing based on configured frequency
  - Support for both long and short positions in the same portfolio
- **Frontend UI**
  - Strategy type selector in strategy creation/editing form
  - Conditional display of single-symbol vs cross-sectional configuration fields
  - Multi-select symbol picker for cross-sectional strategies
  - Full i18n support (Chinese and English)

See `docs/CROSS_SECTIONAL_STRATEGY_GUIDE_CN.md` or `docs/CROSS_SECTIONAL_STRATEGY_GUIDE_EN.md` for detailed usage instructions.

### 🐛 Bug Fixes
- Fixed decimal precision issues in exchange order quantities (Binance Spot LOT_SIZE filter errors)
- Improved `_dec_str` method across all exchange clients for accurate quantity formatting
- Enhanced quantity normalization to respect exchange precision requirements
- Fixed validation logic for cross-sectional strategies (now validates correct symbol list field)
- Fixed success message to show correct strategy count for cross-sectional strategies

### 📋 Database Migration

**Run the following SQL on your PostgreSQL database before deploying V2.1.3:**

```sql
-- ============================================================
-- QuantDinger V2.1.3 Database Migration
-- Cross-Sectional Strategy Support
-- ============================================================

-- Add last_rebalance_at column to track rebalancing time for cross-sectional strategies
-- Note: Cross-sectional strategy configurations (symbol_list, portfolio_size, long_ratio, rebalance_frequency)
-- are stored in the trading_config JSON field, not as separate database columns.
-- This migration only adds the last_rebalance_at timestamp field which is needed for rebalancing logic.

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_strategies_trading' 
        AND column_name = 'last_rebalance_at'
    ) THEN
        ALTER TABLE qd_strategies_trading 
        ADD COLUMN last_rebalance_at TIMESTAMP;
        RAISE NOTICE 'Added last_rebalance_at column to qd_strategies_trading';
    ELSE
        RAISE NOTICE 'Column last_rebalance_at already exists';
    END IF;
END $$;
```

**Migration Notes:**
- This migration is safe to run multiple times (uses IF NOT EXISTS check)
- Cross-sectional strategy configurations are stored in the `trading_config` JSON field, so no additional columns are needed
- The `last_rebalance_at` field is used to track when the last rebalancing occurred for cross-sectional strategies
- If you don't run this migration, cross-sectional strategies will still work, but rebalancing frequency checks may not function correctly

---

## V2.1.2 (2026-02-01)

### 🚀 New Features

#### Indicator Parameter Support
- **External Parameter Passing** - Indicators can now declare parameters using `# @param` syntax that can be configured per-strategy
  - Supported types: `int`, `float`, `bool`, `str`
  - Parameters are displayed in the strategy creation form after selecting an indicator
  - Different strategies using the same indicator can have different parameter values
- **Cross-Indicator Calling** - Indicators can now call other indicators using `call_indicator(id_or_name, df)` function
  - Supports calling by indicator ID (number) or name (string)
  - Maximum call depth of 5 to prevent circular dependencies
  - Only allows calling own indicators or published community indicators

#### Parameter Declaration Syntax
```
# @param <name> <type> <default> <description>
```

| Field | Description | Example |
|-------|-------------|---------|
| name | Parameter name (variable name) | `ma_fast` |
| type | Data type: `int`, `float`, `bool`, `str` | `int` |
| default | Default value | `5` |
| description | Description (shown in UI tooltip) | `Short-term MA period` |

#### Example: Dual Moving Average with Parameters
```python
# @param sma_short int 14 Short-term MA period
# @param sma_long int 28 Long-term MA period

# Get parameters
sma_short_period = params.get('sma_short', 14)
sma_long_period = params.get('sma_long', 28)

my_indicator_name = "Dual MA Strategy"
my_indicator_description = f"SMA{sma_short_period}/{sma_long_period} crossover"

df = df.copy()
sma_short = df["close"].rolling(sma_short_period).mean()
sma_long = df["close"].rolling(sma_long_period).mean()

# Golden cross / Death cross
buy = (sma_short > sma_long) & (sma_short.shift(1) <= sma_long.shift(1))
sell = (sma_short < sma_long) & (sma_short.shift(1) >= sma_long.shift(1))

df["buy"] = buy.fillna(False).astype(bool)
df["sell"] = sell.fillna(False).astype(bool)

# Chart markers
buy_marks = [df["low"].iloc[i] * 0.995 if df["buy"].iloc[i] else None for i in range(len(df))]
sell_marks = [df["high"].iloc[i] * 1.005 if df["sell"].iloc[i] else None for i in range(len(df))]

output = {
    "name": my_indicator_name,
    "plots": [
        {"name": f"SMA{sma_short_period}", "data": sma_short.tolist(), "color": "#FF9800", "overlay": True},
        {"name": f"SMA{sma_long_period}", "data": sma_long.tolist(), "color": "#3F51B5", "overlay": True}
    ],
    "signals": [
        {"type": "buy", "text": "B", "data": buy_marks, "color": "#00E676"},
        {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"}
    ]
}
```

#### Example: Using call_indicator()
```python
# Call another indicator by name or ID
# rsi_df = call_indicator('RSI', df)           # By name
# rsi_df = call_indicator(5, df)               # By ID
# rsi_df = call_indicator('RSI', df, {'period': 14})  # With params

# Note: The called indicator must be created first
# and accessible (own indicator or published community indicator)
```

### 🐛 Bug Fixes

#### Dashboard Fixes
- **Fixed current positions showing records from other users** - Position synchronization now correctly associates positions with the strategy owner's user_id
- **Fixed strategy distribution pie chart always showing "No Data"** - Chart now uses `strategy_stats` data which includes all strategies with trading activity
- **Removed AI strategy count from running strategies card** - Dashboard now only shows indicator strategy count since AI strategies category has been removed

---

## V2.1.1 (2026-01-31)

### 🚀 New Features

#### AI Analysis System Overhaul
- **Fast Analysis Mode**: Replaced the complex multi-agent system with a streamlined single LLM call architecture for faster and more accurate analysis
- **Progressive Loading**: Market data now loads independently - each section (sentiment, indices, heatmap, calendar) displays as soon as it's ready
- **Professional Loading Animation**: New progress bar with step indicators during AI analysis
- **Analysis Memory**: Store analysis results for history review and user feedback
- **Stop Loss/Take Profit Calculation**: Now based on ATR (Average True Range) and Support/Resistance levels with clear methodology hints

#### Global Market Integration
- Integrated Global Market data directly into AI Analysis page
- Real-time scrolling display of major global indices with flags, prices, and percentage changes
- Interactive heatmaps for Crypto, Commodities, Sectors, and Forex
- Economic calendar with bullish/bearish/neutral impact indicators
- Commodities heatmap added (Gold, Silver, Crude Oil, etc.)

#### Indicator Community Enhancements
- **Admin Review System**: Administrators can now review, approve, reject, unpublish, and delete community indicators
- **Purchase & Rating System**: Users can buy indicators, leave ratings and comments
- **Statistics Tracking**: Purchase count, average rating, rating count, view count for each indicator

#### Trading Assistant Improvements
- Improved IBKR/MT5 connection test feedback
- Added local deployment warning for external trading platforms
- Virtual profit/loss calculation for signal-only strategies

### 🐛 Bug Fixes
- Fixed progress bar and timer not animating during AI analysis
- Fixed missing i18n translations for various components
- Fixed Tiingo API rate limit issues with caching
- Fixed data fetching with multiple fallback sources
- Fixed watchlist price batch fetch timeout handling
- Fixed heatmap multi-language support for commodities and forex
- **Fixed AI analysis history not filtered by user** - All users were seeing the same history records; now each user only sees their own analysis history
- **Fixed "Missing Turnstile token" error when changing password** - Logged-in users no longer need Turnstile verification to request password change verification code

### 🎨 UI/UX Improvements
- Reorganized left menu: Indicator Market moved below Indicator Analysis, Settings moved to bottom
- Skeleton loading animations for progressive data display
- Dark theme support for all new components
- Compact market overview bar design

### 📋 Database Migration

**Run the following SQL on your PostgreSQL database before deploying V2.1.1:**

```sql
-- ============================================================
-- QuantDinger V2.1.1 Database Migration
-- ============================================================

-- 1. AI Analysis Memory Table
CREATE TABLE IF NOT EXISTS qd_analysis_memory (
    id SERIAL PRIMARY KEY,
    market VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    decision VARCHAR(10) NOT NULL,
    confidence INT DEFAULT 50,
    price_at_analysis DECIMAL(24, 8),
    entry_price DECIMAL(24, 8),
    stop_loss DECIMAL(24, 8),
    take_profit DECIMAL(24, 8),
    summary TEXT,
    reasons JSONB,
    risks JSONB,
    scores JSONB,
    indicators_snapshot JSONB,
    raw_result JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP,
    actual_outcome VARCHAR(20),
    actual_return_pct DECIMAL(10, 4),
    was_correct BOOLEAN,
    user_feedback VARCHAR(20),
    feedback_at TIMESTAMP
);

-- Add raw_result column if table exists but column doesn't
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_analysis_memory' AND column_name = 'raw_result'
    ) THEN
        ALTER TABLE qd_analysis_memory ADD COLUMN raw_result JSONB;
    END IF;
END $$;

-- Add user_id column for user-specific history filtering
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_analysis_memory' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE qd_analysis_memory ADD COLUMN user_id INT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_analysis_memory_symbol ON qd_analysis_memory(market, symbol);
CREATE INDEX IF NOT EXISTS idx_analysis_memory_created ON qd_analysis_memory(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_memory_validated ON qd_analysis_memory(validated_at) WHERE validated_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_analysis_memory_user ON qd_analysis_memory(user_id);

-- 2. Indicator Purchase Records
CREATE TABLE IF NOT EXISTS qd_indicator_purchases (
    id SERIAL PRIMARY KEY,
    indicator_id INTEGER NOT NULL REFERENCES qd_indicator_codes(id) ON DELETE CASCADE,
    buyer_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    seller_id INTEGER NOT NULL REFERENCES qd_users(id),
    price DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(indicator_id, buyer_id)
);

CREATE INDEX IF NOT EXISTS idx_purchases_indicator ON qd_indicator_purchases(indicator_id);
CREATE INDEX IF NOT EXISTS idx_purchases_buyer ON qd_indicator_purchases(buyer_id);
CREATE INDEX IF NOT EXISTS idx_purchases_seller ON qd_indicator_purchases(seller_id);

-- 3. Indicator Comments
CREATE TABLE IF NOT EXISTS qd_indicator_comments (
    id SERIAL PRIMARY KEY,
    indicator_id INTEGER NOT NULL REFERENCES qd_indicator_codes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES qd_users(id) ON DELETE CASCADE,
    rating INTEGER DEFAULT 5 CHECK (rating >= 1 AND rating <= 5),
    content TEXT DEFAULT '',
    parent_id INTEGER REFERENCES qd_indicator_comments(id) ON DELETE CASCADE,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_indicator ON qd_indicator_comments(indicator_id);
CREATE INDEX IF NOT EXISTS idx_comments_user ON qd_indicator_comments(user_id);

-- 4. Indicator Codes Extensions
DO $$
BEGIN
    -- Purchase count
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'purchase_count'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN purchase_count INTEGER DEFAULT 0;
    END IF;
    
    -- Average rating
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'avg_rating'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN avg_rating DECIMAL(3,2) DEFAULT 0;
    END IF;
    
    -- Rating count
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'rating_count'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN rating_count INTEGER DEFAULT 0;
    END IF;
    
    -- View count
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'view_count'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN view_count INTEGER DEFAULT 0;
    END IF;
    
    -- Review status
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'review_status'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN review_status VARCHAR(20) DEFAULT 'approved';
        UPDATE qd_indicator_codes SET review_status = 'approved' WHERE publish_to_community = 1;
    END IF;
    
    -- Review note
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'review_note'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN review_note TEXT DEFAULT '';
    END IF;
    
    -- Reviewed at
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'reviewed_at'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN reviewed_at TIMESTAMP;
    END IF;
    
    -- Reviewed by
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_indicator_codes' AND column_name = 'reviewed_by'
    ) THEN
        ALTER TABLE qd_indicator_codes ADD COLUMN reviewed_by INTEGER;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_indicator_review_status ON qd_indicator_codes(review_status);

-- 5. User Table Extensions
DO $$
BEGIN
    -- Token version (for single-client login)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_users' AND column_name = 'token_version'
    ) THEN
        ALTER TABLE qd_users ADD COLUMN token_version INTEGER DEFAULT 1;
    END IF;
    
    -- Notification settings
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'qd_users' AND column_name = 'notification_settings'
    ) THEN
        ALTER TABLE qd_users ADD COLUMN notification_settings TEXT DEFAULT '{}';
    END IF;
END $$;

-- Migration Complete
DO $$
BEGIN
    RAISE NOTICE '✅ QuantDinger V2.1.1 database migration completed!';
END $$;
```

### 🗑️ Removed
- Old multi-agent AI analysis system (`backend_api_python/app/services/agents/` directory)
- Old analysis routes and services
- Standalone Global Market page (merged into AI Analysis)
- Reflection worker background process

### ⚠️ Breaking Changes
- AI Analysis API endpoints changed from `/api/analysis/*` to `/api/fast-analysis/*`
- Old analysis history data is not compatible with new format

### 📝 Configuration Notes
- No new environment variables required
- Existing LLM configuration in System Settings will be used for AI Analysis

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| V3.1.0 | 2026-05-02 | AI Agent Gateway (`/api/agent/v1`), MCP server with stdio/SSE/HTTP transports, SSE job progress streaming, Vue Admin UI for agent tokens & audit, paper-only-by-default trading safety, 4 new DB tables |
| V2.2.2 | 2026-02-28 | Polymarket prediction markets integration, AI-driven prediction analysis, asset trading recommendations |
| V2.2.1 | 2026-02-27 | Membership & Billing, USDT TRC20 payment, VIP free indicators, AI Trading Radar, simplified strategy creation |
| V2.1.3 | 2026-02-XX | Cross-sectional strategy support |
| V2.1.2 | 2026-02-01 | Indicator parameters, cross-indicator calling |
| V2.1.1 | 2026-01-31 | AI Analysis overhaul, Global Market integration, Indicator Community enhancements |

---

*For questions or issues, please open a GitHub issue or contact the maintainers.*
