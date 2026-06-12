"""v1.0.6 参数敏感性证伪实验（临时脚本）。

怀疑点：+204% 主要来自 trailingStopPct=0.0003（0.03% 追踪幅度）在
bar 内模拟的乐观成交假设。验证方法：同代码、同窗口、同费率，仅把
追踪幅度换成现实值（1%），看绩效变化幅度。
"""
from __future__ import annotations

import copy
import glob
import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.WARNING)

os.environ.setdefault("SECRET_KEY", "diag")
os.environ.setdefault("ADMIN_USER", "diag")
os.environ.setdefault("ADMIN_PASSWORD", "diag12345")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("SKIP_STARTUP_HOOKS", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.services.backtest import BacktestService  # noqa: E402

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "indicator_simulated_trading"
)

# 与截图回测面板一致：4H、2 年、3x、手续费 0.05%、滑点 0.05%
TIMEFRAME = "4H"
START = datetime(2024, 6, 12)
END = datetime(2026, 6, 10)
CAPITAL = 10000.0
LEVERAGE = 3
COMMISSION = 0.0005
SLIPPAGE = 0.0005

# 与 v1.0.6 头部 @strategy 一致的风控配置
BASE_CONFIG = {
    "execution": {"signalTiming": "next_bar_open"},
    "risk": {
        "stopLossPct": 0.063,
        "takeProfitPct": 0.0813,
        "trailing": {"enabled": True, "pct": 0.0003, "activationPct": 0.0049},
    },
    "position": {"entryPct": 0.122},
    "exitOwner": "engine",
}

KEYS = ("totalReturn", "maxDrawdown", "sharpeRatio", "winRate", "profitFactor",
        "totalTrades", "totalCommission")


def main() -> None:
    path = glob.glob(os.path.join(STRATEGY_DIR, "v1.0.6*.py"))[0]
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    # 实验组：仅改追踪幅度 / 激活阈值为现实量级，其余完全一致
    cfg_realistic = copy.deepcopy(BASE_CONFIG)
    cfg_realistic["risk"]["trailing"] = {"enabled": True, "pct": 0.01, "activationPct": 0.02}

    # 对照组 2：关闭追踪，只留固定止损/止盈，量化"利润有多少来自 trailing"
    cfg_no_trailing = copy.deepcopy(BASE_CONFIG)
    cfg_no_trailing["risk"]["trailing"] = {"enabled": False, "pct": 0.0, "activationPct": 0.0}

    runs = (
        ("原参数 trailing=0.03%/0.49%", BASE_CONFIG),
        ("现实参数 trailing=1%/2%", cfg_realistic),
        ("关闭 trailing（仅固定SL/TP）", cfg_no_trailing),
    )

    service = BacktestService()
    summary = []
    for label, cfg in runs:
        try:
            result = service.run(
                indicator_code=code,
                market="Crypto",
                symbol="ETH/USDT",
                timeframe=TIMEFRAME,
                start_date=START,
                end_date=END,
                initial_capital=CAPITAL,
                commission=COMMISSION,
                slippage=SLIPPAGE,
                leverage=LEVERAGE,
                trade_direction="both",
                strategy_config=cfg,
            )
            metrics = {k: result.get(k) for k in KEYS if k in result}
            # 统计出场类型分布，确认利润来源
            sides = {}
            for t in result.get("trades") or []:
                key = str(t.get("type") or "?")
                sides[key] = sides.get(key, 0) + 1
            metrics["tradeSides"] = sides
        except Exception as exc:
            metrics = {"error": str(exc)}
        summary.append((label, metrics))
        print(f"\n[{label}]")
        print(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
