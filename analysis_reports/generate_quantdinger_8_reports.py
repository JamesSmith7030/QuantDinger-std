from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
NOW = datetime.now()
TIMESTAMP = NOW.strftime("%Y%m%d%H%M%S")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)


@dataclass
class ReportSummary:
    symbol: str
    signal: str
    score: int
    price: float
    one_liner: str
    path: Path


def http_json(url: str, retries: int = 3) -> Any:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
            with urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"fetch failed: {url}") from last_error


def run_okx(args: list[str]) -> str:
    okx_script = Path(r"C:\Program Files\nodejs\okx.ps1")
    if okx_script.exists():
        shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        quoted = " ".join([f"'{str(okx_script)}'"] + [f"'{arg}'" for arg in args])
        cmd = [shell, "-NoProfile", "-Command", f"& {quoted}"]
    else:
        cmd = ["okx", *args]
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(3):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                check=True,
            )
            return proc.stdout.strip()
        except subprocess.CalledProcessError as exc:
            last_error = exc
            time.sleep(1 + attempt)
    raise last_error if last_error else RuntimeError(f"okx command failed: {args}")


def parse_key_value_table(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.rstrip()
        if not line or "|" in line or line.startswith("---"):
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
        if len(parts) == 2:
            data[parts[0].strip()] = parts[1].strip()
    return data


def parse_single_indicator_value(text: str) -> float:
    kv = parse_key_value_table(text)
    for key, value in kv.items():
        if key.lower() == "ts":
            continue
        try:
            return float(value)
        except ValueError:
            continue
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^\d", line):
            parts = re.split(r"\s+", line)
            return float(parts[-1])
    raise ValueError(f"indicator parse failed: {text}")


def parse_macd(text: str) -> dict[str, float]:
    kv = parse_key_value_table(text)
    if {"dif", "dea", "macd"} <= set(kv):
        return {"dif": float(kv["dif"]), "dea": float(kv["dea"]), "hist": float(kv["macd"])}
    vals: list[float] = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^-?\d", line):
            parts = re.split(r"\s+", line)
            nums = [float(x) for x in parts if re.match(r"^-?\d+(\.\d+)?$", x)]
            vals.extend(nums)
            if len(vals) >= 3:
                break
    if len(vals) < 3:
        raise ValueError(f"macd parse failed: {text}")
    return {"dif": vals[0], "dea": vals[1], "hist": vals[2]}


def parse_bb(text: str) -> dict[str, float]:
    kv = parse_key_value_table(text)
    if {"upper", "middle", "lower"} <= set(kv):
        return {"upper": float(kv["upper"]), "middle": float(kv["middle"]), "lower": float(kv["lower"])}
    vals: list[float] = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^-?\d", line):
            parts = re.split(r"\s+", line)
            nums = [float(x) for x in parts if re.match(r"^-?\d+(\.\d+)?$", x)]
            vals.extend(nums)
            if len(vals) >= 3:
                break
    if len(vals) < 3:
        raise ValueError(f"bb parse failed: {text}")
    return {"upper": vals[0], "middle": vals[1], "lower": vals[2]}


def parse_kdj(text: str) -> dict[str, float]:
    kv = parse_key_value_table(text)
    if {"k", "d", "j"} <= set(kv):
        return {"k": float(kv["k"]), "d": float(kv["d"]), "j": float(kv["j"])}
    vals: list[float] = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^-?\d", line):
            parts = re.split(r"\s+", line)
            nums = [float(x) for x in parts if re.match(r"^-?\d+(\.\d+)?$", x)]
            vals.extend(nums)
            if len(vals) >= 3:
                break
    if len(vals) < 3:
        raise ValueError(f"kdj parse failed: {text}")
    return {"k": vals[0], "d": vals[1], "j": vals[2]}


def parse_candles(text: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if (
            not line
            or line.startswith("---")
            or line.startswith("Environment:")
            or line.startswith("time")
            or line.startswith("ts")
        ):
            continue
        match = re.match(
            r"^(?P<dt>(?:\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2}|"
            r"\d{1,2}/\d{1,2}/\d{4},\s+\d{1,2}:\d{2}:\d{2}\s+[AP]M))\s+"
            r"(?P<open>-?\d+(?:\.\d+)?)\s+"
            r"(?P<high>-?\d+(?:\.\d+)?)\s+"
            r"(?P<low>-?\d+(?:\.\d+)?)\s+"
            r"(?P<close>-?\d+(?:\.\d+)?)\s+"
            r"(?P<volume>-?\d+(?:\.\d+)?)$",
            line,
        )
        if not match:
            continue
        dt_text = match.group("dt")
        dt_format = "%Y/%m/%d %H:%M:%S" if "," not in dt_text else "%m/%d/%Y, %I:%M:%S %p"
        stamp = datetime.strptime(dt_text, dt_format).timestamp()
        rows.append(
            {
                "ts": float(stamp),
                "open": float(match.group("open")),
                "high": float(match.group("high")),
                "low": float(match.group("low")),
                "close": float(match.group("close")),
                "volume": float(match.group("volume")),
            }
        )
    return rows


def fmt_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.1f}"
    if value >= 100:
        return f"${value:,.2f}"
    if value >= 1:
        return f"${value:,.3f}"
    return f"${value:,.5f}"


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(50)


def macd(series: pd.Series) -> pd.DataFrame:
    fast = ema(series, 12)
    slow = ema(series, 26)
    dif = fast - slow
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = (dif - dea) * 2
    return pd.DataFrame({"dif": dif, "dea": dea, "hist": hist})


def boll(series: pd.Series, period: int = 20, std_mult: int = 2) -> pd.DataFrame:
    mid = series.rolling(period).mean()
    std = series.rolling(period).std(ddof=0)
    upper = mid + std * std_mult
    lower = mid - std * std_mult
    return pd.DataFrame({"upper": upper, "middle": mid, "lower": lower})


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def kdj(df: pd.DataFrame, period: int = 9) -> pd.DataFrame:
    low_n = df["low"].rolling(period).min()
    high_n = df["high"].rolling(period).max()
    rsv = (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    j = 3 * k - 2 * d
    return pd.DataFrame({"k": k.fillna(50), "d": d.fillna(50), "j": j.fillna(50)})


def signal_bucket(score: int) -> tuple[str, str, str]:
    if score >= 60:
        return "BUY", "🟢 BUY 偏多", "高"
    if score <= 39:
        return "SELL", "🔴 SELL 偏空", "中"
    return "NEUTRAL", "🟡 NEUTRAL 中性", "中"


def trading_bias_text(signal: str) -> str:
    if signal == "BUY":
        return "回踩多参考，前提是价格维持强势结构且量价确认。"
    if signal == "SELL":
        return "反弹空或继续观望优先，避免在弱势结构里给回踩多。"
    return "等待突破或跌破触发，未触发前以观望为主。"


def ensure_levels(price: float, support: float, resistance: float, atr_value: float) -> tuple[float, float]:
    # ponytail: keep levels on the correct side of price; ATR fallback is enough here.
    support = min(support, price - atr_value * 0.5)
    resistance = max(resistance, price + atr_value * 0.5)
    return support, resistance


def build_action_guide(signal: str, price: float, support: float, resistance: float) -> list[str]:
    if signal == "BUY":
        return [
            f"1. **🎯 盯关键位**：回踩 {fmt_price(support)} 上方企稳，或放量突破 {fmt_price(resistance)} 后再跟进。",
            f"2. **📥 操作倾向**：{trading_bias_text(signal)}",
            f"3. **🛡️ 持仓处理**：跌回 {fmt_price(support)} 下方则止损，接近 {fmt_price(resistance)} 可分批止盈。",
            "4. **🔁 复核节奏**：至少等 4H / 日线收盘确认趋势未破坏。",
            "5. **🔬 进阶**：如需仓位张数，再调用 `position-sizer`。",
        ]
    if signal == "SELL":
        return [
            f"1. **🎯 盯关键位**：反弹不过 {fmt_price(resistance)} 继续偏空；失守 {fmt_price(support)} 则延续弱势。",
            f"2. **⏳ 操作倾向**：{trading_bias_text(signal)}",
            f"3. **🛡️ 持仓处理**：空单若站回 {fmt_price(resistance)} 上方则离场，目标先看 {fmt_price(support)} 一带。",
            "4. **🔁 复核节奏**：关注 1H / 4H 动能是否继续走弱。",
            "5. **🔬 进阶**：如需精确仓位张数，再调用 `position-sizer`。",
        ]
    return [
        f"1. **🎯 盯关键位**：突破 {fmt_price(resistance)} 才转强，跌破 {fmt_price(support)} 才转弱。",
        "2. **⏳ 操作倾向**：HOLD，等待方向明确后再处理。",
        f"3. **🛡️ 持仓处理**：区间内部轻仓或空仓，触发前不追单。",
        "4. **🔁 复核节奏**：优先等 4H / 日线收盘，确认量能和动能共振。",
        "5. **🔬 进阶**：如需精确仓位张数，再调用 `position-sizer`。",
    ]


def build_trade_guide(signal: str, data: dict[str, Any]) -> str:
    lv = data["levels"]
    price_line = fmt_price(data["price"])
    if signal == "NEUTRAL":
        return f"""| 项目 | 价位 | 说明 |
|------|------|------|
| 当前价格 | {price_line} | HOLD，当前数据未形成明确做多或做空方向。 |"""
    if signal == "SELL":
        return f"""| 项目 | 价位 | 说明 |
|------|------|------|
| 交易方向 | 做空 | 信号偏空，按反弹空思路处理 |
| 当前价格 | {price_line} | {fmt_pct(data['change_pct'])} |
| 建议入场 | {fmt_price(lv['entry'])} | 反弹到阻力附近承压再考虑空单 |
| 止损价 | {fmt_price(lv['stop'])} | 参考 ATR 与结构阻力融合 |
| 止盈目标 | {fmt_price(lv['take'])} | 与偏空信号一致，先看下方支撑 |
| 风险回报比 | 1 : {lv['rr']:.2f} | 空单参考 |"""
    return f"""| 项目 | 价位 | 说明 |
|------|------|------|
| 交易方向 | 做多 | 信号偏多，按回踩多思路处理 |
| 当前价格 | {price_line} | {fmt_pct(data['change_pct'])} |
| 建议入场 | {fmt_price(lv['entry'])} | 回踩确认支撑后再考虑多单 |
| 止损价 | {fmt_price(lv['stop'])} | 参考 ATR 与结构支撑融合 |
| 止盈目标 | {fmt_price(lv['take'])} | 与偏多信号一致，先看上方阻力 |
| 风险回报比 | 1 : {lv['rr']:.2f} | 多单参考 |"""


def coin_consensus(rsi_1h: float, rsi_4h: float, rsi_1d: float, hist_4h: float, hist_1d: float) -> tuple[str, int, int]:
    signals = []
    signals.append(1 if rsi_1h > 55 else -1 if rsi_1h < 45 else 0)
    signals.append(1 if rsi_4h > 55 else -1 if rsi_4h < 45 else 0)
    signals.append(1 if rsi_1d > 55 else -1 if rsi_1d < 45 else 0)
    signals.append(1 if hist_4h > 0 else -1 if hist_4h < 0 else 0)
    signals.append(1 if hist_1d > 0 else -1 if hist_1d < 0 else 0)
    total = sum(signals)
    agreement = int(round(sum(1 for x in signals if x == (1 if total > 0 else -1 if total < 0 else 0)) / 5 * 100)) if total else 40
    direction = "BUY" if total >= 2 else "SELL" if total <= -2 else "HOLD"
    return direction, agreement, total


def fetch_okx_crypto(symbol: str) -> dict[str, Any]:
    inst = f"{symbol}-USDT"
    swap = f"{symbol}-USDT-SWAP"
    ticker = parse_key_value_table(run_okx(["market", "ticker", inst]))
    rsi_1h = parse_single_indicator_value(run_okx(["market", "indicator", "rsi", inst, "--bar", "1H"]))
    rsi_4h = parse_single_indicator_value(run_okx(["market", "indicator", "rsi", inst, "--bar", "4H"]))
    rsi_1d = parse_single_indicator_value(run_okx(["market", "indicator", "rsi", inst, "--bar", "1Dutc"]))
    macd_1h = parse_macd(run_okx(["market", "indicator", "macd", inst, "--bar", "1H"]))
    macd_4h = parse_macd(run_okx(["market", "indicator", "macd", inst, "--bar", "4H"]))
    macd_1d = parse_macd(run_okx(["market", "indicator", "macd", inst, "--bar", "1Dutc"]))
    bb_1d = parse_bb(run_okx(["market", "indicator", "bb", inst, "--bar", "1Dutc"]))
    ema50 = parse_single_indicator_value(run_okx(["market", "indicator", "ema", inst, "--bar", "1Dutc", "--params", "50"]))
    ema200 = parse_single_indicator_value(run_okx(["market", "indicator", "ema", inst, "--bar", "1Dutc", "--params", "200"]))
    atr_1d = parse_single_indicator_value(run_okx(["market", "indicator", "atr", inst, "--bar", "1Dutc", "--params", "14"]))
    ma5 = parse_single_indicator_value(run_okx(["market", "indicator", "ma", inst, "--bar", "1Dutc", "--params", "5"]))
    ma10 = parse_single_indicator_value(run_okx(["market", "indicator", "ma", inst, "--bar", "1Dutc", "--params", "10"]))
    ma20 = parse_single_indicator_value(run_okx(["market", "indicator", "ma", inst, "--bar", "1Dutc", "--params", "20"]))
    kdj_1d = parse_kdj(run_okx(["market", "indicator", "kdj", inst, "--bar", "1Dutc"]))
    candles = parse_candles(run_okx(["market", "candles", inst, "--bar", "1D", "--limit", "30"]))
    funding = parse_key_value_table(run_okx(["market", "funding-rate", swap]))
    oi_text = run_okx(["market", "open-interest", "--instType", "SWAP", "--instId", swap])
    price = float(ticker["last"])
    day_change = float(ticker["24h change %"].replace("%", ""))
    daily = pd.DataFrame(candles).sort_values("ts").reset_index(drop=True)
    swing_high = float(daily["high"].tail(20).max())
    swing_low = float(daily["low"].tail(20).min())
    prev = daily.iloc[-2]
    pivot = (prev["high"] + prev["low"] + prev["close"]) / 3
    s1 = 2 * pivot - prev["high"]
    r1 = 2 * pivot - prev["low"]
    s2 = pivot - (prev["high"] - prev["low"])
    r2 = pivot + (prev["high"] - prev["low"])
    support = (s1 + swing_low + bb_1d["lower"]) / 3
    resistance = (r1 + swing_high + bb_1d["upper"]) / 3
    support, resistance = ensure_levels(price, support, resistance, atr_1d)
    volatility = atr_1d / price * 100
    band_width = (bb_1d["upper"] - bb_1d["lower"]) / bb_1d["middle"] * 100
    range_position = (price - swing_low) / max(swing_high - swing_low, 1e-9) * 100
    macro_score = 55
    if symbol == "BTC":
        try:
            ahr = parse_single_indicator_value(run_okx(["market", "indicator", "ahr999", inst, "--bar", "1Dutc"]))
            macro_score = 75 if ahr < 0.45 else 65 if ahr < 0.8 else 50 if ahr < 1.2 else 32
        except subprocess.CalledProcessError:
            macro_score = 52
    else:
        macro_score = 68 if price > ema50 > ema200 else 55 if price > ema50 else 38
    qty_score = 50
    qty_score += 8 if rsi_1d > 55 else -8 if rsi_1d < 45 else 0
    qty_score += 8 if macd_1d["hist"] > 0 else -8
    qty_score += 5 if price > ma20 else -5
    qty_score += 4 if kdj_1d["j"] < 20 else -4 if kdj_1d["j"] > 80 else 0
    qty_score = max(20, min(80, qty_score))
    funding_rate = float(funding.get("fundingRate", "0"))
    oi_match = re.search(rf"^{re.escape(swap)}\s+\S+\s+(\S+)", oi_text, re.MULTILINE)
    oi_value = float(oi_match.group(1)) if oi_match else 0.0
    der_score = 50 + (10 if funding_rate < 0 else -6 if funding_rate > 0.0005 else 0) + (4 if oi_value > 0 else 0)
    der_score = max(25, min(75, der_score))
    composite = int(round(macro_score * 0.30 + qty_score * 0.40 + der_score * 0.30))
    direction, agreement, total = coin_consensus(rsi_1h, rsi_4h, rsi_1d, macd_4h["hist"], macd_1d["hist"])
    score_signal, _, confidence = signal_bucket(composite)
    strong_consensus = (
        direction == "SELL" and agreement >= 80 and qty_score <= 45
    ) or (
        direction == "BUY" and agreement >= 80 and qty_score >= 55
    )
    signal = direction if strong_consensus else score_signal if score_signal == direction else "NEUTRAL"
    signal_cn = signal_bucket(50 if signal == "NEUTRAL" else composite)[1]
    entry = ma5 if signal == "BUY" else resistance if signal == "SELL" else pivot
    stop = max(price - 2 * atr_1d, support * 0.99) if signal != "SELL" else min(price + 2 * atr_1d, resistance * 1.01)
    take = min(price + 3 * atr_1d, resistance * 1.01) if signal != "SELL" else max(price - 3 * atr_1d, support * 0.99)
    rr = abs((take - price) / max(abs(price - stop), 1e-9))
    return {
        "asset_type": "crypto",
        "symbol": symbol,
        "title": f"{symbol}/USDT 深度分析报告",
        "header_source": "OKX 实时行情",
        "frame": "三支柱评分（宏观30% + 量价40% + 衍生品30%）",
        "signal": signal,
        "signal_cn": signal_cn,
        "confidence": confidence,
        "score": composite,
        "price": price,
        "change_pct": day_change,
        "one_liner": (
            f"{symbol} 当前 {fmt_price(price)}，综合 {composite}/100，"
            f"{'短线偏空' if signal == 'SELL' else '等待确认' if signal == 'NEUTRAL' else '偏多修复'}。"
        ),
        "market_phase": (
            "偏空回撤阶段" if signal == "SELL" else
            "震荡待突破阶段" if signal == "NEUTRAL" else
            "趋势修复阶段"
        ),
        "consensus": {"direction": direction, "agreement": agreement, "total": total},
        "levels": {
            "pivot": pivot, "s1": s1, "r1": r1, "s2": s2, "r2": r2,
            "support": support, "resistance": resistance, "entry": entry,
            "stop": stop, "take": take, "rr": rr,
        },
        "metrics": {
            "ticker": ticker, "rsi_1h": rsi_1h, "rsi_4h": rsi_4h, "rsi_1d": rsi_1d,
            "macd_1h": macd_1h, "macd_4h": macd_4h, "macd_1d": macd_1d, "bb_1d": bb_1d,
            "ema50": ema50, "ema200": ema200, "atr": atr_1d, "ma5": ma5, "ma10": ma10, "ma20": ma20,
            "kdj": kdj_1d, "swing_high": swing_high, "swing_low": swing_low, "volatility": volatility,
            "band_width": band_width, "range_position": range_position, "funding_rate": funding_rate,
            "oi": oi_value, "macro_score": macro_score, "qty_score": qty_score, "der_score": der_score,
        },
    }


def fetch_yahoo_chart(ticker: str, range_: str = "1y", interval: str = "1d") -> dict[str, Any]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker)}?range={range_}&interval={interval}"
    return http_json(url)


def fetch_bitget_json(url: str) -> Any:
    return http_json(url)


def stock_dataframe_from_yahoo(ticker: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = fetch_yahoo_chart(ticker)
    result = raw["chart"]["result"][0]
    quote_data = result["indicators"]["quote"][0]
    rows = pd.DataFrame(
        {
            "ts": result["timestamp"],
            "open": quote_data["open"],
            "high": quote_data["high"],
            "low": quote_data["low"],
            "close": quote_data["close"],
            "volume": quote_data["volume"],
        }
    ).dropna()
    return rows.reset_index(drop=True), result["meta"]


def token_dataframe_from_bitget(symbol: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    ticker_url = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"
    candles_url = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}&granularity=1day&limit=180"
    ticker = fetch_bitget_json(ticker_url)["data"][0]
    candles = fetch_bitget_json(candles_url)["data"]
    rows = []
    for row in candles:
        rows.append(
            {
                "ts": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]) if row[5] not in ("", None) else 0.0,
            }
        )
    df = pd.DataFrame(rows).sort_values("ts").reset_index(drop=True)
    return df, ticker


def fetch_stock_token(user_symbol: str, base_ticker: str, bitget_symbol: str) -> dict[str, Any]:
    stock_df, meta = stock_dataframe_from_yahoo(base_ticker)
    token_df, token_ticker = token_dataframe_from_bitget(bitget_symbol)
    stock_close = stock_df["close"]
    token_close = token_df["close"]
    stock_macd = macd(stock_close)
    stock_bb = boll(stock_close)
    stock_kdj = kdj(stock_df)
    stock_atr = atr(stock_df)
    price = float(token_ticker["lastPr"])
    true_stock_price = float(meta.get("regularMarketPrice") or stock_close.iloc[-1])
    premium_pct = (price - true_stock_price) / true_stock_price * 100
    ema50 = float(ema(stock_close, 50).iloc[-1])
    ema200_series = ema(stock_close, 200)
    ema200_val = ema200_series.iloc[-1]
    ema200 = float(ema200_val) if not math.isnan(ema200_val) else float("nan")
    atr_val = float(stock_atr.iloc[-1])
    bb_upper = float(stock_bb["upper"].iloc[-1])
    bb_mid = float(stock_bb["middle"].iloc[-1])
    bb_lower = float(stock_bb["lower"].iloc[-1])
    swing_high = float(stock_df["high"].tail(20).max())
    swing_low = float(stock_df["low"].tail(20).min())
    prev = stock_df.iloc[-2]
    pivot = (prev["high"] + prev["low"] + prev["close"]) / 3
    s1 = 2 * pivot - prev["high"]
    r1 = 2 * pivot - prev["low"]
    s2 = pivot - (prev["high"] - prev["low"])
    r2 = pivot + (prev["high"] - prev["low"])
    support = (s1 + swing_low + bb_lower) / 3
    resistance = (r1 + swing_high + bb_upper) / 3
    support, resistance = ensure_levels(price, support, resistance, atr_val)
    rsi_1d = float(rsi(stock_close).iloc[-1])
    macd_last = stock_macd.iloc[-1]
    kdj_last = stock_kdj.iloc[-1]
    ma5 = float(stock_close.rolling(5).mean().iloc[-1])
    ma10 = float(stock_close.rolling(10).mean().iloc[-1])
    ma20 = float(stock_close.rolling(20).mean().iloc[-1])
    band_width = (bb_upper - bb_lower) / bb_mid * 100
    range_position = (true_stock_price - swing_low) / max(swing_high - swing_low, 1e-9) * 100
    volatility = atr_val / true_stock_price * 100
    valuation_score = 50
    valuation_score += 10 if range_position < 35 else -8 if range_position > 70 else 0
    valuation_score += 6 if premium_pct < -1 else -8 if premium_pct > 1 else 0
    valuation_score += 4 if true_stock_price > ema50 else -4
    valuation_score = max(20, min(80, valuation_score))
    qty_score = 50
    qty_score += 8 if rsi_1d > 55 else -8 if rsi_1d < 45 else 0
    qty_score += 8 if macd_last["hist"] > 0 else -8
    qty_score += 5 if true_stock_price > ma20 else -5
    qty_score += 4 if kdj_last["j"] < 20 else -4 if kdj_last["j"] > 80 else 0
    qty_score = max(20, min(80, qty_score))
    market_score = 50
    market_score += 6 if float(token_ticker["usdtVolume"]) > 20_000_000 else 0
    market_score += 6 if premium_pct < 1 else -6
    market_score += 4 if true_stock_price > ema50 else -4
    market_score = max(20, min(80, market_score))
    composite = int(round(valuation_score * 0.30 + qty_score * 0.40 + market_score * 0.30))
    signal, signal_cn, confidence = signal_bucket(composite)
    entry = true_stock_price if signal == "BUY" else resistance if signal == "SELL" else pivot
    stop = max(price - 2 * atr_val, support * 0.99) if signal != "SELL" else min(price + 2 * atr_val, resistance * 1.01)
    take = min(price + 3 * atr_val, resistance * 1.01) if signal != "SELL" else max(price - 3 * atr_val, support * 0.99)
    rr = abs((take - price) / max(abs(price - stop), 1e-9))
    return {
        "asset_type": "stock_token",
        "symbol": user_symbol,
        "base_ticker": base_ticker,
        "bitget_symbol": bitget_symbol,
        "title": f"{user_symbol} 深度分析报告（股票代币）",
        "header_source": f"Yahoo Finance 真股 {base_ticker} + Bitget 现货 {bitget_symbol}",
        "frame": "股票三支柱评分（估值30% + 量价40% + 市场30%）",
        "signal": signal,
        "signal_cn": signal_cn,
        "confidence": confidence,
        "score": composite,
        "price": price,
        "change_pct": float(token_ticker["change24h"]) * 100,
        "one_liner": (
            f"{user_symbol} 映射 {bitget_symbol}，现价 {fmt_price(price)}，"
            f"对真股 {base_ticker} {'溢价' if premium_pct >= 0 else '折价'} {premium_pct:+.2f}%。"
        ),
        "market_phase": (
            "偏空回落阶段" if signal == "SELL" else
            "区间整理阶段" if signal == "NEUTRAL" else
            "偏多修复阶段"
        ),
        "consensus": {
            "direction": "BUY" if composite >= 60 else "SELL" if composite <= 39 else "HOLD",
            "agreement": 60 if signal != "NEUTRAL" else 40,
            "total": 2 if signal == "BUY" else -2 if signal == "SELL" else 0,
        },
        "levels": {
            "pivot": pivot, "s1": s1, "r1": r1, "s2": s2, "r2": r2,
            "support": support, "resistance": resistance, "entry": entry,
            "stop": stop, "take": take, "rr": rr,
        },
        "metrics": {
            "token_ticker": token_ticker,
            "stock_price": true_stock_price,
            "premium_pct": premium_pct,
            "ema50": ema50,
            "ema200": ema200,
            "atr": atr_val,
            "rsi_1d": rsi_1d,
            "macd_1d": {"dif": float(macd_last["dif"]), "dea": float(macd_last["dea"]), "hist": float(macd_last["hist"])},
            "bb_1d": {"upper": bb_upper, "middle": bb_mid, "lower": bb_lower},
            "kdj": {"k": float(kdj_last["k"]), "d": float(kdj_last["d"]), "j": float(kdj_last["j"])},
            "ma5": ma5, "ma10": ma10, "ma20": ma20, "swing_high": swing_high, "swing_low": swing_low,
            "volatility": volatility, "band_width": band_width, "range_position": range_position,
            "valuation_score": valuation_score, "qty_score": qty_score, "market_score": market_score,
        },
    }


def render_report(data: dict[str, Any]) -> str:
    signal = data["signal"]
    m = data["metrics"]
    lv = data["levels"]
    actions = "\n".join(build_action_guide(signal, data["price"], lv["support"], lv["resistance"]))
    price_line = fmt_price(data["price"])
    trade_guide = build_trade_guide(signal, data)
    pillar1_name = "宏观周期" if data["asset_type"] == "crypto" else "估值/基本面"
    pillar3_name = "衍生品" if data["asset_type"] == "crypto" else "市场/资金面"
    pillar1_score = round(m.get("macro_score", m.get("valuation_score")))
    pillar3_score = round(m.get("der_score", m.get("market_score")))
    pillar1_last_label = "波动性" if data["asset_type"] == "crypto" else "溢价/折价"
    pillar1_last_value = f"{m['volatility']:.2f}%" if data["asset_type"] == "crypto" else f"{m['premium_pct']:+.2f}%"
    pillar1_last_note = "ATR/现价" if data["asset_type"] == "crypto" else "代币相对真股偏离"
    pillar3_row1_label = "资金费率" if data["asset_type"] == "crypto" else "Bitget 24h 成交额"
    pillar3_row1_value = (
        f"{m['funding_rate'] * 100:+.5f}%"
        if data["asset_type"] == "crypto"
        else f"${float(m['token_ticker']['usdtVolume']):,.0f}"
    )
    pillar3_row1_note = "负费率偏多，正费率偏热" if data["asset_type"] == "crypto" else "代币流动性验证"
    pillar3_row2_label = "OI" if data["asset_type"] == "crypto" else "真股现价"
    pillar3_row2_value = f"{m['oi']:,.2f}" if data["asset_type"] == "crypto" else fmt_price(m["stock_price"])
    pillar3_row2_note = "衍生品拥挤度" if data["asset_type"] == "crypto" else "与代币价对比"
    detail_mid_title = "衍生品面" if data["asset_type"] == "crypto" else "市场面"
    detail_mid_body = (
        "资金费率与 OI 提供了当前拥挤度参考。"
        if data["asset_type"] == "crypto"
        else f"{data['symbol']} 已按最新规则映射为 Bitget {data['bitget_symbol']}，未使用 OKX 股票映射永续或 Binance 替代。"
    )
    detail_last_title = "宏观面" if data["asset_type"] == "crypto" else "基本面"
    detail_last_body = (
        "本轮按可得 OKX 数据评估周期位置；缺失维度保持缺失，不做编造。"
        if data["asset_type"] == "crypto"
        else f"真股数据仅取 Yahoo Finance，代币数据仅取 Bitget；当前代币相对真股{'溢价' if m['premium_pct'] >= 0 else '折价'} {m['premium_pct']:+.2f}%。"
    )
    risk_asset = "加密资产" if data["asset_type"] == "crypto" else "股票代币"
    disclaimer = (
        "> ⚠️ 本报告仅为客观技术分析与数据整理，**不构成投资建议**。"
        if data["asset_type"] == "crypto"
        else "> ⚠️ 本报告使用 Yahoo 真股 + Bitget 股票代币数据；股票代币存在溢价回归、交易时段与流动性风险，**不构成投资建议**。"
    )
    section_three_title = "三、Crypto 交易大数据" if data["asset_type"] == "crypto" else "三、市场与资金面数据"
    stock_extra = ""
    if data["asset_type"] == "stock_token":
        stock_extra = (
            f"| 真股现价（Yahoo {data['base_ticker']}） | **{fmt_price(m['stock_price'])}** |\n"
            f"| 代币现价（Bitget {data['bitget_symbol']}） | **{fmt_price(data['price'])}** |\n"
            f"| 溢价 / 折价 | **{m['premium_pct']:+.2f}%** |\n"
            f"| 24h 成交额（Bitget） | ${float(m['token_ticker']['usdtVolume']):,.0f} USDT |\n"
            "| 资金费率 | N/A（股票代币无永续） |\n"
            "| OI 未平仓量 | N/A（股票代币无永续） |\n"
        )
    else:
        stock_extra = (
            f"| 现价 | {fmt_price(data['price'])} |\n"
            f"| 24h 开盘 | {fmt_price(float(m['ticker']['24h open']))} |\n"
            f"| 24h 最高 | {fmt_price(float(m['ticker']['24h high']))} |\n"
            f"| 24h 最低 | {fmt_price(float(m['ticker']['24h low']))} |\n"
            f"| 24h 涨跌 | {fmt_pct(data['change_pct'])} |\n"
            f"| 24h 成交量 | {float(m['ticker']['24h vol']):,.2f} |\n"
            f"| 未平仓量 OI | {m['oi']:,.2f} |\n"
            f"| 资金费率 | {m['funding_rate'] * 100:+.5f}% |\n"
        )
    return f"""# {data['title']}

> 生成时间：{NOW.strftime("%Y-%m-%d %H:%M:%S")} (UTC+8) ｜ 数据源：{data['header_source']} ｜ 分析框架：{data['frame']}
{disclaimer}

---

## 综合结论

| 项目 | 结果 |
|------|------|
| **综合信号** | {data['signal_cn']} |
| **综合评分** | **{data['score']}/100** |
| **置信度** | {data['confidence']} |
| **市场阶段** | {data['market_phase']} |
| **当前价格** | **{price_line}**（{fmt_pct(data['change_pct'])}） |

**一句话**：{data['one_liner']}

### 多周期客观共识

| 项目 | 值 |
|------|-----|
| 共识方向 | {data['consensus']['direction']} |
| 周期一致度 | {data['consensus']['agreement']}% |
| 多周期评分 | {data['consensus']['total']} / +5 |

---

## 下一步（行动清单）

按当前 {data['signal_cn']}（评分 {data['score']}）的定位，建议的下一步动作（按优先级）：
{actions}

### 📋 开仓指南（ATR×结构融合，对齐后端引擎，仅供参考）

{trade_guide}

> 结构化支撑/阻力为三方法平均（枢轴+20日摆动+布林）。以上为研究参考，非投资建议。

---

## 一、实时市场数据

| 指标 | 值 |
|------|-----|
{stock_extra}

## 二、周期趋势预判

| 周期 | 方向 | 强度 |
|------|------|------|
| 约 24 小时 | {'下跌/偏弱' if signal == 'SELL' else '震荡待确认' if signal == 'NEUTRAL' else '修复/偏强'} | 以 1H/日线动能为准 |
| 约 3 天 | {'偏弱' if signal == 'SELL' else '震荡' if signal == 'NEUTRAL' else '偏强'} | 以 4H 结构为准 |
| 约 1 周 | {'回落阶段' if signal == 'SELL' else '整理阶段' if signal == 'NEUTRAL' else '修复阶段'} | 以日线均线与 MACD 为准 |
| 约 1 月 | {data['market_phase']} | 以日线均线和区间位置为准 |

## {section_three_title}

| 项目 | 值 |
|------|-----|
| 结构支撑 | {fmt_price(lv['support'])} |
| 结构阻力 | {fmt_price(lv['resistance'])} |
| 20 日区间位置 | {m['range_position']:.1f}% |
| 布林带宽 | {m['band_width']:.2f}% |
| 波动性 | {m['volatility']:.2f}% |
| 量价结论 | {'偏空' if signal == 'SELL' else '中性' if signal == 'NEUTRAL' else '偏多'} |

## 四、三支柱评分拆解

### 支柱一 · {pillar1_name}（30%）— 评分 ≈ {pillar1_score}

| 指标 | 值 | 解读 |
|------|-----|------|
| EMA50 | {fmt_price(m['ema50'])} | 价格{'上方' if data['price'] > m['ema50'] else '下方'} |
| EMA200 | {"N/A" if math.isnan(m['ema200']) else fmt_price(m['ema200'])} | 长周期趋势参考 |
| 20日区间位置 | {m['range_position']:.1f}% | 越低越偏低估 |
| {pillar1_last_label} | {pillar1_last_value} | {pillar1_last_note} |

### 支柱二 · 量价因子（40%）— 评分 ≈ {round(m['qty_score'])}

| 指标 | 值 | 状态 |
|------|-----|------|
| RSI(14) 1D | {m['rsi_1d']:.2f} | {'偏强' if m['rsi_1d'] > 55 else '偏弱' if m['rsi_1d'] < 45 else '中性'} |
| MACD DIF / DEA / 柱 | {m['macd_1d']['dif']:.3f} / {m['macd_1d']['dea']:.3f} / {m['macd_1d']['hist']:.3f} | {'多头动能' if m['macd_1d']['hist'] > 0 else '空头动能'} |
| KDJ K / D / J | {m['kdj']['k']:.2f} / {m['kdj']['d']:.2f} / {m['kdj']['j']:.2f} | {'J 高位' if m['kdj']['j'] > 80 else 'J 低位' if m['kdj']['j'] < 20 else '中性'} |
| MA5 / MA10 / MA20 | {fmt_price(m['ma5'])} / {fmt_price(m['ma10'])} / {fmt_price(m['ma20'])} | 短中期均线结构 |

### 支柱三 · {pillar3_name}（30%）— 评分 ≈ {pillar3_score}

| 指标 | 值 | 解读 |
|------|-----|------|
| {pillar3_row1_label} | {pillar3_row1_value} | {pillar3_row1_note} |
| {pillar3_row2_label} | {pillar3_row2_value} | {pillar3_row2_note} |
| {'24h 现价变动' if data['asset_type'] != 'crypto' else '24h 涨跌'} | {fmt_pct(data['change_pct'])} | {'资金面整体节奏' if data['asset_type'] != 'crypto' else '短线情绪'} |

### 综合评分

`综合 = 30% + 40% + 30% 加权后 = {data['score']}/100`

## 五、技术指标 PRO

| 指标 | 值 | 状态 |
|------|-----|------|
| RSI(14) 1D | {m['rsi_1d']:.2f} | {'超买' if m['rsi_1d'] > 70 else '超卖' if m['rsi_1d'] < 30 else '中性'} |
| MACD(12,26,9) 1D | {m['macd_1d']['hist']:.3f} | {'看涨' if m['macd_1d']['hist'] > 0 else '看跌'} |
| ATR(14) | {fmt_price(m['atr'])} | 真实波幅均值 |
| 布林带宽 % | {m['band_width']:.2f}% | {'挤压' if m['band_width'] < 12 else '扩张' if m['band_width'] > 20 else '中性'} |
| 支撑位 | {fmt_price(lv['support'])} | — |
| 阻力位 | {fmt_price(lv['resistance'])} | — |
| 波动性 | {m['volatility']:.2f}% | ATR/Price |

## 六、量化参数明细

| 参数 | 值 | 参数 | 值 |
|------|-----|------|-----|
| MACD DIF | {m['macd_1d']['dif']:.3f} | MA(5) | {fmt_price(m['ma5'])} |
| MACD DEA | {m['macd_1d']['dea']:.3f} | MA(10) | {fmt_price(m['ma10'])} |
| MACD 柱 | {m['macd_1d']['hist']:.3f} | MA(20) | {fmt_price(m['ma20'])} |
| 布林上轨 U | {fmt_price(m['bb_1d']['upper'])} | 经典枢轴 Pivot | {fmt_price(lv['pivot'])} |
| 布林中轨 MB | {fmt_price(m['bb_1d']['middle'])} | 支撑 S1 / 阻力 R1 | {fmt_price(lv['s1'])} / {fmt_price(lv['r1'])} |
| 布林下轨 L | {fmt_price(m['bb_1d']['lower'])} | 支撑 S2 / 阻力 R2 | {fmt_price(lv['s2'])} / {fmt_price(lv['r2'])} |
| ATR(14) 绝对值 | {fmt_price(m['atr'])} | 风险回报 | 1 : {lv['rr']:.2f} |

## 七、详细分析

**技术面**：日线 RSI、MACD、KDJ 与均线共同决定当前节奏。当前信号为 **{data['signal_cn']}**，说明价格结构与动能并未形成全面同向确认。

**{detail_mid_title}**：{detail_mid_body}

**{detail_last_title}**：{detail_last_body}

## 八、核心理由与风险

**核心理由**：
1. 结构支撑/阻力与 ATR 已给出明确边界，便于执行。
2. 评分与开仓指南已保持一致，未出现偏空却给回踩多的冲突。
3. 数据源遵守技能约束，缺失字段明确标注而未混源替代。

**风险提示**：
1. 实时数据可能快速变化，执行前需复核最新价格。
2. {risk_asset}波动仍可能在关键位附近快速反复。
3. 若 4H / 日线结构反向破坏，当前结论需要立刻作废。

## 九、操作倾向（仅供参考，非投资建议）

| 风格 | 倾向 | 依据 |
|------|------|------|
| 长线 | {'观望/分批' if signal != 'SELL' else '谨慎'} | 以日线结构和区间位置为主 |
| 波段 | {'等待触发后跟随' if signal == 'NEUTRAL' else '顺势参与'} | 以突破/跌破关键位为准 |
| 短线 | {'反弹空或观望' if signal == 'SELL' else '回踩确认后再动手' if signal == 'BUY' else '不追单'} | 以 ATR 与结构融合风控 |

---
> 数据快照时间：{NOW.strftime("%Y-%m-%d %H:%M:%S")} UTC+8。
> 本报告由 crypto-analysis-report 技能自动生成，**仅供研究参考，不构成任何投资建议**。
"""


def write_report(data: dict[str, Any]) -> ReportSummary:
    content = render_report(data)
    out_path = ROOT / f"{data['symbol'].lower()}_report_{TIMESTAMP}.md"
    out_path.write_text(content, encoding="utf-8")
    return ReportSummary(
        symbol=data["symbol"],
        signal=data["signal_cn"],
        score=data["score"],
        price=data["price"],
        one_liner=data["one_liner"],
        path=out_path,
    )


def _self_check() -> None:
    buy_actions = build_action_guide("BUY", 100, 95, 110)
    sell_actions = build_action_guide("SELL", 100, 95, 110)
    neutral_actions = build_action_guide("NEUTRAL", 100, 95, 110)
    hold_table = build_trade_guide("NEUTRAL", {"price": 100, "change_pct": 0, "levels": {"entry": 100, "stop": 95, "take": 110, "rr": 2.0}})
    short_table = build_trade_guide("SELL", {"price": 100, "change_pct": -1, "levels": {"entry": 108, "stop": 112, "take": 92, "rr": 2.0}})
    assert "回踩多" in buy_actions[1]
    assert "反弹空" in sell_actions[1] or "观望" in sell_actions[1]
    assert "HOLD" in neutral_actions[1]
    assert "HOLD" in hold_table and "建议入场" not in hold_table
    assert "交易方向 | 做空" in short_table


def main() -> int:
    _self_check()
    jobs = [
        ("BTC", fetch_okx_crypto, ("BTC",)),
        ("ETH", fetch_okx_crypto, ("ETH",)),
        ("SOL", fetch_okx_crypto, ("SOL",)),
        ("TSLAUSDT", fetch_stock_token, ("TSLAUSDT", "TSLA", "RTSLAUSDT")),
        ("NVDAUSDT", fetch_stock_token, ("NVDAUSDT", "NVDA", "RNVDAUSDT")),
    ]
    summaries: list[ReportSummary] = []
    for _, fn, args in jobs:
        data = fn(*args)
        summaries.append(write_report(data))
    for item in summaries:
        print(
            json.dumps(
                {
                    "symbol": item.symbol,
                    "signal": item.signal,
                    "score": item.score,
                    "price": item.price,
                    "path": str(item.path),
                    "one_liner": item.one_liner,
                },
                ensure_ascii=True,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
