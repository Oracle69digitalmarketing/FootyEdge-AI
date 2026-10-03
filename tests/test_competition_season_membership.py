"""Objective 6C: canonical competition-season membership tests (offline only).

No network, no database, no live provider APIs, no production Supabase.
Validates the 004 migration contract statically, membership enforcement
through the (unchanged) resolver contract, and the read-only
fetch_competition_season_membership retrieval via stub Supabase with
FK + composite-PK enforcement mirroring the real schema.
"""
import ast
from pathlib import Path

import pytest

from competition_provenance import (
    CompetitionIdentityConflictError,
    UnknownCompetitionIdentityError,
    fetch_competition_seasons,
    fetch_provider_competition_mappings,
    fetch_provider_season_mappings,
    resolve_competition_season,
)

_REPO = Path(__file__).resolve().parent.parent
_MIGRATION = _REPO / "supabase_migrations" / "004_competition_season_membership.sql"
_MODULE_SRC = (_REPO / "competition_provenance.py").read_text()

EPL = {"id": 1, "code": "ENG-Premier League", "name": "Premier League"}
LA_LIGA = {"id": 2, "code": "ESP-La Liga", "name": "La Liga"}
S2526 = {"id": 10, "label": "2025/26", "start_year": 2025, "end_year": 2026}
S2425 = {"id": 11, "label": "2024/25", "start_year": 2024, "end_year": 2025}


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
            [r for r in self._table.rows
             if all(r.get(c) == v for c, v in self._filters)]
        )


class _Insert:
    """Mirrors postgrest-py, enforcing the schema's PK/FK guards."""

    def __init__(self, table, row):
        self._table = table
        self._row = row

    def execute(self):
        for keys in self._table._unique_keys:
            key = tuple(self._row.get(k) for k in keys)
            for existing in self._table.rows:
                if tuple(existing.get(k) for k in keys) == key:
                    raise ValueError(f"duplicate key {keys}={key}")
        for col, valid_ids in self._table._fk.items():
            if self._row.get(col) not in valid_ids:
                raise ValueError(f"foreign key violation {col}={self._row.get(col)!r}")
        stored = dict(self._row)
        self._table.rows.append(stored)
        return _Result([stored])


class _Table:
    def __init__(self, rows=(), unique_keys=(), fk=None):
        self.rows = [dict(r) for r in rows]
        self._unique_keys = unique_keys
        self._fk = fk or {}

    def select(self, _columns):
        return _Query(self)

    def insert(self, row):
        return _Insert(self, row)


class StubSupabase:
    """Fake with the PK/FK guards the 004 schema enforces."""

    def __init__(self, competitions=(), seasons=(), comp_mappings=(),
                 season_mappings=(), membership=()):
        comp_ids = {r["id"] for r in competitions}
        season_ids = {r["id"] for r in seasons}
        self._tables = {
            "competitions": _Table(competitions),
            "seasons": _Table(seasons),
            "provider_competition_mapping": _Table(comp_mappings),
            "provider_season_mapping": _Table(season_mappings),
            "competition_season": _Table(
                membership,
                unique_keys=[("competition_id", "season_id")],
                fk={"competition_id": comp_ids, "season_id": season_ids},
            ),
        }

    def table(self, name):
        return self._tables[name]


def _db():
    return StubSupabase(
        competitions=[EPL, LA_LIGA],
        seasons=[S2526, S2425],
        comp_mappings=[
            {"source": "odds-api",
             "external_competition_id": "soccer_epl", "competition_id": 1},
        ],
        season_mappings=[
            {"source": "odds-api",
             "external_season_id": "2025-26", "season_id": 10},
        ],
        membership=[{"competition_id": 1, "season_id": 10}],
    )


def _resolve(db, **overrides):
    kwargs = dict(
        competitions=[EPL, LA_LIGA],
        seasons=[S2526, S2425],
        competition_mappings=fetch_provider_competition_mappings(db),
        season_mappings=fetch_provider_season_mappings(db),
        membership=fetch_competition_seasons(db),
    )
    kwargs.update(overrides)
    return resolve_competition_season(**kwargs)


# --- Migration contract ---


def test_membership_table_contract():
    sql = _MIGRATION.read_text()
    assert "CREATE TABLE IF NOT EXISTS competition_season" in sql
    assert "competition_id BIGINT NOT NULL" in sql
    assert "season_id BIGINT NOT NULL" in sql
    assert "REFERENCES competitions(id)" in sql
    assert "REFERENCES seasons(id)" in sql
    assert "PRIMARY KEY (competition_id, season_id)" in sql
    assert "ON DELETE CASCADE" in sql


def test_migration_is_additive_without_seeds_or_side_effects():
    sql = _MIGRATION.read_text()
    code = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    assert code.count("CREATE TABLE") == 1
    assert "INSERT INTO competition_season" not in code
    assert "external_" not in code
    assert "team_" not in code
    for forbidden in ("DROP TABLE", "DROP COLUMN", "ALTER TABLE competitions",
                      "ALTER TABLE seasons", "DELETE FROM", "UPDATE "):
        assert forbidden not in code


# --- Req 1/2: valid membership resolves (canonical + provider paths) ---


def test_valid_canonical_membership_resolves():
    res = _resolve(
        db=_db(),
        competition_code="ENG-Premier League",
        season_label="2025/26",
        competition_mappings=[],
        season_mappings=[],
    )
    assert (res.competition_id, res.season_id) == (1, 10)
    assert res.competition_code == "ENG-Premier League"
    assert res.season_label == "2025/26"


def test_valid_provider_pair_resolves_through_mappings():
    res = _resolve(
        db=_db(),
        source="odds-api",
        external_competition_id="soccer_epl",
        external_season_id="2025-26",
    )
    assert (res.competition_id, res.season_id) == (1, 10)


# --- Req 3/4: one side missing ---


def test_existing_competition_missing_season():
    with pytest.raises(UnknownCompetitionIdentityError):
        _resolve(db=_db(), competition_code="ENG-Premier League",
                 season_label="1999/00")


def test_existing_season_missing_competition():
    with pytest.raises(UnknownCompetitionIdentityError):
        _resolve(db=_db(), competition_code="NON-Existent League",
                 season_label="2025/26")


# --- Req 5/6: both sides valid, pair absent ---


def test_both_exist_without_membership():
    with pytest.raises(UnknownCompetitionIdentityError):
        _resolve(db=_db(), competition_code="ESP-La Liga",
                 season_label="2024/25")


def test_mappings_resolve_individually_without_pair_membership():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            source="odds-api",
            external_competition_id="soccer_epl",
            external_season_id="2025-26",
            competitions=[EPL],
            seasons=[S2526],
            competition_mappings=[
                {"source": "odds-api",
                 "external_competition_id": "soccer_epl", "competition_id": 1}],
            season_mappings=[
                {"source": "odds-api",
                 "external_season_id": "2025-26", "season_id": 10}],
            membership=[],  # sides resolve; pair absent
        )


# --- Req 7/8/9: ambiguity and conflict preserved ---


def test_ambiguous_provider_competition_remains_conflict():
    db = _db()
    db.table("provider_competition_mapping").rows.append(
        {"source": "odds-api",
         "external_competition_id": "soccer_epl", "competition_id": 2})
    with pytest.raises(CompetitionIdentityConflictError):
        _resolve(db=db, source="odds-api",
                 external_competition_id="soccer_epl",
                 external_season_id="2025-26")


def test_ambiguous_provider_season_remains_conflict():
    db = _db()
    db.table("provider_season_mapping").rows.append(
        {"source": "odds-api",
         "external_season_id": "2025-26", "season_id": 11})
    with pytest.raises(CompetitionIdentityConflictError):
        _resolve(db=db, source="odds-api",
                 external_competition_id="soccer_epl",
                 external_season_id="2025-26")


def test_conflicting_canonical_provider_identity_remains_conflict():
    with pytest.raises(CompetitionIdentityConflictError):
        _resolve(db=_db(), competition_code="ESP-La Liga",
                 season_label="2025/26", source="odds-api",
                 external_competition_id="soccer_epl",
                 external_season_id="2025-26")


# --- Req 10/11: membership FK guards ---


def test_membership_cannot_reference_nonexistent_competition():
    db = _db()
    with pytest.raises(ValueError, match="foreign key violation"):
        db.table("competition_season").insert(
            {"competition_id": 999, "season_id": 10}).execute()


def test_membership_cannot_reference_nonexistent_season():
    db = _db()
    with pytest.raises(ValueError, match="foreign key violation"):
        db.table("competition_season").insert(
            {"competition_id": 1, "season_id": 999}).execute()


# --- Req 12: duplicate membership rejected ---


def test_duplicate_membership_rejected():
    db = _db()
    with pytest.raises(ValueError, match="duplicate key"):
        db.table("competition_season").insert(
            {"competition_id": 1, "season_id": 10}).execute()
    assert len(db.table("competition_season").rows) == 1


# --- Req 13: independent reuse across valid pairs ---


def test_sides_reusable_across_valid_pairs():
    db = _db()
    db.table("competition_season").rows.append(
        {"competition_id": 1, "season_id": 11})
    db.table("competition_season").rows.append(
        {"competition_id": 2, "season_id": 10})
    assert _resolve(db=db, competition_code="ENG-Premier League",
                    season_label="2024/25").season_id == 11
    assert _resolve(db=db, competition_code="ESP-La Liga",
                    season_label="2025/26").competition_id == 2
    assert _resolve(db=db, competition_code="ENG-Premier League",
                    season_label="2025/26").season_id == 10


# --- Req 14: resolver creates nothing ---


def test_resolver_does_not_create_missing_membership():
    db = _db()
    before = list(db.table("competition_season").rows)
    with pytest.raises(UnknownCompetitionIdentityError):
        _resolve(db=db, competition_code="ESP-La Liga",
                 season_label="2024/25")
    assert db.table("competition_season").rows == before
    assert ".insert(" not in _MODULE_SRC
    assert _MODULE_SRC.count('table("competition_season")') == 1


# --- Req 15: deterministic ---


def test_membership_resolution_is_deterministic():
    db = _db()
    first = _resolve(db=db, source="odds-api",
                     external_competition_id="soccer_epl",
                     external_season_id="2025-26")
    second = _resolve(db=db, source="odds-api",
                      external_competition_id="soccer_epl",
                      external_season_id="2025-26")
    assert first == second
    assert hash(first) == hash(second)


# --- Retrieval layer shape ---


def test_fetch_competition_seasons_returns_resolver_rows():
    rows = fetch_competition_seasons(_db())
    assert rows == [{"competition_id": 1, "season_id": 10}]
    # Dict rows feed the resolver's membership parameter directly.
    res = resolve_competition_season(
        competition_code="ENG-Premier League",
        season_label="2025/26",
        competitions=[EPL],
        seasons=[S2526],
        membership=rows,
    )
    assert (res.competition_id, res.season_id) == (1, 10)
