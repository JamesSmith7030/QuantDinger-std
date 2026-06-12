"""实盘冲突锁开关（LIVE_STRATEGY_LOCK_ENFORCE）行为测试。

默认必须开启（与上游 v3.0.30 行为一致）；显式设为 false 时跳过冲突检查，
用于多策略共用 demo/测试网账户做实验的场景。
"""
from __future__ import annotations

import importlib


def _reload_module(monkeypatch, env_value):
    if env_value is None:
        monkeypatch.delenv("LIVE_STRATEGY_LOCK_ENFORCE", raising=False)
    else:
        monkeypatch.setenv("LIVE_STRATEGY_LOCK_ENFORCE", env_value)
    import app.routes.strategy as strategy_routes
    return importlib.reload(strategy_routes)


def test_lock_enforced_by_default(monkeypatch):
    mod = _reload_module(monkeypatch, None)
    assert mod._live_lock_enforced() is True


def test_lock_disabled_by_env_false(monkeypatch):
    mod = _reload_module(monkeypatch, "false")
    assert mod._live_lock_enforced() is False
    # 关闭后，冲突检查应直接放行（不触达数据库）
    dummy = {"id": 32, "execution_mode": "live"}
    assert mod._find_live_strategy_conflict(dummy, user_id=1) is None


def test_lock_disabled_by_env_zero(monkeypatch):
    mod = _reload_module(monkeypatch, "0")
    assert mod._live_lock_enforced() is False


def test_lock_enforced_for_garbage_value(monkeypatch):
    # 非法取值按安全默认处理：仍然开启
    mod = _reload_module(monkeypatch, "banana")
    assert mod._live_lock_enforced() is True
