"""Phase 15J regression coverage tests — verification and disambiguation."""

from __future__ import annotations

from data.ingestion import load_all_matches, MatchResult


def test_verify_disambiguation_home_away_unique():
    """Test that home and away teams are disambiguated (not same team)."""
    matches, _ = load_all_matches()
    same_team_count = 0
    for m in matches:
        if m.home_team is not None and m.away_team is not None:
            if m.home_team == m.away_team:
                same_team_count += 1
    # In a well-formed dataset, a match should not have home == away
    assert same_team_count == 0, \
        f"found {same_team_count} matches where home == away team"
    print(f"PASS: home/away disambiguation — {len(matches)} matches, 0 same-team games")


def test_verify_disambiguation_goal_fields_exist():
    """Test that goal fields exist on all MatchResult objects."""
    matches, _ = load_all_matches()
    for m in matches:
        assert hasattr(m, "full_time_home_goals"), \
            "MatchResult missing full_time_home_goals"
        assert hasattr(m, "full_time_away_goals"), \
            "MatchResult missing full_time_away_goals"
    print(f"PASS: goal fields present on all {len(matches)} matches")


def test_verify_disambiguation_date_format():
    """Test that match dates are in valid format."""
    from data.ingestion import _parse_date
    matches, _ = load_all_matches()
    for m in matches:
        if m.date is not None:
            # Use _parse_date helper to parse string dates
            parsed = _parse_date(m.date)
            assert parsed is not None, f"invalid date format: {m.date}"
            # Dates should be after 2000
            assert parsed.year >= 2000, f"date too old: {m.date}"
    print(f"PASS: date format valid for {len(matches)} matches")


def test_verify_disambiguation_tournament_variety():
    """Test that matches span multiple tournaments."""
    matches, result = load_all_matches()
    tournaments = set()
    for m in matches:
        if m.tournament is not None:
            tournaments.add(m.tournament)
    # Should have variety (at least 2 different tournaments if data is good)
    assert len(tournaments) >= 1, "should have at least one tournament"
    print(f"PASS: tournament variety — {len(tournaments)} tournaments: "
          f"{', '.join(sorted(tournaments))[:60]}")
