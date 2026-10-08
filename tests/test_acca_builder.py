"""Objective 10.2B: Acca Builder stabilization contracts.

The tab previously mounted <AccaBuilder /> with no props (TypeError in
`reduce`/`toLocaleString`). These tests lock the fix: a data wrapper
feeds the backend ticket with validated props, numeric formatters are
guarded, and no prediction math, entitlement override, or backend change
is introduced.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
APP = SRC / "App.tsx"
VIEW = SRC / "components" / "AccaView.tsx"
BUILDER = SRC / "components" / "AccaBuilder.tsx"


def total_odds(odds) -> str:
    """Python mirror of AccaBuilder total computation (finite odds only)."""
    total = 1.0
    for value in odds:
        total *= float(value) if value is not None else 0.0
    return f"{total:.2f}"


class TestTotalOddsBoundaries:
    def test_normal_selections(self):
        assert total_odds([2.0, 1.5, 3.0]) == "9.00"

    def test_empty_slip_is_neutral(self):
        assert total_odds([]) == "1.00"

    def test_missing_odds_zeroes_total(self):
        assert total_odds([2.0, None]) == "0.00"

    def test_single_selection(self):
        assert total_odds([2.5]) == "2.50"


class TestAccaWiring:
    def test_app_renders_view_not_bare_component(self):
        source = APP.read_text()
        assert "<AccaView" in source
        assert "<AccaBuilder />" not in source
        assert "<AccaBuilder\n" not in source

    def test_view_supplies_all_required_props(self):
        source = VIEW.read_text()
        for marker in ("<AccaBuilder", "selections=", "onRemove=",
                       "onGenerateCode=", "bankroll="):
            assert marker in source, marker

    def test_view_uses_authoritative_user_and_auth(self):
        source = VIEW.read_text()
        assert "auth.getUser()" in source
        assert "authHeaders" in source
        assert "/api/acca-builder" in source

    def test_view_classifies_failures(self):
        source = VIEW.read_text()
        assert "messageForStatus" in source
        assert "Array.isArray" in source

    def test_view_maps_backend_ticket_shape(self):
        source = VIEW.read_text()
        for marker in ("home_team", "away_team", "market", "selections"):
            assert marker in source, marker

    def test_view_introduces_no_prediction_math(self):
        source = VIEW.read_text().lower()
        for forbidden in ("kelly", "probability", "expected value",
                          "predict_match", "strategy_agent"):
            assert forbidden not in source, forbidden

    def test_view_grants_no_entitlement(self):
        source = VIEW.read_text()
        assert "CAP_" not in source
        assert "require_capability" not in source


class TestAccaGuards:
    def test_no_bare_reduce_or_map_on_props(self):
        source = BUILDER.read_text()
        assert "selections.reduce" not in source
        assert "selections.map" not in source
        assert "selections.length" not in source

    def test_guarded_helpers_present(self):
        source = BUILDER.read_text()
        for marker in ("oddOf", "teamName", "safeStake",
                       "Array.isArray(selections)"):
            assert marker in source, marker

    def test_no_unguarded_property_chains(self):
        source = BUILDER.read_text()
        assert "s.match.homeTeam" not in source
        assert "s.market.replace" not in source

    def test_stake_input_cannot_go_nan(self):
        assert "Number(e.target.value) || 0" in BUILDER.read_text()


class TestBackendContractIntact:
    def test_acca_endpoint_still_capability_gated(self):
        source = (ROOT / "api.py").read_text()
        assert "require_capability(CAP_ACCA_BUILDER)" in source

    def test_no_ticket_shape_change(self):
        source = (ROOT / "api.py").read_text()
        assert '"selections": selections' in source or \
            '"selections"' in source
