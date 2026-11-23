"""Phase 15J admin API integration: import, route registration and auth.

FastAPI is not installed in this environment, so these tests install a
minimal stub that records decorator registrations. The real modules
(admin_billing, account_activity, entitlements) are stdlib-only at import
time and are used unmodified.
"""

from __future__ import annotations

import ast
import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXPECTED_ROUTES = {
    ("GET", "/api/admin/billing/overview"),
    ("GET", "/api/admin/billing/users"),
    ("GET", "/api/admin/activity"),
    ("GET", "/api/admin/actions"),
    ("POST", "/api/admin/billing/usage/probe"),
    ("GET", "/api/admin/billing/usage/probe"),
    ("GET", "/api/admin/billing/usage"),
    ("GET", "/api/admin/billing/subscriptions"),
    ("GET", "/api/admin/billing/events"),
}


def _install_fastapi_stub(monkeypatch):
    class RecordingRouter:
        def __init__(self):
            self.routes = []

        def _register(self, method, path, **kwargs):
            def decorator(fn):
                self.routes.append((method, path, fn, kwargs))
                return fn
            return decorator

        def get(self, path, **kwargs):
            return self._register("GET", path, **kwargs)

        def post(self, path, **kwargs):
            return self._register("POST", path, **kwargs)

        def include_router(self, other, **kwargs):
            self.routes.extend(getattr(other, "routes", []))

    class StubHTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)

    def stub_depends(dep):
        return dep

    def stub_query(default=None, **kwargs):
        return default

    stub = types.ModuleType("fastapi")
    stub.APIRouter = RecordingRouter
    stub.Depends = stub_depends
    stub.HTTPException = StubHTTPException
    stub.Query = stub_query
    monkeypatch.setitem(sys.modules, "fastapi", stub)
    return stub


def _import_admin_api(monkeypatch):
    _install_fastapi_stub(monkeypatch)
    sys.modules.pop("admin_api", None)
    return importlib.import_module("admin_api")


class TestAdminApiImport:
    def test_admin_api_module_parses(self):
        source = (ROOT / "admin_api.py").read_text()
        ast.parse(source)

    def test_imported_symbols_exist(self):
        import account_activity
        import admin_billing

        modules = {
            "admin_billing": admin_billing,
            "account_activity": account_activity,
        }
        tree = ast.parse((ROOT / "admin_api.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in modules:
                for alias in node.names:
                    assert hasattr(modules[node.module], alias.name), (
                        f"{node.module}.{alias.name} missing"
                    )

    def test_admin_api_imports_with_stubbed_fastapi(self, monkeypatch):
        module = _import_admin_api(monkeypatch)
        assert hasattr(module, "router")


class TestAdminRouterRegistration:
    def test_all_nine_routes_registered(self, monkeypatch):
        module = _import_admin_api(monkeypatch)
        registered = {(method, path) for method, path, _, _ in module.router.routes}
        assert registered == EXPECTED_ROUTES
        assert len(module.router.routes) == 9

    def test_api_can_include_admin_router(self, monkeypatch):
        stub = _install_fastapi_stub(monkeypatch)
        admin = importlib.import_module("admin_api")
        app_router = stub.APIRouter()
        app_router.include_router(admin.router)
        registered = {(method, path) for method, path, _, _ in app_router.routes}
        assert registered == EXPECTED_ROUTES


class TestAdminAuthorization:
    def test_every_route_requires_admin_guard(self, monkeypatch):
        module = _import_admin_api(monkeypatch)
        assert module.ADMIN_GUARD is not None
        for method, path, fn, _ in module.router.routes:
            defaults = list(fn.__defaults__ or ()) + list(fn.__kwdefaults__ or {}.values())
            assert module.ADMIN_GUARD in defaults, f"{method} {path} missing ADMIN_GUARD"

    def test_guard_uses_owner_admin_roles(self):
        source = (ROOT / "admin_api.py").read_text()
        assert 'require_role("owner", "admin")' in source

    def test_no_unguarded_probe_endpoint(self):
        source = ast.parse((ROOT / "admin_api.py").read_text())
        for node in ast.walk(source):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "admin_probe_endpoint":
                    pytest.fail("redundant undecorated probe endpoint must stay removed")


class TestAdminFailureNotSilent:
    def test_admin_router_import_failure_re_raised(self):
        source = (ROOT / "api.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                block = "".join(
                    ast.unparse(stmt) for stmt in handler.body
                )
                if "admin router failed to mount" in block:
                    assert "raise" in block
                    assert "logger.error" in block
                    return
        pytest.fail("admin router failure handler not found")
