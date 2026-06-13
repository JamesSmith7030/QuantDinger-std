"""Un-closeable "dust" residual positions must stop re-emitting server-side exits.

Repro (2026-06-13, Binance USDT-M): a residual XRP/USDT short of ~0.6 XRP
(notional ~0.68 USDT) sits below the symbol's minNotional (5 USDT). Every bar the
server-side stop-loss / trailing exit submitted close_short, Binance rejected it
with -2022 (ReduceOnly rejected), the worker confirmed the exchange still held the
position (exch_qty>0) and kept the local row "to retry" — spamming an error every
hour forever.

The earlier ghost-position fix (commit b32b23b) only handles exch_qty==0 (exchange
flat → clear local row). This is the third case: the exchange DOES hold a real
position, but it is too small to ever close. The fix suppresses the repeated
server-exit emission and emits one actionable warning, WITHOUT deleting the local
L3 row (deleting it would recreate the opposite ghost-position bug).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List

import pytest

from app.services.trading_executor import TradingExecutor


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
EXCHANGE_CONFIG = {"exchange_id": "binance", "market_type": "swap"}
MIN_NOTIONAL = 5.0


def _executor(min_notional: float = MIN_NOTIONAL) -> TradingExecutor:
    """A bare TradingExecutor with only the state the dust path needs (no DB/thread)."""
    ex = TradingExecutor.__new__(TradingExecutor)
    ex._min_notional_cache = {}
    ex._min_notional_cache_lock = threading.Lock()
    ex._min_notional_cache_ttl_sec = 3600
    ex._dust_exit_suppress = {}
    ex._dust_exit_suppress_lock = threading.Lock()
    ex._dust_warn_interval_sec = 3600
    ex._dust_margin = 0.0
    # Avoid any real exchange/network call; minNotional is injected.
    ex._get_symbol_min_notional = lambda exchange_config, symbol, market_type: float(min_notional)  # type: ignore[assignment]
    return ex


@pytest.fixture
def warns(monkeypatch) -> List[str]:
    """Capture actionable warnings written via append_strategy_log."""
    captured: List[str] = []

    def _fake_log(strategy_id, level, message):
        if level == "warning":
            captured.append(message)

    monkeypatch.setattr("app.services.trading_executor.append_strategy_log", _fake_log)
    return captured


def _trading_config(**overrides: Any) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {"exchange_config": dict(EXCHANGE_CONFIG)}
    cfg.update(overrides)
    return cfg


# --------------------------------------------------------------------------- #
# _residual_exit_is_dust — core logic
# --------------------------------------------------------------------------- #
def test_dust_position_is_suppressed_and_warns_once(warns):
    ex = _executor()
    # 0.6 XRP @ 1.13 = 0.678 USDT << 5 USDT minNotional
    args = (1, "XRP/USDT:USDT", "short", 0.6, 1.13, "swap", _trading_config())

    assert ex._residual_exit_is_dust(*args) is True
    assert len(warns) == 1
    assert "minNotional" in warns[0]

    # Same dust position next bar: still suppressed, but NOT re-warned (throttled).
    assert ex._residual_exit_is_dust(*args) is True
    assert len(warns) == 1


def test_normal_position_is_not_dust(warns):
    ex = _executor()
    # 100 XRP @ 1.13 = 113 USDT >> 5 USDT
    assert (
        ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 100.0, 1.13, "swap", _trading_config())
        is False
    )
    assert warns == []


def test_unknown_min_notional_fails_open(warns):
    """If minNotional can't be resolved (0), never suppress — normal close proceeds."""
    ex = _executor(min_notional=0.0)
    assert (
        ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 0.6, 1.13, "swap", _trading_config())
        is False
    )
    assert warns == []


def test_signal_mode_without_exchange_fails_open(warns):
    """No exchange bound (signal mode) → can't be a live dust loop → never suppress."""
    ex = _executor()
    tc = {"exchange_config": {}}  # unbound
    assert ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 0.6, 1.13, "swap", tc) is False
    assert warns == []


def test_size_change_re_warns(warns):
    ex = _executor()
    cfg = _trading_config()
    assert ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 0.6, 1.13, "swap", cfg) is True
    assert len(warns) == 1
    # Position shrank (partial manual close): treated as a change → warn again.
    assert ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 0.3, 1.13, "swap", cfg) is True
    assert len(warns) == 2


def test_suppression_clears_when_position_grows_back(warns):
    ex = _executor()
    cfg = _trading_config()
    key = (1, "XRP/USDT", "short")
    assert ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 0.6, 1.13, "swap", cfg) is True
    assert key in ex._dust_exit_suppress
    # Grows above minNotional → not dust, state cleared, exits resume.
    assert ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 100.0, 1.13, "swap", cfg) is False
    assert key not in ex._dust_exit_suppress


def test_dust_check_does_not_delete_local_position(monkeypatch, warns):
    """Suppression must be emit-only: the L3 row stays (exchange still holds it)."""
    ex = _executor()
    # Any attempt to touch the DB/clear positions would blow up here (no such attr set).
    assert ex._residual_exit_is_dust(1, "XRP/USDT:USDT", "short", 0.6, 1.13, "swap", _trading_config()) is True


# --------------------------------------------------------------------------- #
# minNotional parsing
# --------------------------------------------------------------------------- #
def test_parse_min_notional_binance_futures_shape():
    fdict = {"MIN_NOTIONAL": {"notional": "5"}}
    assert TradingExecutor._parse_min_notional_from_filters(fdict) == 5.0


def test_parse_min_notional_binance_spot_shape():
    fdict = {"NOTIONAL": {"minNotional": "10", "applyMinToMarket": True}}
    assert TradingExecutor._parse_min_notional_from_filters(fdict) == 10.0


def test_parse_min_notional_absent_returns_zero():
    assert TradingExecutor._parse_min_notional_from_filters({"LOT_SIZE": {"stepSize": "0.1"}}) == 0.0
    assert TradingExecutor._parse_min_notional_from_filters(None) == 0.0


# --------------------------------------------------------------------------- #
# Integration: server-side stop-loss emit path
# --------------------------------------------------------------------------- #
def _wire_stop_loss(ex: TradingExecutor, positions: List[Dict[str, Any]], sl_ratio: float = 0.01):
    ex._indicator_owns_exits = lambda tc: False  # type: ignore[assignment]
    ex._is_server_side_exit_enabled = lambda tc, key: True  # type: ignore[assignment]
    ex._risk_params_from_trading_config = lambda tc: {"stop_loss_ratio": sl_ratio}  # type: ignore[assignment]
    ex._get_current_positions = lambda sid, sym: positions  # type: ignore[assignment]


def test_stop_loss_suppressed_for_dust_position(warns):
    ex = _executor()
    pos = {"symbol": "XRP/USDT:USDT", "side": "short", "size": 0.6, "entry_price": 0.5}
    _wire_stop_loss(ex, [pos])
    # current 0.52 >= 0.5*(1+0.01)=0.505 → SL triggers; but notional 0.6*0.52=0.31 < 5 → dust.
    sig = ex._server_side_stop_loss_signal(
        strategy_id=1, symbol="XRP/USDT:USDT", current_price=0.52,
        market_type="swap", leverage=1.0, trading_config=_trading_config(),
        timeframe_seconds=60,
    )
    assert sig is None
    assert len(warns) == 1


def test_stop_loss_fires_for_normal_position(warns):
    ex = _executor()
    pos = {"symbol": "XRP/USDT:USDT", "side": "short", "size": 100.0, "entry_price": 0.5}
    _wire_stop_loss(ex, [pos])
    sig = ex._server_side_stop_loss_signal(
        strategy_id=1, symbol="XRP/USDT:USDT", current_price=0.52,
        market_type="swap", leverage=1.0, trading_config=_trading_config(),
        timeframe_seconds=60,
    )
    assert sig is not None
    assert sig["type"] == "close_short"
    assert warns == []


# --------------------------------------------------------------------------- #
# Integration: server-side trailing-stop emit path
# --------------------------------------------------------------------------- #
def _wire_trailing(ex: TradingExecutor, positions: List[Dict[str, Any]], monkeypatch):
    ex._indicator_owns_exits = lambda tc: False  # type: ignore[assignment]
    ex._is_server_side_exit_enabled = lambda tc, key: True  # type: ignore[assignment]
    ex._risk_params_from_trading_config = lambda tc: {  # type: ignore[assignment]
        "take_profit_ratio": 0.0,
        "trailing_enabled": True,
        "trailing_stop_ratio": 0.01,
        "trailing_activation_ratio": 0.0,
    }
    ex._get_current_positions = lambda sid, sym: positions  # type: ignore[assignment]
    ex._effective_taker_fee_rate = lambda sid, tc: 0.0005  # type: ignore[assignment]
    ex._update_position = lambda **kwargs: None  # type: ignore[assignment]
    # Force the "profit locked" gate so the trailing exit actually fires.
    monkeypatch.setattr("app.services.trading_executor.trailing_exit_locks_net_profit", lambda *a, **k: True)


def test_trailing_stop_suppressed_for_dust_position(monkeypatch, warns):
    ex = _executor()
    # Short: lowest 0.40, entry 0.50; trailing stop line = 0.40*1.01 = 0.404.
    pos = {"symbol": "XRP/USDT:USDT", "side": "short", "size": 0.6,
           "entry_price": 0.50, "lowest_price": 0.40}
    _wire_trailing(ex, [pos], monkeypatch)
    sig = ex._server_side_take_profit_or_trailing_signal(
        strategy_id=1, symbol="XRP/USDT:USDT", current_price=0.405,
        market_type="swap", leverage=1.0, trading_config=_trading_config(),
        timeframe_seconds=60,
    )
    assert sig is None
    assert len(warns) == 1


def test_trailing_stop_fires_for_normal_position(monkeypatch, warns):
    ex = _executor()
    pos = {"symbol": "XRP/USDT:USDT", "side": "short", "size": 100.0,
           "entry_price": 0.50, "lowest_price": 0.40}
    _wire_trailing(ex, [pos], monkeypatch)
    sig = ex._server_side_take_profit_or_trailing_signal(
        strategy_id=1, symbol="XRP/USDT:USDT", current_price=0.405,
        market_type="swap", leverage=1.0, trading_config=_trading_config(),
        timeframe_seconds=60,
    )
    assert sig is not None
    assert sig["type"] == "close_short"
    assert warns == []
