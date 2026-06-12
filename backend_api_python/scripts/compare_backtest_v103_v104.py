"""Offline backtest comparison: v1.0.3 (two-way) vs v1.0.4 (four-way rewrite).

Runs three configurations on the same symbol/window through BacktestService:
  1. v1.0.3 + trade_direction=long  (the direction declared in the code)
  2. v1.0.3 + trade_direction=both  (the misconfigured live deployment)
  3. v1.0.4 + trade_direction=long  (four-way rewrite; shorts hard-disabled)

Usage (inside the backend Docker image, repo mounted at /repo):
  python scripts/compare_backtest_v103_v104.py
"""
from __future__ import annotations

import glob
import json
import logging
import os
import sys
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

os.environ.setdefault("SECRET_KEY", "compare-backtest-secret")
os.environ.setdefault("ADMIN_USER", "compare")
os.environ.setdefault("ADMIN_PASSWORD", "compare123")
os.environ.setdefault("CACHE_ENABLED", "false")
os.environ.setdefault("SKIP_STARTUP_HOOKS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.services.backtest import BacktestService  # noqa: E402

STRATEGY_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "indicator_simulated_trading"
)

MARKET = "Crypto"
SYMBOL = "ETH/USDT"
TIMEFRAME = "30m"
# Gate public API only serves the most recent ~10000 candles per timeframe,
# so keep the window comfortably inside that budget (30m x ~6300 bars).
START = datetime(2026, 2, 1)
END = datetime(2026, 6, 10)
CAPITAL = 10000.0
LEVERAGE = 3
COMMISSION = 0.001

# Mirrors the # @strategy block shared by both versions.
STRATEGY_CONFIG = {
    "execution": {"signalTiming": "next_bar_open"},
    "risk": {
        "stopLossPct": 0.028,
        "takeProfitPct": 0.065,
        "trailing": {"enabled": True, "pct": 0.005, "activationPct": 0.009},
    },
    "position": {"entryPct": 0.1},
    "exitOwner": "engine",
}

METRIC_KEYS = (
    "totalReturn", "totalReturnPct", "annualizedReturn", "maxDrawdown",
    "maxDrawdownPct", "sharpeRatio", "winRate", "profitFactor",
    "totalTrades", "winningTrades", "losingTrades", "totalCommission",
    "finalEquity", "netProfit",
)


def find_one(pattern: str) -> str:
    matches = glob.glob(os.path.join(STRATEGY_DIR, pattern))
    if not matches:
        raise SystemExit(f"strategy file not found: {pattern}")
    return matches[0]


def load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def pick_metrics(result: dict) -> dict:
    out = {}
    for key in METRIC_KEYS:
        if key in result:
            out[key] = result[key]
    # Fall back: surface any scalar metric we did not anticipate.
    if not out:
        for key, value in result.items():
            if isinstance(value, (int, float, str)) and not str(key).startswith("_"):
                out[key] = value
    return out


def main() -> None:
    code_103 = load(find_one("v1.0.3*.py"))
    code_104 = load(find_one("v1.0.4*.py"))

    # Simulate the live snapshot whose trading_config carried 'both': flip the
    # code-declared direction too, in case the engine reads it from @strategy.
    code_103_both = code_103.replace(
        "# @strategy tradeDirection long", "# @strategy tradeDirection both"
    )

    runs = (
        ("v1.0.3 / long (代码声明方向)", code_103, "long"),
        ("v1.0.3 / both (线上误配方向)", code_103_both, "both"),
        ("v1.0.4 / long (四路修复版)", code_104, "long"),
    )

    service = BacktestService()
    summary = []
    for label, code, direction in runs:
        print(f"\n=== {label} ===", flush=True)
        try:
            result = service.run(
                indicator_code=code,
                market=MARKET,
                symbol=SYMBOL,
                timeframe=TIMEFRAME,
                start_date=START,
                end_date=END,
                initial_capital=CAPITAL,
                commission=COMMISSION,
                slippage=0.0,
                leverage=LEVERAGE,
                trade_direction=direction,
                strategy_config=STRATEGY_CONFIG,
            )
        except Exception as exc:  # surface, keep comparing the rest
            print(f"FAILED: {exc}")
            summary.append((label, {"error": str(exc)}))
            continue
        metrics = pick_metrics(result)
        trades = result.get("trades") or []
        sides = {}
        for t in trades:
            key = str(t.get("type") or t.get("side") or "?")
            sides[key] = sides.get(key, 0) + 1
        metrics["tradeSides"] = sides
        print(json.dumps(metrics, ensure_ascii=False, indent=2, default=str))
        summary.append((label, metrics))

    print("\n\n================ SUMMARY ================")
    for label, metrics in summary:
        print(f"\n[{label}]")
        for key, value in metrics.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
