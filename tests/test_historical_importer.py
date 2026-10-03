"""Historical importer identity tests (stub Supabase only — offline).

resolve_historical_teams() and lookup_historical_team_id() live in
scripts/import_historical_data.py, whose module-level imports require
pandas/supabase. Both functions are loaded from their exact AST nodes and
executed in isolation with the real DB-backed resolver injected. The stub
mirrors the repo's Supabase call chains:
  supabase.table(name).select(cols).eq(col, val).execute().data
  supabase.table(name).insert(row).execute()
"""
import ast
import logging
from pathlib import Path

from team_identity import (
    CANONICAL_TEAMS,
    UnknownTeamIdentityError,
    generate_canonical_id,
    resolve_canonical_id_db,
)

_IMPORTER_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "import_historical_data.py"
)

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


class _Insert:
    """Mirrors postgrest-py: insert() only executes on .execute()."""

    def __init__(self, table, row):
        self._table = table
        self._row = row

    def execute(self):
        stored = dict(self._row)
        self._table.rows.append(stored)
        return _Result([stored])


class _Table:
    def __init__(self, rows=()):
        self.rows = [dict(r) for r in rows]

    def select(self, _columns):
        return _Query(self)

    def insert(self, row):
        return _Insert(self, row)


class StubSupabase:
    def __init__(self, teams=(), aliases=(), mappings=()):
        self._tables = {
            "teams": _Table(teams),
            "team_aliases": _Table(aliases),
            "team_identity_sources": _Table(mappings),
        }

    def table(self, name):
        return self._tables[name]


def _load_helpers():
    source = _IMPORTER_PATH.read_text()
    module = ast.parse(source)
    namespace = {
        "resolve_canonical_id_db": resolve_canonical_id_db,
        "HISTORICAL_SOURCE": "club-data",
        "UnknownTeamIdentityError": UnknownTeamIdentityError,
        "logger": logging.getLogger("test"),
    }
    wanted = {"resolve_historical_teams", "lookup_historical_team_id"}
    found = {}
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            exec(
                compile(ast.Module(body=[node], type_ignores=[]), str(_IMPORTER_PATH), "exec"),
                namespace,
            )
            found[node.name] = namespace[node.name]
    if set(found) != wanted:
        raise AssertionError(f"importer helpers not found: {sorted(found)}")
    return found


_HELPERS = _load_helpers()
resolve_historical_teams = _HELPERS["resolve_historical_teams"]
lookup_historical_team_id = _HELPERS["lookup_historical_team_id"]


def _canon_db(**overrides):
    kwargs = {
        "teams": [{"id": ARSENAL, "name": "Arsenal"}, {"id": MAN_CITY, "name": "Man City"}],
    }
    kwargs.update(overrides)
    return StubSupabase(**kwargs)


def test_canonical_csv_name_resolves():
    cache, failures = resolve_historical_teams(["Arsenal", "Man City"], _canon_db())
    assert failures == []
    assert cache["Arsenal"] == ("Arsenal", ARSENAL)
    assert cache["Man City"] == ("Man City", MAN_CITY)


def test_alias_csv_name_resolves_to_existing_canonical_team():
    db = _canon_db(
        aliases=[{"team_id": ARSENAL, "alias": "Arsenal FC", "source": "club-data"}]
    )
    before = len(db.table("teams").rows)
    cache, failures = resolve_historical_teams(["Arsenal FC"], db)
    assert failures == []
    assert cache["Arsenal FC"] == ("Arsenal", ARSENAL)
    assert len(db.table("teams").rows) == before


def test_new_historical_team_uses_canonical_sha_id():
    cache, failures = resolve_historical_teams(["Nigeria"], _canon_db())
    assert failures == []
    assert cache["Nigeria"] == ("Nigeria", generate_canonical_id("Nigeria"))


def test_allow_create_behavior_is_explicit():
    source = _IMPORTER_PATH.read_text()
    assert "allow_create=True" in source
    # ...and unknown names resolve only through that explicit path:
    cache, _ = resolve_historical_teams(["Nigeria"], _canon_db())
    assert cache["Nigeria"][1] == generate_canonical_id("Nigeria")


def test_no_second_team_created_for_mapped_variant():
    db = _canon_db(
        aliases=[{"team_id": ARSENAL, "alias": "Arsenal FC", "source": "club-data"}]
    )
    cache, failures = resolve_historical_teams(["Arsenal", "Arsenal FC"], db)
    assert failures == []
    assert cache["Arsenal"][1] == cache["Arsenal FC"][1] == ARSENAL
    assert len(db.table("teams").rows) == 2


def test_no_mapping_row_written_without_genuine_external_id():
    db = _canon_db()
    resolve_historical_teams(["Nigeria", "Arsenal"], db)
    assert db.table("team_identity_sources").rows == []


def test_no_fake_provider_id_generated_when_absent():
    source = _IMPORTER_PATH.read_text()
    # Documented in a comment only; never passed as a resolver argument.
    assert "external_team_id=" not in source


def test_canonical_teams_name_is_stored():
    db = _canon_db()
    cache, _ = resolve_historical_teams(["  Arsenal ", "Man   City"], db)
    assert cache["  Arsenal "] == ("Arsenal", ARSENAL)
    assert cache["Man   City"] == ("Man City", MAN_CITY)
    module_source = _IMPORTER_PATH.read_text()
    assert '"name": canonical_name' in module_source


def test_conflicting_identity_is_not_silently_skipped():
    db = StubSupabase(
        aliases=[
            {"team_id": ARSENAL, "alias": "United", "source": "a"},
            {"team_id": MAN_CITY, "alias": "United", "source": "b"},
        ]
    )
    cache, failures = resolve_historical_teams(["United", "Arsenal"], db)
    assert "United" not in cache
    assert [name for name, _ in failures] == ["United"]
    assert cache["Arsenal"] == ("Arsenal", ARSENAL)


def test_error_identifies_affected_csv_team_and_row_context():
    cache, _ = resolve_historical_teams(["Arsenal"], _canon_db())
    assert lookup_historical_team_id("Arsenal", cache) == ARSENAL
    try:
        lookup_historical_team_id("Nott'm Forest", cache)
    except UnknownTeamIdentityError as exc:
        assert "Nott'm Forest" in str(exc)
    else:
        raise AssertionError("expected UnknownTeamIdentityError")
    module_source = _IMPORTER_PATH.read_text()
    assert "Skipping CSV row" in module_source
    assert "team_name_to_id.get(" not in module_source


def test_same_historical_source_identity_is_deterministic():
    first, _ = resolve_historical_teams(["Nigeria", "Arsenal"], _canon_db())
    second, _ = resolve_historical_teams(["Nigeria", "Arsenal"], _canon_db())
    assert first == second


def test_existing_historical_match_lookup_behavior_intact():
    db = _canon_db()
    cache, failures = resolve_historical_teams(["Arsenal", "Man City"], db)
    assert failures == []
    assert lookup_historical_team_id("Arsenal", cache) == ARSENAL
    assert lookup_historical_team_id("Man City", cache) == MAN_CITY
