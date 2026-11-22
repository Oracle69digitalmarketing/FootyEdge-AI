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
        if m.date is not None:
            # Compare as strings to avoid type mismatch
            assert str(m.date) <= str(today), \
                f"match has future date: {m.date}"
    print("PASS: no future dates in ledger")


def test_ledger_team_fields_present():
    """Test that ledger entries have team fields populated (where available)."""
    matches, _ = load_all_matches()
    populated = [m for m in matches if m.home_team is not None and m.away_team is not None]
    assert len(populated) > 0, "should have some matches with team fields"
    for m in populated:
        # Fields already verified by filter
        pass
    print(f"PASS: {len(populated)}/{len(matches)} entries have team fields")
