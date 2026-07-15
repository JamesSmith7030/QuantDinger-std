# -*- coding: utf-8 -*-
import argparse
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
REFS = ROOT / "references"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build_report = load_module("crypto_build_report", REFS / "build_report.py")
pull_okx_data = load_module("crypto_pull_okx_data", REFS / "pull_okx_data.py")


def market(*, bullish=False, rsi=None):
    price = 110.0 if bullish else 90.0
    hist = (1.0, 1.0, 1.0, 1.0) if bullish else (-1.0, -1.0, -1.0, -1.0)
    return {
        "mode": "short",
        "labels": build_report.LABELS["short"],
        "unit": "ETH",
        "price": price,
        "h24": price + 2,
        "l24": price - 2,
        "vol24": 12345.0,
        "chg": 1.5 if bullish else -1.5,
        "rsi": tuple(rsi or ((60.0,) * 4 if bullish else (40.0,) * 4)),
        "hist": hist,
        "macd1d": (1.0, 0.5, hist[-1]),
        "bb1d": (120.0, 100.0, 80.0),
        "kdj": (50.0, 50.0, 50.0),
        "ema50": 105.0,
        "ema200": 120.0 if not bullish else 95.0,
        "atr": 5.0,
        "ma": (100.0, 100.0, 100.0),
        "tls": (0.45, 0.55, 0.82),
        "funding": 0.01,
        "oi": 9999.0,
        "sw_hi": 120.0,
        "sw_lo": 70.0,
        "prev": (100.0, 80.0, 90.0),
    }


def levels(*, short_rr=2.0):
    return {
        "P": 98.0,
        "R1": 110.0,
        "S1": 85.0,
        "R2": 120.0,
        "S2": 75.0,
        "support": 80.0,
        "resistance": 115.0,
        "sl": 80.0,
        "tp": 95.0,
        "rr": 0.5,
        "sl_s": 105.0,
        "tp_s": 60.0,
        "rr_s": short_rr,
        "rangepos": 30.0,
        "bw": 40.0,
        "volp": 5.5,
        "atr_stop": 5.0,
        "atr_tf": "1D",
    }


class DecisionContractTests(unittest.TestCase):
    def test_bearish_setup_is_sell_with_full_bearish_consensus(self):
        d = market()
        dec = build_report.decide(d, levels(), (25.0, 35.0, 40.0, 35.0))

        self.assertEqual("做空", dec["dir"])
        self.assertTrue(dec["sig"].startswith("🔴 SELL"), dec["sig"])
        self.assertEqual("SELL", dec["cons"])
        self.assertEqual("100%", dec["tf"])

    def test_bullish_setup_is_buy_with_full_bullish_consensus(self):
        d = market(bullish=True)
        k = {**levels(), "rr": 2.0}
        dec = build_report.decide(d, k, (45.0, 65.0, 55.0, 52.0))

        self.assertEqual("做多", dec["dir"])
        self.assertTrue(dec["sig"].startswith("🟢 BUY"), dec["sig"])
        self.assertEqual("BUY", dec["cons"])
        self.assertEqual("100%", dec["tf"])

    def test_overheated_market_can_sell_only_when_short_setup_is_confirmed(self):
        dec = build_report.decide(
            market(), levels(), (75.0, 60.0, 70.0, 68.0)
        )

        self.assertEqual("做空", dec["dir"])
        self.assertTrue(dec["sig"].startswith("🔴 SELL"), dec["sig"])

    def test_overheated_market_can_buy_when_long_setup_is_confirmed(self):
        d = market(bullish=True)
        dec = build_report.decide(
            d, {**levels(), "rr": 2.0}, (75.0, 60.0, 70.0, 68.0)
        )

        self.assertEqual("做多", dec["dir"])
        self.assertTrue(dec["sig"].startswith("🟢 BUY"), dec["sig"])

    def test_overheated_market_without_structure_remains_hold(self):
        d = market(bullish=True)
        d["hist"] = (1.0, 1.0, -1.0, -1.0)
        dec = build_report.decide(
            d, {**levels(), "rr": 2.0}, (75.0, 60.0, 70.0, 68.0)
        )

        self.assertEqual("HOLD", dec["dir"])
        self.assertTrue(dec["sig"].startswith("🟡 NEUTRAL"), dec["sig"])
        self.assertIsNone(dec["ref_dir"])

    def test_split_consensus_is_mixed_at_fifty_percent(self):
        d = market(rsi=(60.0, 60.0, 40.0, 40.0))
        dec = build_report.decide(d, levels(short_rr=0.5), (45.0, 50.0, 50.0, 50.0))

        self.assertEqual("MIXED", dec["cons"])
        self.assertEqual("50%", dec["tf"])

    def test_swing_uses_weekly_trend_and_atr(self):
        d = market(bullish=True)
        d.update(mode="swing", labels=build_report.LABELS["swing"], atr_w=20.0)
        k = build_report.derive(d)
        decision_levels = {**levels(), "rr": 2.0}
        dec = build_report.decide(d, decision_levels, (45.0, 65.0, 55.0, 52.0))

        self.assertEqual("1W", k["atr_tf"])
        self.assertEqual(20.0, k["atr_stop"])
        self.assertEqual("做多", dec["dir"])
        self.assertTrue(dec["sig"].startswith("🟢 BUY"), dec["sig"])

    def test_rejected_short_uses_short_follow_up_language(self):
        dec = build_report.decide(
            market(), levels(short_rr=0.5), (25.0, 35.0, 40.0, 35.0)
        )

        self.assertEqual("HOLD", dec["dir"])
        self.assertEqual("做空", dec["ref_dir"])
        self.assertIn("不追空", dec["entry"])
        self.assertNotIn("不追高", dec["entry"])

    def test_rejected_long_below_ema50_requires_reclaim_not_pullback(self):
        d = market(bullish=True)
        d["ema50"] = 120.0
        dec = build_report.decide(d, levels(), (45.0, 65.0, 55.0, 52.0))

        self.assertEqual("HOLD", dec["dir"])
        self.assertEqual("做多", dec["ref_dir"])
        self.assertIn("收复 EMA50", dec["entry"])
        self.assertNotIn("回踩 MA5 100 / EMA50", dec["entry"])


class ReportRenderingTests(unittest.TestCase):
    def test_short_report_uses_short_side_values_and_reasons(self):
        d = market()
        k = levels()
        sc = (25.0, 35.0, 40.0, 35.0)

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(build_report, "parse", return_value=d), \
                mock.patch.object(build_report, "score", return_value=sc), \
                mock.patch.object(build_report, "derive", return_value=k):
            summary = build_report.report(tmp, tmp, "ETH", "short", "20260715000000", "2026-07-15 00:00:00")
            text = Path(summary["path"]).read_text(encoding="utf-8")

        self.assertEqual("做空", summary["dir"])
        self.assertEqual(2.0, summary["rr"])
        self.assertIn("| **综合信号** | 🔴 SELL", text)
        self.assertIn("| **市场温度评分** | **35.0/100**", text)
        self.assertIn("止损参考 $105.00", text)
        self.assertIn("做空 RR 1:2.00", text)
        self.assertNotIn("做多 RR 1:0.50，支撑", text)
        self.assertNotIn("波段（数天-数周）", text)

    def test_direction_selector_is_mirrored(self):
        k = levels()
        self.assertEqual((80.0, 95.0, 0.5), build_report.directional_levels(k, "做多"))
        self.assertEqual((105.0, 60.0, 2.0), build_report.directional_levels(k, "做空"))

    def test_neutral_report_does_not_invent_long_bias_and_shows_actual_ema_sides(self):
        d = market(bullish=True)
        d.update(hist=(1.0, 1.0, -1.0, -1.0), ema200=120.0)
        k = {**levels(), "rr": 2.0}

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(build_report, "parse", return_value=d), \
                mock.patch.object(build_report, "score", return_value=(75.0, 60.0, 70.0, 68.0)), \
                mock.patch.object(build_report, "derive", return_value=k):
            summary = build_report.report(tmp, tmp, "ETH", "short", "20260715000000", "2026-07-15 00:00:00")
            text = Path(summary["path"]).read_text(encoding="utf-8")

        self.assertEqual("HOLD", summary["dir"])
        self.assertIn("结构未共振", text)
        self.assertNotIn("当前位置追多性价比不足", text)
        self.assertIn("EMA50上方 / EMA200下方", text)


class InputValidationTests(unittest.TestCase):
    def test_symbol_parsing_accepts_normal_symbols(self):
        expected = ["BTC", "1000PEPE"]
        self.assertEqual(expected, build_report.parse_symbols("btc,1000pepe"))
        self.assertEqual(expected, pull_okx_data.parse_symbols("btc,1000pepe"))

    def test_symbol_parsing_rejects_path_and_shell_characters(self):
        for raw in ("BTC,../ETH", r"BTC,..\ETH", "BTC&whoami", "BTC ETH", ""):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    build_report.parse_symbols(raw)
                with self.assertRaises(ValueError):
                    pull_okx_data.parse_symbols(raw)

    def test_symbol_parsing_rejects_duplicates_and_oversized_batches(self):
        too_many = ",".join(f"C{i}" for i in range(21))
        for raw in ("BTC,BTC", too_many):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    build_report.parse_symbols(raw)
                with self.assertRaises(ValueError):
                    pull_okx_data.parse_symbols(raw)

    def test_pull_runtime_arguments_fail_fast(self):
        valid = argparse.Namespace(
            retries=2, min_delay=1.0, max_delay=2.0, timeout=20.0, candle_limit=25
        )
        pull_okx_data.validate_runtime_args(valid)

        for changes in (
            {"retries": -1},
            {"min_delay": 3.0, "max_delay": 2.0},
            {"timeout": 0.0},
            {"candle_limit": 21},
        ):
            values = vars(valid) | changes
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pull_okx_data.validate_runtime_args(argparse.Namespace(**values))

    def test_auto_mode_rejects_mixed_raw_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "BTC.txt").write_text("=== MODE ===\nshort\n", encoding="utf-8")
            Path(tmp, "ETH.txt").write_text("=== MODE ===\nswing\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mixed|混合"):
                build_report.detect_mode(tmp, ["BTC", "ETH"])

    def test_auto_mode_rejects_invalid_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "BTC.txt").write_text("=== MODE ===\nintraday\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MODE.*无效"):
                build_report.detect_mode(tmp, ["BTC"])

    def test_clis_reject_invalid_symbol_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = (
                (
                    build_report,
                    ["build_report.py", "--symbols", "../BTC", "--in-dir", str(root),
                     "--out-dir", str(root / "report-out")],
                    root / "report-out",
                ),
                (
                    pull_okx_data,
                    ["pull_okx_data.py", "--symbols", "../BTC", "--out-dir",
                     str(root / "raw-out")],
                    root / "raw-out",
                ),
            )
            for module, argv, out_dir in cases:
                with self.subTest(module=module.__name__), \
                        mock.patch.object(sys, "argv", argv), \
                        contextlib.redirect_stderr(io.StringIO()), \
                        self.assertRaises(SystemExit):
                    module.main()
                self.assertFalse(out_dir.exists())


class BatchStatusTests(unittest.TestCase):
    def test_partial_render_failure_returns_nonzero(self):
        def fake_report(_in, out, coin, _mode, _ts, _tsh):
            if coin == "ETH":
                raise ValueError("missing raw data")
            report_path = Path(out) / "btc_report.md"
            report_path.write_text("BTC report", encoding="utf-8")
            return {
                "coin": coin,
                "price": 100.0,
                "comp": 50.0,
                "zone": "中性",
                "form": "A",
                "dir": "做空",
                "rr": 1.8,
                "rr_long": 0.6,
                "rr_short": 1.8,
                "rangepos": 50.0,
                "path": str(report_path),
            }

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(build_report, "report", side_effect=fake_report), \
                mock.patch.object(
                    sys,
                    "argv",
                    ["build_report.py", "--symbols", "BTC,ETH", "--in-dir", tmp,
                     "--out-dir", tmp, "--mode", "short"],
                ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, build_report.main())
            self.assertEqual("BTC report", Path(tmp, "btc_report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
