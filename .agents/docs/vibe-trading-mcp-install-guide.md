# Vibe-Trading MCP 安装与维护指南（新手向）

> 创建：2026-07-02（任务 202607021049）｜ 基于本机实际安装过程整理，含真实踩坑记录
> 适用：Windows + Claude Code；其它平台命令相同、路径自行替换
> 姊妹文档：[vibe-trading-mcp-test-plan.md](vibe-trading-mcp-test-plan.md)（装完照它验收）

## 这是什么

[HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) 是港大数据智能实验室的开源 AI 金融研究工作台。装好后 Claude Code 多出 54 个 MCP 工具：行情取数（加密/A股/美股/宏观）、回测、因子分析、期权定价、券商只读连接等。**定位是研究与模拟，不是自动交易。**

## 安装前检查（2 分钟）

### 1. Python ≥ 3.11

```powershell
python --version        # 需 ≥ 3.11
python -m pip --version # 注意看 pip 挂在哪个 Python 下！
```

> ⚠️ **坑 1（本机实测）**：`pip --version` 和 `python --version` 可能指向**不同的 Python**（本机 `python` 是 3.13，裸 `pip` 却挂在另一个 3.11 环境）。
> **规避**：全程用 `python -m pip ...`，别用裸 `pip`，保证装进 `python` 命令对应的那个环境。

### 2. 核验包的真伪（安全习惯，1 分钟）

装任何第三方交易类包之前，先确认不是钓鱼包：

- 打开 https://pypi.org/project/vibe-trading-ai/ ，确认发布者是 `HKUDS`、主页指向 `github.com/HKUDS/Vibe-Trading`；
- 打开仓库的 `pyproject.toml`，确认 `name = "vibe-trading-ai"`、入口点含 `vibe-trading-mcp`。
- 两边吻合才装。（2026-07-02 已核验通过：发布者 `HKUDS <hkuds@connect.hku.hk>`，双向吻合。）

## 安装（3 步）

### 第 1 步：安装 Python 包

```powershell
python -m pip install vibe-trading-ai
```

约 150 个依赖（langchain/fastapi/ccxt/akshare/yfinance 等），国内镜像下约 3–5 分钟。

### 第 2 步：验证命令可用

```powershell
vibe-trading-mcp --help
```

看到 `usage: vibe-trading-mcp [-h] [--transport {stdio,sse}] [--port PORT]` 即成功。

> ⚠️ **坑 2**：`vibe-trading --version` 显示的版本号可能比实际落后一个小版本（本机 0.1.10 显示 0.1.9），是上游版本串没同步的小 bug，**不影响使用**，以 `python -m pip show vibe-trading-ai` 为准。
>
> ⚠️ **坑 3**：若提示"不是内部或外部命令"，说明 Python 的 `Scripts` 目录不在 PATH。用 `where.exe vibe-trading-mcp` 查；anaconda 用户确认 `%USERPROFILE%\anaconda3\Scripts` 在 PATH 中，或直接用完整路径注册（见下一步）。

### 第 3 步：注册到 Claude Code

```powershell
claude mcp add --scope user vibe-trading -- vibe-trading-mcp
claude mcp list        # 应显示：vibe-trading: vibe-trading-mcp - √ Connected
```

- `--scope user` = 全局可用（写入 `~/.claude.json`）；只想在某个项目用就去掉该参数在项目目录里执行。
- 其它客户端：Claude Desktop 在 `claude_desktop_config.json` 加 `{"mcpServers": {"vibe-trading": {"command": "vibe-trading-mcp"}}}`；Cursor/Windsurf 同理指向该命令；Web 类客户端用 `vibe-trading-mcp --transport sse --port <端口>`。

> ⚠️ **坑 4（最容易忘）**：注册后**当前会话看不到新工具**，必须**新开一个 Claude Code 会话**，工具（`mcp__vibe-trading__*`）才会加载。

## 可选配置：LLM key（只有用 Swarm 多智能体时才需要）

数据/回测类工具走免费行情源（OKX/CCXT/yfinance/Eastmoney/FRED），**无需任何 key**。
只有 `run_swarm` 等 agent 功能需要 LLM key，在包的 `.env` 中配置：

```env
LANGCHAIN_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
LANGCHAIN_MODEL_NAME=deepseek-v4-pro
```

支持 OpenAI / DeepSeek / Gemini / Groq / Ollama（本地免 key）等。

> 🔒 **安全红线**：key 只写进本地 `.env`，**绝不在对话里粘贴**；`.env` 不进 git。trading_* 券商连接器默认未配置即不可用，配置也只走 paper/只读，本仓库红线见 `AGENTS.md`。

## 验收

装完跑姊妹文档 [vibe-trading-mcp-test-plan.md](vibe-trading-mcp-test-plan.md) 的 L1（工具发现）+ L2a（拉 BTC 行情）两条即可确认可用，全套验收 20–30 分钟。

## 日常维护

### 升级

```powershell
python -m pip install -U vibe-trading-ai
vibe-trading-mcp --help      # 升级后冒烟
claude mcp list              # 确认仍 Connected
```

项目在 Beta（0.1.x）快速迭代期，**升级前看一眼 [Releases](https://github.com/HKUDS/Vibe-Trading/releases)**，大版本升级后建议重跑测试方案 L1–L3。

### 健康检查（出问题先跑这三条）

```powershell
claude mcp list                              # √ Connected？
vibe-trading-mcp --help                      # 命令本身还在？
python -m pip show vibe-trading-ai          # 装在哪个环境、什么版本？
```

### 常见故障速查

| 症状 | 原因 | 处置 |
|------|------|------|
| `claude mcp list` 显示 ✗ Failed | 命令不在 PATH / 换了 Python 环境 | `where.exe vibe-trading-mcp` 找到全路径，`claude mcp remove vibe-trading` 后用全路径重新 add |
| Claude 会话里找不到工具 | 没开新会话（坑 4） | 新开会话 |
| 工具调用报数据源错误 | 免费源限流或网络 | 稍后重试；A 股源（Eastmoney）偶尔限流属正常 |
| pip 升级后命令消失 | 装进了另一个 Python | 回到坑 1，用 `python -m pip` 重装 |
| swarm 工具报 key 错误 | `.env` 未配 | 按上文可选配置节处理，或不用 swarm |

### 卸载

```powershell
claude mcp remove --scope user vibe-trading   # 先摘注册
python -m pip uninstall vibe-trading-ai       # 再卸包
```

## 本机安装档案（维护参考）

| 项 | 值 |
|-----|-----|
| 安装日期 | 2026-07-02 |
| 包版本 | vibe-trading-ai 0.1.10 |
| Python 环境 | anaconda3（Python 3.13.0），`python -m pip` 安装 |
| 注册方式 | `claude mcp add --scope user vibe-trading -- vibe-trading-mcp`（stdio） |
| 配置落点 | `C:\Users\JeffChiu\.claude.json` |
| LLM key | 未配置（L6 swarm 暂不启用） |
| 验收状态 | L0 ✅；L1+ 见测试方案结果记录表 |
