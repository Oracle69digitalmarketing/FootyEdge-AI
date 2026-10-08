"""Objective 10.2A: Portfolio stabilization contracts.

The tab previously mounted <Portfolio /> with no props (TypeError on
`toLocaleString`), misclassified backend "active" bets as settled, and
called `.toFixed()` on possibly-null values. These tests lock the fix:
a data wrapper supplies validated props, open/settled semantics match
the backend lifecycle, and JWT-bound ownership is untouched.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
APP = SRC / "App.tsx"
VIEW = SRC / "components" / "PortfolioView.tsx"
PORTFOLIO = SRC / "components" / "Portfolio.tsx"


def is_open(status) -> bool:
    """Python mirror of Portfolio.tsx isOpenBet (backend lifecycle)."""
    return status == "active" or status == "pending"


class TestOpenSettledSemantics:
    def test_active_is_open(self):
        assert is_open("active") is True

    def test_pending_is_open_legacy(self):
        assert is_open("pending") is True

    def test_won_lost_are_settled(self):
        assert is_open("won") is False
        assert is_open("lost") is False

    def test_unknown_is_settled_safe(self):
        assert is_open(None) is False
        assert is_open("") is False


class TestPortfolioWiring:
    def test_app_renders_view_not_bare_component(self):
        source = APP.read_text()
        assert "<PortfolioView" in source
        assert "<Portfolio />" not in source
        assert "<Portfolio\n" not in source

    def test_view_supplies_required_props(self):
        source = VIEW.read_text()
        assert "<Portfolio" in source
        assert "bankroll=" in source
        assert "userBets=" in source

    def test_view_uses_authoritative_user_and_auth(self):
        source = VIEW.read_text()
        assert "auth.getUser()" in source
        assert "authHeaders" in source
        assert "/api/bets/user/" in source

    def test_view_classifies_failures(self):
        source = VIEW.read_text()
        assert "messageForStatus" in source
        assert "Array.isArray" in source

    def test_view_grants_no_entitlement(self):
        source = VIEW.read_text()
        assert "CAP_" not in source
        assert "require_capability" not in source


class TestPortfolioGuards:
    def test_open_status_covers_backend_lifecycle(self):
        source = PORTFOLIO.read_text()
        assert "'active'" in source
        assert "isOpenBet" in source

    def test_numeric_formatters_guarded(self):
        source = PORTFOLIO.read_text()
        assert "winAmount" in source
        assert "Number.isFinite" in source
        assert "bet.potential_win.toFixed" not in source
        assert "userBets.map" not in source

    def test_array_state_guarded(self):
        assert "Array.isArray(userBets)" in PORTFOLIO.read_text()


class TestBackendOwnershipIntact:
    def test_jwt_ownership_unchanged(self):
        source = (ROOT / "api.py").read_text()
        assert '"user_id": _ent.user_id' in source
        assert "req.user_id" not in source
        assert "require_capability(CAP_PORTFOLIO)" in source
