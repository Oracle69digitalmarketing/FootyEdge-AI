"""Objective 10.1B: authoritative owner/admin access.

Proves the backend role guard reads profiles.role (never email), the
401/403/200 matrix holds, the frontend no longer treats an email
allowlist as authority, and AdminMetrics is correctly wired. No network,
no Supabase, no production data. Follows the stub precedent of
test_bet_ownership.py.
"""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run(coro):
    return asyncio.run(coro)


class FakeChain:
    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        self._rows = list(self._tables.get(name, []))
        return self

    def select(self, *a, **k):
        return self

    def eq(self, column, value):
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def limit(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        return SimpleNamespace(data=[dict(r) for r in self._rows])


class FakeAuth:
    """Stub for the Supabase Auth user endpoint (httpx)."""

    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.body = body if body is not None else {"id": "user-1",
                                                   "email": "u@example.com"}

    def get(self, url, headers=None, timeout=None):
        response = SimpleNamespace(status_code=self.status_code)
        response.json = lambda: dict(self.body)
        return response


@pytest.fixture()
def role_env(monkeypatch):
    """Fake Supabase client factory + Auth transport for entitlements."""
    import entitlements as ent

    state = {"profiles": [], "httpx": FakeAuth()}

    def factory():
        return FakeChain({"profiles": state["profiles"],
                          "subscriptions": []})

    monkeypatch.setattr(ent, "_get_supabase_client", lambda: factory)
    fake_httpx = types.ModuleType("httpx")
    fake_httpx.get = lambda url, headers=None, timeout=None: state[
        "httpx"].get(url, headers=headers, timeout=timeout)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return state


def _check():
    from entitlements import require_role

    return require_role("owner", "admin")


class TestRequireRoleMatrix:
    def test_owner_allowed(self, role_env):
        role_env["profiles"] = [{"id": "user-1", "role": "owner"}]
        result = run(_check()(authorization="Bearer jwt"))
        assert result.role == "owner"

    def test_admin_allowed_where_intended(self, role_env):
        role_env["profiles"] = [{"id": "user-1", "role": "admin"}]
        result = run(_check()(authorization="Bearer jwt"))
        assert result.role == "admin"

    def test_ordinary_user_denied_403(self, role_env):
        role_env["profiles"] = [{"id": "user-1", "role": "user"}]
        with pytest.raises(Exception) as exc:
            run(_check()(authorization="Bearer jwt"))
        assert getattr(exc.value, "status_code", None) == 403

    def test_missing_profile_denied_403(self, role_env):
        role_env["profiles"] = []
        with pytest.raises(Exception) as exc:
            run(_check()(authorization="Bearer jwt"))
        assert getattr(exc.value, "status_code", None) == 403

    def test_unauthenticated_denied_401(self, role_env):
        with pytest.raises(Exception) as exc:
            run(_check()(authorization=None))
        assert getattr(exc.value, "status_code", None) == 401

    def test_invalid_jwt_denied_401(self, role_env, monkeypatch):
        role_env["httpx"] = FakeAuth(status_code=401, body={})
        with pytest.raises(Exception) as exc:
            run(_check()(authorization="Bearer bogus"))
        assert getattr(exc.value, "status_code", None) == 401


class TestRoleSourceIsProfiles:
    def test_no_email_allowlist_in_backend(self):
        source = (ROOT / "entitlements.py").read_text()
        assert "OWNER_BOOTSTRAP" not in source
        assert "admin@footyedge.ai" not in source

    def test_guard_resolves_role_from_profiles(self):
        source = (ROOT / "entitlements.py").read_text()
        assert "resolve_role_from_profile" in source
        assert 'select("role")' in source

    def test_role_lookup_fail_closed(self, role_env):
        from entitlements import resolve_role_from_profile

        assert resolve_role_from_profile(FakeChain({"profiles": []}),
                                         "ghost") == "user"


class TestAuthRoleEndpoint:
    def test_route_registered_with_entitlement_dependency(self):
        source = (ROOT / "api.py").read_text()
        assert '"/api/auth/role"' in source
        assert "get_entitlements" in source

    def test_returns_only_role(self):
        source = (ROOT / "api.py").read_text()
        start = source.index('"/api/auth/role"')
        block = source[start:start + 900]
        # The handler returns exactly the role; the docstring documents
        # what is deliberately excluded, so match the return statement.
        assert 'return {"role": _ent.role}' in block
        assert "user_id" not in block
        assert "capabilities" not in block


class TestFrontendRoleModel:
    def test_no_email_allowlist_in_frontend(self):
        for path in (ROOT / "src").rglob("*.ts*"):
            if "node_modules" in str(path):
                continue
            assert "OWNER_BOOTSTRAP_EMAILS" not in path.read_text(), path

    def test_resolve_access_is_email_blind(self):
        source = (ROOT / "src" / "lib" / "access.ts").read_text()
        assert ".includes(email" not in source
        assert "roleSource" in source

    def test_app_uses_server_role(self):
        source = (ROOT / "src" / "App.tsx").read_text()
        assert "/api/auth/role" in source
        assert "persistentRole" in source
        assert "serverRole" in source

    def test_admin_metrics_sends_jwt(self):
        source = (ROOT / "src" / "pages" / "AdminMetrics.tsx").read_text()
        assert "authHeaders" in source
        assert "/api/admin/metrics" in source

    def test_dead_backup_control_removed(self):
        source = (ROOT / "src" / "pages" / "AdminMetrics.tsx").read_text()
        assert "backup-now" not in source
        assert "handleBackupNow" not in source
