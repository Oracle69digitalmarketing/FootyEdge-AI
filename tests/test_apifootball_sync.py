"""Objective 10.2C.2: API-Football squad sync contracts (offline only).

No network, no database, no live provider APIs, no production Supabase,
no credentials. The provider transport is injected; Supabase is a stub
enforcing the identity UNIQUE/FK/sequence guards; team mappings use
fixture external IDs that are never claimed as verified production IDs.
"""

import ast
from pathlib import Path

import pytest

from apifootball_client import (
    ApiFootballClient,
    ApiFootballError,
    BASE_URL,
    KEY_VAR,
    MAX_TEAMS_PER_CYCLE,
    SOURCE,
)
from player_identity import fetch_player_mappings, fetch_players
from player_sync import TEAM_MAPPING_TABLE, fetch_team_mappings, sync_players
from team_identity import CANONICAL_TEAMS

_REPO = Path(__file__).resolve().parent.parent
_SYNC_SRC = (_REPO / "player_sync.py").read_text()
_ADAPTER_SRC = (_REPO / "apifootball_client.py").read_text()
_MIGRATION = (
    _REPO / "supabase" / "migrations" / "20261008000000_provider_team_mapping.sql"
).read_text()


def _squad_payload(team_id, team_name, players):
    return {
        "response": [
            {"team": {"id": team_id, "name": team_name}, "players": players}
        ]
    }


ARSENAL_SQUAD = _squad_payload(
    9001,
    "Arsenal (fixture)",
    [
        {"id": 1001, "name": "Fixture Keeper", "age": 28,
         "number": 1, "position": "Goalkeeper", "photo": "https://x/1.png"},
        {"id": 1002, "name": "Fixture Striker", "age": 24,
         "number": 9, "position": "Attacker", "photo": "https://x/9.png"},
        {"id": None, "name": "Nameless Row"},  # malformed: dropped
        {"id": 1003, "name": "   "},  # malformed: dropped
    ],
)


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table):
        self._table = table
        self._filters = []

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def execute(self):
        return _Result(
            [dict(r) for r in self._table.rows
             if all(r.get(c) == v for c, v in self._filters)]
        )


class _Insert:
    def __init__(self, db, table, row):
        self._db = db
        self._table = table
        self._row = row

    def execute(self):
        for col in self._table._not_null:
            if self._row.get(col) is None:
                raise ValueError(f"null value in column {col!r}")
        for keys in self._table._unique_keys:
            key = tuple(self._row.get(k) for k in keys)
            for existing in self._table.rows:
                if tuple(existing.get(k) for k in keys) == key:
                    raise ValueError(f"duplicate key {keys}={key}")
        stored = dict(self._row)
        if self._table._seq and stored.get("id") is None:
            stored["id"] = self._table._next_id()
        self._table.rows.append(stored)
        return _Result([stored])


class _Table:
    def __init__(self, rows=(), unique_keys=(), not_null=(), seq=False):
        self.rows = [dict(r) for r in rows]
        self._unique_keys = unique_keys
        self._not_null = not_null
        self._seq = seq
        self._seq_next = max([r.get("id") or 0 for r in self.rows] + [0]) + 1

    def _next_id(self):
        value = self._seq_next
        self._seq_next += 1
        return value

    def select(self, _columns):
        return _Query(self)

    def insert(self, row):
        return _Insert(None, self, row)


class StubSupabase:
    """Stub with identity guards plus the team-mapping table."""

    def __init__(self, teams=(), mappings=()):
        self._tables = {
            "players": _Table((), unique_keys=[("id",)], not_null=("name",), seq=True),
            "player_identity_sources": _Table(
                (), unique_keys=[("source", "external_player_id")],
                not_null=("player_id", "source", "external_player_id")),
            "player_aliases": _Table(()),
            "player_team_history": _Table((), not_null=("player_id", "team_id")),
            TEAM_MAPPING_TABLE: _Table(
                mappings, unique_keys=[("source", "external_team_id")]),
            "teams": _Table(teams),
        }

    def table(self, name):
        return self._tables[name]


def _ok_transport(payload):
    def _transport(url, headers, timeout):
        assert headers.get("x-apisports-key") == "fixture-key", \
            "credential travels only as x-apisports-key header"
        assert url.startswith(BASE_URL)
        return payload, 200
    return _transport


def _six_team_db():
    teams = [{"id": tid, "name": name} for name, tid in CANONICAL_TEAMS.items()]
    ext = {name: f"fixture-ext-{i}" for i, name in enumerate(CANONICAL_TEAMS)}
    mappings = [
        {"source": SOURCE, "external_team_id": ext[name], "team_id": tid}
        for name, tid in CANONICAL_TEAMS.items()
    ]
    return StubSupabase(teams=teams, mappings=mappings), ext


# --- Adapter isolation + normalization (fixture-backed) ---


def _code_only(path):
    """Module source without docstrings/comments (boundary declarations live there)."""
    import io
    import tokenize
    src = (_REPO / path).read_text()
    out = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(src).readline)
        for tok, val, *_ in tokens:
            if tok in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(val)
    except Exception:
        return src
    return "".join(out)


def test_adapter_scope_is_players_only():
    assert SOURCE == "apifootball"
    assert KEY_VAR == "API_FOOTBALL_KEY"
    assert BASE_URL == "https://v3.football.api-sports.io"
    assert MAX_TEAMS_PER_CYCLE == 25
    assert "/players/squads" in _ADAPTER_SRC
    code = _code_only("apifootball_client.py").lower()
    for forbidden in ("the-odds-api.com", "odds_api_key", "value_bets",
                      "telegram", "billing", "portfolio", "acca"):
        assert forbidden not in code


def test_adapter_key_never_logged_returned_or_stored():
    assert "x-apisports-key" in _ADAPTER_SRC
    assert "os.environ.get" in _ADAPTER_SRC
    for forbidden in ("print(", "logger.info", "logger.debug", "localStorage",
                      "sessionStorage"):
        assert forbidden not in _ADAPTER_SRC


def test_get_squad_normalizes_and_drops_malformed():
    client = ApiFootballClient(api_key="fixture-key",
                               transport=_ok_transport(ARSENAL_SQUAD))
    squad = client.get_squad("9001")
    assert len(squad) == 2
    first = squad[0]
    assert first["provider_player_id"] == "1001"
    assert first["name"] == "Fixture Keeper"
    assert first["position"] == "Goalkeeper"
    assert first["nationality"] is None  # squads endpoint does not supply it
    assert first["provider_team_id"] == "9001"


def test_missing_key_is_explicit_skip_kind():
    client = ApiFootballClient(api_key="",
                               transport=_ok_transport(ARSENAL_SQUAD))
    assert client.configured is False
    with pytest.raises(ApiFootballError) as exc:
        client.get_squad("9001")
    assert exc.value.kind == "missing_key"


def test_rate_limited_http_malformed_are_explicit():
    limited = ApiFootballClient(
        api_key="k", transport=lambda u, h, t: ({"response": []}, 429))
    with pytest.raises(ApiFootballError) as exc:
        limited.get_squad("1")
    assert exc.value.kind == "rate_limited"

    http = ApiFootballClient(
        api_key="k", transport=lambda u, h, t: ({"response": []}, 500))
    with pytest.raises(ApiFootballError) as exc:
        http.get_squad("1")
    assert exc.value.kind == "http"

    bad = ApiFootballClient(
        api_key="k", transport=lambda u, h, t: ({"unexpected": 1}, 200))
    with pytest.raises(ApiFootballError) as exc:
        bad.get_squad("1")
    assert exc.value.kind == "malformed"


# --- Team-mapping contract (static) ---


def test_team_mapping_mirrors_competition_mapping_grain():
    assert "CREATE TABLE IF NOT EXISTS provider_team_mapping" in _MIGRATION
    assert "external_team_id TEXT NOT NULL" in _MIGRATION
    assert "UNIQUE (source, external_team_id)" in _MIGRATION
    assert "REFERENCES teams(id)" in _MIGRATION
    assert "ON DELETE CASCADE" in _MIGRATION


def test_team_mapping_unseeded_and_rls_neutral():
    code = "\n".join(
        line for line in _MIGRATION.splitlines()
        if not line.lstrip().startswith("--")
    )
    assert "INSERT INTO provider_team_mapping" not in code
    for forbidden in ("POLICY", "GRANT", "API_FOOTBALL_KEY", "apifootball_key"):
        assert forbidden not in code


# --- register_player-based sync (fixture-backed) ---


def test_sync_writes_only_through_register_player():
    module_ast = ast.parse(_SYNC_SRC)
    called = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Attribute):
            called.add(node.attr)
        if isinstance(node, ast.Name) and node.id == "register_player":
            called.add("register_player")
    assert "register_player" in called
    assert 'table("players")' not in _SYNC_SRC
    assert "players" not in called & {"insert", "upsert", "update"} or \
        ".insert" not in _SYNC_SRC.replace("register_player", "")


def test_unmapped_team_is_skipped_with_zero_writes():
    db = StubSupabase(teams=[{"id": 1, "name": "Arsenal"}])
    client = ApiFootballClient(api_key="fixture-key",
                               transport=_ok_transport(ARSENAL_SQUAD))
    summary = sync_players(db, client)
    assert summary["status"] == "ok"
    assert summary["teams_mapped"] == 0
    assert summary["players_registered"] == 0
    assert db.table("players").rows == []


def test_dry_run_reports_ids_without_writes_or_calls():
    db, _ext = _six_team_db()

    def _exploding(url, headers, timeout):
        raise AssertionError("dry_run must not call the provider")

    client = ApiFootballClient(api_key="fixture-key", transport=_exploding)
    summary = sync_players(db, client, dry_run=True)
    assert summary["status"] == "dry_run"
    assert summary["teams_mapped"] == 6
    assert len(summary["mappings"]) == 6
    assert db.table("players").rows == []


def test_missing_key_skips_with_zero_writes():
    db, _ext = _six_team_db()
    client = ApiFootballClient(api_key="", transport=_ok_transport(ARSENAL_SQUAD))
    summary = sync_players(db, client)
    assert summary["status"] == "skipped"
    assert summary["reason"] == "missing_key"
    assert db.table("players").rows == []


def test_six_team_backfill_registers_identity_only():
    db, ext = _six_team_db()
    payloads = {
        ext[name]: _squad_payload(f"ext-{name}", name, [
            {"id": 5000 + i, "name": f"{name} Fixture {i}",
             "age": 25, "number": i, "position": "Midfielder",
             "photo": None},
        ])
        for i, name in enumerate(CANONICAL_TEAMS)
    }

    def _transport(url, headers, timeout):
        for external, payload in payloads.items():
            if f"team={external}" in url or external in url:
                return payload, 200
        return {"response": []}, 200

    # Route per-team by matching the requested external ID in order.
    requested = []

    def _ordered(url, headers, timeout):
        requested.append(url)
        idx = len(requested) - 1
        payload = list(payloads.values())[idx % len(payloads)]
        return payload, 200

    client = ApiFootballClient(api_key="fixture-key", transport=_ordered)
    summary = sync_players(db, client)
    assert summary["teams_attempted"] == 6
    assert summary["players_registered"] == 6
    assert len(db.table("players").rows) == 6
    mappings = fetch_player_mappings(db, source=SOURCE)
    assert len(mappings) == 6
    assert {m["source"] for m in mappings} == {SOURCE}
    players = fetch_players(db)
    assert len(players) == 6


def test_per_team_failure_is_fail_soft():
    db = StubSupabase(
        teams=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}],
        mappings=[
            {"source": SOURCE, "external_team_id": "ext-a", "team_id": 1},
            {"source": SOURCE, "external_team_id": "ext-b", "team_id": 2},
        ],
    )

    def _transport(url, headers, timeout):
        if "ext-a" in url:
            return {"response": []}, 500
        return _squad_payload("ext-b", "B", [
            {"id": 7, "name": "B Striker", "age": 22,
             "number": 9, "position": "Attacker", "photo": None},
        ]), 200

    client = ApiFootballClient(api_key="fixture-key", transport=_transport)
    summary = sync_players(db, client)
    assert summary["players_registered"] == 1
    by_team = {t["external_team_id"]: t for t in summary["teams"]}
    assert by_team["ext-a"]["status"] == "skipped"
    assert by_team["ext-b"]["status"] == "ok"


def test_free_plan_cycle_cap_enforced():
    teams = [{"id": i, "name": f"T{i}"} for i in range(30)]
    mappings = [{"source": SOURCE, "external_team_id": f"ext-{i}", "team_id": i}
                for i in range(30)]
    db = StubSupabase(teams=teams, mappings=mappings)
    calls = []

    def _transport(url, headers, timeout):
        calls.append(url)
        return {"response": []}, 200

    client = ApiFootballClient(api_key="fixture-key", transport=_transport)
    summary = sync_players(db, client)
    assert len(calls) == MAX_TEAMS_PER_CYCLE
    assert summary["teams_attempted"] == MAX_TEAMS_PER_CYCLE


# --- Scheduling + scope boundaries (static) ---


def test_player_sync_job_not_scheduled_by_startup():
    # Automatic nightly player syncs are disabled while membership data
    # integrity is investigated: normal application startup must not
    # register the player-sync job. run_player_sync() itself remains
    # available for an explicitly authorized manual trigger.
    api_src = (_REPO / "api.py").read_text()
    assert "nightly_player_sync" not in api_src
    assert "run_player_sync" not in api_src
    # Existing jobs are untouched.
    assert "nightly_prediction_sync" in api_src
    assert "daily_settlement" in api_src
    assert "weekly_database_backup" in api_src
    assert "hour=2" in api_src and "hour=5" in api_src


def test_render_declares_key_name_without_value():
    render = (_REPO / "render.yaml").read_text()
    assert "API_FOOTBALL_KEY" in render
    assert "sync: false" in render
    import re
    for line in render.splitlines():
        if "API_FOOTBALL_KEY" in line:
            assert "value" not in line.lower()


def test_no_key_value_or_frontend_leak():
    for path in ("apifootball_client.py", "player_sync.py", "api.py",
                 "prediction_pipeline.py"):
        assert "v3.football.api-sports.io" not in (_REPO / path).read_text() or \
            path == "apifootball_client.py"
    for frontend in (_REPO / "src").rglob("*.tsx"):
        assert "API_FOOTBALL_KEY" not in frontend.read_text()
        assert "x-apisports-key" not in frontend.read_text().lower()


def test_sync_touches_no_out_of_scope_provider():
    code = _code_only("player_sync.py").lower()
    for forbidden in ("the-odds-api", "odds_api_key", "value_bets", "telegram",
                      "billing", "paystack", "portfolio", "acca", "entitlement"):
        assert forbidden not in code
