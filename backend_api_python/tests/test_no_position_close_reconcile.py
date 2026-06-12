"""Reduce-only close rejected with "no position in this direction" must be
recognized so the worker can reconcile the ghost local position.

Repro case (2026-06-12, OKX demo trading): local qd_strategy_positions held a
short that no longer existed on OKX; every 30m bar the server trailing stop
submitted close_short, OKX rejected with sCode 51169, and both-mode flips to
open_long stayed blocked for 36+ hours.
"""
from __future__ import annotations

from app.services.pending_order_worker import PendingOrderWorker


def _worker() -> PendingOrderWorker:
    return PendingOrderWorker.__new__(PendingOrderWorker)  # no DB/thread setup needed


OKX_51169 = (
    "OKX error: {'code': '1', 'data': [{'clOrdId': 'qd258724mkt', 'ordId': '', "
    "'sCode': '51169', 'sMsg': \"Order failed because you don't have any positions "
    "in this direction for this contract to reduce or close. \", 'subCode': '', "
    "'tag': '56fa80b0ce8cBCDE', 'ts': '1781230210358'}], 'msg': 'All operations failed'}"
)

BINANCE_2022 = "Binance error code=-2022: ReduceOnly Order is rejected."
BYBIT_110017 = '{"retCode":110017,"retMsg":"current position is zero, cannot fix reduce-only order qty"}'


def test_okx_51169_is_recognized():
    assert _worker()._is_no_position_to_close_error(OKX_51169)


def test_binance_reduce_only_rejected_is_recognized():
    assert _worker()._is_no_position_to_close_error(BINANCE_2022)


def test_bybit_zero_position_is_recognized():
    assert _worker()._is_no_position_to_close_error(BYBIT_110017)


def test_min_notional_error_is_not_treated_as_no_position():
    msg = (
        "Order notional is below MIN_NOTIONAL. symbol=ETHUSDT side=BUY qty=0.002 "
        "markPrice=1672.15 notional=3.3443 minNotional=20"
    )
    assert not _worker()._is_no_position_to_close_error(msg)


def test_okx_busy_error_is_not_treated_as_no_position():
    msg = 'OKX HTTP 500: {"code":"50013","data":[],"msg":"Systems are busy. Please try again later."}'
    assert not _worker()._is_no_position_to_close_error(msg)


def test_empty_error_is_not_matched():
    assert not _worker()._is_no_position_to_close_error("")
    assert not _worker()._is_no_position_to_close_error(None)
