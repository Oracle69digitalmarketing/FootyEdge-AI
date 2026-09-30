"""Canonical identity tests (stdlib-only, no network/DB)."""
import hashlib

from team_identity import (
    CANONICAL_TEAMS,
    LEGACY_TEAM_IDS,
    canonicalize_name,
    generate_canonical_id,
    is_canonical_id_for_name,
    is_legacy_id,
    resolve_canonical_id,
)

EXPECTED = {
    "Arsenal": 221659396777490,
    "Man City": 149534346580314,
    "Real Madrid": 83469380690940,
    "Barcelona": 6794002167939,
    "Liverpool": 116955586910447,
    "Bayern Munich": 18768778449461,
}


def test_canonical_teams_match_authoritative_ids():
    assert CANONICAL_TEAMS == EXPECTED
    for name, team_id in EXPECTED.items():
        assert generate_canonical_id(name) == team_id
        assert is_canonical_id_for_name(team_id, name)


def test_sha_algorithm_locked():
    for name, team_id in EXPECTED.items():
        assert team_id == int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:12], 16)
        assert 0 < team_id <= (16 ** 12) - 1


def test_canonicalize_whitespace():
    assert canonicalize_name("  Arsenal  ") == "Arsenal"
    assert canonicalize_name("Man   City") == "Man City"
    assert canonicalize_name("Real\tMadrid\n") == "Real Madrid"


def test_meaningful_words_preserved():
    assert canonicalize_name("Manchester United FC") == "Manchester United FC"
    assert "FC" in canonicalize_name("Arsenal FC")


def test_legacy_ids_rejected():
    for legacy in (101, 102, 103, 104, 105, 106, 10001, 10002, 10003, 10004):
        assert is_legacy_id(legacy)
    for team_id in EXPECTED.values():
        assert not is_legacy_id(team_id)
    assert LEGACY_TEAM_IDS == frozenset({101, 102, 103, 104, 105, 106, 10001, 10002, 10003, 10004})


def test_resolve_never_returns_legacy():
    for raw in ["Arsenal", "  Arsenal ", "Man   City", "Barcelona"]:
        _name, team_id = resolve_canonical_id(raw)
        assert not is_legacy_id(team_id)


def test_alias_resolution_evidence_based():
    name, team_id = resolve_canonical_id("Man Utd", aliases={"Man Utd": "Manchester United"})
    assert name == "Manchester United"
    assert team_id == generate_canonical_id("Manchester United")
    # Without evidence, similar names stay distinct.
    a = resolve_canonical_id("Nottm Forest")
    b = resolve_canonical_id("Nottingham Forest")
    assert a != b


def test_unknown_entity_gets_stable_new_canonical():
    first = resolve_canonical_id("Nigeria")
    second = resolve_canonical_id("  Nigeria ")
    assert first == second
    assert first[1] == generate_canonical_id("Nigeria")


def test_empty_name_rejected():
    import pytest

    for bad in ("", "   ", "\t\n"):
        try:
            canonicalize_name(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")
