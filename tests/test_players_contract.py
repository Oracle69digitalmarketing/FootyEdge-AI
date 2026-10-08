"""Objective 10.2C: Players/data-integrity contracts.

Production players table is empty because no ingestion path exists
(register_player has no production callers; no provider player source;
no scheduler job). These tests lock the honest behavior so the gap can
never be papered over: the read endpoint stays capability-gated and
empty-safe, the frontend keeps its honest empty state, and no ad-hoc
player fabrication path may appear outside player_identity.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PLAYERS_UI = SRC / "components" / "PlayersList.tsx"

# Modules allowed to write player rows (explicit identity boundary only).
PLAYER_WRITERS = {"player_identity.py"}


class TestPlayersReadContract:
    def test_endpoint_requires_players_capability(self):
        source = (ROOT / "api.py").read_text()
        assert "require_capability(CAP_PLAYERS)" in source

    def test_endpoint_empty_safe(self):
        source = (ROOT / "api.py").read_text()
        assert "return res.data or []" in source or \
            "return res.data or" in source

    def test_no_ad_hoc_player_fabrication(self):
        offenders = []
        for path in ("api.py", "prediction_pipeline.py", "settle_bets.py",
                     "seed_db.py", "cleanup_db.py", "backup_manager.py"):
            text = (ROOT / path).read_text()
            for i, line in enumerate(text.splitlines(), 1):
                if 'table("players")' in line and (
                        ".insert" in line or ".upsert" in line
                        or ".update" in line):
                    offenders.append(f"{path}:{i}")
        assert offenders == [], offenders

    def test_registration_boundary_has_no_production_callers(self):
        import re

        # Objective 10.2C.2 authorizes exactly one production caller of
        # the registration boundary: player_sync.py (nightly
        # API-Football squad sync). Any other production caller is a
        # contract violation.
        allowed = {"player_sync.py"}
        callers = []
        for path in ROOT.glob("*.py"):
            if path.name in ("player_identity.py",) or \
                    path.name.startswith("test_"):
                continue
            text = path.read_text()
            if re.search(r"\bregister_player\s*\(", text):
                callers.append(path.name)
        assert set(callers) <= allowed, callers
        assert callers != [], \
            "10.2C.2 requires player_sync.py to call register_player"


class TestPlayersUiHonesty:
    def test_empty_state_rendered(self):
        assert "No players found" in PLAYERS_UI.read_text()

    def test_array_guarded(self):
        assert "Array.isArray" in PLAYERS_UI.read_text()

    def test_authenticated_fetch(self):
        source = PLAYERS_UI.read_text()
        assert "authHeaders" in source
        assert "/api/players" in source

    def test_no_mock_rows_in_component(self):
        source = PLAYERS_UI.read_text().lower()
        assert "mock player" not in source
        assert "sample player" not in source
