"""Objective 10.2C.2.2: history-authoritative membership contracts (offline only).

No network, no database, no live provider APIs, no production Supabase,
no credentials. Provider payloads and team/player IDs are obvious
fixtures, never production claims.

Covers:
- attach_current_teams / current_history_row / fetch/append helpers
- api.py wiring (static contract: fastapi is not installed in this env,
  so handlers stay thin and all behavior lives in tested helpers)
- player_sync.py transfer-append + repeated-sync idempotency
"""

import asyncio
from pathlib import Path

import pytest

from apifootball_client import ApiFootballClient, SOURCE
from player_identity import (
    append_team_history,
    current_history_row,
    fetch_player_history,
)
from player_team_membership import attach_current_teams
from player_sync import sync_players

_REPOSRC = Path(__file__).resolve().parent.parent
_API_SRC = (_REPOSRC / "api.py").read_text()
_SYNC_SRC = (_REPOSRC / "player_sync.py").read_text()


# --- Offline fakes (eq/in_/insert with UNIQUE/NOT NULL/sequence guards) ---


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table):
        self._table = table
        self._eq = []
        self._in = []

    def eq(self, column, value):
        self._eq.append((column, value))
        return self

    def in_(self, column, values):
        self._in.append((column, list(values)))
        return self

    def limit(self, _n):
        return self

    def order(self, *_a, **_k):
        return self

    def execute(self):
        if self._table._fail_on_select:
            raise self._table._fail_on_select
        return _Result([
            dict(r) for r in self._table.rows
            if all(r.get(c) == v for c, v in self._eq)
            and all(r.get(c) in vals for c, vals in self._in)
        ])


class _Insert:
    def __init__(self, table, row):
        self._table = table
        self._row = row

    def execute(self):
        if self._table._fail_on_insert:
            raise self._table._fail_on_insert
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
        self._fail_on_select = None
        self._fail_on_insert = None

    def _next_id(self):
        value = self._seq_next
        self._seq_next += 1
        return value

    def select(self, _columns):
        return _Query(self)

    def insert(self, row):
        return _Insert(self, row)


class FakeSupabase:
    def __init__(self, players=(), history=(), teams=(), mappings=(),
                 aliases=()):
        self._tables = {
            "players": _Table(players, unique_keys=[("id",)],
                              not_null=("name",), seq=True),
            "player_identity_sources": _Table(
                (), unique_keys=[("source", "external_player_id")],
                not_null=("player_id", "source", "external_player_id")),
            "player_aliases": _Table(aliases),
            "player_team_history": _Table(
                history, not_null=("player_id", "team_id"), seq=True),
            "provider_team_mapping": _Table(
                mappings, unique_keys=[("source", "external_team_id")]),
            "teams": _Table(teams),
        }

    def table(self, name):
        return self._tables[name]


def _squad(team_ext, team_name, entries):
    return {"response": [{
        "team": {"id": team_ext, "name": team_name},
        "players": [
            {"id": pid, "name": name, "age": 25, "number": n,
             "position": "Midfielder", "photo": None}
            for n, (pid, name) in enumerate(entries)
        ],
    }]}


def _client_for(payloads):
    def _transport(url, headers, timeout):
        for ext, payload in payloads.items():
            if f"team={ext}" in url or url.rstrip("/").endswith(f"/{ext}"):
                return payload, 200
        for ext, payload in payloads.items():
            if ext in url:
                return payload, 200
        return {"response": []}, 200
    return ApiFootballClient(api_key="fixture-key", transport=_transport)


ARSENAL = {"id": 101, "name": "Arsenal", "logo_url": "https://x/arsenal.png"}
LIVERPOOL = {"id": 102, "name": "Liverpool", "logo_url": "https://x/liverpool.png"}


def _run(coro):
    return asyncio.run(coro)


# --- API: attach_current_teams behavior ---


def test_single_history_row_resolves_correct_team_with_logo():
    db = FakeSupabase(
        players=[{"id": 1, "name": "Winger", "team_id": None}],
        history=[{"id": 10, "player_id": 1, "team_id": 101}],
        teams=[ARSENAL, LIVERPOOL],
    )
    out = _run(attach_current_teams(db, db.table("players").rows))
    assert len(out) == 1
    assert out[0]["teams"] == ARSENAL
    assert out[0]["teams"]["logo_url"] == "https://x/arsenal.png"


def test_multiple_history_rows_resolve_greatest_id():
    db = FakeSupabase(
        players=[{"id": 1, "name": "Winger", "team_id": None}],
        history=[
            {"id": 10, "player_id": 1, "team_id": 101},
            {"id": 30, "player_id": 1, "team_id": 102},
            {"id": 20, "player_id": 1, "team_id": 101},
        ],
        teams=[ARSENAL, LIVERPOOL],
    )
    out = _run(attach_current_teams(db, db.table("players").rows))
    assert out[0]["teams"] == LIVERPOOL


def test_no_history_resolves_null_without_fabrication():
    db = FakeSupabase(
        players=[{"id": 1, "name": "Free", "team_id": None}],
        history=[],
        teams=[ARSENAL],
    )
    out = _run(attach_current_teams(db, db.table("players").rows))
    assert out[0]["teams"] is None


def test_existing_fields_preserved_and_inputs_unmutated():
    rows = [{"id": 1, "name": "Winger", "position": "Attacker",
             "team_id": None}]
    snapshot = [dict(r) for r in rows]
    db = FakeSupabase(players=rows,
                      history=[{"id": 4, "player_id": 1, "team_id": 101}],
                      teams=[ARSENAL])
    out = _run(attach_current_teams(db, rows))
    assert rows == snapshot  # inputs not mutated
    assert out[0]["name"] == "Winger"
    assert out[0]["position"] == "Attacker"
    assert out[0]["id"] == 1
    assert out[0]["teams"] == ARSENAL


def test_malformed_history_or_missing_team_resolves_null():
    db = FakeSupabase(
        players=[{"id": 1, "name": "A", "team_id": None},
                 {"id": 2, "name": "B", "team_id": None}],
        history=[
            {"id": 5, "player_id": 1, "team_id": 999},  # team row absent
            {"id": 6, "player_id": 2, "team_id": "Arsenal"},  # non-int
        ],
        teams=[ARSENAL],
    )
    out = _run(attach_current_teams(db, db.table("players").rows))
    assert out[0]["teams"] is None
    assert out[1]["teams"] is None


def test_history_query_failure_propagates_not_swallowed():
    db = FakeSupabase(players=[{"id": 1, "name": "A"}])
    db.table("player_team_history")._fail_on_select = RuntimeError("db down")
    with pytest.raises(RuntimeError):
        _run(attach_current_teams(db, db.table("players").rows))


def test_teams_query_failure_propagates_not_swallowed():
    db = FakeSupabase(
        players=[{"id": 1, "name": "A"}],
        history=[{"id": 2, "player_id": 1, "team_id": 101}],
        teams=[ARSENAL],
    )
    db.table("teams")._fail_on_select = RuntimeError("db down")
    with pytest.raises(RuntimeError):
        _run(attach_current_teams(db, db.table("players").rows))


def test_empty_players_returns_empty():
    db = FakeSupabase()
    assert _run(attach_current_teams(db, [])) == []


def test_current_history_row_ordering_and_fail_closed():
    assert current_history_row([]) is None
    rows = [{"id": 3, "player_id": 1, "team_id": 101},
            {"id": 9, "player_id": 1, "team_id": 102}]
    assert current_history_row(rows)["team_id"] == 102
    # A lone row needs no ordering and is returned as-is.
    lone = {"player_id": 1, "team_id": 101}
    assert current_history_row([lone]) == lone
    # Several rows with no orderable id are ambiguous: fail closed.
    with pytest.raises(Exception):
        current_history_row([{"player_id": 1, "team_id": 101},
                             {"player_id": 1, "team_id": 102}])


# --- API: static wiring contract (fastapi not installed here) ---


def test_api_handlers_resolve_from_history_not_fk_embed():
    assert _API_SRC.count("attach_current_teams") >= 3  # import + 2 calls
    assert "teams(name)" not in _API_SRC
    assert "teams(*)" not in _API_SRC


def test_api_list_preserves_gate_limit_and_mock_fallback():
    assert "require_capability(CAP_PLAYERS)" in _API_SRC
    assert ".limit(100)" in _API_SRC
    assert '"Bukayo Saka"' in _API_SRC


def test_api_detail_preserves_auth_404_and_fallback():
    assert "Player not found" in _API_SRC
    assert "HTTPException(status_code=404" in _API_SRC
    assert '"Mock Player"' in _API_SRC
    assert '@router.get("/api/players/{player_id}")' in _API_SRC
    assert '@router.get("/api/players")' in _API_SRC


# --- Sync: transfer-append + idempotency ---


def _db_with_mapping(team_id=101, ext="ext-a"):
    return FakeSupabase(
        teams=[ARSENAL, LIVERPOOL],
        mappings=[{"source": SOURCE, "external_team_id": ext,
                   "team_id": team_id}],
    )


def test_new_player_gets_correct_initial_membership():
    db = _db_with_mapping()
    client = _client_for({"ext-a": _squad("ext-a", "Arsenal",
                                          [("p1", "New Winger")])})
    summary = sync_players(db, client)
    assert summary["players_registered"] == 1
    hist = db.table("player_team_history").rows
    assert len(hist) == 1
    assert hist[0]["player_id"] == db.table("players").rows[0]["id"]
    assert hist[0]["team_id"] == 101
    assert db.table("players").rows[0].get("team_id") is None  # never written


def test_repeat_sync_appends_no_duplicate_history():
    db = _db_with_mapping()
    client = _client_for({"ext-a": _squad("ext-a", "Arsenal",
                                          [("p1", "New Winger")])})
    first = sync_players(db, client)
    second = sync_players(db, client)
    assert first["players_registered"] == 1
    assert second["players_registered"] == 1  # identity idempotent
    assert len(db.table("players").rows) == 1
    assert len(db.table("player_team_history").rows) == 1
    assert second["teams"][0]["history_errors"] == []


def test_team_change_appends_exactly_one_row_then_stabilizes():
    db = _db_with_mapping(team_id=101)
    payload = _squad("ext-a", "Arsenal", [("p1", "Mover")])
    client = _client_for({"ext-a": payload})
    sync_players(db, client)
    assert len(db.table("player_team_history").rows) == 1
    # Transfer: same provider player now maps to Liverpool.
    db.table("provider_team_mapping").rows[0]["team_id"] = 102
    moved = sync_players(db, client)
    assert moved["players_registered"] == 1
    hist = db.table("player_team_history").rows
    assert len(hist) == 2
    assert current_history_row(hist)["team_id"] == 102
    assert len(db.table("players").rows) == 1  # identity stable
    # Repeat: no further row.
    again = sync_players(db, client)
    assert again["players_registered"] == 1
    assert len(db.table("player_team_history").rows) == 2
    assert again["teams"][0]["history_errors"] == []


def test_unmapped_team_skipped_with_zero_history_writes():
    db = FakeSupabase()
    client = _client_for({"ext-x": _squad("ext-x", "X", [("p1", "Ghost")])})
    summary = sync_players(db, client)
    assert summary["teams_mapped"] == 0
    assert db.table("player_team_history").rows == []


def test_ambiguous_identity_assigns_nothing():
    db = FakeSupabase(
        teams=[ARSENAL],
        mappings=[{"source": SOURCE, "external_team_id": "ext-9",
                   "team_id": 101}],
    )
    # Pre-seed: canonical player 1 "Real Name" owns ext-9 + history.
    db.table("players").rows.append({"id": 1, "name": "Real Name"})
    db.table("player_identity_sources").rows.append(
        {"player_id": 1, "source": SOURCE, "external_player_id": "ext-9"})
    db.table("player_team_history").rows.append(
        {"id": 1, "player_id": 1, "team_id": 101})
    client = _client_for({"ext-9": _squad("ext-9", "Arsenal",
                                          [("ext-9", "Different Name")])})
    summary = sync_players(db, client)
    assert summary["players_registered"] == 0
    assert summary["teams"][0]["skipped"] == 1
    assert len(db.table("player_team_history").rows) == 1  # unchanged
    assert len(db.table("player_identity_sources").rows) == 1  # intact


def test_history_read_failure_is_reported_not_synchronized():
    db = _db_with_mapping()
    db.table("player_team_history")._fail_on_select = RuntimeError("db down")
    client = _client_for({"ext-a": _squad("ext-a", "Arsenal",
                                          [("p1", "Winger")])})
    summary = sync_players(db, client)
    assert summary["players_registered"] == 0
    entry = summary["teams"][0]
    assert entry["skipped"] == 1
    assert entry["status"] == "partial"
    assert len(entry["history_errors"]) == 1


def test_history_write_failure_is_reported_not_synchronized():
    db = FakeSupabase(
        teams=[ARSENAL, LIVERPOOL],
        mappings=[{"source": SOURCE, "external_team_id": "ext-a",
                   "team_id": 101}],
    )
    # Pre-registered player at Arsenal (history row exists).
    db.table("players").rows.append({"id": 1, "name": "Mover"})
    db.table("player_identity_sources").rows.append(
        {"player_id": 1, "source": SOURCE, "external_player_id": "ext-a"})
    db.table("player_team_history").rows.append(
        {"id": 1, "player_id": 1, "team_id": 101})
    # Transfer to Liverpool, but history writes now fail.
    db.table("provider_team_mapping").rows[0]["team_id"] = 102
    db.table("player_team_history")._fail_on_insert = RuntimeError("db down")
    client = _client_for({"ext-a": _squad("ext-a", "Arsenal",
                                          [("ext-a", "Mover")])})
    summary = sync_players(db, client)
    assert summary["players_registered"] == 0
    entry = summary["teams"][0]
    assert entry["skipped"] == 1
    assert entry["status"] == "partial"
    assert len(entry["history_errors"]) == 1
    assert len(db.table("player_team_history").rows) == 1  # unchanged


def test_sync_never_writes_players_team_id_and_mappings_intact():
    db = _db_with_mapping()
    client = _client_for({"ext-a": _squad("ext-a", "Arsenal",
                                          [("p1", "Winger")])})
    sync_players(db, client)
    for row in db.table("players").rows:
        assert row.get("team_id") is None
    assert 'table("players")' not in _SYNC_SRC
    assert db.table("provider_team_mapping").rows == [
        {"source": SOURCE, "external_team_id": "ext-a", "team_id": 101}]


def test_fetch_and_append_helpers_round_trip():
    db = FakeSupabase()
    db.table("players").rows.append({"id": 1, "name": "Winger"})
    assert fetch_player_history(db, 1) == []
    stored = append_team_history(db, player_id=1, team_id=101)
    assert stored["player_id"] == 1 and stored["team_id"] == 101
    assert len(fetch_player_history(db, 1)) == 1
