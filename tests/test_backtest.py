"""Phase 15J regression coverage tests — backtest functionality."""

from __future__ import annotations

import numpy as np
from datetime import date

from data.ingestion import load_all_matches, MatchResult, Result


def test_backtest_loads_matches():
    """Test that load_all_matches returns valid MatchResult objects."""
    matches, result = load_all_matches()
    assert isinstance(matches, list), "load_all_matches should return a list"
    assert len(matches) > 0, "should have matches from CSV"
    assert result.date_range[0] <= result.date_range[1], "date range is inverted"
    print(f"PASS: {len(matches)} matches loaded, period {result.date_range[0]} – {result.date_range[1]}")


def test_backtest_chronological_order():
    """Test that matches are in chronological ascending order."""
    matches, _ = load_all_matches()
    dates = [m.date for m in matches]
    sorted_dates = sorted(dates)
    assert dates == sorted_dates, "matches must be chronologically sorted ascending"
    print("PASS: matches are in chronological ascending order")


def test_backtest_match_result_fields():
    """Test that MatchResult dataclass has expected fields."""
    matches, _ = load_all_matches()
    assert len(matches) > 0, "should have matches"
    m = matches[0]
    assert hasattr(m, "date"), "MatchResult should have date field"
    assert hasattr(m, "home_team"), "MatchResult should have home_team field"
    assert hasattr(m, "away_team"), "MatchResult should have away_team field"
    print("PASS: MatchResult has all expected fields")


def test_backtest_data_coverage():
    """Test that loaded matches provide reasonable data coverage."""
    matches, result = load_all_matches()
    assert result.loaded > 0, "should load matches successfully"
    assert result.errors == 0, "should have no parse errors"
    print(f"PASS: data coverage — {result.loaded} loaded, {result.errors} errors")
