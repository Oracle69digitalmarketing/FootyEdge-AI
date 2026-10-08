"""Objective 10.1A: JWT-bound bet ownership + safe errors + profile RLS contract.

The FastAPI/pandas stack is unavailable in this sandbox, so `api` is
imported with minimal framework stubs (same precedent as the FastAPI stub
in test_telegram_adapter.py). The ownership decision itself runs for real:
route functions execute against a fake Supabase chain with User-A/User-B
identities. No network, no Supabase, no production data.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent

USER_A = "user-aaaa-0001"
USER_B = "user-bbbb-0002"


def run(coro):
    return asyncio.run(coro)


class _ModelShim:
    """Minimal pydantic v2 stand-in: declared fields only, extras ignored."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

    def __init__(self, **kwargs):
        annotations = {}
        for klass in reversed(type(self).__mro__):
            annotations.update(getattr(klass, "__annotations__", {}))
        for name in annotations:
            setattr(self, name, kwargs.get(name))


def _install_stubs(monkeypatch):
    saved = {}

    def _stub(name, **attrs):
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        if name in sys.modules:
            saved[name] = sys.modules[name]
        monkeypatch.setitem(sys.modules, name, module)
        return module

    class _HTTPException(Exception):
        def __init__(self, status_code=500, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def _decorator(*args, **kwargs):
        def wrap(fn):
            return fn
        return wrap

    class _Router:
        def get(self, *a, **k):
            return _decorator()

        def post(self, *a, **k):
            return _decorator()

        def include_router(self, *a, **k):
            return None

    class _App:
        def __init__(self, *a, **k):
            pass

        def include_router(self, *a, **k):
            return None

        def add_middleware(self, *a, **k):
            return None

        def mount(self, *a, **k):
            return None

        def exception_handler(self, *a, **k):
            return _decorator()

    _stub("fastapi", FastAPI=_App, BackgroundTasks=object, Query=lambda *a, **k: None,
          Depends=lambda dep=None, **k: dep, HTTPException=_HTTPException,
          APIRouter=_Router, Header=lambda default=None, **k: default)
    for sub, attrs in {
        "fastapi.middleware.cors": {"CORSMiddleware": object},
        "fastapi.staticfiles": {"StaticFiles": object},
        "fastapi.responses": {"FileResponse": object, "JSONResponse": object},
    }.items():
        _stub(sub, **attrs)
    _stub("pydantic", BaseModel=_ModelShim,
          Field=lambda default=None, **k: default)
    _stub("supabase", create_client=lambda *a, **k: object(), Client=object)
    _stub("pandas", DataFrame=object)
    _stub("apscheduler", BackgroundScheduler=object)
    _stub("apscheduler.schedulers.background",
          BackgroundScheduler=type("BGS", (), {"__init__": lambda self, *a, **k: None,
                                               "add_job": lambda self, *a, **k: None,
                                               "start": lambda self: None}))
    _stub("apscheduler.triggers.cron", CronTrigger=object)
    for name in ("prediction_pipeline", "backup_manager", "settle_bets"):
        _stub(name, run_pipeline=lambda *a, **k: None,
              run_database_backup=lambda *a, **k: None,
              run_settlement=lambda *a, **k: None)
    _stub("football_api_client",
          FootballAPIClient=type("FAC", (), {"__init__": lambda self, *a, **k: None}))
    if "api" in sys.modules:
        saved["api"] = sys.modules.pop("api")
    return saved, _HTTPException


@pytest.fixture()
def api_module(monkeypatch):
    saved, http_exc = _install_stubs(monkeypatch)
    module = importlib.import_module("api")
    yield module, http_exc
    sys.modules.pop("api", None)
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


class FakeChain:
    """Chainable supabase-table double. Records filters and payloads."""

    def __init__(self, rows=None, fail_on=None):
        self.rows = [dict(r) for r in (rows or [])]
        self.fail_on = fail_on
        self.filters = []
        self.inserts = []

    def table(self, name):
        self.table_name = name
        return self

    def select(self, *a, **k):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, payload):
        if self.fail_on == "insert":
            raise RuntimeError("db unavailable")
        self.inserts.append(dict(payload))
        return self

    def execute(self):
        if self.fail_on == "execute":
            raise RuntimeError("db unavailable")
        rows = self.rows
        for column, value in self.filters:
            rows = [r for r in rows if r.get(column) == value]
        return SimpleNamespace(data=[dict(r) for r in rows])


def _ent(user_id):
    return SimpleNamespace(user_id=user_id, email="t@example.com",
                           role="user", plan="starter", capabilities=frozenset())


class TestBetOwnership:
    def test_get_own_bets_allowed(self, api_module):
        api, _ = api_module
        chain = FakeChain(rows=[{"user_id": USER_A, "id": 1},
                                {"user_id": USER_B, "id": 2}])
        result = run(api.get_user_bets(USER_A, _ent(USER_A), chain))
        assert [r["id"] for r in result] == [1]
        assert ("user_id", USER_A) in chain.filters

    def test_get_other_user_bets_denied_without_read(self, api_module):
        api, http_exc = api_module
        chain = FakeChain(rows=[{"user_id": USER_B, "id": 2}])
        with pytest.raises(http_exc) as exc:
            run(api.get_user_bets(USER_B, _ent(USER_A), chain))
        assert exc.value.status_code == 403
        assert chain.filters == []

    def test_post_ignores_client_supplied_user_id(self, api_module):
        api, _ = api_module
        chain = FakeChain()
        body = api.BetRecordRequest(user_id=USER_B, market="1x2",
                                    selection="Home", odds=2.0, stake=10.0)
        result = run(api.record_bet(body, _ent(USER_A), chain))
        assert result["status"] == "success"
        assert len(chain.inserts) == 1
        assert chain.inserts[0]["user_id"] == USER_A
        assert chain.inserts[0]["user_id"] != USER_B

    def test_recorded_bet_bound_to_authenticated_user(self, api_module):
        api, _ = api_module
        chain = FakeChain()
        body = api.BetRecordRequest(market="1x2", selection="Home",
                                    odds=2.0, stake=10.0)
        result = run(api.record_bet(body, _ent(USER_A), chain))
        assert result["data"]["user_id"] == USER_A

    def test_request_model_has_no_user_id_field(self, api_module):
        api, _ = api_module
        assert "user_id" not in api.BetRecordRequest.__annotations__

    def test_record_failure_returns_safe_error(self, api_module):
        api, _ = api_module
        chain = FakeChain(fail_on="insert")
        body = api.BetRecordRequest(market="1x2", selection="Home",
                                    odds=2.0, stake=10.0)
        result = run(api.record_bet(body, _ent(USER_A), chain))
        assert result == {"status": "error",
                          "message": "Could not record bet. Please try again."}
        assert "unavailable" not in result["message"]
        assert "RuntimeError" not in result["message"]

    def test_capability_gate_preserved(self):
        source = (ROOT / "api.py").read_text()
        assert source.count("require_capability(CAP_PORTFOLIO)") >= 2
        assert "def get_user_bets" in source
        assert "def record_bet" in source

    def test_unauthenticated_still_401(self, monkeypatch):
        import types as _types

        from entitlements import get_current_user

        # Sandbox-only: entitlements imports httpx before its auth check;
        # stub the transport module so the test exercises the real 401 path
        # (production always has httpx installed; no production change).
        monkeypatch.setitem(sys.modules, "httpx",
                            _types.ModuleType("httpx"))
        with pytest.raises(Exception) as exc:
            asyncio.run(get_current_user(None, object()))
        assert getattr(exc.value, "status_code", None) == 401


class TestProfileRoleContract:
    @staticmethod
    def _migration() -> str:
        return (ROOT / "supabase" / "migrations" /
                "20261001000000_subscriptions_and_rls.sql").read_text()

    def test_table_update_revoked_from_app_roles(self):
        source = self._migration()
        assert ("REVOKE UPDATE ON TABLE public.profiles "
                "FROM anon, authenticated;") in source

    def test_self_service_columns_only(self):
        source = self._migration()
        assert ("GRANT UPDATE (full_name, avatar_url) ON TABLE "
                "public.profiles TO authenticated;") in source

    def test_no_client_promotion_path_in_routes(self):
        source = (ROOT / "api.py").read_text()
        assert '.table("profiles").update' not in source
        assert ".table('profiles').update" not in source
