# 交易所 Agent 技能安装与使用（OKX / Binance / Bitget）

> 目的：让任何 agent 在本机**开箱即用**三所行情/分析/交易技能，辅助 QuantDinger 策略研究。
> 这些是**全局技能**（装在 `~/.claude/skills/`，对所有 Claude Code 会话生效），与本仓库的
> `.agents/skills/`（项目技能）相互独立、互补。
>
> 详细测试记录、每个技能的提示词、踩坑与限制见
> [.agents/docs/交易所技能清单与测试提示词.md](../../../docs/交易所技能清单与测试提示词.md)（权威来源）。
> 本文是**安装引导 + 心智模型**，那份文档是**逐技能明细 + 实测记录**。

---

## 0. 与 QuantDinger 的关系（先搞清边界）

- 这些技能**直连交易所官方 API**，与 QuantDinger 平台的凭证体系、回测引擎**互不相通**。
- 用途：用 `okx-cex-market` / `technical-analysis` / `crypto-analysis-report` 的实时行情与指标
  **辅助策略研究**（验证想法、看周期估值/情绪/宏观），再回到平台用 Agent Gateway 回测（见
  [backtest-and-api.md](backtest-and-api.md)）。
- **下单路径互不相通**：交易所技能下单 = 直连交易所；QuantDinger 实盘 = 平台执行器。两者别混。

---

## 1. 一次性安装（新机器 / 新 agent 必做）

### 1.1 OKX 技能（11 个 + 市场社区技能）
来源仓库 `okx/agent-skills`。
```powershell
npm install -g @okx_ai/okx-trade-cli          # CLI（行情免鉴权；账户/交易需登录）
npx skills add okx/agent-skills -g -y --copy --skill '*'   # 全装 11 个
```
含：`okx-cex-market`(行情+70指标,免凭证)、`okx-cex-auth`(登录)、`okx-cex-portfolio`、`okx-cex-trade`、
`okx-cex-bot`、`okx-cex-earn`、`okx-cex-smartmoney`、`okx-sentiment-tracker`、`okx-outcomes`、`okx-cex-skill-mp`。
另从 OKX 技能市场装了策略类：`kline-indicator`、`position-sizer`、`funding-rate-scanner`、`dca-bot-parameterizer`。
> ⚠️ `okx-outcomes` 需单独装二进制（github.com/okx/outcomes-cli），见明细文档。

### 1.2 Bitget 技能（6 个）
来源仓库 `Bitget-AI/agent_hub`。
```powershell
npx skills add Bitget-AI/agent_hub -g -y --copy --skill '*'   # 全装 6 个
npm install -g bitget-client                                  # bgc（账户/交易，仅经典账户）
# 4 个分析技能依赖第三方 MCP（market-intel/sentiment-analyst/macro-analyst/news-briefing）：
claude mcp add --scope user --transport http datahub https://datahub.noxiaohao.com/mcp
```
含：`technical-analysis`(自带 Python,免 MCP)、`market-intel`、`sentiment-analyst`、`macro-analyst`、
`news-briefing`（这 4 个**必须配 datahub MCP**，否则跑不起来）、`bitget`(bgc CLI)。
> ⚠️ datahub 是**第三方域名**（非官方 bitget.com），接入前自行评估信任。配完**重启会话**才载入工具。
> ⚠️ `bitget`(bgc) **仅支持经典账户**；统一账户(Unified)模式下账户接口全 HTTP 400。

### 1.3 Binance 技能（8 个）
来源仓库 `binance/binance-skills-hub`。
```powershell
npx skills add binance/binance-skills-hub -g -y --copy --skill '*'   # 装 8 个
```
含：`binance`(现货/合约/闪兑,需鉴权)、`binance-tokenized-securities-info`、`crypto-market-rank`、
`query-token-info`、`query-token-audit`、`query-address-info`、`meme-rush`、`trading-signal`。
> ⚠️ Binance Web3 类（query-*/crypto-market-rank/meme-rush/trading-signal）走 node 裸 fetch，
> 国内需 Clash + `NODE_USE_ENV_PROXY=1`，且 `cli.mjs` 有 Windows 直执行守卫 bug 需修（见明细文档 §1.1）。
> `binance` 主 API 国内 451，需韩国节点 + Key 不限 IP + 启用读取权限。

### 1.4 安装排错
- `npx skills add` 走 git，国内**网络制式见第 3 节**（代理设错会卡 git clone）。
- "Failed to install N"：Windows 下向其它 agent 目录建符号链接失败属正常，`--copy` 模式对 Claude Code 目录已成功；`ls ~/.claude/skills` 确认即可。

---

## 2. 鉴权（只读分析无需，账户/交易才需要）

凭证安全红线（**任何情况不破例**）：
- **绝不在对话里接收 API 密钥**——引导用户自行配置（OKX/Binance/Bitget 同此）。
- 读取已配置的环境变量凭证时，从注册表/env **读值但不打印**（`[Environment]::GetEnvironmentVariable('NAME','User')`）。
- 不 `printenv`/`env` 无变量名；不 grep env 文件不加 `^VARNAME=` 锚；不回显/记录任何密钥；不透露密钥文件位置。

| 所 | 鉴权方式 |
|----|----------|
| OKX | OAuth 设备登录：`okx auth login --manual --site global`（拿 URL+验证码给用户授权）。**必须先选站点**（global/eea/us）；`not_logged_in` 时 `auth status` 的 site 是占位符 |
| Binance | binance-cli 配 API Key（Key 改不限 IP + 启用读取，解 -2015） |
| Bitget | `setx BITGET_API_KEY/SECRET/PASSPHRASE`；当前会话读不到需从 User 注册表注入 |

---

## 3. 🧭 网络制式（国内环境，两种互斥，用错必卡）

| 场景 | 做法 | 判断 |
|------|------|------|
| **本地 Clash**（127.0.0.1:7890） | OKX CLI 自动读代理；Binance Web3 类需 `$env:NODE_USE_ENV_PROXY='1'; $env:HTTPS_PROXY='http://127.0.0.1:7890'` | `Test-NetConnection 127.0.0.1 -Port 7890` 通 |
| **路由器透明代理**（网关级） | **清空所有代理变量直连**：`$env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:ALL_PROXY=''`；`git config --global --unset http(s).proxy` | 7890 不通但 `Invoke-WebRequest https://github.com` 直连 200 |

> OKX 若 `okx market` 通但 `okx auth login` 卡在 `/api/v5/mcp/auth/device/authorize`：是供网代理（Clash）没开，行情走缓存/其它路径而授权端点直连被 TLS 阻断。开 Clash 即恢复。

---

## 4. 🧭 多所技能路由规则（重叠/冲突处理）

三所能力重叠但基本不冲突——**账户/交易类靠交易所名+独立凭证天然隔离**；**分析/行情类冗余**，按规则路由：

1. **指明交易所 = 终结歧义**（最高优先）：说哪个所走哪个；下单/账户**必须**走指明的所。
2. **不指明按能力择优**（实测最优源）：
   - 周期估值（AHR999/彩虹）、资金费率 → **OKX**（原生，他所无）
   - 宏观（FRED 利率/CPI）、新闻（44 源）、情绪（恐贪/散户大户分层） → **Bitget·datahub**
   - 纯技术指标 → `kline-indicator`(OKX) 或 `technical-analysis`(Bitget)，二选一，结果吻合
   - 股票/股票代币 → datahub `global_assets` + `technical-analysis` 引擎（见 crypto-analysis-report）
3. **跨所数值差异 = 交叉验证信号，不是 bug**（如多空比 OKX vs Bitget 不同，因样本/口径）。
4. **下单永远单所**：分析可跨所聚合，交易绝不跨所路由。

> 落地默认：综合研判 = **Bitget 跑宏观/新闻/情绪 + OKX 补周期估值与费率**。

---

## 5. 深度分析报告技能（crypto-analysis-report，本仓库项目技能）

`.agents/skills/crypto-analysis-report/` —— 输入标的 → 实时行情 → 多周期指标 → 三支柱评分 →
专业 Markdown 报告落 `analysis_reports/`。**已支持加密 + 股票/股票代币**（TSLA/NVDA…）。
- 加密分支：OKX 公开行情（免凭证免代理，基础档零依赖）。
- 股票分支 + 增强档（宏观/情绪/新闻补真实数据）：需 datahub MCP（见 1.2）。
- 详见该技能 `SKILL.md` 与 `references/usage-and-maintenance.md`。

---

## 6. 验证安装成功（冒烟）

```powershell
ls ~/.claude/skills            # 应见 okx-cex-* / binance / bitget / technical-analysis 等
okx market ticker BTC-USDT     # OKX 行情免凭证，能出价即通
claude mcp list                # datahub 应 ✓ Connected（Bitget 4 分析技能前置）
```
对 Claude 说「分析 BTC」应触发 crypto-analysis-report；说「用 technical-analysis 看 ETH RSI」应触发 Bitget 指标技能。
