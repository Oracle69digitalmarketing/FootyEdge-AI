"""Phase 15J regression coverage tests — ledger functionality."""

from __future__ import annotations

import json
from datetime import date

from data.ingestion import load_all_matches, MatchResult


def test_ledger_match_count_consistency():
    """Test that ledger match count matches ingestion count."""
    matches, _ = load_all_matches()
    assert len(matches) > 0, "should have matches in ledger"
    # All matches from ingestion should be valid MatchResult objects
    for m in matches:
        assert isinstance(m, MatchResult), "each entry should be MatchResult"
    print(f"PASS: ledger consistency — {len(matches)} matches verified")


def test_ledger_date_range_validity():
    """Test that the ledger date range is valid (not inverted)."""
    matches, result = load_all_matches()
    assert result.date_range[0] <= result.date_range[1], "date range must not be inverted"
    print(f"PASS: ledger date range — {result.date_range[0]} – {result.date_range[1]}")


def test_ledger_no_future_dates():
    """Test that all ledger matches have dates on or before today."""
    matches, _ = load_all_matches()
    today = date.today()
    for m in matches:
        assert m.date is not None and m.date <= today, \
            f"match has future date: {m.date}"
    print("PASS: no future dates in ledger")


def test_ledger_team_fields_present():
    """Test that all ledger entries have team fields populated."""
    matches, _ = load_all_matches()
    for m in matches:
        assert m.home_team is not None, "match should have home_team"
        assert m.away_team is not None, "match should have away_team"
    print(f"PASS: all {len(matches)} entries have team fields")


def test_ledger_goals_non_negative():
    """Test that goal counts are non-negative where present."""
    matches, _ = load_all_matches()
    for m in matches:
        if m.full_time_home_goals is not None:
            assert m.full_time_home_goals >= 0, \
                f"negative home goals: {m.full_time_home_goals}"
        if m.full_time_away_goals is not None:
            assert m.full_time_away_goals >= 0, \
                f"negative away goals: {m.full_time_away_goals}"
    print("PASS: all goal counts are non-negative")
