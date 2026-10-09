"""Server-authoritative plan display + owner preview wiring (static source).

Follows the repo convention (tests/test_frontend_auth_ux.py): the
entitlements endpoint and frontend display are asserted via source
contracts; behavior lives in unit-tested entitlements.py helpers.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api.py"
ACCESS = ROOT / "src" / "lib" / "access.ts"
APP = ROOT / "src" / "App.tsx"
PRODUCT_PAGE = ROOT / "src" / "components" / "product" / "ProductPage.tsx"


def _handler_block(source, route, length=1400):
    start = source.index(route)
    return source[start:start + length]


def test_entitlements_endpoint_uses_server_resolution():
    src = API.read_text()
    assert '"/api/auth/entitlements"' in src
    block = _handler_block(src, '"/api/auth/entitlements"')
    assert "Depends(get_entitlements)" in block
    for key in ('"role"', '"plan"', '"subscription_status"',
                '"has_subscription"', '"capabilities"', '"owner_preview"'):
        assert key in block, key
    for secret in ("provider_customer_id", "provider_subscription_id",
                   "service_role", "apikey", "API_FOOTBALL_KEY"):
        assert secret not in block, secret
    # No client-supplied identity: no user_id/email params or overrides.
    assert "user_id" not in block


def test_owner_preview_rule_is_role_only():
    src = (ROOT / "entitlements.py").read_text()
    assert 'owner_preview = role == "owner"' in src
    assert "IMPLEMENTED_CAPABILITIES" in src
    for forbidden in ("OWNER_EMAIL", "ALLOWLIST", "allowlist",
                      "preview_users", "preview_emails"):
        assert forbidden not in src


def test_access_model_is_server_driven():
    src = ACCESS.read_text()
    assert "EntitlementsResponse" in src
    assert "planSource" in src
    assert "'unavailable'" in src
    assert "ownerPreview" in src
    assert "subscriptionStatusLabel" in src
    assert "'Unavailable'" in src
    assert "No subscription" in src
    assert '"Starter (default)"' not in src
    assert "(default)" not in src


def test_starter_copy_matches_hard_capability_gates():
    src = ACCESS.read_text()
    for advertised in ("Match intelligence", "Team analysis",
                       "Player analysis", "Core prediction analytics"):
        assert advertised in src
    for removed in ("Value-bet access at controlled usage",
                    "Portfolio workflows"):
        # Starter must not advertise hard-gated Growth capabilities.
        starter = src[src.index("id: 'starter'"):src.index("id: 'growth'")]
        assert removed not in starter, removed


def test_app_fetches_entitlements_and_renders_segments():
    src = APP.read_text()
    assert "/api/auth/entitlements" in src
    assert "headers: await authHeaders()" in src
    assert "setEntitlements" in src
    assert "entitlements }" in src or "entitlements}" in src \
        or "entitlements," in src or "entitlements)" in src
    assert "Owner Preview" in src
    assert "subscriptionStatusLabel(access)" in src
    # Prior disclosure contracts retained.
    assert "server-gated" in src
    assert "checked server-side" in src
    assert "planIsPlaceholder" in src
    assert "/api/auth/role" in src


def test_comparison_matrix_does_not_promise_starter_gates():
    src = PRODUCT_PAGE.read_text()
    for row in ("'Value bets', starter:", "'Portfolio', starter:",
                "'Acca Builder', starter:"):
        line = next(ln for ln in src.splitlines() if row in ln)
        assert "'Controlled'" not in line, line
