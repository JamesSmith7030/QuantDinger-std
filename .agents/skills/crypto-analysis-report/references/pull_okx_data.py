#!/usr/bin/env python3
"""okx CLI 行情/指标批量拉取器：内置重试 + 字段完整性校验。

替代 crypto-analysis-report 技能第 1A 步里内联手写的 bash 拉取命令。
每条 okx 命令拉完立即用「下游 parse 实际会用到的字段」正则校验输出：
不通过（网络抖动导致空/半截输出）就退避 1-2 秒重试，默认最多 2 次；
仍失败则在文件里写明确的 [FETCH_FAILED: 原因] 标记并计入汇总，
绝不把空/半截数据静默写进文件让下游 parse/pipeline 猜或崩溃。

用法：
    python pull_okx_data.py --symbols BTC,ETH,SOL,BNB,XRP --out-dir <目录>

产物（`generate_crypto_reports.py` 可直接读）：
    <目录>/<SYM>.txt       各项指标，`=== 段名 ===` 分段
    <目录>/<SYM>_c20.txt   近 N 日 K 线（供 20 日摆动高低计算），无分段头

退出码：0 = 全部成功；1 = 存在重试耗尽仍失败的字段（终端打印汇总，含缺失项与原因）。
"""

from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP"]

# Windows 上 okx 是 npm 装的 .cmd 包装脚本，subprocess 在 shell=False 时
# 无法直接启动 .cmd（非 PE 可执行文件），必须走 shell=True 才能被 cmd.exe 解析执行。
USE_SHELL = os.name == "nt"


@dataclass
class Section:
    name: str
    cmd: list[str]
    patterns: list[str]  # 全部命中才算成功；对齐下游 parse 实际用到的正则


@dataclass
class FetchResult:
    section: str
    ok: bool
    output: str
    reason: str = ""
    attempts: int = 0


def build_sections(symbol: str) -> list[Section]:
    spot = f"{symbol}-USDT"
    swap = f"{symbol}-USDT-SWAP"
    sections = [
        Section(
            "TICKER",
            ["okx", "market", "ticker", spot],
            [r"^last\s+[\d.]+", r"^24h high\s+[\d.]+", r"^24h low\s+[\d.]+",
             r"^24h open\s+[\d.]+", r"^24h vol\s+[\d.]+",
             r"^24h change %\s+-?[\d.]+%",
             r"^time\s+\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2}"],
        ),
    ]
    for bar in ("15m", "1H", "4H", "1Dutc"):
        sections.append(Section(
            f"RSI {bar}",
            ["okx", "market", "indicator", "rsi", spot, "--bar", bar],
            [r"^\s*14\s+[\d.]+", r"^ts\s+\S"],
        ))
    for bar in ("15m", "1H", "4H", "1Dutc"):
        sections.append(Section(
            f"MACD {bar}",
            ["okx", "market", "indicator", "macd", spot, "--bar", bar],
            [r"^dif\s+-?[\d.]+", r"^dea\s+-?[\d.]+", r"^macd\s+-?[\d.]+"],
        ))
    sections.append(Section(
        "BB 1D",
        ["okx", "market", "indicator", "bb", spot, "--bar", "1Dutc"],
        [r"^upper\s+[\d.]+", r"^middle\s+[\d.]+", r"^lower\s+[\d.]+"],
    ))
    sections.append(Section(
        "KDJ 1D",
        ["okx", "market", "indicator", "kdj", spot, "--bar", "1Dutc"],
        [r"^k\s+-?[\d.]+", r"^d\s+-?[\d.]+", r"^j\s+-?[\d.]+"],
    ))
    sections.append(Section(
        "EMA50",
        ["okx", "market", "indicator", "ema", spot, "--bar", "1Dutc", "--params", "50"],
        [r"^\s*50\s+[\d.]+"],
    ))
    sections.append(Section(
        "EMA200",
        ["okx", "market", "indicator", "ema", spot, "--bar", "1Dutc", "--params", "200"],
        [r"^\s*200\s+[\d.]+"],
    ))
    sections.append(Section(
        "ATR14",
        ["okx", "market", "indicator", "atr", spot, "--bar", "1Dutc", "--params", "14"],
        [r"^\s*14\s+[\d.]+"],
    ))
    for period in ("5", "10", "20"):
        sections.append(Section(
            f"MA{period}",
            ["okx", "market", "indicator", "ma", spot, "--bar", "1Dutc", "--params", period],
            [rf"^\s*{period}\s+[\d.]+"],
        ))
    if symbol.upper() == "BTC":
        sections.append(Section(
            "AHR999",
            ["okx", "market", "indicator", "ahr999", spot, "--bar", "1Dutc"],
            [r"^ahr999\s+[\d.]+", r"^zone\s+\d+"],
        ))
        sections.append(Section(
            "RAINBOW",
            ["okx", "market", "indicator", "rainbow", spot, "--bar", "1Dutc"],
            [r"^band\s+\d+"],
        ))
    sections.append(Section(
        "TLS",
        ["okx", "market", "indicator", "top-long-short", spot, "--bar", "1Dutc"],
        [r"^longRatio\s+[\d.]+", r"^shortRatio\s+[\d.]+", r"^longShortRatio\s+[\d.]+"],
    ))
    sections.append(Section(
        "FUNDING",
        ["okx", "market", "funding-rate", swap],
        [r"^fundingRate\s+-?[\d.]+"],
    ))
    sections.append(Section(
        "OI",
        ["okx", "market", "open-interest", "--instType", "SWAP", "--instId", swap],
        [rf"^{re.escape(swap)}\s+[\d.]+\s+[\d.]+\s+"
         r"\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}:\d{2}"],
    ))
    return sections


def build_candle_cmd(symbol: str, limit: int) -> list[str]:
    return ["okx", "market", "candles", f"{symbol}-USDT", "--bar", "1D", "--limit", str(limit)]


def parse_symbols(raw: str) -> list[str]:
    symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()))
    if not symbols:
        raise ValueError("至少需要一个币种")
    if len(symbols) > 50:
        raise ValueError("单次最多拉取 50 个币种")
    invalid = [symbol for symbol in symbols if not re.fullmatch(r"[A-Z0-9]{2,12}", symbol)]
    if invalid:
        raise ValueError(f"币种格式非法：{', '.join(invalid)}")
    return symbols


def validate(output: str, patterns: list[str]) -> tuple[bool, str]:
    if not output or not output.strip():
        return False, "输出为空"
    lower = output.lower()
    for marker in ("error", "exception", "traceback", "unauthorized", "econnrefused", "requires a period"):
        if marker in lower:
            return False, f"输出含错误标记 '{marker}'"
    for pattern in patterns:
        if not re.search(pattern, output, re.MULTILINE):
            return False, f"缺少预期字段（正则未命中：{pattern}）"
    return True, ""


def run_with_retry(cmd: list[str], patterns: list[str], retries: int, min_delay: float,
                    max_delay: float, timeout: float) -> FetchResult:
    section_hint = " ".join(cmd)
    last_output, last_reason = "", "未知原因"
    for attempt in range(1, retries + 2):  # 首次 + retries 次重试
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout, shell=USE_SHELL)
            last_output = proc.stdout
            if proc.returncode != 0:
                last_reason = f"退出码 {proc.returncode}：{(proc.stderr or '').strip()[:200]}"
            else:
                ok, reason = validate(last_output, patterns)
                if ok:
                    return FetchResult(section_hint, True, last_output, attempts=attempt)
                last_reason = reason
        except subprocess.TimeoutExpired:
            last_reason = f"命令超时（>{timeout}s）"
        except Exception as exc:  # noqa: BLE001 - 需要把任意子进程异常都归为一次失败重试
            last_reason = f"命令执行异常：{exc}"
        if attempt < retries + 1:
            time.sleep(random.uniform(min_delay, max_delay))
    return FetchResult(section_hint, False, last_output, reason=last_reason, attempts=retries + 1)


def fetch_symbol(symbol: str, out_dir: Path, retries: int, min_delay: float, max_delay: float,
                  timeout: float, candle_limit: int) -> tuple[str, list[str]]:
    sections = build_sections(symbol)
    lines: list[str] = []
    failures: list[str] = []
    for sec in sections:
        result = run_with_retry(sec.cmd, sec.patterns, retries, min_delay, max_delay, timeout)
        lines.append(f"=== {sec.name} ===")
        if result.ok:
            lines.append(result.output.rstrip("\n"))
        else:
            lines.append(f"[FETCH_FAILED: {result.reason}]")
            failures.append(f"{symbol}.{sec.name}: {result.reason}（已重试 {result.attempts} 次）")

    (out_dir / f"{symbol}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    candle_patterns = [r"\d{4}/\d+/\d+ \d+:\d+:\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+"]
    candle_cmd = build_candle_cmd(symbol, candle_limit)
    candle_result = run_with_retry(candle_cmd, candle_patterns, retries, min_delay, max_delay, timeout)
    if candle_result.ok:
        row_count = len(re.findall(candle_patterns[0], candle_result.output))
        if row_count < 21:
            failures.append(
                f"{symbol}.CANDLES: 只拿到 {row_count} 行收盘K线（需要至少 21 行算 20 日摆动高低），"
                f"请提高 --candle-limit（当前 {candle_limit}）"
            )
        (out_dir / f"{symbol}_c20.txt").write_text(candle_result.output, encoding="utf-8")
    else:
        failures.append(f"{symbol}.CANDLES: {candle_result.reason}（已重试 {candle_result.attempts} 次）")
        (out_dir / f"{symbol}_c20.txt").write_text(f"[FETCH_FAILED: {candle_result.reason}]\n", encoding="utf-8")

    return symbol, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                         help="逗号分隔的币种列表，如 BTC,ETH,SOL,BNB,XRP")
    parser.add_argument("--out-dir", required=True, help="写入 <SYM>.txt / <SYM>_c20.txt 的目录")
    parser.add_argument("--retries", type=int, default=2, help="单条命令失败后的最大重试次数（默认 2）")
    parser.add_argument("--min-delay", type=float, default=1.0, help="重试前最小等待秒数（默认 1.0）")
    parser.add_argument("--max-delay", type=float, default=2.0, help="重试前最大等待秒数（默认 2.0）")
    parser.add_argument("--timeout", type=float, default=20.0, help="单条 okx 命令超时秒数（默认 20）")
    parser.add_argument("--candle-limit", type=int, default=25,
                         help="K 线拉取根数，需 >=21 才够 20 日摆动高低计算（默认 25）")
    args = parser.parse_args()

    try:
        symbols = parse_symbols(args.symbols)
    except ValueError as exc:
        parser.error(str(exc))
    if args.candle_limit < 21:
        parser.error("--candle-limit 必须 >=21")
    if args.retries < 0 or args.min_delay < 0 or args.max_delay < args.min_delay or args.timeout <= 0:
        parser.error("重试次数、延迟或超时参数非法")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_failures: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as pool:
        futures = [
            pool.submit(fetch_symbol, sym, out_dir, args.retries, args.min_delay,
                        args.max_delay, args.timeout, args.candle_limit)
            for sym in symbols
        ]
        for fut in futures:
            symbol, failures = fut.result()
            all_failures[symbol] = failures

    print(f"拉取完成：{', '.join(symbols)} → {out_dir}")
    has_failure = False
    for symbol in symbols:
        failures = all_failures[symbol]
        if not failures:
            print(f"  [OK] {symbol}：全部字段拉取成功")
            continue
        has_failure = True
        print(f"  [缺失] {symbol}：{len(failures)} 项重试耗尽后仍失败")
        for item in failures:
            print(f"    - {item}")

    if has_failure:
        print("\n存在缺失字段，请检查上方原因（多为网络抖动/接口限流）；"
              "对应 <SYM>.txt 内该字段已标记 [FETCH_FAILED: ...]，不会被下游误读为 0 或空值。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
