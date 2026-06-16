---
name: crypto-analysis-report
version: 1.2.0
date: 2026-06-13
updated: 2026-06-16
description: >-
  加密货币与股票/股票代币深度分析与专业报告生成技能。获取实时行情、计算多周期
  技术指标、按三支柱框架评分（加密：宏观30%+量价40%+衍生品30%；股票：估值30%+
  量价40%+市场30%），生成结构化 Markdown 专业分析报告。支持单标的与多标的；
  多标的时各自独立成报告。当用户说"分析 BTC/ETH/SOL"、"分析 TSLA/NVDA/AAPL 股票"、
  "分析特斯拉股票代币"、"生成行情报告"、"深度分析某币/某股"、"出一份专业报告"
  时使用。报告落盘到 analysis_reports/<symbol>_report_<时间戳>.md。
---

<!-- 变更日志（维护用）：
  v1.2.0 (2026-06-16) — 数据源唯一化：真股仅 Yahoo Finance、股票代币仅 Bitget（移除 binance-tokenized-securities-info）；新增 version/date/updated 维护字段。
    前置依赖：明确真股=Yahoo、代币=Bitget，禁 OKX 股票永续/Binance RWA/datahub 替代
  v1.1.0 (2026-06-15) — 新增股票/股票代币分支（股票三支柱）+ 多所数据源路由（基础档/增强档）。
  v1.0.0 (2026-06-13) — 加密三支柱报告流程初版（OKX 行情）。
-->


# 加密货币 / 股票深度分析报告技能

把"实时数据 → 技术指标 → 三支柱深度分析 → 专业 Markdown 报告"固化为可复用流程。
**加密**走 OKX 公开行情（**免凭证、免代理**，国内可直连 okx CLI）；**股票（真股）只走
Yahoo Finance 真股数据**，**股票代币只走 Bitget 股票代币现货数据**，指标由 technical-analysis
引擎或等价本地公式计算。分析框架复用本机全局技能 `kline-indicator`
（技术分析大师）的三支柱评分法。两类标的的取数与降级策略见下方「数据源路由」。

> 📖 **新人使用 + 维护管理文档**：[references/usage-and-maintenance.md](references/usage-and-maintenance.md)
> （含提示词示例、报告速读、维护红线、改完技能的自测清单）。第一次用或要改这个技能先看它。

## 何时使用

- "分析 BTC / 帮我看看 ETH 行情 / 出一份 SOL 专业报告"
- "分析 TSLA / NVDA 股票 / 特斯拉股票代币"（股票分支：真股仅 Yahoo Finance，股票代币仅 Bitget）
- "同时分析 BTC、ETH、SOL"（多标的 → 各自独立报告；加密与股票可混合）
- 需要带评分、关键价位、下一步行动清单的结构化研究报告

## 前置依赖

- **okx CLI**（基础档必需）：`npm install -g @okx_ai/okx-trade-cli`（行情命令免鉴权、免代理）。
- **Yahoo Finance 公共 chart 数据**（股票真股必需）：仅用于 TSLA/NVDA/AAPL/MSFT 等真股价格、OHLCV、52 周区间、成交量等；不得用 OKX 股票映射永续、Binance RWA 或 datahub 替代。
- **Bitget 公开股票代币现货接口**（股票代币必需）：仅用于 `TSLAONUSDT`/`NVDAONUSDT`/`AAPLONUSDT` 等股票代币价格与 OHLCV；不得用 OKX `TSLA-USDT-SWAP`/`NVDA-USDT-SWAP` 等股票映射永续替代。
- **datahub MCP**（加密增强档可选）：仅用于加密宏观/情绪/新闻增强；**不得用于股票（真股）或股票代币取数**。
- 全局技能 `kline-indicator` 提供三支柱框架定义（`references/three-pillars.md`）；
  本技能内置了评分口径，无该技能也可独立运行。

## 输出约定（务必遵守）

- 目录：`analysis_reports/`（不存在则创建）。
- 文件名：`<symbol>_report_<YYYYMMDDHHmmss>.md`，symbol 用小写无斜杠，
  如 `btc_report_20260613174319.md`、`eth_report_20260613174320.md`。
- **多币种 = 每个币一个独立文件**，不要合并成一份。
- 报告语言中文；格式 Markdown；**必须含免责声明**（仅研究参考、非投资建议）。

---

## 数据源路由（唯一口径，报告内适用）

本技能**只做分析/取数、不下单**。股票相关资产采用唯一数据源口径，禁止跨源替代：

| 资产类型 | 唯一取数源 | 禁止替代源 |
|----------|------------|------------|
| 加密货币 | OKX 公开行情；可选 datahub 只补加密宏观/情绪/新闻 | 不用股票数据源替代 |
| 股票（真股） | **Yahoo Finance 真股 chart 数据** | 禁止 OKX 股票映射永续、Binance RWA、datahub 作为股票取数源 |
| 股票代币 | **Bitget 股票代币现货**（如 `TSLAONUSDT`） | 禁止 OKX `TSLA-USDT-SWAP` 等股票映射永续、Binance RWA、Yahoo 代替代币价 |

**加密分支**仍分两档运行，自动降级，绝不因缺数据源而编造：

| 档位 | 触发条件 | 取数策略 |
|------|----------|----------|
| **基础档**（默认·零依赖） | 仅有 okx CLI | 全走 OKX 公开行情（免凭证免代理）。宏观面/情绪面/新闻维度**如实标「数据缺失/需额外数据源」** |
| **增强档**（自动启用） | datahub MCP 已配（`claude mcp list` 见 datahub Connected） | 仅补加密宏观/情绪/新闻，把原「数据缺失」维度升级为真实数据 |

**增强档能力择优表**（实测最优源）：

| 维度 | 取自 | 说明 |
|------|------|------|
| 周期估值（AHR999/彩虹/抄底区） | **OKX** `okx market indicator ahr999/rainbow` | 原生，datahub 无 |
| 资金费率 | **OKX** `okx market funding-rate` | datahub 不暴露 funding |
| 多周期技术指标 | **OKX**（默认）或 technical-analysis 引擎 | 二者吻合 |
| 宏观（利率/收益率曲线/CPI/就业） | **Bitget·datahub** `rates_yields`/`macro_indicators` | FRED 官方全套 |
| 恐惧贪婪指数 | **Bitget·datahub** `sentiment_index` | OKX 无 |
| 情绪/多空分层（散户vs大户/OI） | **Bitget·datahub** `derivatives_sentiment` | 可拆散户/大户+OI 趋势 |
| 新闻简报 | **Bitget·datahub** `news_feed`（44 源） | 时效强、多空双视角 |
| DXY/VIX | WebSearch（如可用） | 两所均无原生 |

**规则③落地**：增强档若同时取到多所同类指标（如多空比 OKX vs Bitget），报告中**标注来源并交叉验证**，差异大视为信号（如散户/大户背离），不当作错误。报告头的「数据源」据实列出实际用到的源。

> 这样：加密基础档报告与改造前完全一致（向后兼容）；加密增强档自动让宏观/情绪/新闻三块从「--」升级为真实数据。股票与股票代币不走增强档混源。

## 工作流

### 第 0 步 · 解析标的列表并判定资产类型

从用户输入提取一个或多个标的，**先判定资产类型**，再走对应分支：

| 资产类型 | 识别特征 | 走哪条流程 |
|----------|----------|-----------|
| **加密货币** | BTC / ETH / SOL / 主流币名 | 第 1A–4 步（加密三支柱，本节默认流程） |
| **股票（真股）** | TSLA / NVDA / AAPL / MSFT、"特斯拉股票"、"英伟达股票" | **见后文「股票 / 股票代币分析（资产类型扩展）」**，只取 Yahoo Finance 真股 |
| **股票代币** | 明确说"股票代币"、`TSLAON`/`TSLAONUSDT`、`NVDAON`/`NVDAONUSDT`、`xStock` | **见后文「股票 / 股票代币分析（资产类型扩展）」**，只取 Bitget 股票代币 |

加密统一成 OKX instId：
- 现货 ticker / 指标：`BTC-USDT`、`ETH-USDT`、`SOL-USDT`
- 永续（资金费率/持仓量）：`BTC-USDT-SWAP`
- 多标的：逐个循环，**每个标的走完取数→评分→落盘并各自独立成报告**；加密与股票可混合请求，各按自己的分支处理。

### 第 1A 步 · 拉实时数据与指标（加密分支，每个币）

OKX 行情命令（免凭证；指标日线周期写 `1Dutc`，K线周期写 `1D`——两者不同）：

```bash
okx market ticker BTC-USDT                                  # 现价/24h高低/量/涨跌
okx market indicator rsi BTC-USDT --bar 15m                 # 多周期 RSI
okx market indicator rsi BTC-USDT --bar 1H
okx market indicator rsi BTC-USDT --bar 4H
okx market indicator rsi BTC-USDT --bar 1Dutc
okx market indicator macd BTC-USDT --bar 1H                 # 多周期 MACD
okx market indicator macd BTC-USDT --bar 4H
okx market indicator macd BTC-USDT --bar 1Dutc
okx market indicator bb  BTC-USDT --bar 1Dutc               # 布林带（日/4H）
okx market indicator bb  BTC-USDT --bar 4H
okx market indicator kdj BTC-USDT --bar 1Dutc               # KDJ
okx market indicator ema BTC-USDT --bar 1Dutc --params 50   # 均线结构（趋势）
okx market indicator ema BTC-USDT --bar 1Dutc --params 200
okx market indicator atr BTC-USDT --bar 1Dutc --params 14   # ATR（开仓指南/波动性/止损止盈用）
okx market indicator ma  BTC-USDT --bar 1Dutc --params 5    # MA5/10/20（量化参数明细）
okx market indicator ma  BTC-USDT --bar 1Dutc --params 10
okx market indicator ma  BTC-USDT --bar 1Dutc --params 20
okx market indicator ahr999   BTC-USDT --bar 1Dutc          # 宏观周期（仅 BTC）
okx market indicator rainbow  BTC-USDT --bar 1Dutc          # 彩虹图（仅 BTC）
okx market indicator top-long-short BTC-USDT --bar 1Dutc    # 顶级交易员多空比（大数据）
okx market candles BTC-USDT --bar 1D --limit 3              # 取上一日 H/L/C 算经典枢轴
okx market funding-rate BTC-USDT-SWAP                       # 资金费率
okx market open-interest --instType SWAP --instId BTC-USDT-SWAP   # 持仓量
```

**经典枢轴**（用上一根已收盘日线的 H/L/C 自算）：
```
Pivot = (H + L + C) / 3
R1 = 2·Pivot − L ；S1 = 2·Pivot − H
R2 = Pivot + (H − L) ；S2 = Pivot − (H − L)
```

**带宽% / 区间位置 / 波动性**：
```
布林带宽% = (BB_upper − BB_lower) / BB_middle × 100
20日区间位置% = (现价 − 20日最低) / (20日最高 − 20日最低) × 100
波动性 = ATR / 现价 × 100   （≤2% 低 · 2–5% 中 · >5% 高，阈值对齐后端）
```

提取要点提醒：
- RSI 表格值在 `^\s*14\s` 行（period 列+值），过滤时别误删值行。
- 指标若返回 "requires a period" 用 `--params`（EMA→50/200，MA→5/10/20，ATR→14，supertrend→`10,3`）。
- `ahr999`/`rainbow` **仅 BTC 支持**；其它币种该支柱用价格位置/均线替代估值维度。
- 部分维度（基本面深度、情绪面 DXY/VIX/新闻、交易所净流/稳定币净流、预测市场）**OKX 行情无法提供**，报告中如实标注「数据缺失/需额外数据源」，**不得编造**（参考报告里这些字段也显示为 `--`）。

### 第 2 步 · 三支柱评分（每个币）

| 支柱 | 权重 | 数据 | 打分方向 |
|------|------|------|----------|
| 宏观周期 | 30% | AHR999、彩虹图、价格 vs EMA50/200 | **分数越低=越低估=越利多**（0-20 深度价值 … 80-100 狂热） |
| 量价因子 | 40% | 多周期 RSI/MACD 共振、布林位置、KDJ、均线结构 | 0-100，越高越强势 |
| 衍生品 | 30% | 资金费率（负=空头付费=偏多）、持仓量 | 0-100，越高越偏多 |

`综合 = 宏观×0.30 + 量价×0.40 + 衍生品×0.30`（0-100）

信号分区：0-20 极度低估/抄底 · 20-40 复苏 · 40-60 中性 · 60-80 过热减仓 · 80-100 狂热对冲。
据综合分给 **BUY / NEUTRAL / SELL**（含中文：买入/中性/卖出）+ 置信度。

> ⚠️ **诚实第一**：信号必须由真实数据算出，**不得照抄任何样例报告的结论**。
> 多空交织时如实给 NEUTRAL，别为"好看"硬凑方向。

### 第 2.5 步 · 开仓指南（ATR×结构 融合，对齐后端引擎）

> 算法**对齐后端** `MarketDataCollector._calculate_indicators` 的 `trading_levels`（method=
> `atr_support_resistance`），即平台专业报告同款口径——ATR 与支撑/阻力结构融合，比裸 ATR 更稳。

**第一步：算结构化支撑/阻力（三方法平均）**
```
support    = (枢轴 S1 + 20日摆动低 swing_low + 布林下轨 BB_lower) / 3
resistance = (枢轴 R1 + 20日摆动高 swing_high + 布林上轨 BB_upper) / 3
```

**第二步：ATR 与结构融合定止损止盈（多单）**
```
止损 = max(现价 − 2×ATR, support × 0.99)      # ATR止损 与 支撑位 取更保守(更高)者，略低于支撑
止盈 = min(现价 + 3×ATR, resistance × 1.01)   # ATR止盈 与 阻力位 取更近(更低)者，略高于阻力
风险回报比 = (止盈 − 现价) / (现价 − 止损)
建议入场 = 现价附近回踩（参考 Pivot / MA5）；RR 与止损止盈均以现价为基准计算
空单：止损 = min(现价 + 2×ATR, resistance×1.01)；止盈 = max(现价 − 3×ATR, support×0.99)，方向镜像
```

- ATR 用日线 ATR(14)；倍数固定 **2×(止损)/3×(止盈)** 与后端一致，报告注明「基于 ATR 波动率」。
- 方向跟随综合信号；NEUTRAL 给多单参考并标注「观望优先」。
- 这组止损止盈即「量化参数明细」里的支撑/阻力同源，全报告**逻辑自洽**。

### 第 3 步 · 套用报告模板渲染

按下面「报告模板」逐节填充。板块顺序固定，含 **下一步（行动清单）** 板块。

### 第 4 步 · 落盘

写入 `analysis_reports/<symbol>_report_<时间戳>.md`。多币种重复第 1–4 步。
最后向用户汇总：生成了哪几份报告（带可点击路径）+ 每份的一句话结论。

---

## 报告模板

````markdown
# <SYMBOL>/USDT 深度分析报告

> 生成时间：<YYYY-MM-DD HH:mm:ss> (UTC+8) ｜ 数据源：OKX 实时行情 ｜ 分析框架：三支柱评分（宏观30% + 量价40% + 衍生品30%）
> ⚠️ 本报告仅为客观技术分析与数据整理，**不构成投资建议**。加密资产波动剧烈，请自行研究（DYOR）并自担风险。

---

## 综合结论
| 项目 | 结果 |
|------|------|
| **综合信号** | <🟢 BUY 买入 / 🟡 NEUTRAL 中性 / 🔴 SELL 卖出> |
| **综合评分** | **<分>/100**（<分区>） |
| **置信度** | <高/中/低 ~xx%> |
| **市场阶段** | <一句话定位> |
| **当前价格** | **$<价>**（24h <涨跌>） |

**一句话**：<多空因素综述与倾向>

### 多周期客观共识
| 项目 | 值 |
|------|-----|
| 共识方向 | <BUY/HOLD/SELL> |
| 周期一致度 | <xx%>（5 个周期信号同向比例） |
| 多周期评分 | <-5 ~ +5> |

---

## 下一步（行动清单）
按当前 <信号>（评分 <分>）的定位，建议的下一步动作（按优先级）：
1. **🎯 盯关键位**：<阻力/支撑具体价位与触发条件>
2. **📥 / ⏳ 操作倾向**：<定投/观望/试仓，结合分区>
3. **🛡️ 持仓处理**：<止损位、减仓位>
4. **🔁 复核节奏**：<按哪个周期收盘复核哪些指标>
5. **🔬 进阶**：如需精确仓位张数，调用 `position-sizer`

### 📋 开仓指南（ATR×结构融合，对齐后端引擎，仅供参考）
| 项目 | 价位 | 说明 |
|------|------|------|
| 当前价格 | $<价> | <24h 涨跌> |
| 建议入场 | $<入场> | <回踩位依据：Pivot/MA5> |
| 止损价 | $<止损> | max(现价−2×ATR, 支撑×0.99)；ATR=<值>，支撑=$<值> |
| 止盈目标 | $<止盈> | min(现价+3×ATR, 阻力×1.01)；阻力=$<值> |
| 风险回报比 | 1 : <RR> | 多/空单参考 |

> 结构化支撑/阻力为三方法平均（枢轴+20日摆动+布林）。以上为基于数据的行动倾向，非投资建议。

---

## 一、实时市场数据
<现价 / 24h 高低 / 涨跌 / 成交量 / 持仓量 / 资金费率 表>

## 二、周期趋势预判
| 周期 | 方向 | 强度 |
|------|------|------|
| 约 24 小时 | <上涨/震荡/下跌> | <强度值/neutral> |
| 约 3 天 | … | … |
| 约 1 周 | … | … |
| 约 1 月 | … | … |

## 三、Crypto 交易大数据
| 项目 | 值 |
|------|-----|
| 24h 成交量 | <BTC 量> |
| 资金费率 | <值>（正=多头付费/负=空头付费） |
| 未平仓量 OI | <值> |
| 顶级交易员多空比 | <long/short>（=<比值>） |
| 交易所净流 | -- （数据缺失，OKX 行情不提供） |
| 稳定币净流 | -- （数据缺失） |

> 因子偏向：<中性/偏多/偏空>；挤仓风险：<低/中/高>。

## 四、三支柱评分拆解
### 支柱一 · 宏观周期（30%）— 评分 ≈ <分>
<AHR999 / 彩虹图 / 均线估值 表 + 解读；非 BTC 注明 AHR999 不适用、改用均线/布林近似>
### 支柱二 · 量价因子（40%）— 评分 ≈ <分>
<多周期 RSI 表 + 多周期 MACD 表 + 布林/KDJ/均线 + 解读>
### 支柱三 · 衍生品（30%）— 评分 ≈ <分>
<资金费率 / 持仓量 / 多空比 表 + 解读>
### 综合评分
<计算式>

## 五、技术指标 PRO
| 指标 | 值 | 状态 |
|------|-----|------|
| RSI(14) 1D | <值> | <超买/中性/超卖> |
| MACD(12,26,9) 1D | <金叉/死叉> | <看涨/看跌> |
| 均线趋势 | <上升/下降/震荡> | — |
| ATR(14) | $<值> | 真实波幅均值 |
| 布林带宽 % | <值>% | <挤压/扩张> |
| 20 日区间位置 | <值>% | 0–100% |
| 量比 | <值>× | 相对 20 均量 |
| 支撑位 | $<值> | — |
| 阻力位 | $<值> | — |
| 波动性 | <低/中/高>(<值>%) | ATR/Price |

## 六、量化参数明细
| 参数 | 值 | 参数 | 值 |
|------|-----|------|-----|
| MACD DIF(快线) | <值> | MA(5) | $<值> |
| MACD DEA(信号线) | <值> | MA(10) | $<值> |
| MACD 柱(动能) | <值> | MA(20) | $<值> |
| 布林上轨 U | $<值> | 经典枢轴 Pivot | $<值> |
| 布林中轨 MB | $<值> | 支撑 S1 / 阻力 R1 | $<值> / $<值> |
| 布林下轨 L | $<值> | 支撑 S2 / 阻力 R2 | $<值> / $<值> |
| 布林带宽 % | <值>% | 20 周期摆动高/低 | $<值> / $<值> |
| ATR(14) 绝对值 | $<值>(<%>) | 风险回报(多单参考) | 1 : <RR> |
| 计算用收盘价 | $<值> | — | — |

## 七、详细分析
**技术面**：<多周期/形态/结构详述>
**衍生品面**：<资金费率/OI/多空比/挤仓详述>
**宏观面**：<周期估值详述；非 BTC 注明数据限制；**增强档**补 FRED 利率/CPI、恐贪指数、44 源新闻>
> 基础档：基本面深度与情绪面（DXY/VIX/新闻）需额外数据源暂缺。**增强档（datahub 已配）**：宏观/情绪/新闻据实填真实数据并注明来源（见「数据源路由」）。

## 八、核心理由与风险
**核心理由**：<3 条>
**风险提示**：<3-4 条>

## 九、操作倾向（仅供参考，非投资建议）
<长线/波段/合约 三类风格倾向表>

---
> 数据快照时间：<时间>。技术指标为时点值，决策前请复核最新数据。
> 本报告由 crypto-analysis-report 技能自动生成，**仅供研究参考，不构成任何投资建议**。
````

---

## 股票 / 股票代币分析（资产类型扩展）

当第 0 步判定为**股票/股票代币**时走本节，取数与评分换成股票口径，**评分完成后回到上面共享的第 3 步（渲染）、第 4 步（落盘）**。整体仍是「实时数据 → 多周期指标 → 三支柱评分 → 专业报告」，只是支柱定义与数据源不同。

> ⚠️ 依赖 **datahub MCP**（`claude mcp add --scope user --transport http datahub https://datahub.noxiaohao.com/mcp`，需重启会话载入）与 **technical-analysis** 技能的指标引擎。MCP 未配时本分支不可用，需先按 §维护文档配置。

### 第 1B 步 · 拉股票数据（每个标的）

> 🔒 **数据源唯一化（硬性规定）**：**真股数据只取 Yahoo Finance；股票代币数据只取 Bitget。**
> 二者不得混用、不得用其它来源替代（如不得用 Bitget 代币价当真股价、不得用其它交易所/技能取股票数据）。

**真股票**（标的本体）——**数据源唯一 = Yahoo Finance 直连**（不经 datahub，见前置依赖）。周期 `1d`，区间 `1y` 起。
真股的**现价 / OHLCV / 52周 / 均线 / ATR / 指标 / 与大盘相关性 / 基本面**全部来自 Yahoo Finance：
```
# 真股 OHLCV + 现价（meta.regularMarketPrice）：
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/TSLA?range=1y&interval=1d"
# 与大盘相关性（市场面，可选）：同样直连 Yahoo 拉 TSLA 与 ^NDX/^GSPC 日线，自算 Pearson 相关系数
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/%5ENDX?range=3mo&interval=1d"   # 纳指
```
- 基本面（P/E、股息率、52周）若需要，**同源 Yahoo Finance**（chart meta / quoteSummary）；Yahoo 取不到则报告标注「需额外数据源」，**不得编造、不得改用其它源**。

**股票代币**（用户问代币或要算溢价时）——**数据源唯一 = Bitget 现货**。符号形如 `TSLAONUSDT`/`NVDAONUSDT`/`AAPLONUSDT`/`MSFTONUSDT`：
```
curl -s "https://api.bitget.com/api/v2/spot/market/candles?symbol=TSLAONUSDT&granularity=1day&limit=120"
curl -s "https://api.bitget.com/api/v2/spot/market/tickers?symbol=TSLAONUSDT"   # 代币现价/24h量
```
- **溢价/折价% = (Bitget 代币价 − Yahoo 真股价) / Yahoo 真股价 × 100**（正=溢价、负=折价；折价深=潜在套利/抛压信号）。这是唯一允许跨两源的派生量（分子取 Bitget、分母取 Yahoo）。
- 代币的现价、24h 量、K 线**只用 Bitget**；Bitget 无该代币则报告标注「该代币 Bitget 未上市/数据缺失」，**不得用真股价或其它源冒充代币价**。

**指标计算**——把对应来源的 OHLCV（真股→Yahoo；代币→Bitget）喂给 **technical-analysis 引擎**（`~/.claude/skills/technical-analysis/src/kline_indicator_utils.py` 的 `IndicatorManager`，已实测可吃股票/股票代币 K 线）算 RSI/MACD/BOLL/KDJ/MA/ATR；ATR 取引擎 `ATR.series.ATR`（NATR 为波动率%）。报告主体技术指标以**真股（Yahoo）**为准，代币仅用于溢价与代币持有者视角。**勿用** datahub `technical_analysis` 工具算股票——它只接受 `X/USDT` 形态、仅限加密。枢轴/带宽%/区间位置/波动性公式与加密分支**完全一致**（复用上文）。

### 第 2B 步 · 股票三支柱评分（每个标的）

权重不变（30/40/30），把加密专属支柱替换为股票口径：

| 支柱 | 权重 | 股票数据 | 打分方向 |
|------|------|----------|----------|
| **估值/基本面** | 30% | P/E vs 行业、52周区间位置、价 vs EMA50/200、（代币）溢价/折价 | **越低估=越利多**（替代加密的 AHR999/彩虹） |
| **量价因子** | 40% | 多周期 RSI/MACD/BOLL/KDJ/均线（引擎与加密通用） | 0-100，越高越强势 |
| **市场/资金面** | 30% | 真股成交量趋势、与纳指/标普相关性（均 Yahoo 源）、（代币）Bitget 溢价/折价 | 替代加密的资金费率/OI；顺大盘+健康溢价=偏多 |

`综合 = 估值×0.30 + 量价×0.40 + 市场×0.30`（0-100）；信号分区 / BUY-NEUTRAL-SELL / 置信度口径同加密分支。**诚实第一，禁止照抄样例结论。**

> 注意股票特性：①**仅美股交易时段有实时波动**，盘后/周末为静态值，报告标注快照时段；②股票代币可能 24/7 交易但流动性低、溢价波动大；③无永续资金费率/OI，相关字段标注 `N/A（股票无永续合约）`。

### 第 2.5B 步 · 开仓指南

ATR×结构融合算法**与加密分支完全相同**（support/resistance 三方法平均 → 止损 max(价−2×ATR, 支撑×0.99)、止盈 min(价+3×ATR, 阻力×1.01)）。ATR 用日线 ATR(14)。**额外标注**：股票需考虑交易时段（跳空风险）、股票代币需标注溢价回归风险。

### 第 3–4 步（共享）

回到上面**共享的第 3 步渲染、第 4 步落盘**。报告模板沿用同一套，按下表做**股票版字段替换**（其余板块结构不变）：

| 模板板块 | 股票版改动 |
|----------|-----------|
| 标题 H1 | 去掉 `/USDT`，写 `# <TICKER> 深度分析报告（股票 / 股票代币）` |
| 报告头 | 数据源写「Yahoo Finance 真股 + Bitget 股票代币」；框架写「股票三支柱（估值30%+量价40%+市场30%）」 |
| 一、实时市场数据 | 加：真股价 / 代币价 / **溢价折价%** / 52周高低 / 成交量；删永续 OI/资金费率行 |
| 三、Crypto 交易大数据 | 改标题为「三、市场与资金面数据」：真股成交量趋势、**与纳指/标普相关性**（Yahoo）、（代币）Bitget 溢价/折价；资金费率/OI = `N/A（股票无永续）`；链上持有人/流动性 = `N/A（Bitget 不提供，已不取 binance 源）` |
| 四、三支柱评分拆解 | 用**股票三支柱**（估值/基本面、量价、市场/资金面） |
| 七、详细分析 | 「宏观面」改为「**基本面**」：P/E/股息/财报/52周位置；「衍生品面」改为「**市场面**」：相关性/溢价/成交量 |
| 免责声明 | 追加：证券投资风险、**股票代币溢价回归与赎回风险**、**仅美股时段实时**、非证券投资建议 |

文件名：`<ticker>_report_<时间戳>.md`，ticker 小写，如 `tsla_report_20260615...md`、`nvda_report_...md`。

---

## 范例参考

已落盘的标准范例：`analysis_reports/btc_report_20260614175608.md`（BTC，含全部 9 个板块、
多周期共识、开仓指南、技术指标 PRO、量化参数明细）。新报告的结构、表格粒度、免责口径应与之对齐。
股票版报告在此基础上按「股票版字段替换」表调整支柱与数据面板。

## 多币种处理要点

- 串行处理：A 币走完 1-4 步落盘 → B 币重复，**互不混写**。
- 时间戳逐个生成（同一秒可加序号避免重名），文件名前缀用各自 symbol。
- AHR999/彩虹图仅 BTC 有；其它币种宏观支柱改用"价格 vs EMA50/200 + 布林位置"近似估值，并在报告里注明该差异。
- 汇总回复：列出 N 份报告路径 + 各自信号/评分一行速览。
