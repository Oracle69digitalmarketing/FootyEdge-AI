"""Objective 6A: canonical competition/season resolver tests (offline only).

No network, no database, no live provider APIs. Registries, mappings, and
membership are plain caller-supplied data mirroring the repository schema
(001: competitions.code UNIQUE, seasons.label UNIQUE).
"""
import ast
import copy
import inspect
from pathlib import Path

import pytest

import competition_provenance as cp
from competition_provenance import (
    CompetitionIdentityConflictError,
    CompetitionIdentityError,
    CompetitionSeasonResolution,
    UnknownCompetitionIdentityError,
    resolve_competition,
    resolve_competition_season,
    resolve_season,
)

_REPO = Path(__file__).resolve().parent.parent
_MODULE_SRC = (_REPO / "competition_provenance.py").read_text()

EPL = {"id": 1, "code": "ENG-Premier League", "name": "Premier League"}
LA_LIGA = {"id": 2, "code": "ESP-La Liga", "name": "La Liga"}
S2526 = {"id": 10, "label": "2025/26", "start_year": 2025, "end_year": 2026}
S2425 = {"id": 11, "label": "2024/25", "start_year": 2024, "end_year": 2025}

COMPETITIONS = [EPL, LA_LIGA]
SEASONS = [S2526, S2425]
MEMBERSHIP = [(1, 10), (1, 11), (2, 10)]

COMP_MAPPINGS = [
    {"source": "odds-api", "external_competition_id": "soccer_epl", "competition_id": 1},
]
SEASON_MAPPINGS = [
    {"source": "odds-api", "external_season_id": "2025-26", "season_id": 10},
]


def _resolve_canonical():
    return resolve_competition_season(
        competition_code="ENG-Premier League",
        season_label="2025/26",
        competitions=COMPETITIONS,
        seasons=SEASONS,
        membership=MEMBERSHIP,
    )


# 1. Valid canonical competition + season resolution
def test_valid_canonical_resolution():
    res = _resolve_canonical()
    assert res == CompetitionSeasonResolution(
        competition_id=1,
        competition_code="ENG-Premier League",
        season_id=10,
        season_label="2025/26",
    )


# 2. Valid provider mapping resolution
def test_valid_provider_mapping_resolution():
    res = resolve_competition_season(
        source="odds-api",
        external_competition_id="soccer_epl",
        external_season_id="2025-26",
        competitions=COMPETITIONS,
        seasons=SEASONS,
        competition_mappings=COMP_MAPPINGS,
        season_mappings=SEASON_MAPPINGS,
        membership=MEMBERSHIP,
    )
    assert (res.competition_id, res.season_id) == (1, 10)
    # Canonical spelling comes from the registry, never provider text.
    assert res.competition_code == "ENG-Premier League"
    assert res.season_label == "2025/26"


# 3. Unknown provider competition
def test_unknown_provider_competition():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            source="odds-api",
            external_competition_id="soccer_unknown",
            external_season_id="2025-26",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            competition_mappings=COMP_MAPPINGS,
            season_mappings=SEASON_MAPPINGS,
            membership=MEMBERSHIP,
        )


# 4. Unknown provider season
def test_unknown_provider_season():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            source="odds-api",
            external_competition_id="soccer_epl",
            external_season_id="1900-01",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            competition_mappings=COMP_MAPPINGS,
            season_mappings=SEASON_MAPPINGS,
            membership=MEMBERSHIP,
        )


# 5. Missing competition mapping (season resolves, competition absent)
def test_missing_competition_mapping():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            season_label="2025/26",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            membership=MEMBERSHIP,
        )


# 6. Missing season mapping (competition resolves, season absent)
def test_missing_season_mapping():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            competition_code="ENG-Premier League",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            membership=MEMBERSHIP,
        )


# 7. Ambiguous competition mapping
def test_ambiguous_competition_mapping():
    mappings = COMP_MAPPINGS + [
        {"source": "odds-api", "external_competition_id": "soccer_epl", "competition_id": 2},
    ]
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_competition(
            source="odds-api",
            external_competition_id="soccer_epl",
            competitions=COMPETITIONS,
            competition_mappings=mappings,
        )


# 8. Ambiguous season mapping
def test_ambiguous_season_mapping():
    mappings = SEASON_MAPPINGS + [
        {"source": "odds-api", "external_season_id": "2025-26", "season_id": 11},
    ]
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_season(
            source="odds-api",
            external_season_id="2025-26",
            seasons=SEASONS,
            season_mappings=mappings,
        )


# 9. Both exist individually but the relationship is invalid
def test_invalid_relationship_despite_valid_sides():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            competition_code="ESP-La Liga",
            season_label="2024/25",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            membership=MEMBERSHIP,  # (2, 11) absent
        )


def test_missing_membership_info_fails_closed():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            competition_code="ENG-Premier League",
            season_label="2025/26",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            membership=None,
        )


# 10. Conflicting provider identity
def test_conflicting_provider_and_canonical_identity():
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_competition_season(
            competition_code="ESP-La Liga",
            season_label="2025/26",
            source="odds-api",
            external_competition_id="soccer_epl",  # maps to EPL (1), not La Liga (2)
            external_season_id="2025-26",
            competitions=COMPETITIONS,
            seasons=SEASONS,
            competition_mappings=COMP_MAPPINGS,
            season_mappings=SEASON_MAPPINGS,
            membership=MEMBERSHIP,
        )


def test_mapping_to_nonexistent_canonical_id_conflicts():
    mappings = [
        {"source": "odds-api", "external_competition_id": "soccer_epl", "competition_id": 999},
    ]
    with pytest.raises(CompetitionIdentityConflictError):
        resolve_competition(
            source="odds-api",
            external_competition_id="soccer_epl",
            competitions=COMPETITIONS,
            competition_mappings=mappings,
        )


# 11. Empty/null provider identity
@pytest.mark.parametrize("external_id", [None, ""])
def test_empty_provider_identity_resolves_nothing(external_id):
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition_season(
            source="odds-api",
            external_competition_id=external_id,
            external_season_id=external_id,
            competitions=COMPETITIONS,
            seasons=SEASONS,
            competition_mappings=COMP_MAPPINGS,
            season_mappings=SEASON_MAPPINGS,
            membership=MEMBERSHIP,
        )


def test_partial_provider_reference_fails_closed():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition(
            source="odds-api",
            competitions=COMPETITIONS,
            competition_mappings=COMP_MAPPINGS,
        )


def test_non_string_external_id_fails_closed_without_cast():
    with pytest.raises(TypeError):
        resolve_competition(
            source="odds-api",
            external_competition_id=39,
            competitions=COMPETITIONS,
            competition_mappings=COMP_MAPPINGS,
        )


# 12. Fails closed rather than guessing
def test_no_fuzzy_or_inferred_resolution():
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition(code="ENG-PremierLeague", competitions=COMPETITIONS)
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_competition(code="premier league", competitions=COMPETITIONS)
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_season(label="2025-26", seasons=SEASONS)
    with pytest.raises(UnknownCompetitionIdentityError):
        resolve_season(label="2025/26 ", seasons=SEASONS)
    # No date/fixture inference surface exists on the resolver.
    params = set(inspect.signature(resolve_competition_season).parameters)
    assert not (params & {"date", "match_date", "fixture", "fixture_id", "home_team", "away_team"})


def test_errors_are_value_errors():
    assert issubclass(UnknownCompetitionIdentityError, CompetitionIdentityError)
    assert issubclass(CompetitionIdentityConflictError, CompetitionIdentityError)
    assert issubclass(CompetitionIdentityError, ValueError)


# 13. Resolver does not create canonical records
def test_resolver_is_read_only_over_inputs():
    competitions = copy.deepcopy(COMPETITIONS)
    seasons = copy.deepcopy(SEASONS)
    comp_mappings = copy.deepcopy(COMP_MAPPINGS)
    season_mappings = copy.deepcopy(SEASON_MAPPINGS)
    membership = copy.deepcopy(MEMBERSHIP)
    _resolve_canonical()
    resolve_competition_season(
        source="odds-api",
        external_competition_id="soccer_epl",
        external_season_id="2025-26",
        competitions=competitions,
        seasons=seasons,
        competition_mappings=comp_mappings,
        season_mappings=season_mappings,
        membership=membership,
    )
    assert competitions == COMPETITIONS
    assert seasons == SEASONS
    assert comp_mappings == COMP_MAPPINGS
    assert season_mappings == SEASON_MAPPINGS
    assert membership == MEMBERSHIP
    module_ast = ast.parse(_MODULE_SRC)
    called = set()
    for node in ast.walk(module_ast):
        if isinstance(node, ast.Attribute):
            called.add(node.attr)
    # Write paths are forbidden everywhere; select+execute reads are allowed
    # only for the 6B retrieval layer (fetch_provider_*_mappings).
    assert not (called & {"insert", "upsert", "update", "delete", "create"})
    for node in ast.walk(module_ast):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("fetch_"):
            body_attrs = {n.attr for n in ast.walk(node)
                          if isinstance(n, ast.Attribute)}
            assert "execute" not in body_attrs, node.name


# 14. Deterministic
def test_resolver_is_deterministic():
    first = _resolve_canonical()
    second = resolve_competition_season(
        season_label="2025/26",
        competition_code="ENG-Premier League",
        seasons=list(reversed(SEASONS)),
        competitions=list(reversed(COMPETITIONS)),
        membership=list(reversed(MEMBERSHIP)),
    )
    assert first == second
    assert hash(first) == hash(second)


# 15. Objective 5 fixture identity behavior remains unaffected
def test_objective5_fixture_provenance_unaffected():
    from fixture_provenance import record_fixture_provenance

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
        def __init__(self, table, row):
            self._table = table
            self._row = row

        def execute(self):
            self._table.rows.append(dict(self._row))
            return _Result([dict(self._row)])

    class _Table:
        def __init__(self):
            self.rows = []

        def select(self, _cols):
            return _Query(self)

        def insert(self, row):
            return _Insert(self, row)

    class _Db:
        def __init__(self):
            self._t = {"match_provider_identity": _Table()}

        def table(self, name):
            return self._t[name]

    db = _Db()
    row = record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    assert row["match_id"] == 10
    repeat = record_fixture_provenance(
        db, source="odds-api", external_match_id="EVENT-123", match_id=10)
    assert repeat["match_id"] == 10
    assert len(db.table("match_provider_identity").rows) == 1
    # Competition module is a separate namespace: no fixture/team writes.
    assert "match_provider_identity" not in _MODULE_SRC
    assert "team_identity_sources" not in _MODULE_SRC
