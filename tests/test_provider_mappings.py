"""Objective 6B: provider competition/season mapping tests (offline only).

No network, no database, no live provider APIs, no production Supabase.
Validates the 003 migration contract statically, the retrieval layer via
stub Supabase (unique-enforcing, mirroring test_team_identity_db.py), and
fetch->resolver integration without modifying the 6A resolver contract.
"""
import ast
from pathlib import Path

import pytest

from competition_provenance import (
    CompetitionIdentityConflictError,
    UnknownCompetitionIdentityError,
    fetch_provider_competition_mappings,
    fetch_provider_season_mappings,
    resolve_competition,
    resolve_competition_season,
    resolve_season,
)

_REPO = Path(__file__).resolve().parent.parent
_MIGRATION = _REPO / "supabase_migrations" / "003_provider_competition_mappings.sql"
_MODULE_SRC = (_REPO / "competition_provenance.py").read_text()
_PIPELINE_SRC = (_REPO / "prediction_pipeline.py").read_text()

def _code(sql: str) -> str:
    """Migration code without -- comments (docs may name out-of-scope items)."""
    return "\n".join(
        line for line in sql.splitlines()
        if not line.lstrip().startswith("--")
    )


EPL = {"id": 1, "code": "ENG-Premier League", "name": "Premier League"}
S2526 = {"id": 10, "label": "2025/26", "start_year": 2025, "end_year": 2026}


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
    def __init__(self, rows=(), unique_keys=()):
        self.rows = [dict(r) for r in rows]
        self._unique_keys = unique_keys

    def select(self, _columns):
        return _Query(self)

    def insert(self, row):
        return _Insert(self, row)


class StubSupabase:
    """Fake with the uniqueness the 003 schema enforces."""

    def __init__(self, competitions=(), seasons=(), comp_mappings=(), season_mappings=()):
        self._tables = {
            "competitions": _Table(competitions),
            "seasons": _Table(seasons),
            "provider_competition_mapping": _Table(
                comp_mappings, unique_keys=[("source", "external_competition_id")]),
            "provider_season_mapping": _Table(
                season_mappings, unique_keys=[("source", "external_season_id")]),
        }

    def table(self, name):
        return self._tables[name]


def _seeded_db():
    return StubSupabase(
        competitions=[EPL],
        seasons=[S2526],
        comp_mappings=[
            {"id": 1, "source": "odds-api",
             "external_competition_id": "soccer_epl", "competition_id": 1},
        ],
        season_mappings=[
            {"id": 1, "source": "odds-api",
             "external_season_id": "2025-26", "season_id": 10},
        ],
    )


# --- Req 1/2: unique provider identity (schema contract) ---


def test_competition_mapping_contract():
    sql = _MIGRATION.read_text()
    assert "CREATE TABLE IF NOT EXISTS provider_competition_mapping" in sql
    assert "external_competition_id TEXT NOT NULL" in sql
    assert "source TEXT NOT NULL" in sql
    assert "competition_id BIGINT NOT NULL" in sql
    assert "UNIQUE (source, external_competition_id)" in sql
    assert "provider_competition_mapping_source_external_key" in sql
    assert "idx_provider_competition_mapping_competition" in sql


def test_season_mapping_contract():
    sql = _MIGRATION.read_text()
    assert "CREATE TABLE IF NOT EXISTS provider_season_mapping" in sql
    assert "external_season_id TEXT NOT NULL" in sql
    assert "UNIQUE (source, external_season_id)" in sql
    assert "provider_season_mapping_source_external_key" in sql
    assert "idx_provider_season_mapping_season" in sql


# --- Req 3/4: canonical FKs ---


def test_canonical_fk_targets():
    sql = _MIGRATION.read_text()
    assert "REFERENCES competitions(id)" in sql
    assert "REFERENCES seasons(id)" in sql
    assert sql.count("ON DELETE CASCADE") >= 2


# --- Req 9 (schema half): no membership enforcement, nothing destructive ---


def test_no_membership_or_destructive_operations():
    sql = _MIGRATION.read_text()
    code = _code(sql)
    assert code.count("CREATE TABLE") == 2
    assert "membership" not in code.lower()
    assert "competition_season" not in code.replace(
        "provider_competition_mapping", "").replace("provider_season_mapping", "")
    for forbidden in ("DROP TABLE", "DROP COLUMN", "ALTER TABLE competitions",
                      "ALTER TABLE seasons", "ALTER TABLE matches",
                      "ALTER TABLE teams", "DELETE FROM", "UPDATE "):
        assert forbidden not in code


# --- Mapping data: seeded vs deliberately unseeded ---


def test_seed_rows_match_repository_evidence():
    sql = _MIGRATION.read_text()
    code = _code(sql)
    # Every seeded external key must appear in the repo's own Odds config.
    for sport_key in ("soccer_epl", "soccer_spain_la_liga",
                      "soccer_germany_bundesliga", "soccer_italy_serie_a",
                      "soccer_france_ligue_one"):
        assert sport_key in code
        assert sport_key in _PIPELINE_SRC
    for code_value in ("ENG-Premier League", "ESP-La Liga", "GER-Bundesliga",
                       "ITA-Serie A", "FRA-Ligue 1"):
        assert code_value in code
    # INT-World Cup link deliberately absent from code (only named in docs):
    # no seeded competitions.code exists for it.
    assert "INT-World Cup" not in code
    assert "FIFA-World Cup" not in code
    # Targets resolve by code lookup, never hardcoded BIGSERIAL ids.
    assert "WHERE code =" in code
    assert "ON CONFLICT (source, external_competition_id) DO NOTHING" in code


def test_season_mappings_left_unseeded():
    sql = _MIGRATION.read_text()
    assert "INSERT INTO provider_season_mapping" not in sql


# --- Req 5: missing canonical target rejected ---


def test_dangling_competition_target_rejected():
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_competition(
            source="odds-api",
            external_competition_id="soccer_epl",
            competitions=[EPL],  # id 1 absent
            competition_mappings=[
                {"source": "odds-api",
                 "external_competition_id": "soccer_epl", "competition_id": 999},
            ],
        )


def test_dangling_season_target_rejected():
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_season(
            source="odds-api",
            external_season_id="2025-26",
            seasons=[S2526],  # id 10 absent
            season_mappings=[
                {"source": "odds-api",
                 "external_season_id": "2025-26", "season_id": 999},
            ],
        )


# --- Req 6: duplicate provider identity rejected ---


def test_duplicate_competition_identity_rejected():
    db = _seeded_db()
    with pytest.raises(ValueError, match="duplicate key"):
        db.table("provider_competition_mapping").insert(
            {"source": "odds-api",
             "external_competition_id": "soccer_epl", "competition_id": 1}
        ).execute()


def test_duplicate_season_identity_rejected():
    db = _seeded_db()
    with pytest.raises(ValueError, match="duplicate key"):
        db.table("provider_season_mapping").insert(
            {"source": "odds-api",
             "external_season_id": "2025-26", "season_id": 10}
        ).execute()


# --- Req 7: no silent repoint to another canonical record ---


def test_provider_identity_cannot_silently_repoint():
    db = _seeded_db()
    # The UNIQUE grain blocks a second row for the same provider identity,
    # so the "repoint" insert is rejected rather than stored.
    with pytest.raises(ValueError, match="duplicate key"):
        db.table("provider_competition_mapping").insert(
            {"source": "odds-api",
             "external_competition_id": "soccer_epl", "competition_id": 2}
        ).execute()
    # And divergent in-memory rows fail closed in the resolver.
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_competition(
            source="odds-api",
            external_competition_id="soccer_epl",
            competitions=[EPL, {"id": 2, "code": "ESP-La Liga"}],
            competition_mappings=[
                {"source": "odds-api",
                 "external_competition_id": "soccer_epl", "competition_id": 1},
                {"source": "odds-api",
                 "external_competition_id": "soccer_epl", "competition_id": 2},
            ],
        )
    # The retrieval layer exposes no update/remap path.
    module_ast = ast.parse(_MODULE_SRC)
    called = {n.attr for n in ast.walk(module_ast) if isinstance(n, ast.Attribute)}
    assert not (called & {"update", "upsert", "delete"})


# --- Req 8: competition/season mapping separation ---


def test_competition_and_season_mappings_are_separate():
    db = _seeded_db()
    comp_rows = fetch_provider_competition_mappings(db, source="odds-api")
    season_rows = fetch_provider_season_mappings(db, source="odds-api")
    assert {r["external_competition_id"] for r in comp_rows} == {"soccer_epl"}
    assert {r["external_season_id"] for r in season_rows} == {"2025-26"}
    assert all("external_season_id" not in r for r in comp_rows)
    assert all("external_competition_id" not in r for r in season_rows)
    # Same raw external string under the other namespace does not cross over.
    db.table("provider_season_mapping").rows.append(
        {"source": "odds-api", "external_season_id": "soccer_epl", "season_id": 10})
    assert fetch_provider_competition_mappings(db, source="odds-api") == comp_rows


# --- Req 9 (behavior half): membership NOT enforced in 6B ---


def test_sides_resolve_without_membership():
    db = _seeded_db()
    comp_id, code = resolve_competition(
        source="odds-api",
        external_competition_id="soccer_epl",
        competitions=[EPL],
        competition_mappings=fetch_provider_competition_mappings(db, source="odds-api"),
    )
    season_id, label = resolve_season(
        source="odds-api",
        external_season_id="2025-26",
        seasons=[S2526],
        season_mappings=fetch_provider_season_mappings(db, source="odds-api"),
    )
    assert (comp_id, code) == (1, "ENG-Premier League")
    assert (season_id, label) == (10, "2025/26")


# --- Retrieval layer: exact source filtering + resolver-shaped rows ---


def test_fetch_helpers_filter_source_exactly():
    db = _seeded_db()
    db.table("provider_competition_mapping").rows.append(
        {"source": "provider-b",
         "external_competition_id": "soccer_epl", "competition_id": 7})
    scoped = fetch_provider_competition_mappings(db, source="odds-api")
    assert len(scoped) == 1
    assert scoped[0]["competition_id"] == 1
    unscoped = fetch_provider_competition_mappings(db)
    assert len(unscoped) == 2
    # No case-insensitive guessing.
    assert fetch_provider_competition_mappings(db, source="ODDS-API") == []


def test_fetch_to_resolve_end_to_end_matches_6a_contract():
    db = _seeded_db()
    # Rows carry real SELECT-output shape (extra id/timestamp keys harmless).
    db.table("provider_competition_mapping").rows[0].update(
        {"id": 1, "created_at": "2026-01-01T00:00:00+00:00"})
    res = resolve_competition_season(
        source="odds-api",
        external_competition_id="soccer_epl",
        external_season_id="2025-26",
        competitions=[EPL],
        seasons=[S2526],
        competition_mappings=fetch_provider_competition_mappings(db, source="odds-api"),
        season_mappings=fetch_provider_season_mappings(db, source="odds-api"),
        membership=[(1, 10)],
    )
    assert (res.competition_id, res.season_id) == (1, 10)


def test_unmapped_fetch_yields_unknown_not_guess():
    db = _seeded_db()
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition(
            source="odds-api",
            external_competition_id="soccer_unknown",
            competitions=[EPL],
            competition_mappings=fetch_provider_competition_mappings(db, source="odds-api"),
        )


def test_external_ids_stay_verbatim_text():
    db = _seeded_db()
    with pytest.raises(TypeError):
        fetch_provider_competition_mappings(db, source=39)
    with pytest.raises(TypeError):
        resolve_season(
            source="odds-api",
            external_season_id=202526,
            seasons=[S2526],
            season_mappings=fetch_provider_season_mappings(db, source="odds-api"),
        )
