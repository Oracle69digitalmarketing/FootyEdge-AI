"""Predictor identity-path tests (stub Supabase only — no network, no database).

resolve_predictor_team_id() and get_team_matches() live in predictor.py,
whose module-level imports require the full application stack. Both
functions are loaded from their exact AST nodes and executed in isolation
with the real DB-backed resolver injected. The stub mirrors the repo's
Supabase call chains:
  supabase.table(name).select(cols).eq(col, val).order(...).limit(...).execute().data
"""
import ast
import asyncio
import logging
import types
from pathlib import Path
from typing import Dict, List

from team_identity import (
    CANONICAL_TEAMS,
    generate_canonical_id,
    resolve_canonical_id_db,
)

_PREDICTOR_PATH = Path(__file__).resolve().parent.parent / "predictor.py"

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

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def execute(self):
        return _Result(
            [
                row
                for row in self._table.rows
                if all(row.get(col) == val for col, val in self._filters)
            ]
        )


class _Table:
    def __init__(self, rows=()):
        self.rows = [dict(r) for r in rows]

    def select(self, _columns):
        return _Query(self)


class StubSupabase:
    def __init__(self, teams=(), aliases=(), mappings=(), matches=()):
        self._tables = {
            "teams": _Table(teams),
            "team_aliases": _Table(aliases),
            "team_identity_sources": _Table(mappings),
            "matches": _Table(matches),
        }

    def table(self, name):
        return self._tables[name]


def _load_functions():
    source = _PREDICTOR_PATH.read_text()
    module = ast.parse(source)
    namespace = {
        "resolve_canonical_id_db": resolve_canonical_id_db,
        "PREDICTOR_TEAM_SOURCE": "internal",
        "logger": logging.getLogger("test"),
        "List": List,
        "Dict": Dict,
    }
    found = {}
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "FootyEdgePredictor":
            for item in node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == "get_team_matches":
                    exec(
                        compile(ast.Module(body=[item], type_ignores=[]), str(_PREDICTOR_PATH), "exec"),
                        namespace,
                    )
                    found["get_team_matches"] = namespace["get_team_matches"]
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_predictor_team_id":
            exec(
                compile(ast.Module(body=[node], type_ignores=[]), str(_PREDICTOR_PATH), "exec"),
                namespace,
            )
            found["resolve_predictor_team_id"] = namespace["resolve_predictor_team_id"]
    if set(found) != {"resolve_predictor_team_id", "get_team_matches"}:
        raise AssertionError(f"predictor identity functions not found: {sorted(found)}")
    return found


_FUNCS = _load_functions()
resolve_predictor_team_id = _FUNCS["resolve_predictor_team_id"]
_get_team_matches = _FUNCS["get_team_matches"]


def _canon_db(**overrides):
    kwargs = {
        "teams": [{"id": ARSENAL, "name": "Arsenal"}, {"id": MAN_CITY, "name": "Man City"}],
        "matches": [
            {
                "id": 1,
                "home_team_id": ARSENAL,
                "away_team_id": MAN_CITY,
                "match_date": "2026-01-01T20:00:00",
                "home_goals": 2,
                "away_goals": 1,
            }
        ],
    }
    kwargs.update(overrides)
    return StubSupabase(**kwargs)


def _predictor_stub(db):
    return types.SimpleNamespace(supabase=db)


def test_canonical_team_name_resolves_by_canonical_id():
    name, team_id = resolve_predictor_team_id("Arsenal", _canon_db())
    assert (name, team_id) == ("Arsenal", ARSENAL)
    assert team_id == generate_canonical_id("Arsenal")


def test_alias_resolves_to_same_canonical_team():
    db = _canon_db(
        aliases=[{"team_id": ARSENAL, "alias": "Arsenal FC", "source": "internal"}]
    )
    assert resolve_predictor_team_id("Arsenal FC", db) == ("Arsenal", ARSENAL)


def test_provider_mapping_resolves_to_same_canonical_team():
    db = _canon_db(
        mappings=[
            {
                "team_id": ARSENAL,
                "source": "internal",
                "external_team_id": "rx-7",
                "external_name": "Arsenal FC",
            }
        ]
    )
    name, team_id = resolve_predictor_team_id(
        "Arsenal FC", db, external_team_id="rx-7"
    )
    # The mapping carries the unknown display name to the stored canonical row.
    assert (name, team_id) == ("Arsenal", ARSENAL)


def test_raw_spelling_variant_is_not_fuzzy_matched():
    db = _canon_db()
    assert resolve_predictor_team_id("Arsenal FC", db) == (None, None)
    assert resolve_predictor_team_id("ARSENAL", db) == (None, None)


def test_unknown_team_fails_cleanly_without_fabrication():
    db = _canon_db()
    assert resolve_predictor_team_id("Nottingham Forest", db) == (None, None)
    assert resolve_predictor_team_id("", db) == (None, None)
    assert resolve_predictor_team_id(None, db) == (None, None)
    # No rows fabricated anywhere.
    assert len(db.table("teams").rows) == 2
    assert db.table("matches").rows is not None


def test_predictor_queries_team_by_canonical_id_rather_than_name():
    db = _canon_db()
    matches = asyncio.run(_get_team_matches(_predictor_stub(db), "Arsenal"))
    assert len(matches) == 1
    assert matches[0]["opponent_id"] == MAN_CITY
    assert matches[0]["opponent_name"] == "Man City"


def test_no_fallback_raw_name_lookup_remains_as_identity_mechanism():
    source = _PREDICTOR_PATH.read_text()
    assert '.eq("name"' not in source
    assert "resolve_predictor_team_id" in source
    assert "resolve_canonical_id_db" in source


def test_existing_prediction_path_intact_for_canonical_teams():
    db = _canon_db()
    unknown = asyncio.run(_get_team_matches(_predictor_stub(db), "Nott'm Forest"))
    assert unknown == []
    known = asyncio.run(_get_team_matches(_predictor_stub(db), "  Arsenal "))
    assert len(known) == 1
    assert known[0]["result"] == "win"
    assert known[0]["date"] == "2026-01-01"
