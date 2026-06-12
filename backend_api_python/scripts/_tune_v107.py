"""v1.0.7 参数甄选实验（临时脚本）。

思路：
1. 基线 A = v1.0.6 调优参数 + 现实 trailing（已知 +42.7%，但信号模块被调死）；
2. B/C/D = 恢复 RSI/ATR/突破回看等模块的有效值，扫几组现实 trailing；
3. 入选组在 BTC/USDT 同窗口做外样本检验，看逻辑是否跨标的成立。
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

TIMEFRAME = "4H"
START = datetime(2024, 6, 12)
END = datetime(2026, 6, 10)
CAPITAL = 10000.0
LEVERAGE = 3
COMMISSION = 0.0005
SLIPPAGE = 0.0005

KEYS = ("totalReturn", "maxDrawdown", "sharpeRatio", "winRate", "profitFactor", "totalTrades")


def cfg(trail_pct: float, trail_act: float) -> dict:
    """生成风控配置：固定 SL/TP 沿用 v1.0.6，仅变化追踪参数。"""
    return {
        "execution": {"signalTiming": "next_bar_open"},
        "risk": {
            "stopLossPct": 0.063,
            "takeProfitPct": 0.0813,
            "trailing": {"enabled": True, "pct": trail_pct, "activationPct": trail_act},
        },
        "position": {"entryPct": 0.122},
        "exitOwner": "engine",
    }


# 恢复各信号模块有效性的参数组（结构周期沿用 v1.0.6 的 56/158/15）
RESTORED = {
    "fast_len": 56, "slow_len": 158, "rsi_len": 15,
    "rsi_floor": 52.0, "rsi_ceiling": 45.0,
    "rsi_long_exit": 44.0, "rsi_short_exit": 56.0,
    "atr_len": 14, "atr_filter_mult": 2.0,
    "breakout_len": 12, "pullback_buffer": 0.015,
}

RUNS = (
    ("A: v1.0.6调优参数+trailing 1%/2%", "ETH/USDT", None, cfg(0.01, 0.02)),
    ("B: 恢复模块+trailing 1%/2%", "ETH/USDT", RESTORED, cfg(0.01, 0.02)),
    ("C: 恢复模块+trailing 1.5%/2.5%", "ETH/USDT", RESTORED, cfg(0.015, 0.025)),
    ("D: 恢复模块+trailing 2%/3%", "ETH/USDT", RESTORED, cfg(0.02, 0.03)),
    ("外样本: B参数跑BTC", "BTC/USDT", RESTORED, cfg(0.01, 0.02)),
    ("外样本: A参数跑BTC", "BTC/USDT", None, cfg(0.01, 0.02)),
)


def main() -> None:
    path = glob.glob(os.path.join(STRATEGY_DIR, "v1.0.6*.py"))[0]
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    service = BacktestService()
    for label, symbol, ind_params, strategy_config in RUNS:
        try:
            result = service.run(
                indicator_code=code,
                market="Crypto",
                symbol=symbol,
                timeframe=TIMEFRAME,
                start_date=START,
                end_date=END,
                initial_capital=CAPITAL,
                commission=COMMISSION,
                slippage=SLIPPAGE,
                leverage=LEVERAGE,
                trade_direction="both",
                strategy_config=copy.deepcopy(strategy_config),
                indicator_params=ind_params,
            )
            metrics = {k: result.get(k) for k in KEYS if k in result}
        except Exception as exc:
            metrics = {"error": str(exc)}
        print(f"[{label}] {json.dumps(metrics, ensure_ascii=False, default=str)}")


if __name__ == "__main__":
    main()
