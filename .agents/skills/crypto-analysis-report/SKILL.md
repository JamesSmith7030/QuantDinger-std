---
name: crypto-analysis-report
description: >-
  加密货币深度分析与专业报告生成技能。获取实时行情、计算多周期技术指标、
  按三支柱框架（宏观30% + 量价40% + 衍生品30%）评分，生成结构化 Markdown
  专业分析报告。支持单币种与多币种；多币种时各自独立成报告。当用户说
  "分析 BTC/ETH/SOL"、"生成行情报告"、"深度分析某币"、"出一份专业报告"
  时使用。报告落盘到 analysis_reports/<symbol>_report_<时间戳>.md。
---

# 加密货币深度分析报告技能

把"实时数据 → 技术指标 → 三支柱深度分析 → 专业 Markdown 报告"固化为可复用流程。
数据走 OKX 公开行情（**免凭证、免代理**，国内可直连 okx CLI），分析框架复用本机全局
技能 `kline-indicator`（技术分析大师）的三支柱评分法。

> 📖 **新人使用 + 维护管理文档**：[references/usage-and-maintenance.md](references/usage-and-maintenance.md)
> （含提示词示例、报告速读、维护红线、改完技能的自测清单）。第一次用或要改这个技能先看它。

## 何时使用

- "分析 BTC / 帮我看看 ETH 行情 / 出一份 SOL 专业报告"
- "同时分析 BTC、ETH、SOL"（多币种 → 各自独立报告）
- 需要带评分、关键价位、下一步行动清单的结构化研究报告

## 前置依赖

- **okx CLI**：`npm install -g @okx_ai/okx-trade-cli`（行情命令免鉴权、免代理）。
- 全局技能 `kline-indicator` 提供三支柱框架定义（`references/three-pillars.md`）；
  本技能内置了评分口径，无该技能也可独立运行。

## 输出约定（务必遵守）

- 目录：`analysis_reports/`（不存在则创建）。
- 文件名：`<symbol>_report_<YYYYMMDDHHmmss>.md`，symbol 用小写无斜杠，
  如 `btc_report_20260613174319.md`、`eth_report_20260613174320.md`。
- **多币种 = 每个币一个独立文件**，不要合并成一份。
- 报告语言中文；格式 Markdown；**必须含免责声明**（仅研究参考、非投资建议）。

---

## 工作流

### 第 0 步 · 解析币种列表

从用户输入提取一个或多个币种，统一成 OKX instId：
- 现货 ticker / 指标：`BTC-USDT`、`ETH-USDT`、`SOL-USDT`
- 永续（资金费率/持仓量）：`BTC-USDT-SWAP`
- 多币种：逐个循环，**每个币走完第 1–4 步并各自落盘一份报告**。

### 第 1 步 · 拉实时数据与指标（每个币）

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
okx market indicator ahr999   BTC-USDT --bar 1Dutc          # 宏观周期（仅 BTC）
okx market indicator rainbow  BTC-USDT --bar 1Dutc          # 彩虹图（仅 BTC）
okx market funding-rate BTC-USDT-SWAP                       # 资金费率
okx market open-interest --instType SWAP --instId BTC-USDT-SWAP   # 持仓量
```

提取要点提醒：
- RSI 表格值在 `^\s*14\s` 行（period 列+值），过滤时别误删值行。
- 指标若返回 "requires a period" 用 `--params`（EMA→50/200，supertrend→`10,3`）。
- `ahr999`/`rainbow` **仅 BTC 支持**；其它币种该支柱用价格位置/均线替代估值维度。

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

---

## 下一步（行动清单）
按当前 <信号>（评分 <分>）的定位，建议的下一步动作（按优先级）：
1. **🎯 盯关键位**：<阻力/支撑具体价位与触发条件>
2. **📥 / ⏳ 操作倾向**：<定投/观望/试仓，结合分区>
3. **🛡️ 持仓处理**：<止损位、减仓位>
4. **🔁 复核节奏**：<按哪个周期收盘复核哪些指标>
5. **🔬 进阶**：如需精确入场/止损/张数，调用 `position-sizer`
> 以上为基于数据的行动倾向，非投资建议。

---

## 一、实时市场数据
<现价 / 24h 高低 / 涨跌 / 成交量 / 持仓量 / 资金费率 表>

## 二、三支柱评分拆解
### 支柱一 · 宏观周期（30%）— 评分 ≈ <分>
<AHR999 / 彩虹图 / 均线估值 表 + 解读>
### 支柱二 · 量价因子（40%）— 评分 ≈ <分>
<多周期 RSI 表 + 多周期 MACD 表 + 布林/KDJ/均线 + 解读>
### 支柱三 · 衍生品（30%）— 评分 ≈ <分>
<资金费率 / 持仓量 表 + 解读>
### 综合评分
<计算式>

## 三、关键价位
<阻力/现价/支撑 表，依据 EMA、布林轨>

## 四、核心观点
<3 条>

## 五、风险提示
<3-4 条>

## 六、操作倾向（仅供参考，非投资建议）
<长线/波段/合约 三类风格倾向表>

---
> 数据快照时间：<时间>。技术指标为时点值，决策前请复核最新数据。
> 本报告由 crypto-analysis-report 技能自动生成，**仅供研究参考，不构成任何投资建议**。
````

---

## 范例参考

已落盘的标准范例：`analysis_reports/btc_report_20260613174319.md`（BTC，含全部板块与下一步）。
新报告的结构、表格粒度、免责口径应与之对齐。

## 多币种处理要点

- 串行处理：A 币走完 1-4 步落盘 → B 币重复，**互不混写**。
- 时间戳逐个生成（同一秒可加序号避免重名），文件名前缀用各自 symbol。
- AHR999/彩虹图仅 BTC 有；其它币种宏观支柱改用"价格 vs EMA50/200 + 布林位置"近似估值，并在报告里注明该差异。
- 汇总回复：列出 N 份报告路径 + 各自信号/评分一行速览。
