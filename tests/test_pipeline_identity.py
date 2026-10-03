"""Pipeline identity-path tests (stub Supabase only — no network, no database).

ensure_fixture_teams() lives in prediction_pipeline.py, whose module-level
imports require the full application stack. The function's exact AST node
is loaded and executed in isolation with the real DB-backed resolver
injected. The stub mirrors the repo's Supabase call chains:
  supabase.table(name).select(cols).eq(col, val).execute().data
  supabase.table(name).upsert(row).execute()
"""
import ast
from pathlib import Path

import pytest

from team_identity import (
    CANONICAL_TEAMS,
    UnknownTeamIdentityError,
    generate_canonical_id,
    resolve_canonical_id_db,
)

_PIPELINE_PATH = Path(__file__).resolve().parent.parent / "prediction_pipeline.py"

ARSENAL = CANONICAL_TEAMS["Arsenal"]
MAN_CITY = CANONICAL_TEAMS["Man City"]


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
            [
                row
                for row in self._table.rows
                if all(row.get(col) == val for col, val in self._filters)
            ]
        )


class _Upsert:
    def __init__(self, table, row):
        self._table = table
        self._row = row

    def execute(self):
        self._table.upserts.append(dict(self._row))
        for existing in self._table.rows:
            if existing.get("id") == self._row.get("id"):
                existing.update(self._row)
                return _Result([existing])
        stored = dict(self._row)
        self._table.rows.append(stored)
        return _Result([stored])


class _Table:
    def __init__(self, rows=()):
        self.rows = [dict(r) for r in rows]
        self.upserts = []

    def select(self, _columns):
        return _Query(self)

    def insert(self, row):
        return _Upsert(self, row)

    def upsert(self, row, **_kwargs):
        return _Upsert(self, row)


class StubSupabase:
    def __init__(self, teams=(), aliases=(), mappings=()):
        self._tables = {
            "teams": _Table(teams),
            "team_aliases": _Table(aliases),
            "team_identity_sources": _Table(mappings),
        }

    def table(self, name):
        return self._tables[name]


def _load_ensure_fixture_teams():
    source = _PIPELINE_PATH.read_text()
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "ensure_fixture_teams":
            namespace = {
                "resolve_canonical_id_db": resolve_canonical_id_db,
                "PIPELINE_TEAM_SOURCE": "fbref",
            }
            exec(
                compile(ast.Module(body=[node], type_ignores=[]), str(_PIPELINE_PATH), "exec"),
                namespace,
            )
            return namespace["ensure_fixture_teams"]
    raise AssertionError("ensure_fixture_teams not found in prediction_pipeline.py")


ensure_fixture_teams = _load_ensure_fixture_teams()


def _canon_db():
    return StubSupabase(
        teams=[{"id": ARSENAL, "name": "Arsenal"}, {"id": MAN_CITY, "name": "Man City"}]
    )


def test_known_canonical_teams_resolve_without_creation():
    db = _canon_db()
    before = len(db.table("teams").rows)
    (home, away) = ensure_fixture_teams("Arsenal", "Man City", "ENG-Premier League", db)
    assert home == ("Arsenal", ARSENAL)
    assert away == ("Man City", MAN_CITY)
    assert len(db.table("teams").rows) == before


def test_fixture_resolution_is_source_scoped_to_fbref():
    db = _canon_db()
    # A mapping for the same display name under another source must not leak
    # into the pipeline's fbref-scoped fixture resolution.
    db.table("team_identity_sources").rows.append(
        {
            "team_id": ARSENAL,
            "source": "other-provider",
            "external_team_id": "fb-1",
            "external_name": "Arsenal FC",
        }
    )
    with pytest.raises(UnknownTeamIdentityError):
        ensure_fixture_teams("Arsenal FC", "Man City", "ENG-Premier League", db)
    assert db.table("teams").upserts == []


def test_alias_resolves_to_canonical_team_in_fixture():
    db = _canon_db()
    db.table("team_aliases").rows.append(
        {"team_id": ARSENAL, "alias": "Arsenal FC", "source": "fbref"}
    )
    (home, _away) = ensure_fixture_teams("Arsenal FC", "Man City", "ENG-Premier League", db)
    # The stored canonical spelling wins, never the alias text.
    assert home == ("Arsenal", ARSENAL)


def test_unknown_provider_name_does_not_auto_mint_during_prediction():
    db = _canon_db()
    with pytest.raises(UnknownTeamIdentityError):
        ensure_fixture_teams("Nottingham Forest", "Man City", "ENG-Premier League", db)
    assert db.table("teams").upserts == []


def test_spelling_variant_cannot_create_second_team():
    db = _canon_db()
    before = [dict(r) for r in db.table("teams").rows]
    with pytest.raises(UnknownTeamIdentityError):
        ensure_fixture_teams("Arsenal FC", "Man City", "ENG-Premier League", db)
    assert db.table("teams").rows == before
    assert db.table("teams").upserts == []


def test_provider_id_is_never_used_as_teams_id():
    db = _canon_db()
    db.table("team_identity_sources").rows.append(
        {"team_id": ARSENAL, "source": "fbref", "external_team_id": "99999"}
    )
    ensure_fixture_teams("Arsenal", "Man City", "ENG-Premier League", db)
    written_ids = {u["id"] for u in db.table("teams").upserts}
    assert 99999 not in written_ids
    assert written_ids == {ARSENAL, MAN_CITY}


def test_teams_name_remains_canonical():
    db = _canon_db()
    ensure_fixture_teams("  Arsenal ", "Man   City", "ENG-Premier League", db)
    written = {u["id"]: u["name"] for u in db.table("teams").upserts}
    assert written == {ARSENAL: "Arsenal", MAN_CITY: "Man City"}


def test_resolver_errors_propagate_for_controlled_fixture_failure():
    db = _canon_db()
    with pytest.raises(UnknownTeamIdentityError):
        ensure_fixture_teams("Unknown XI", "Also Unknown", "ENG-Premier League", db)
    # Nothing was written: the loop's except-path sees zero side effects.
    assert db.table("teams").upserts == []


def test_existing_successful_fixture_behavior_intact():
    (home, away) = ensure_fixture_teams("Arsenal", "Man City", "ENG-Premier League", _canon_db())
    assert home[1] == generate_canonical_id("Arsenal")
    assert away[1] == generate_canonical_id("Man City")
    db = _canon_db()
    ensure_fixture_teams("Arsenal", "Man City", "ENG-Premier League", db)
    assert len(db.table("teams").upserts) == 2


def test_no_duplicate_team_write_when_canonical_exists():
    db = _canon_db()
    ensure_fixture_teams("Arsenal", "Man City", "ENG-Premier League", db)
    for upsert in db.table("teams").upserts:
        match = next(r for r in db.table("teams").rows if r["id"] == upsert["id"])
        assert upsert["name"] == match["name"]
    assert len({u["id"] for u in db.table("teams").upserts}) == 2
