"""DB-backed resolver tests (stub Supabase only — no network, no database).

The stub mirrors the real contract used across the repo:
  supabase.table(name).select(cols).eq(col, val)[.eq(...)].execute().data
  supabase.table(name).insert(row).execute()
Column names match the live production schema (teams, team_aliases,
team_identity_sources as created by 001_global_football_identity.sql).
"""
import hashlib

import pytest

from team_identity import (
    CANONICAL_TEAMS,
    LEGACY_TEAM_IDS,
    TeamIdentityConflictError,
    UnknownTeamIdentityError,
    generate_canonical_id,
    resolve_canonical_id_db,
)

ARSENAL = CANONICAL_TEAMS["Arsenal"]
MAN_CITY = CANONICAL_TEAMS["Man City"]


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table, columns):
        self._table = table
        self._columns = columns
        self._filters = []

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def execute(self):
        rows = [
            row
            for row in self._table.rows
            if all(row.get(col) == val for col, val in self._filters)
        ]
        return _Result(rows)


class _Insert:
    """Mirrors postgrest-py: insert() only executes on .execute()."""

    def __init__(self, table, row):
        self._table = table
        self._row = row

    def execute(self):
        for keys in self._table._unique_keys:
            key = tuple(self._row.get(k) for k in keys)
            for existing in self._table.rows:
                if tuple(existing.get(k) for k in keys) == key:
                    raise ValueError(f"duplicate key {keys}={key}")
        stored = dict(self._row)
        self._table.rows.append(stored)
        return _Result([stored])


class _Table:
    def __init__(self, rows, unique_keys=()):
        self.rows = list(rows)
        self._unique_keys = unique_keys

    def select(self, columns):
        return _Query(self, columns)

    def insert(self, row):
        return _Insert(self, row)


class StubSupabase:
    """Fake with the uniqueness the real schema enforces."""

    def __init__(self, teams=(), aliases=(), mappings=()):
        self._tables = {
            "teams": _Table(list(teams), unique_keys=[("id",)]),
            "team_aliases": _Table(list(aliases)),
            "team_identity_sources": _Table(
                list(mappings), unique_keys=[("source", "external_team_id")]
            ),
        }

    def table(self, name):
        return self._tables[name]


def _canon_db():
    return StubSupabase(
        teams=[{"id": ARSENAL, "name": "Arsenal"}, {"id": MAN_CITY, "name": "Man City"}]
    )


def test_db_exact_canonical_name_resolves():
    name, team_id = resolve_canonical_id_db("  Arsenal ", "fbref", _canon_db())
    assert (name, team_id) == ("Arsenal", ARSENAL)


def test_db_alias_resolves_to_canonical_team():
    db = _canon_db()
    db.table("team_aliases").rows.append(
        {"team_id": ARSENAL, "alias": "Man Utd", "source": "odds-api"}
    )
    # "Man Utd" is not a canonical team; the alias carries it to Arsenal.
    name, team_id = resolve_canonical_id_db("Man Utd", "odds-api", db)
    assert team_id == ARSENAL


def test_db_provider_source_and_external_id_resolve():
    db = _canon_db()
    db.table("team_identity_sources").rows.append(
        {
            "team_id": MAN_CITY,
            "source": "api-football",
            "external_team_id": "33",
            "external_name": "Man City",
        }
    )
    _, team_id = resolve_canonical_id_db("Whatever Name", "api-football", db, "33")
    assert team_id == MAN_CITY


def test_db_provider_identity_requires_both_source_and_id():
    db = _canon_db()
    db.table("team_identity_sources").rows.append(
        {"team_id": MAN_CITY, "source": "api-football", "external_team_id": "33"}
    )
    # Same external ID under a different source must NOT resolve.
    with pytest.raises(UnknownTeamIdentityError):
        resolve_canonical_id_db("Unknown Side", "other-source", db, "33")


def test_db_alias_takes_precedence_over_canonical_name_lookup():
    db = StubSupabase(
        teams=[
            {"id": ARSENAL, "name": "Arsenal"},
            {"id": generate_canonical_id("Man Utd"), "name": "Man Utd"},
        ],
        aliases=[{"team_id": ARSENAL, "alias": "Man Utd", "source": "odds-api"}],
    )
    _, team_id = resolve_canonical_id_db("Man Utd", "odds-api", db)
    assert team_id == ARSENAL


def test_db_provider_mapping_takes_precedence_over_canonical_name_lookup():
    man_utd_id = generate_canonical_id("Man Utd")
    db = StubSupabase(
        teams=[
            {"id": ARSENAL, "name": "Arsenal"},
            {"id": man_utd_id, "name": "Man Utd"},
        ],
        mappings=[
            {"team_id": ARSENAL, "source": "api-football", "external_team_id": "40"}
        ],
    )
    _, team_id = resolve_canonical_id_db("Man Utd", "api-football", db, "40")
    assert team_id == ARSENAL


def test_db_unknown_name_raises_by_default():
    with pytest.raises(UnknownTeamIdentityError):
        resolve_canonical_id_db("Nottingham Forest", "fbref", _canon_db())
    with pytest.raises(UnknownTeamIdentityError):
        resolve_canonical_id_db("Nottm Forest", "fbref", _canon_db())


def test_db_allow_create_uses_existing_sha_namespace():
    db = _canon_db()
    name, team_id = resolve_canonical_id_db("Nigeria", "fbref", db, allow_create=True)
    assert name == "Nigeria"
    assert team_id == int(hashlib.sha256(b"Nigeria").hexdigest()[:12], 16)
    repeat = resolve_canonical_id_db("  Nigeria ", "fbref", db)
    assert repeat == (name, team_id)


def test_db_registration_stores_provider_mapping():
    db = _canon_db()
    _, team_id = resolve_canonical_id_db(
        "Nigeria", "api-football", db, external_team_id="19", allow_create=True
    )
    stored = db.table("team_identity_sources").rows
    assert {
        "team_id": team_id,
        "source": "api-football",
        "external_team_id": "19",
    }.items() <= stored[0].items()


def test_db_registration_does_not_create_alias():
    db = _canon_db()
    resolve_canonical_id_db(
        "Nigeria", "api-football", db, external_team_id="19", allow_create=True
    )
    assert db.table("team_aliases").rows == []


def test_db_same_provider_id_resolves_deterministically():
    db = _canon_db()
    db.table("team_identity_sources").rows.append(
        {"team_id": ARSENAL, "source": "api-football", "external_team_id": "40"}
    )
    first = resolve_canonical_id_db("A", "api-football", db, "40")
    second = resolve_canonical_id_db("Totally Different", "api-football", db, "40")
    assert first[1] == second[1] == ARSENAL


def test_db_provider_id_conflict_raises():
    db = StubSupabase(
        mappings=[
            {"team_id": ARSENAL, "source": "api-football", "external_team_id": "40"},
            {"team_id": MAN_CITY, "source": "api-football", "external_team_id": "40"},
        ]
    )
    with pytest.raises(TeamIdentityConflictError):
        resolve_canonical_id_db("Anything", "api-football", db, "40")


def test_db_alias_conflict_raises_instead_of_picking_one():
    db = StubSupabase(
        aliases=[
            {"team_id": ARSENAL, "alias": "United", "source": "a"},
            {"team_id": MAN_CITY, "alias": "United", "source": "b"},
        ]
    )
    with pytest.raises(TeamIdentityConflictError):
        resolve_canonical_id_db("United", "a", db)


def test_db_provider_vs_alias_conflict_raises():
    db = StubSupabase(
        aliases=[{"team_id": MAN_CITY, "alias": "Reds", "source": "odds-api"}],
        mappings=[{"team_id": ARSENAL, "source": "odds-api", "external_team_id": "7"}],
    )
    with pytest.raises(TeamIdentityConflictError):
        resolve_canonical_id_db("Reds", "odds-api", db, "7")


def test_db_legacy_ids_are_rejected():
    db = _canon_db()
    for legacy in sorted(LEGACY_TEAM_IDS):
        with pytest.raises(ValueError):
            resolve_canonical_id_db("Arsenal", "fbref", db, str(legacy))
    poisoned = StubSupabase(
        mappings=[{"team_id": 101, "source": "fbref", "external_team_id": "9"}]
    )
    with pytest.raises(ValueError):
        resolve_canonical_id_db("Anything", "fbref", poisoned, "9")


def test_db_no_fuzzy_matching_occurs():
    db = _canon_db()
    # Near-miss spellings are distinct unknowns, never near-matches.
    for variant in ("Arsenal FC", "ArsenalFC", "ARSENAL", "Arsenall"):
        with pytest.raises(UnknownTeamIdentityError):
            resolve_canonical_id_db(variant, "fbref", db)


def test_db_canonical_formula_exactly_unchanged():
    for name, expected in CANONICAL_TEAMS.items():
        assert generate_canonical_id(name) == expected == int(
            hashlib.sha256(name.encode()).hexdigest()[:12], 16
        )


def test_db_never_overwrites_existing_team_on_registration_race():
    db = _canon_db()
    # Name exists under a different (legacy-style) row is a conflict, not an overwrite.
    db.table("teams").rows.append({"id": 999999, "name": "Arsenal"})
    with pytest.raises(TeamIdentityConflictError):
        resolve_canonical_id_db("Arsenal", "fbref", db)
