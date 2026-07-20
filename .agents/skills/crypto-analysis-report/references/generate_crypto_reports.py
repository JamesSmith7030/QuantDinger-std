#!/usr/bin/env python3
"""从 pull_okx_data.py 的已校验快照生成确定性加密深度报告。

用法：
    python generate_crypto_reports.py \
      --input-dir <快照目录> --out-dir analysis_reports \
      --symbols BTC,ETH,SOL,BNB,XRP

本脚本是加密分支「解析→评分→信号→渲染→校验」的单一真相源。
综合状态评分描述市场状态，不是上涨概率；交易动作由方向共识和确认门控独立决定。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PERIODS = ("15m", "1H", "4H", "1Dutc")
PERIOD_WEIGHTS = {"15m": 1, "1H": 2, "4H": 3, "1Dutc": 4}


def resolve_generation_clock(timestamp: str | None) -> tuple[datetime, str]:
    """固定时间戳既控制文件名也控制页眉，确保冻结快照可字节级复现。"""
    if timestamp is None:
        generated_at = datetime.now()
        return generated_at, generated_at.strftime("%Y%m%d%H%M%S")
    generated_at = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
    return generated_at, timestamp


def validate_symbols(symbols: list[str]) -> None:
    if not symbols or len(symbols) > 50:
        raise ValueError("symbols 必须包含 1–50 个币种")
    if len(set(symbols)) != len(symbols):
        raise ValueError("symbols 不得重复")
    if any(not re.fullmatch(r"[A-Z0-9]{2,12}", symbol) for symbol in symbols):
        raise ValueError("symbols 必须是 2–12 位大写字母/数字")


def weighted_score(macro: int, momentum: int, derivatives: int) -> float:
    """返回一位小数的状态评分；三个输入必须在 0..100。"""
    if any(not 0 <= value <= 100 for value in (macro, momentum, derivatives)):
        raise ValueError("支柱评分必须位于 0..100")
    return round(macro * 0.30 + momentum * 0.40 + derivatives * 0.30, 1)


def decide_signal(
    *,
    state_score: float,
    momentum_score: int,
    derivatives_score: int,
    consensus_score: int,
    price: float,
    ema50: float,
    rsi_4h: float,
    rsi_1d: float,
    kdj_j: float,
) -> dict[str, str]:
    """把市场状态与交易动作解耦，避免低估=买入、过热=做空。"""
    overheat = state_score >= 60 and price >= ema50 and (
        rsi_4h >= 70 or rsi_1d >= 70 or kdj_j >= 85
    )
    if overheat:
        return {"signal": "REDUCE", "label": "过热减仓（不做空）", "execution": "REDUCE"}
    if consensus_score >= 5 and momentum_score >= 60 and derivatives_score >= 50 and price >= ema50:
        return {"signal": "BUY", "label": "偏多确认", "execution": "LONG"}
    if consensus_score <= -5 and momentum_score <= 40 and derivatives_score <= 45 and price < ema50:
        return {"signal": "SELL", "label": "偏空确认", "execution": "SHORT"}
    label = "动能偏多" if momentum_score >= 58 else "动能偏弱" if momentum_score <= 35 else "动能分化"
    return {"signal": "NEUTRAL", "label": label, "execution": "HOLD"}


def validate_report(text: str) -> None:
    required = ("## 综合结论", "信号解释：", "执行动作", "## 下一步", "不构成投资建议")
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"报告缺少必要内容：{', '.join(missing)}")
    if len(re.findall(r"(?m)^##\s+", text)) != 11:
        raise ValueError("报告必须包含 11 个二级章节")
    if re.search(r"(?i)\b(?:TODO|TBD|PLACEHOLDER)\b|待补充|待填写", text):
        raise ValueError("报告含未替换占位符")


def split_sections(text: str) -> dict[str, str]:
    if "[FETCH_FAILED:" in text:
        raise ValueError("输入快照包含 FETCH_FAILED，拒绝生成报告")
    matches = list(re.finditer(r"(?m)^=== (.+?) ===\r?$", text))
    if not matches:
        raise ValueError("输入快照没有分段头")
    return {
        match.group(1): text[match.end() : matches[index + 1].start() if index + 1 < len(matches) else None]
        for index, match in enumerate(matches)
    }


def parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^(.+?)\s{2,}(\S.*)$", line.strip())
        if match:
            values[match.group(1).strip()] = match.group(2).strip()
    return values


def number(section: str, key: str) -> float:
    values = parse_key_values(section)
    if key not in values:
        raise ValueError(f"字段缺失：{key}")
    return float(values[key].replace("%", ""))


def parse_macd(section: str) -> dict[str, float]:
    return {"dif": number(section, "dif"), "dea": number(section, "dea"), "hist": number(section, "macd")}


def parse_candles(text: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    pattern = re.compile(
        r"^(?P<date>\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2})\s+"
        r"(?P<open>-?[\d.]+)\s+(?P<high>-?[\d.]+)\s+(?P<low>-?[\d.]+)\s+"
        r"(?P<close>-?[\d.]+)\s+(?P<volume>-?[\d.]+)"
    )
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match:
            rows.append(
                {
                    "ts": datetime.strptime(match.group("date"), "%Y/%m/%d %H:%M:%S").timestamp(),
                    **{key: float(match.group(key)) for key in ("open", "high", "low", "close", "volume")},
                }
            )
    if len(rows) < 20:
        raise ValueError(f"K线不足：需要至少20行，实际{len(rows)}行")
    return sorted(rows, key=lambda row: row["ts"], reverse=True)


def choose_levels(
    *,
    price: float,
    atr: float,
    s1: float,
    swing_low: float,
    bb_lower: float,
    r1: float,
    swing_high: float,
    bb_upper: float,
) -> tuple[float, float, str]:
    support = (s1 + swing_low + bb_lower) / 3
    resistance = (r1 + swing_high + bb_upper) / 3
    if all(math.isfinite(value) for value in (support, price, resistance)) and support < price < resistance:
        return support, resistance, "枢轴+20日摆动+布林三方法平均"
    return max(0.0, price - 2 * atr), price + 3 * atr, "结构位失真，已退回ATR保护带"


def clamp(value: float, low: int = 20, high: int = 80) -> int:
    return int(round(max(low, min(high, value))))


def calculate_macro_score(symbol: str, snapshot: dict[str, Any]) -> int:
    if symbol == "BTC":
        ahr = snapshot["ahr999"]
        return 25 if ahr < 0.45 else 35 if ahr < 0.8 else 50 if ahr < 1.2 else 70 if ahr < 2 else 85
    return clamp(
        42
        + 0.12 * (snapshot["range_position"] - 50)
        + (8 if snapshot["price"] > snapshot["ema50"] else -3)
        + (7 if snapshot["price"] > snapshot["ema200"] else -4)
    )


def calculate_momentum_score(snapshot: dict[str, Any]) -> int:
    score = 50
    for period in PERIODS:
        weight = PERIOD_WEIGHTS[period]
        rsi_value = snapshot["rsi"][period]
        score += weight if rsi_value > 55 else -weight if rsi_value < 45 else 0
        hist = snapshot["macd"][period]["hist"]
        score += weight if hist > 0 else -weight if hist < 0 else 0
    score += 3 if snapshot["price"] > snapshot["ma20"] else -3
    score += 2 if snapshot["price"] > snapshot["ema50"] else -2
    score -= 2 if snapshot["kdj"]["j"] > 90 or snapshot["kdj"]["j"] < 20 else 0
    score = clamp(score)
    if max(snapshot["rsi"].values()) < 70 and snapshot["kdj"]["j"] < 85:
        score = min(score, 72)
    return score


def calculate_derivatives_score(snapshot: dict[str, Any]) -> int:
    # OI 单点只有规模，没有方向；没有历史变化时不加减分。
    funding = snapshot["funding_rate"]
    score = 50 + (8 if funding < 0 else -4 if funding > 0.00005 else 0)
    ratio = snapshot["top_ls_ratio"]
    score += 10 if ratio >= 1.2 else 5 if ratio >= 1.05 else -10 if ratio <= 0.8 else -5 if ratio <= 0.95 else 0
    return clamp(score)


def calculate_consensus(snapshot: dict[str, Any]) -> tuple[int, int]:
    votes: list[int] = []
    for period in PERIODS:
        rsi_value = snapshot["rsi"][period]
        votes.append(1 if rsi_value > 55 else -1 if rsi_value < 45 else 0)
        hist = snapshot["macd"][period]["hist"]
        votes.append(1 if hist > 0 else -1 if hist < 0 else 0)
    total = sum(votes)
    direction = 1 if total > 0 else -1 if total < 0 else 0
    agreement = round(sum(vote == direction for vote in votes) / len(votes) * 100) if direction else 0
    return total, agreement


def consistency_level(agreement: int, consensus_score: int) -> str:
    if agreement >= 75 and abs(consensus_score) >= 6:
        return "高"
    if agreement >= 62 and abs(consensus_score) >= 4:
        return "中"
    return "低"


def parse_snapshot(symbol: str, input_dir: Path) -> dict[str, Any]:
    parts = split_sections((input_dir / f"{symbol}.txt").read_text(encoding="utf-8"))
    ticker = parse_key_values(parts["TICKER"])
    price = float(ticker["last"])
    rsi = {period: number(parts[f"RSI {period}"], "14") for period in PERIODS}
    macd = {period: parse_macd(parts[f"MACD {period}"]) for period in PERIODS}
    bb = {key: number(parts["BB 1D"], key) for key in ("upper", "middle", "lower")}
    kdj = {key: number(parts["KDJ 1D"], key) for key in ("k", "d", "j")}
    tls = parse_key_values(parts["TLS"])
    oi_match = re.search(
        rf"(?m)^{re.escape(symbol)}-USDT-SWAP\s+(\S+)\s+(\S+)\s+"
        r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2})",
        parts["OI"],
    )
    if not oi_match:
        raise ValueError(f"{symbol} OI字段无法解析")
    candles = parse_candles((input_dir / f"{symbol}_c20.txt").read_text(encoding="utf-8"))
    recent, previous = candles[:20], candles[1]
    swing_high = max(row["high"] for row in recent)
    swing_low = min(row["low"] for row in recent)
    pivot = (previous["high"] + previous["low"] + previous["close"]) / 3
    s1, r1 = 2 * pivot - previous["high"], 2 * pivot - previous["low"]
    s2, r2 = pivot - (previous["high"] - previous["low"]), pivot + (previous["high"] - previous["low"])
    atr = number(parts["ATR14"], "14")
    support, resistance, level_method = choose_levels(
        price=price,
        atr=atr,
        s1=s1,
        swing_low=swing_low,
        bb_lower=bb["lower"],
        r1=r1,
        swing_high=swing_high,
        bb_upper=bb["upper"],
    )
    snapshot: dict[str, Any] = {
        "symbol": symbol,
        "price": price,
        "change_pct": float(ticker["24h change %"].replace("%", "")),
        "open": float(ticker["24h open"]),
        "high": float(ticker["24h high"]),
        "low": float(ticker["24h low"]),
        "volume": float(ticker["24h vol"]),
        "ticker_time": datetime.strptime(ticker["time"], "%Y/%m/%d %H:%M:%S"),
        "oi_time": datetime.strptime(oi_match.group(3), "%Y/%m/%d %H:%M:%S"),
        "rsi": rsi,
        "macd": macd,
        "bb": bb,
        "kdj": kdj,
        "ema50": number(parts["EMA50"], "50"),
        "ema200": number(parts["EMA200"], "200"),
        "atr": atr,
        "ma5": number(parts["MA5"], "5"),
        "ma10": number(parts["MA10"], "10"),
        "ma20": number(parts["MA20"], "20"),
        "funding_rate": number(parts["FUNDING"], "fundingRate"),
        "oi_contracts": float(oi_match.group(1)),
        "oi_ccy": float(oi_match.group(2)),
        "top_long_ratio": float(tls["longRatio"]),
        "top_short_ratio": float(tls["shortRatio"]),
        "top_ls_ratio": float(tls["longShortRatio"]),
        "swing_high": swing_high,
        "swing_low": swing_low,
        "pivot": pivot,
        "s1": s1,
        "r1": r1,
        "s2": s2,
        "r2": r2,
        "support": support,
        "resistance": resistance,
        "level_method": level_method,
        "range_position": (price - swing_low) / max(swing_high - swing_low, 1e-9) * 100,
        "band_width": (bb["upper"] - bb["lower"]) / bb["middle"] * 100,
        "volatility": number(parts["ATR14"], "14") / price * 100,
    }
    if symbol == "BTC":
        rainbow = parse_key_values(parts["RAINBOW"])
        snapshot = {
            **snapshot,
            "ahr999": number(parts["AHR999"], "ahr999"),
            "rainbow_band": int(float(rainbow["band"])),
            "rainbow_deviation": float(rainbow.get("deviation", "nan")),
        }
    return snapshot


def enrich_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    macro = calculate_macro_score(snapshot["symbol"], snapshot)
    momentum = calculate_momentum_score(snapshot)
    derivatives = calculate_derivatives_score(snapshot)
    state = weighted_score(macro, momentum, derivatives)
    consensus, agreement = calculate_consensus(snapshot)
    decision = decide_signal(
        state_score=state,
        momentum_score=momentum,
        derivatives_score=derivatives,
        consensus_score=consensus,
        price=snapshot["price"],
        ema50=snapshot["ema50"],
        rsi_4h=snapshot["rsi"]["4H"],
        rsi_1d=snapshot["rsi"]["1Dutc"],
        kdj_j=snapshot["kdj"]["j"],
    )
    consistency = consistency_level(agreement, consensus)
    return {
        **snapshot,
        "macro_score": macro,
        "momentum_score": momentum,
        "derivatives_score": derivatives,
        "state_score": state,
        "consensus_score": consensus,
        "agreement": agreement,
        "consistency": consistency,
        "decision": decision,
    }


def state_zone(score: float) -> str:
    return "深度价值区" if score < 20 else "复苏区" if score < 40 else "中性区" if score < 60 else "过热区" if score < 80 else "狂热区"


def price_text(value: float, symbol: str) -> str:
    decimals = {"BTC": 1, "ETH": 2, "SOL": 2, "BNB": 2, "XRP": 5}.get(symbol, 4)
    return f"${value:,.{decimals}f}"


def signal_text(decision: dict[str, str]) -> str:
    return {
        "BUY": f"🟢 BUY {decision['label']}",
        "SELL": f"🔴 SELL {decision['label']}",
        "REDUCE": f"🟠 REDUCE {decision['label']}",
        "NEUTRAL": f"🟡 NEUTRAL {decision['label']}",
    }[decision["signal"]]


def momentum_label(value: float) -> str:
    return "多头动能" if value > 0 else "空头动能" if value < 0 else "中性动能"


def signal_explanation(decision: dict[str, str]) -> str:
    if decision["signal"] == "REDUCE":
        return "上涨状态过热，仅表示已有多仓可减仓；不代表开空。"
    if decision["signal"] == "BUY":
        return "多周期、EMA50与衍生品共同偏多；仍须等待结构位确认后执行。"
    if decision["signal"] == "SELL":
        return "多周期、EMA50与衍生品共同偏空；只在破位确认后研究空单。"
    if decision["label"] == "动能偏多":
        return "多周期买方力量占优，但完整做多门控尚未通过，不等于直接BUY。"
    if decision["label"] == "动能偏弱":
        return "多周期卖方力量占优，但完整做空门控尚未通过，不等于自动开空。"
    return "不同周期或支柱方向冲突，暂不建立方向仓位。"


def summary_sentence(data: dict[str, Any]) -> str:
    relative_ema50 = (data["price"] / data["ema50"] - 1) * 100
    return (
        f"量价{data['momentum_score']}、衍生品{data['derivatives_score']}，"
        f"价相对EMA50 {relative_ema50:+.2f}%；执行{data['decision']['execution']}。"
    )


def trade_guide(data: dict[str, Any]) -> str:
    symbol, execution, price, atr = data["symbol"], data["decision"]["execution"], data["price"], data["atr"]
    p = lambda value: price_text(value, symbol)
    if execution in ("HOLD", "REDUCE"):
        note = "已有多仓可分批减仓，不开空" if execution == "REDUCE" else "数据未通过方向门控，不开仓"
        return f"| 项目 | 价位 | 说明 |\n|------|------|------|\n| **执行动作** | **{execution}** | {note} |\n| 当前价格 | {p(price)} | 24h {data['change_pct']:+.2f}% |"
    if execution == "LONG":
        stop = max(price - 2 * atr, data["support"] * 0.99)
        take = min(price + 3 * atr, data["resistance"] * 1.01)
        entry, direction = data["ma5"], "做多"
    else:
        stop = min(price + 2 * atr, data["resistance"] * 1.01)
        take = max(price - 3 * atr, data["support"] * 0.99)
        entry, direction = data["resistance"], "做空"
    rr = abs(take - price) / max(abs(price - stop), 1e-9)
    return (
        "| 项目 | 价位 | 说明 |\n|------|------|------|\n"
        f"| **执行动作** | **{execution}（{direction}）** | 方向门控已通过，仍需价格确认 |\n"
        f"| 当前价格 | {p(price)} | 24h {data['change_pct']:+.2f}% |\n"
        f"| 建议入场 | {p(entry)} | {'回踩确认' if execution == 'LONG' else '反弹承压'} |\n"
        f"| 止损价 | {p(stop)} | ATR×结构融合 |\n| 止盈目标 | {p(take)} | ATR×结构融合 |\n"
        f"| 风险回报比 | 1 : {rr:.2f} | 仅作量化参考 |"
    )


def render_report(data: dict[str, Any], generated_at: datetime, snapshot_window: str) -> str:
    symbol = data["symbol"]
    p = lambda value: price_text(value, symbol)
    d = data["decision"]
    valuation = (
        f"AHR999 {data['ahr999']:.4f}；彩虹 band {data['rainbow_band']}，偏差 {data['rainbow_deviation']:+.4f}"
        if symbol == "BTC" else "非BTC不适用AHR999/彩虹图，以区间位置和EMA结构替代"
    )
    macd_rows = "\n".join(
        f"| {period.replace('1Dutc', '1D')} | {data['macd'][period]['dif']:.4f} | {data['macd'][period]['dea']:.4f} | "
        f"{data['macd'][period]['hist']:+.4f} | {momentum_label(data['macd'][period]['hist'])} |"
        for period in PERIODS
    )
    consensus_direction = "偏多" if data["consensus_score"] >= 3 else "偏空" if data["consensus_score"] <= -3 else "分化"
    action_guidance = {
        "LONG": "方向门控已通过，等待回踩/突破结构确认",
        "SHORT": "方向门控已通过，等待反弹承压/破位确认",
        "HOLD": "方向门控未通过，不因单一动能标签追单",
        "REDUCE": "仅减少已有多仓，不建立空仓",
    }[d["execution"]]
    return f"""# {symbol}/USDT 深度分析报告

> 生成时间：{generated_at:%Y-%m-%d %H:%M:%S} (UTC+8) ｜ 数据源：OKX实时行情（基础档）｜ 模型：crypto-analysis-report v1.3.0
> ⚠️ 本报告仅为客观技术分析与数据整理，**不构成投资建议**。

---

## 综合结论

| 项目 | 结果 |
|------|------|
| **综合信号** | {signal_text(d)} |
| **执行动作** | **{d['execution']}** |
| **综合状态评分** | **{data['state_score']:.1f}/100**（{state_zone(data['state_score'])}） |
| **一致性等级** | {data['consistency']}（指标同向 {data['agreement']}%，非胜率） |
| **当前价格** | **{p(data['price'])}**（24h {data['change_pct']:+.2f}%） |

**一句话**：{summary_sentence(data)}

> 信号解释：{signal_explanation(d)}
>
> 评分说明：状态评分描述周期位置与强弱，不是上涨概率；交易动作由方向共识、EMA50和衍生品门控独立决定。

### 多周期客观共识

| 项目 | 值 |
|------|-----|
| 共识方向 | {consensus_direction} |
| 指标同向比例 | {data['agreement']}%（8项：四周期RSI+MACD） |
| 方向评分 | {data['consensus_score']:+d}（-8至+8） |

---

## 下一步（行动清单）

1. **关键位**：支撑 {p(data['support'])}；阻力 {p(data['resistance'])}。
2. **执行动作**：{d['execution']}；{action_guidance}。
3. **复核条件**：按4H/1D收盘复核EMA50、MACD和顶级交易员多空比。
4. **失效条件**：突破阻力或跌破支撑后，使用新快照重新评分。

### 📋 开仓指南

{trade_guide(data)}

---

## 一、实时市场数据

| 项目 | 值 |
|------|-----|
| 现价 | {p(data['price'])} |
| 24h开/高/低 | {p(data['open'])} / {p(data['high'])} / {p(data['low'])} |
| 24h涨跌 | {data['change_pct']:+.2f}% |
| 24h成交量 | {data['volume']:,.2f} {symbol} |
| OI | {data['oi_ccy']:,.2f} {symbol}（{data['oi_contracts']:,.2f}张） |
| 资金费率 | {data['funding_rate']*100:+.5f}% |

## 二、周期趋势预判

| 周期 | RSI | MACD柱 | 判读 |
|------|-----|--------|------|
| 15m | {data['rsi']['15m']:.2f} | {data['macd']['15m']['hist']:+.4f} | 入场择时 |
| 1H | {data['rsi']['1H']:.2f} | {data['macd']['1H']['hist']:+.4f} | 约24小时 |
| 4H | {data['rsi']['4H']:.2f} | {data['macd']['4H']['hist']:+.4f} | 约3天 |
| 1D | {data['rsi']['1Dutc']:.2f} | {data['macd']['1Dutc']['hist']:+.4f} | 约1周 |

## 三、Crypto 交易大数据

| 项目 | 值 |
|------|-----|
| 资金费率 | {data['funding_rate']*100:+.5f}% |
| OI | {data['oi_ccy']:,.2f} {symbol}（单点快照，不计方向分） |
| 顶级交易员多空比 | {data['top_long_ratio']:.2f}/{data['top_short_ratio']:.2f}（{data['top_ls_ratio']:.2f}） |
| 20日区间位置 | {data['range_position']:.1f}% |
| 周期估值 | {valuation} |
| 交易所/稳定币净流 | --（基础档数据缺失） |

## 四、三支柱评分拆解

### 宏观周期（30%）— {data['macro_score']}

| 指标 | 值 |
|------|-----|
| 周期估值 | {valuation} |
| 价vs EMA50/200 | {(data['price']/data['ema50']-1)*100:+.2f}% / {(data['price']/data['ema200']-1)*100:+.2f}% |
| 20日区间位置 | {data['range_position']:.1f}% |

### 量价因子（40%）— {data['momentum_score']}

| 15m RSI | 1H RSI | 4H RSI | 1D RSI |
|---------|--------|--------|--------|
| {data['rsi']['15m']:.2f} | {data['rsi']['1H']:.2f} | {data['rsi']['4H']:.2f} | {data['rsi']['1Dutc']:.2f} |

| MACD周期 | DIF | DEA | 柱 | 状态 |
|----------|-----|-----|-----|------|
{macd_rows}

KDJ={data['kdj']['k']:.2f}/{data['kdj']['d']:.2f}/{data['kdj']['j']:.2f}；MA5/10/20={p(data['ma5'])}/{p(data['ma10'])}/{p(data['ma20'])}。

### 衍生品（30%）— {data['derivatives_score']}

| 资金费率 | 顶级交易员多空比 | OI |
|----------|------------------|----|
| {data['funding_rate']*100:+.5f}% | {data['top_ls_ratio']:.2f} | 单点仅展示，不加分 |

### 综合状态评分

{data['macro_score']}×0.30 + {data['momentum_score']}×0.40 + {data['derivatives_score']}×0.30 = **{data['state_score']:.1f}/100**。

## 五、技术指标 PRO

| 指标 | 值 | 状态 |
|------|-----|------|
| RSI 1D | {data['rsi']['1Dutc']:.2f} | {'偏强' if data['rsi']['1Dutc'] > 55 else '偏弱' if data['rsi']['1Dutc'] < 45 else '中性'} |
| MACD 1D柱 | {data['macd']['1Dutc']['hist']:+.4f} | {momentum_label(data['macd']['1Dutc']['hist'])} |
| ATR14 | {p(data['atr'])} | 波动率 {data['volatility']:.2f}% |
| 布林带宽 | {data['band_width']:.2f}% | {'扩张' if data['band_width'] > 20 else '挤压' if data['band_width'] < 8 else '常态'} |
| 支撑/阻力 | {p(data['support'])} / {p(data['resistance'])} | {data['level_method']} |

## 六、量化参数明细

| 参数 | 值 | 参数 | 值 |
|------|-----|------|-----|
| Pivot | {p(data['pivot'])} | S1/R1 | {p(data['s1'])}/{p(data['r1'])} |
| S2/R2 | {p(data['s2'])}/{p(data['r2'])} | 20日高/低 | {p(data['swing_high'])}/{p(data['swing_low'])} |
| 布林上/中/下 | {p(data['bb']['upper'])}/{p(data['bb']['middle'])}/{p(data['bb']['lower'])} | ATR14 | {p(data['atr'])} |

## 七、详细分析

**技术面**：方向评分 {data['consensus_score']:+d}/8，价格相对EMA50/200为 {(data['price']/data['ema50']-1)*100:+.2f}%/{(data['price']/data['ema200']-1)*100:+.2f}%。

**衍生品面**：资金费率 {data['funding_rate']*100:+.5f}%，顶级交易员多空比 {data['top_ls_ratio']:.2f}；OI没有历史变化序列，因此不推断增减仓方向。

**数据边界**：基础档未接入宏观、新闻、情绪与净流量，不对缺失维度作推测。

## 八、核心理由与风险

**核心理由**：状态评分、方向评分与执行动作已分离；只有共识、EMA50与衍生品同时通过时才给LONG/SHORT。

**风险提示**：指标可能钝化；ATR波动可能快速扫损；实时行情会变化；缺少OI历史与宏观增强数据。

## 九、操作倾向（仅供参考）

| 风格 | 倾向 |
|------|------|
| 长线 | 结合周期估值分批评估，不因单一低分抄底 |
| 波段 | 按执行动作与关键位等待确认 |
| 合约 | {d['execution']}；REDUCE不做空，HOLD不开仓 |

---
> 数据快照时间：{snapshot_window}。技术指标为时点值，执行前请复核最新数据。
> 本报告由 crypto-analysis-report v1.3.0 生成，**仅供研究参考，不构成投资建议**。
"""


def prepare_output_paths(output_dir: Path, symbols: list[str], stamp: str) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {symbol: output_dir / f"{symbol.lower()}_report_{stamp}.md" for symbol in symbols}
    collisions = [path for path in paths.values() if path.exists()]
    if collisions:
        names = ", ".join(str(path) for path in collisions)
        raise FileExistsError(f"拒绝覆盖已有报告：{names}")
    return paths


def generate(input_dir: Path, output_dir: Path, symbols: list[str], timestamp: str | None = None) -> list[dict[str, Any]]:
    validate_symbols(symbols)
    generated_at, stamp = resolve_generation_clock(timestamp)
    output_paths = prepare_output_paths(output_dir, symbols, stamp)
    snapshots = [enrich_snapshot(parse_snapshot(symbol, input_dir)) for symbol in symbols]
    times = [value for item in snapshots for value in (item["ticker_time"], item["oi_time"])]
    snapshot_window = f"{min(times):%Y-%m-%d %H:%M}–{max(times):%Y-%m-%d %H:%M} (UTC+8)"
    summaries: list[dict[str, Any]] = []
    for item in snapshots:
        content = render_report(item, generated_at, snapshot_window)
        validate_report(content)
        path = output_paths[item["symbol"]]
        path.write_text(content, encoding="utf-8")
        summaries.append(
            {
                "symbol": item["symbol"],
                "signal": signal_text(item["decision"]),
                "execution": item["decision"]["execution"],
                "score": item["state_score"],
                "price": item["price"],
                "change_pct": item["change_pct"],
                "one_liner": summary_sentence(item),
                "path": str(path.resolve()),
                "snapshot": snapshot_window,
            }
        )
    return summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path, help="pull_okx_data.py 的输出目录")
    parser.add_argument("--out-dir", default=Path("analysis_reports"), type=Path, help="报告输出目录")
    parser.add_argument("--symbols", default="BTC,ETH,SOL,BNB,XRP", help="逗号分隔币种")
    parser.add_argument("--timestamp", help="可选固定文件时间戳 YYYYMMDDHHmmss；默认当前时间")
    args = parser.parse_args()
    if args.timestamp and not re.fullmatch(r"\d{14}", args.timestamp):
        parser.error("--timestamp 必须是 YYYYMMDDHHmmss")
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]
    for summary in generate(args.input_dir, args.out_dir, symbols, args.timestamp):
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
