from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("generate_crypto_reports.py")
SPEC = importlib.util.spec_from_file_location("generate_crypto_reports", MODULE_PATH)
assert SPEC and SPEC.loader
REPORTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORTS)

PULL_PATH = Path(__file__).with_name("pull_okx_data.py")
PULL_SPEC = importlib.util.spec_from_file_location("pull_okx_data", PULL_PATH)
assert PULL_SPEC and PULL_SPEC.loader
PULL = importlib.util.module_from_spec(PULL_SPEC)
sys.modules[PULL_SPEC.name] = PULL
PULL_SPEC.loader.exec_module(PULL)


def directional_snapshot(*, bullish: bool) -> dict[str, object]:
    hist = 1.0 if bullish else -1.0
    rsi = 60.0 if bullish else 40.0
    return {
        "rsi": {period: rsi for period in REPORTS.PERIODS},
        "macd": {period: {"hist": hist} for period in REPORTS.PERIODS},
    }


class ScoringTests(unittest.TestCase):
    def test_weighted_score_is_reproducible(self) -> None:
        self.assertEqual(REPORTS.weighted_score(25, 69, 40), 47.1)

    def test_bullish_momentum_can_remain_neutral(self) -> None:
        decision = REPORTS.decide_signal(
            state_score=47.1,
            momentum_score=69,
            derivatives_score=40,
            consensus_score=4,
            price=64_922.6,
            ema50=64_938.2,
            rsi_4h=59.61,
            rsi_1d=56.15,
            kdj_j=81.69,
        )
        self.assertEqual(decision["signal"], "NEUTRAL")
        self.assertEqual(decision["label"], "动能偏多")
        self.assertEqual(decision["execution"], "HOLD")

    def test_overheat_reduction_never_means_short(self) -> None:
        decision = REPORTS.decide_signal(
            state_score=64.0,
            momentum_score=72,
            derivatives_score=55,
            consensus_score=4,
            price=1_930.0,
            ema50=1_800.0,
            rsi_4h=72.0,
            rsi_1d=68.0,
            kdj_j=91.0,
        )
        self.assertEqual(decision["signal"], "REDUCE")
        self.assertEqual(decision["label"], "过热减仓（不做空）")
        self.assertEqual(decision["execution"], "REDUCE")

    def test_long_and_short_require_full_direction_gate(self) -> None:
        long_decision = REPORTS.decide_signal(
            state_score=55.0,
            momentum_score=65,
            derivatives_score=55,
            consensus_score=6,
            price=110.0,
            ema50=100.0,
            rsi_4h=60.0,
            rsi_1d=60.0,
            kdj_j=70.0,
        )
        short_decision = REPORTS.decide_signal(
            state_score=45.0,
            momentum_score=35,
            derivatives_score=40,
            consensus_score=-6,
            price=90.0,
            ema50=100.0,
            rsi_4h=40.0,
            rsi_1d=40.0,
            kdj_j=30.0,
        )
        self.assertEqual((long_decision["signal"], long_decision["execution"]), ("BUY", "LONG"))
        self.assertEqual((short_decision["signal"], short_decision["execution"]), ("SELL", "SHORT"))

    def test_consensus_uses_all_eight_rsi_macd_votes(self) -> None:
        self.assertEqual(REPORTS.calculate_consensus(directional_snapshot(bullish=True)), (8, 100))
        self.assertEqual(REPORTS.calculate_consensus(directional_snapshot(bullish=False)), (-8, 100))

    def test_consistency_requires_net_consensus_not_just_a_bare_majority(self) -> None:
        self.assertEqual(REPORTS.consistency_level(75, 6), "高")
        self.assertEqual(REPORTS.consistency_level(75, 5), "中")
        self.assertEqual(REPORTS.consistency_level(50, 1), "低")

    def test_derivatives_score_ignores_single_point_oi(self) -> None:
        first = {"funding_rate": -0.00001, "top_ls_ratio": 1.1, "oi_contracts": 1.0}
        second = {**first, "oi_contracts": 999_999_999.0}
        self.assertEqual(REPORTS.calculate_derivatives_score(first), REPORTS.calculate_derivatives_score(second))

    def test_zero_macd_is_neutral_in_momentum_score(self) -> None:
        snapshot = {
            "rsi": {period: 50.0 for period in REPORTS.PERIODS},
            "macd": {period: {"hist": 0.0} for period in REPORTS.PERIODS},
            "price": 100.0,
            "ma20": 100.0,
            "ema50": 100.0,
            "kdj": {"j": 50.0},
        }
        self.assertEqual(REPORTS.calculate_momentum_score(snapshot), 45)
        self.assertEqual(REPORTS.momentum_label(0.0), "中性动能")

    def test_negative_kdj_values_are_accepted(self) -> None:
        self.assertEqual(REPORTS.number("k  -2.75\n", "k"), -2.75)

    def test_pull_symbol_validation_deduplicates_and_rejects_shell_tokens(self) -> None:
        self.assertEqual(PULL.parse_symbols("btc, ETH,btc"), ["BTC", "ETH"])
        with self.assertRaises(ValueError):
            PULL.parse_symbols("BTC&whoami")

    def test_pull_contract_requires_ticker_open_and_time(self) -> None:
        ticker = next(section for section in PULL.build_sections("ETH") if section.name == "TICKER")
        incomplete = "last  100\n24h high  110\n24h low  90\n24h vol  123\n24h change %  1.0%\n"
        complete = incomplete + "24h open  99\ntime  2026/07/20 10:45:00\n"
        self.assertFalse(PULL.validate(incomplete, ticker.patterns)[0])
        self.assertTrue(PULL.validate(complete, ticker.patterns)[0])

    def test_pull_contract_requires_complete_oi_row(self) -> None:
        oi = next(section for section in PULL.build_sections("ETH") if section.name == "OI")
        self.assertFalse(PULL.validate("ETH-USDT-SWAP  123\n", oi.patterns)[0])
        complete = "ETH-USDT-SWAP  123  456.7  2026/07/20 10:45:00\n"
        self.assertTrue(PULL.validate(complete, oi.patterns)[0])

    def test_invalid_structural_levels_disclose_atr_fallback(self) -> None:
        support, resistance, method = REPORTS.choose_levels(
            price=100.0,
            atr=5.0,
            s1=120.0,
            swing_low=110.0,
            bb_lower=105.0,
            r1=90.0,
            swing_high=95.0,
            bb_upper=98.0,
        )
        self.assertEqual((support, resistance), (90.0, 115.0))
        self.assertIn("ATR保护带", method)

    def test_fixed_timestamp_is_a_valid_deterministic_clock(self) -> None:
        fixed = "20260720153045"
        generated_at, stamp = REPORTS.resolve_generation_clock(fixed)
        self.assertEqual(generated_at.strftime("%Y-%m-%d %H:%M:%S"), "2026-07-20 15:30:45")
        self.assertEqual(stamp, fixed)

    def test_output_collision_is_checked_before_any_report_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            output_dir = Path(raw_dir)
            existing = output_dir / "eth_report_20260720153045.md"
            existing.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                REPORTS.prepare_output_paths(output_dir, ["BTC", "ETH"], "20260720153045")
            self.assertFalse((output_dir / "btc_report_20260720153045.md").exists())

    def test_generator_rejects_duplicate_symbols_before_reading_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            with self.assertRaises(ValueError):
                REPORTS.generate(Path(raw_dir), Path(raw_dir) / "out", ["BTC", "BTC"], "20260720153045")

    def test_report_validation_rejects_missing_disclaimer(self) -> None:
        with self.assertRaises(ValueError):
            REPORTS.validate_report("# BTC\n\n## 综合结论\nHOLD")


if __name__ == "__main__":
    unittest.main()
