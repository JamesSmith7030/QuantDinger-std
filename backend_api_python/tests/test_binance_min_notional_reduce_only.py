"""Binance futures local MIN_NOTIONAL pre-check must not block reduce-only closes.

Binance USDT-M futures exempts reduce-only orders from the MIN_NOTIONAL filter
(-4164 "... unless you choose reduce only"). A residual position whose notional
is below minNotional (e.g. 0.002 ETH ~ 3.3 USDT vs minNotional=20) can only be
closed with a reduce-only order, so the client-side pre-check must skip it.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from app.services.live_trading.base import LiveTradingError
from app.services.live_trading.binance import BinanceFuturesClient


FILTERS: Dict[str, Any] = {
    "LOT_SIZE": {"stepSize": "0.001", "minQty": "0.001"},
    "MARKET_LOT_SIZE": {"stepSize": "0.001", "minQty": "0.001"},
    "MIN_NOTIONAL": {"notional": "20"},
    "_meta": {"quantityPrecision": 3, "symbol": "ETHUSDT", "contractType": "PERPETUAL"},
}


@pytest.fixture
def client(monkeypatch):
    c = BinanceFuturesClient(api_key="test-key", secret_key="test-secret")
    monkeypatch.setattr(c, "get_symbol_filters", lambda *, symbol: dict(FILTERS))
    monkeypatch.setattr(c, "get_mark_price", lambda *, symbol: 1672.0)
    # One-way position mode: reduceOnly param is sent as-is.
    monkeypatch.setattr(c, "get_dual_side_position", lambda: False)

    captured: Dict[str, Any] = {}

    def fake_signed_request(method, path, *, params=None, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = dict(params or {})
        return {"orderId": "1", "executedQty": params.get("quantity"), "avgPrice": "1672.0"}

    monkeypatch.setattr(c, "_signed_request", fake_signed_request)
    c._captured = captured
    return c


def test_reduce_only_close_below_min_notional_is_not_blocked(client):
    """close_short with notional 3.34 < 20 must reach the exchange (reduceOnly)."""
    result = client.place_market_order(
        symbol="ETH/USDT",
        side="buy",
        quantity=0.002,
        reduce_only=True,
    )
    assert result.exchange_order_id == "1"
    params = client._captured["params"]
    assert params["symbol"] == "ETHUSDT"
    assert params["side"] == "BUY"
    assert params.get("reduceOnly") == "true"


def test_open_order_below_min_notional_is_still_blocked(client):
    """Opening orders keep the local MIN_NOTIONAL pre-check."""
    with pytest.raises(LiveTradingError, match="MIN_NOTIONAL"):
        client.place_market_order(
            symbol="ETH/USDT",
            side="buy",
            quantity=0.002,
            reduce_only=False,
        )
    assert "params" not in client._captured


def test_open_order_above_min_notional_passes(client):
    """Normal open above minNotional is unaffected."""
    result = client.place_market_order(
        symbol="ETH/USDT",
        side="buy",
        quantity=0.05,  # 0.05 * 1672 = 83.6 USDT > 20
        reduce_only=False,
    )
    assert result.exchange_order_id == "1"
    assert client._captured["params"].get("reduceOnly") is None
