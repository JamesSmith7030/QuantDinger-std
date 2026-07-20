# crypto-analysis-report 使用文档（新人向）+ 维护管理指南

> 面向两类人：① 第一次用这个技能出报告的人；② 以后要改/维护这个技能的人。
> 技能主体见 [../SKILL.md](../SKILL.md)；加密评分真相源见
> [scoring-and-signals.md](scoring-and-signals.md)。旧报告只是历史快照，不是当前模板或阈值依据。

---

## 一、这个技能是干嘛的（30 秒看懂）

你说一句"分析 BTC"或"分析 TSLA 股票"，它就自动：**拉实时行情 → 算多周期技术指标 →
计算状态评分与方向共识 → 独立判定执行动作 → 生成中文 Markdown 报告**，存到 `analysis_reports/`。

- **加密分支**：走 OKX 公开行情，免费、免登录、国内直连（不用代理、不用 API Key）。
- **股票/股票代币分支**（TSLA/NVDA/AAPL/MSFT…，v1.2.0 起数据源唯一化）：**真股只走 Yahoo Finance 直连**（query1.finance.yahoo.com，不经 datahub），**股票代币只走 Bitget 现货**，二者禁止跨源替代；
  指标用 technical-analysis 引擎计算，三支柱换成「估值30%+量价40%+市场30%」。**不需要 datahub MCP**。
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
| 分析股票代币 | `分析 TSLAUSDT 股票代币，看溢价和技术面`（用 Bitget R 系 RTSLAUSDT） |
| 多股票 | `分析 TSLA、NVDA、AAPL 各出一份报告` |
| 加密+股票混合 | `分析 BTC 和 TSLA，各出一份` |

### 进阶
| 你想要的 | 这样说 |
|----------|--------|
| 出完报告要交易计划 | `分析 BTC 后，再用 position-sizer 给我入场/止损/张数` |
| 只要快速结论不要长报告 | `BTC 现在什么信号？一句话`（这会走 kline-indicator quick 模式，不落盘） |

> 触发后 agent 先用 `pull_okx_data.py` 拉取并校验，再用 `generate_crypto_reports.py` 统一解析、评分、渲染和自检；最后返回报告路径与总结表。

多标的 Chat 结果固定包含：总结表格、统一判读、数据说明。表格列为
`报告｜综合信号｜执行动作｜状态评分｜现价(24h)｜一句话`；Chat 不得脱离报告重新改分或改信号。

加密基础档标准命令：

```powershell
python .agents/skills/crypto-analysis-report/references/pull_okx_data.py `
  --symbols BTC,ETH,SOL,BNB,XRP --out-dir <快照目录>
python .agents/skills/crypto-analysis-report/references/generate_crypto_reports.py `
  --input-dir <快照目录> --out-dir analysis_reports --symbols BTC,ETH,SOL,BNB,XRP
```

> v1.3.0 的确定性运行时先覆盖加密基础档。股票/股票代币仍按 SKILL.md 的独立数据源流程执行，尚未宣称拥有同等级冻结夹具回放能力。

---

## 三、看懂报告（新人速读）

报告从上到下（综合结论 + 下一步 + 9 个编号板块）：

1. **综合结论**：综合信号、执行动作（LONG/SHORT/HOLD/REDUCE）、状态评分（0-100）、一致性等级和现价，外加**8项多周期客观共识**。操作先看“执行动作”，不要只看分数。
2. **下一步（行动清单）+ 📋开仓指南**：LONG/SHORT 才显示入场、止损、止盈和风险回报比；HOLD/REDUCE 只显示当前价与动作，避免伪精确参数。
3. **实时市场数据**：现价/24h/成交量/OI/资金费率。
4. **周期趋势预判**：24h / 3天 / 1周 / 1月 的方向预判。
5. **Crypto 交易大数据**：OI、资金费率、多空比、净流（净流类 OKX 无数据会标 `--`）。
6. **三支柱评分拆解**：为什么是这个状态分；状态分不直接决定交易动作。
   - 宏观周期(30%)：长线贵不贵（AHR999、彩虹图）。**分低=便宜=利多**；非 BTC 用均线近似。
   - 量价因子(40%)：多周期 RSI/MACD/均线/KDJ。
   - 衍生品(30%)：资金费率与多空比；OI 只有单点时只展示规模、不计方向分。
7. **技术指标 PRO**：RSI/MACD/均线趋势/ATR/带宽/区间位置/量比/支撑阻力/波动性。
8. **量化参数明细**：MACD 分量、MA5/10/20、布林三轨、经典枢轴 S1/R1/S2/R2、摆动高低、ATR、风险回报比。
9. **详细分析 / 核心理由与风险 / 操作倾向**：文字详述与分风格建议。

**新人最该记住四点**：
- 状态评分 40-60 是**中性区**，只表示综合状态较平衡，不等于方向共识；实际操作看执行动作。
- "宏观低估"是周期定位，**不等于马上涨**——便宜可以更便宜。
- `NEUTRAL 动能偏多/偏弱` 是观察描述，真正动作仍是 `HOLD`；`REDUCE` 只减多仓，不做空。
- 报告是**研究参考不是投资建议**，真金白银前自己再核一遍最新行情。

---

## 四、维护管理指南（给改技能的人）

### 4.1 技能文件结构
```
.agents/skills/crypto-analysis-report/
├── SKILL.md                          # 主体：工作流 + 评分口径 + 报告模板
└── references/
    ├── usage-and-maintenance.md      # 本文件：使用文档 + 维护指南
    ├── scoring-and-signals.md        # 加密评分、方向与动作的唯一规范
    ├── pull_okx_data.py              # 加密取数：重试 + 字段完整性校验
    ├── generate_crypto_reports.py    # 加密解析→评分→渲染→校验唯一实现
    └── test_generate_crypto_reports.py # 离线回归测试
```
落盘产物在仓库根 `analysis_reports/`（不在技能目录内）。

### 4.2 常见维护场景

| 要改什么 | 改哪里 |
|----------|--------|
| 报告板块增删/改版式 | SKILL.md「报告模板」节 + 同步更新本文「看懂报告」 |
| 调整加密评分或信号门控 | `scoring-and-signals.md` + `generate_crypto_reports.py` + 回归测试，三处必须同步 |
| 新增/替换技术指标 | SKILL.md「第 1A 步」（加密）/「第 1B 步」（股票）命令清单；加密分支同步改 `references/pull_okx_data.py` 里 `build_sections()` 的命令与校验正则 |
| okx 拉取偶发空输出/字段缺失（网络抖动） | 用 `references/pull_okx_data.py` 而非手写 bash：内置重试（默认 2 次、间隔 1-2s）+ 字段校验，仍失败会在 `<SYM>.txt` 写 `[FETCH_FAILED: 原因]` 并汇总报错退出，不会让下游 parse 静默拿到空值 |
| 换数据源（如加 Binance/Bybit） | 对应「第 1A/1B 步」命令；注意 Binance 主 API 国内需韩国节点+代理（见 `.agents/docs/交易所技能清单与测试提示词.md` §1.1），OKX 直连最省事 |
| 股票数据源/口径（唯一化 v1.2.0） | SKILL.md「股票/股票代币分析」节：**真股仅 Yahoo Finance 直连**（query1.finance.yahoo.com，含 P/E/52周/相关性，不经 datahub）、**代币仅 Bitget 现货**（价/K线/溢价）、指标 technical-analysis 引擎。**禁止** OKX 股票映射永续、Binance RWA、datahub、跨源冒充 |
| 调整股票三支柱 | SKILL.md「第 2B 步」表（估值/量价/市场，权重 30/40/30） |
| 改输出路径/命名 | SKILL.md「输出约定」；股票文件名 `<ticker>_report_<时间戳>.md` |

### 4.3 维护时必须守住的红线
1. **数据真实**：加密基础档来自 OKX；真股来自 Yahoo Finance；股票代币来自 Bitget。所有数值必须来自该分支规定的数据源，**禁止编造或照抄旧报告/样例的结论**。
2. **结论诚实**：状态评分不直接产生交易动作；动作必须经过方向、EMA50、衍生品和过热门控。多空交织给 NEUTRAL/HOLD。
3. **免责声明**：每份报告页眉页脚都必须保留"非投资建议"。
4. **多币种隔离**：N 个币 = N 份独立文件；加密基础档先完成全批解析/评分再统一落盘，任一输入失败时不得产出半套报告。
5. **指标周期坑**：指标日线用 `1Dutc`、K 线用 `1D`；RSI 值在 `^\s*14` 行；`ahr999`/`rainbow` 仅 BTC。

### 4.4 自测清单（改完技能后跑一遍）
- [ ] 离线回归：`python .agents/skills/crypto-analysis-report/references/test_generate_crypto_reports.py -v` 全绿。
- [ ] 语法检查：为 `PYTHONPYCACHEPREFIX` 指定仓库内临时目录后运行 `python -m py_compile`。
- [ ] 单币种：`分析 ETH` → 生成 `analysis_reports/eth_report_<时间戳>.md`，板块齐全含「下一步」。
- [ ] 多币种：`分析 BTC、SOL` → 生成 2 份独立文件，结论各异且与数据吻合。
- [ ] 非 BTC 币种：宏观支柱正确降级为均线/布林近似并注明（因无 AHR999）。
- [ ] **股票**：`分析 TSLA 股票` → 生成 `tsla_report_<时间戳>.md`，三支柱为「估值/量价/市场」，含溢价/52周/相关性，OI/资金费率标 N/A。
- [ ] **股票代币溢价**：报告中「溢价% = (代币价−真股价)/真股价」计算正确。
- [ ] 免责声明、时间戳、现价均正确填充（股票版含证券+代币溢价风险）。
- [ ] 抽查 1 个评分：手动按权重算一遍状态分，与报告完全一致；报告必须显示具体计算式。
- [ ] REDUCE 场景：报告明确“不做空”；HOLD 场景不显示伪精确止损止盈。
- [ ] 同一份冻结快照重复生成，状态分、信号、执行动作完全一致。

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
- **加密分支**：`okx` CLI（`npm install -g @okx_ai/okx-trade-cli`，行情免鉴权免代理）。标准路径固定为 `pull_okx_data.py` → `generate_crypto_reports.py`，两者均只用标准库；其它实验性生成脚本不是评分真相源。Windows 上 `okx` 是 npm 装的 `.cmd` 包装脚本，取数脚本已用 `shell=True` 兼容。加密增强档可选 datahub MCP——**仅补充宏观/情绪/新闻，不静默改变基础档评分**。
- **股票分支**（v1.2.0 数据源唯一化）：
  - **真股：Yahoo Finance 直连**（`https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>`），免凭证、不经 datahub。价/OHLCV/52周/相关性/基本面全部 Yahoo。
  - **股票代币：Bitget 现货直连**（`https://api.bitget.com/api/v2/spot/market/...`），免凭证。**首选 R 系 `RTSLAUSDT`/`RNVDAUSDT`**（流动性高，24h 量千万级）；ON 系 `TSLAONUSDT`/`NVDAONUSDT` 几乎无量、仅备用。裸 `TSLAUSDT`/`NVDAUSDT` 不存在。仅取价/24h量/K线，用于溢价与代币视角。
  - 指标：technical-analysis 技能（`~/.claude/skills/technical-analysis/src/kline_indicator_utils.py` 的 `IndicatorManager`）；需 `pip install pandas numpy`。
  - 备注：datahub `technical_analysis`/`global_assets` 等**不用于股票取数**（唯一源规定）；datahub `technical_analysis` 仅支持加密 `X/USDT`。
- 评分框架参考全局技能 `kline-indicator`（`~/.claude/skills/kline-indicator/references/three-pillars.md`）。
- 相关文档：[.agents/docs/交易所技能清单与测试提示词.md](../../../docs/交易所技能清单与测试提示词.md)（OKX/Binance/Bitget 技能、datahub MCP 与代理坑）。
- 已落盘股票范例：`analysis_reports/tsla_report_20260615115500.md`（TSLA，股票三支柱完整版）。
