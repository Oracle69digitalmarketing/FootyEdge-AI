"""Objective 5: Odds API fixture provenance tests (stub Supabase only).

Offline: no network, no database, no live Odds API credentials.
Covers schema/contract, persistence, namespace protection, existing
identity, and numerical invariance per the objective spec.
"""
import ast
from pathlib import Path

import pytest

from team_identity import (
    CANONICAL_TEAMS,
    UnknownTeamIdentityError,
    resolve_canonical_id_db,
)
from fixture_provenance import (
    ODDS_API_SOURCE,
    FixtureProvenanceConflictError,
    extract_odds_event_id,
    record_fixture_provenance,
    resolve_and_record_odds_event,
)

_REPO = Path(__file__).resolve().parent.parent
_MIGRATION = _REPO / "supabase_migrations" / "002_match_provider_identity.sql"
_MODULE_SRC = (_REPO / "fixture_provenance.py").read_text()

ARSENAL = CANONICAL_TEAMS["Arsenal"]
MAN_CITY = CANONICAL_TEAMS["Man City"]
MATCH_DATE = "2026-04-01T15:00:00+00:00"


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

    def upsert(self, row, **_kwargs):
        return _Insert(self, row)


class StubSupabase:
    def __init__(self, teams=(), aliases=(), mappings=(), matches=(), provenance=()):
        self._tables = {
            "teams": _Table(teams),
            "team_aliases": _Table(aliases),
            "team_identity_sources": _Table(mappings),
            "matches": _Table(matches),
            "match_provider_identity": _Table(provenance),
        }

    def table(self, name):
        return self._tables[name]


def _canon_db(matches=(), provenance=()):
    return StubSupabase(
        teams=[{"id": ARSENAL, "name": "Arsenal"}, {"id": MAN_CITY, "name": "Man City"}],
        matches=matches,
        provenance=provenance,
    )


def _match_row(match_id=10):
    return {
        "id": match_id,
        "home_team_id": ARSENAL,
        "away_team_id": MAN_CITY,
        "match_date": MATCH_DATE,
    }


# --- Schema/contract (spec items 1-3) ---


def test_migration_contract_columns_and_uniqueness():
    sql = _MIGRATION.read_text()
    assert "match_id" in sql
    assert "source" in sql
    assert "external_match_id" in sql
    assert "UNIQUE (source, external_match_id)" in sql
    assert "match_provider_identity_source_external_key" in sql


def test_migration_external_match_id_is_text():
    sql = _MIGRATION.read_text()
    assert "external_match_id TEXT" in sql
    for forbidden in ("external_match_id INT", "external_match_id BIGINT",
                      "external_match_id BIGSERIAL", "external_match_id UUID"):
        assert forbidden not in sql


def test_migration_fk_targets_matches_id():
    sql = _MIGRATION.read_text()
    assert "REFERENCES matches(id)" in sql
    assert "ON DELETE CASCADE" in sql
    assert "idx_match_provider_identity_match_id" in sql


def test_normalization_contract_preserved_in_provider_source():
    src = (_REPO / "football_api_client.py").read_text()
    assert '"id": m.get("id")' in src or '"id": m.get(\'id\')' in src
    assert '"date": m.get("commence_time")' in src or '"date": m.get(\'commence_time\')' in src
    assert '"home": {"name": home_team, "id": None' in src
    assert '"away": {"name": away_team, "id": None' in src


# --- Persistence (spec items 4-12) ---


def test_event_id_preserved_verbatim_and_source_and_match_id():
    db = _canon_db(matches=[_match_row(10)])
    row = resolve_and_record_odds_event(
        db,
        external_match_id="abc-XYZ-123",
        home_name="Arsenal",
        away_name="Man City",
        match_date=MATCH_DATE,
    )
    assert row["external_match_id"] == "abc-XYZ-123"
    assert type(row["external_match_id"]) is str
    assert row["source"] == "odds-api" == ODDS_API_SOURCE
    assert row["match_id"] == 10


def test_extract_odds_event_id_reads_normalized_fixture_verbatim():
    normalized = {"fixture": {"id": "evt-9f2K", "date": "2026-04-01T15:00:00Z"}}
    assert extract_odds_event_id(normalized) == "evt-9f2K"
    assert extract_odds_event_id({"fixture": {"id": None}}) is None
    assert extract_odds_event_id({"fixture": {"id": ""}}) is None
    assert extract_odds_event_id({}) is None


def test_missing_event_id_creates_no_mapping():
    db = _canon_db(matches=[_match_row(10)])
    assert resolve_and_record_odds_event(
        db, external_match_id=None, home_name="Arsenal",
        away_name="Man City", match_date=MATCH_DATE,
    ) is None
    assert record_fixture_provenance(
        db, source="odds-api", external_match_id=None, match_id=10,
    ) is None
    assert db.table("match_provider_identity").rows == []


def test_empty_event_id_creates_no_mapping():
    db = _canon_db(matches=[_match_row(10)])
    assert resolve_and_record_odds_event(
        db, external_match_id="", home_name="Arsenal",
        away_name="Man City", match_date=MATCH_DATE,
    ) is None
    assert db.table("match_provider_identity").rows == []


def test_repeat_same_mapping_is_idempotent():
    db = _canon_db(matches=[_match_row(10)])
    first = record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    second = record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    assert first["match_id"] == second["match_id"] == 10
    assert len(db.table("match_provider_identity").rows) == 1


def test_same_event_under_different_source_is_independent():
    db = _canon_db(matches=[_match_row(10)])
    record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    row = record_fixture_provenance(
        db, source="provider-b", external_match_id="EVENT-123", match_id=10)
    assert row["source"] == "provider-b"
    assert len(db.table("match_provider_identity").rows) == 2


def test_same_source_event_mapped_to_another_match_raises_conflict():
    db = _canon_db(matches=[_match_row(10), _match_row(11)])
    record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    with pytest.raises(FixtureProvenanceConflictError):
        record_fixture_provenance(
            db, source="odds-api", external_match_id="EVENT-123", match_id=11)


def test_no_overwrite_or_remap_after_conflict():
    db = _canon_db(matches=[_match_row(10), _match_row(11)])
    record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    with pytest.raises(FixtureProvenanceConflictError):
        record_fixture_provenance(
            db, source="odds-api", external_match_id="EVENT-123", match_id=11)
    rows = db.table("match_provider_identity").rows
    assert len(rows) == 1
    assert rows[0]["match_id"] == 10


def test_no_authoritative_match_id_writes_nothing():
    db = _canon_db()
    assert record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=None,
    ) is None
    assert db.table("match_provider_identity").rows == []


def test_unresolvable_fixture_writes_nothing_and_fabricates_no_match():
    db = _canon_db(matches=[])
    before = len(db.table("matches").rows)
    assert resolve_and_record_odds_event(
        db, external_match_id="EVENT-123", home_name="Arsenal",
        away_name="Man City", match_date=MATCH_DATE,
    ) is None
    assert len(db.table("matches").rows) == before
    assert db.table("match_provider_identity").rows == []


# --- Namespace protection (spec items 13-16) ---


def test_event_id_never_becomes_teams_id():
    db = _canon_db(matches=[_match_row(10)])
    team_ids_before = {r["id"] for r in db.table("teams").rows}
    resolve_and_record_odds_event(
        db, external_match_id="EVENT-99999", home_name="Arsenal",
        away_name="Man City", match_date=MATCH_DATE,
    )
    team_ids_after = {r["id"] for r in db.table("teams").rows}
    assert team_ids_before == team_ids_after
    assert all(str(tid) != "EVENT-99999" for tid in team_ids_after)


def test_event_id_never_becomes_team_external_team_id():
    db = _canon_db(matches=[_match_row(10)])
    resolve_and_record_odds_event(
        db, external_match_id="EVENT-99999", home_name="Arsenal",
        away_name="Man City", match_date=MATCH_DATE,
    )
    assert db.table("team_identity_sources").rows == []


def test_no_event_id_generated_from_team_names_and_no_integer_cast():
    module_ast = ast.parse(_MODULE_SRC)
    assert "hashlib" not in _MODULE_SRC
    assert "sha256" not in _MODULE_SRC
    assert "md5" not in _MODULE_SRC
    assert "external_team_id=" not in _MODULE_SRC
    assert 'table("team_identity_sources")' not in _MODULE_SRC
    assert "table('team_identity_sources')" not in _MODULE_SRC
    imported = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "hashlib" not in imported
    db = _canon_db(matches=[_match_row(10)])
    with pytest.raises(TypeError):
        record_fixture_provenance(
            db, source="odds-api", external_match_id=99999, match_id=10)
    assert db.table("match_provider_identity").rows == []


# --- Existing identity (spec items 17-18) ---


def test_team_identity_still_resolves_through_db_resolver():
    db = _canon_db(matches=[_match_row(10)])
    name, team_id = resolve_canonical_id_db("Arsenal", source="odds-api", supabase=db)
    assert (name, team_id) == ("Arsenal", ARSENAL)
    row = resolve_and_record_odds_event(
        db, external_match_id="EVENT-123", home_name="Arsenal",
        away_name="Man City", match_date=MATCH_DATE,
    )
    assert row["match_id"] == 10


def test_unknown_team_identity_fails_closed_without_minting():
    db = _canon_db(matches=[_match_row(10)])
    with pytest.raises(UnknownTeamIdentityError):
        resolve_and_record_odds_event(
            db, external_match_id="EVENT-123", home_name="Unknown XI",
            away_name="Man City", match_date=MATCH_DATE,
        )
    assert db.table("match_provider_identity").rows == []


def test_no_forced_persistence_in_live_predictor_path():
    predictor_src = (_REPO / "predictor.py").read_text()
    assert "match_provider_identity" not in predictor_src
    assert "find_all_value_bets" in predictor_src  # path still exists, untouched


# --- Numerical invariance (spec items 19-20) ---


def test_provenance_module_has_no_numerical_coupling():
    module_ast = ast.parse(_MODULE_SRC)
    imported = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"agents", "bet_selection", "predictor", "prediction_pipeline"})
    for token in ("poisson", "kelly", "xg", "probability", "ev_edge"):
        assert token not in _MODULE_SRC.lower()


def test_kelly_golden_output_unchanged():
    from agents.kelly_agent import KellyAgent
    agent = KellyAgent()
    assert agent.calculate_stake(0.6, 2.0) == pytest.approx(5.0)
    assert agent.calculate_stake(0.6, 2.0) == agent.calculate_stake(0.6, 2.0)
