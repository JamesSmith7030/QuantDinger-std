# crypto-analysis-report 使用文档（新人向）+ 维护管理指南

> 面向两类人：① 第一次用这个技能出报告的人；② 以后要改/维护这个技能的人。
> 技能主体见 [../SKILL.md](../SKILL.md)；标准范例见 `analysis_reports/btc_report_20260613174319.md`。

---

## 一、这个技能是干嘛的（30 秒看懂）

你说一句"分析 BTC"或"分析 TSLA 股票"，它就自动：**拉实时行情 → 算多周期技术指标 → 按三支柱打分 →
生成一份带结论、评分、关键价位、下一步行动的中文 Markdown 报告**，存到 `analysis_reports/`。

- **加密分支**：走 OKX 公开行情，免费、免登录、国内直连（不用代理、不用 API Key）。
- **股票/股票代币分支**（TSLA/NVDA/AAPL/MSFT…，v1.2.0 起数据源唯一化）：**真股只走 Yahoo Finance 直连**（query1.finance.yahoo.com，不经 datahub），**股票代币只走 Bitget 现货**，二者禁止跨源替代；
  指标用 technical-analysis 引擎计算，三支柱换成「估值30%+量价40%+市场30%」。**需先配 datahub MCP**（见 4.6）。
- 一次能分析一个标的，也能多个（每个各出一份报告，加密与股票可混合请求）。
- 报告只做客观分析，**永远带"非投资建议"免责声明**。

---

## 二、怎么用（提示词示例）

直接对 Claude 说下面任意一句即可触发：

### 单币种
| 你想要的 | 这样说 |
|----------|--------|
| 分析比特币 | `分析 BTC` ／ `帮我看看 BTC 现在怎么样，出份报告` |
| 分析以太坊 | `深度分析 ETH/USDT，生成专业报告` |
| 指定关注点 | `分析 SOL，重点看多周期 RSI 和资金费率` |

### 多币种（各自独立成报告）
| 你想要的 | 这样说 |
|----------|--------|
| 一次分析三个 | `同时分析 BTC、ETH、SOL，各出一份报告` |
| 主流币扫描 | `给 BTC ETH SOL BNB 各生成一份深度分析报告` |
| 自选清单 | `分析这几个币：DOGE、XRP、ADA` |

### 股票 / 股票代币（真股 Yahoo 直连 + 代币 Bitget，免 datahub）
| 你想要的 | 这样说 |
|----------|--------|
| 分析单只股票 | `分析 TSLA 股票，出份深度报告` ／ `分析特斯拉` |
| 分析股票代币 | `分析 TSLAON 股票代币，看溢价和技术面` |
| 多股票 | `分析 TSLA、NVDA、AAPL 各出一份报告` |
| 加密+股票混合 | `分析 BTC 和 TSLA，各出一份` |

### 进阶
| 你想要的 | 这样说 |
|----------|--------|
| 出完报告要交易计划 | `分析 BTC 后，再用 position-sizer 给我入场/止损/张数` |
| 只要快速结论不要长报告 | `BTC 现在什么信号？一句话`（这会走 kline-indicator quick 模式，不落盘） |

> 触发后 Claude 会自己跑 okx 命令、算分、写文件，最后回你：生成了哪几份报告（带路径）+ 每份一句话结论。

---

## 三、看懂报告（新人速读）

报告从上到下（9 大板块）：

1. **综合结论**：信号（🟢买入/🟡中性/🔴卖出）、评分（0-100）、置信度、现价，外加**多周期客观共识**（共识方向/一致度）。**只看这一块就够做大致判断。**
2. **下一步（行动清单）+ 📋开仓指南**：具体动作 + **当前价格 / 建议入场 / 止损价 / 止盈目标 / 风险回报比**（止损止盈基于 ATR 波动率算）。**想直接知道在哪买、在哪止损止盈，看这块。**
3. **实时市场数据**：现价/24h/成交量/OI/资金费率。
4. **周期趋势预判**：24h / 3天 / 1周 / 1月 的方向预判。
5. **Crypto 交易大数据**：OI、资金费率、多空比、净流（净流类 OKX 无数据会标 `--`）。
6. **三支柱评分拆解**：为什么是这个分。
   - 宏观周期(30%)：长线贵不贵（AHR999、彩虹图）。**分低=便宜=利多**；非 BTC 用均线近似。
   - 量价因子(40%)：多周期 RSI/MACD/均线/KDJ。
   - 衍生品(30%)：资金费率（负=空头多=偏多）、持仓量、多空比。
7. **技术指标 PRO**：RSI/MACD/均线趋势/ATR/带宽/区间位置/量比/支撑阻力/波动性。
8. **量化参数明细**：MACD 分量、MA5/10/20、布林三轨、经典枢轴 S1/R1/S2/R2、摆动高低、ATR、风险回报比。
9. **详细分析 / 核心理由与风险 / 操作倾向**：文字详述与分风格建议。

**新人最该记住三点**：
- 评分 40-60 是**中性区**，意味着多空不明朗，别重仓赌方向。
- "宏观低估"是周期定位，**不等于马上涨**——便宜可以更便宜。
- 报告是**研究参考不是投资建议**，真金白银前自己再核一遍最新行情。

---

## 四、维护管理指南（给改技能的人）

### 4.1 技能文件结构
```
.agents/skills/crypto-analysis-report/
├── SKILL.md                          # 主体：工作流 + 评分口径 + 报告模板
└── references/
    └── usage-and-maintenance.md      # 本文件：使用文档 + 维护指南
```
落盘产物在仓库根 `analysis_reports/`（不在技能目录内）。

### 4.2 常见维护场景

| 要改什么 | 改哪里 |
|----------|--------|
| 报告板块增删/改版式 | SKILL.md「报告模板」节 + 同步更新本文「看懂报告」 |
| 调整三支柱权重或评分口径 | SKILL.md「三支柱评分」表（注意与全局 kline-indicator 的 three-pillars.md 保持一致） |
| 新增/替换技术指标 | SKILL.md「第 1A 步」（加密）/「第 1B 步」（股票）命令清单 |
| 换数据源（如加 Binance/Bybit） | 对应「第 1A/1B 步」命令；注意 Binance 主 API 国内需韩国节点+代理（见 `.agents/docs/交易所技能清单与测试提示词.md` §1.1），OKX 直连最省事 |
| 股票数据源/口径（唯一化 v1.2.0） | SKILL.md「股票/股票代币分析」节：**真股仅 Yahoo Finance 直连**（query1.finance.yahoo.com，含 P/E/52周/相关性，不经 datahub）、**代币仅 Bitget 现货**（价/K线/溢价）、指标 technical-analysis 引擎。**禁止** OKX 股票映射永续、Binance RWA、datahub、跨源冒充 |
| 调整股票三支柱 | SKILL.md「第 2B 步」表（估值/量价/市场，权重 30/40/30） |
| 改输出路径/命名 | SKILL.md「输出约定」；股票文件名 `<ticker>_report_<时间戳>.md` |

### 4.3 维护时必须守住的红线
1. **数据真实**：所有数值来自实时 okx 命令，**禁止编造或照抄旧报告/样例的结论**。
2. **结论诚实**：信号由评分算出；多空交织如实给 NEUTRAL，不为好看凑方向。
3. **免责声明**：每份报告页眉页脚都必须保留"非投资建议"。
4. **多币种隔离**：N 个币 = N 份独立文件，串行处理不混写。
5. **指标周期坑**：指标日线用 `1Dutc`、K 线用 `1D`；RSI 值在 `^\s*14` 行；`ahr999`/`rainbow` 仅 BTC。

### 4.4 自测清单（改完技能后跑一遍）
- [ ] 单币种：`分析 ETH` → 生成 `analysis_reports/eth_report_<时间戳>.md`，板块齐全含「下一步」。
- [ ] 多币种：`分析 BTC、SOL` → 生成 2 份独立文件，结论各异且与数据吻合。
- [ ] 非 BTC 币种：宏观支柱正确降级为均线/布林近似并注明（因无 AHR999）。
- [ ] **股票**：`分析 TSLA 股票` → 生成 `tsla_report_<时间戳>.md`，三支柱为「估值/量价/市场」，含溢价/52周/相关性，OI/资金费率标 N/A。
- [ ] **股票代币溢价**：报告中「溢价% = (代币价−真股价)/真股价」计算正确。
- [ ] 免责声明、时间戳、现价均正确填充（股票版含证券+代币溢价风险）。
- [ ] 抽查 1 个评分：手动按权重算一遍综合分，与报告一致。

### 4.5 算法来源（对齐后端引擎，便于维护时同步）
报告的「开仓指南/支撑阻力/波动性」口径**对齐 QuantDinger 后端**
`backend_api_python/app/services/market_data_collector.py::MarketDataCollector._calculate_indicators`
（专业报告 `/api/fast-analysis/analyze` 同款）：
- **支撑/阻力 = 三方法平均**：`(枢轴S1/R1 + 20日摆动高低 + 布林轨)/3`（method=`pivot_swing_bb_avg`）。
- **止损/止盈 = ATR×结构融合**（method=`atr_support_resistance`）：
  止损=`max(现价−2×ATR, 支撑×0.99)`；止盈=`min(现价+3×ATR, 阻力×1.01)`；RR 以现价为基准。
- **波动性阈值**：≤2% 低 / 2–5% 中 / >5% 高。
> ⚠️ 取其精华去其糟粕：后端的基本面/情绪面/地缘评分依赖 GPT-5.5 + 新闻源 + 积分系统，本技能
> 不复制（无数据源会编造），相关维度一律如实标注「数据缺失」。后端若改算法，按此处同步更新本技能。

### 4.6 依赖与环境
- **加密分支**：`okx` CLI（`npm install -g @okx_ai/okx-trade-cli`，行情免鉴权免代理）。加密增强档（宏观/情绪/新闻）可选 datahub MCP（`claude mcp add --scope user --transport http datahub https://datahub.noxiaohao.com/mcp`）——**仅加密用，股票不用**。
- **股票分支**（v1.2.0 数据源唯一化）：
  - **真股：Yahoo Finance 直连**（`https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>`），免凭证、不经 datahub。价/OHLCV/52周/相关性/基本面全部 Yahoo。
  - **股票代币：Bitget 现货直连**（`https://api.bitget.com/api/v2/spot/market/...`，符号如 `TSLAONUSDT`），免凭证。仅取价/24h量/K线，用于溢价与代币视角。
  - 指标：technical-analysis 技能（`~/.claude/skills/technical-analysis/src/kline_indicator_utils.py` 的 `IndicatorManager`）；需 `pip install pandas numpy`。
  - 备注：datahub `technical_analysis`/`global_assets` 等**不用于股票取数**（唯一源规定）；datahub `technical_analysis` 仅支持加密 `X/USDT`。
- 评分框架参考全局技能 `kline-indicator`（`~/.claude/skills/kline-indicator/references/three-pillars.md`）。
- 相关文档：[.agents/docs/交易所技能清单与测试提示词.md](../../../docs/交易所技能清单与测试提示词.md)（OKX/Binance/Bitget 技能、datahub MCP 与代理坑）。
- 已落盘股票范例：`analysis_reports/tsla_report_20260615115500.md`（TSLA，股票三支柱完整版）。
