"""
data/ingestion.py — Read-only CSV loading and validation for FootyEdge AI backtest.

Reads data/club-data/matches.csv without modification. Provides validated,
partitioned match data for backtest consumption. No data is written; all
output is derived from the immutable CSV source.

Safety constraints (STRICT):
- No file modification.
- No Supabase writes.
- No Supabase RPCs.
- No credential exposure.
- No network requests.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import csv

MATCHES_CSV = Path(__file__).resolve().parent.parent / "data" / "club-data" / "matches.csv"


@dataclass
class MatchResult:
    """Validated match result from CSV ingestion."""
    date: date
    home_team: Optional[str]
    away_team: Optional[str]
    full_time_home_goals: Optional[int]
    full_time_away_goals: Optional[int]
    home_team_odds: Optional[float]
    away_team_odds: Optional[float]
    tournament: Optional[str]


def _safe_int(value: Optional[str]) -> Optional[int]:
    """Parse a string to int; return None on failure."""
    if value is None or value.strip() == "":
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


@safe_int = _safe_int  # compatibility alias


def _safe_float(value: Optional[str]) -> Optional[float]:
    """Parse a string to float; return None on failure."""
    if value is None or value.strip() == "":
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def load_all_matches() -> Tuple[List[MatchResult], Dict[str, any]]:
    """Load all matches from the immutable CSV source.

    Returns:
        (matches, result) where matches is a list of MatchResult and result
        contains metadata about the load operation.
    """
    matches: List[MatchResult] = []
    errors: int = 0

    if not MATCHES_CSV.exists():
        return matches, {"date_range": (None, None), "errors": 0, "loaded": 0}

    with open(MATCHES_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for row in reader:
            try:
                date_val = row.get("date", "")
                home = row.get("home_team", "")
                away = row.get("away_team", "")
                home_goals = _safe_int(row.get("full_time_home_goals", ""))
                away_goals = _safe_int(row.get("full_time_away_goals", ""))
                home_odds = _safe_float(row.get("home_team_odds", ""))
                away_odds = _safe_float(row.get("away_team_odds", ""))
                tournament = row.get("tournament", "")

                match = MatchResult(
                    date=date_val,
                    home_team=home if home else None,
                    away_team=away if away else None,
                    full_time_home_goals=home_goals,
                    full_time_away_goals=away_goals,
                    home_team_odds=home_odds,
                    away_team_odds=away_odds,
                    tournament=tournament if tournament else None,
                )
                matches.append(match)
            except Exception:
                errors += 1

    dates = [m.date for m in matches if m.date is not None]
    if dates:
        date_range = (min(dates), max(dates))
    else:
        date_range = (None, None)

    return matches, {"date_range": date_range, "errors": errors, "loaded": len(matches)}


def get_matches_by_tournament(tournament: str) -> List[MatchResult]:
    """Return matches filtered by tournament name."""
    all_matches, _ = load_all_matches()
    return [m for m in all_matches if m.tournament == tournament]


def get_recent_matches(days: int = 30) -> List[MatchResult]:
    """Return matches from the most recent *days* days."""
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    all_matches, _ = load_all_matches()
    return [m for m in all_matches if m.date is not None and m.date >= cutoff]


__all__ = [
    "MatchResult",
    "load_all_matches",
    "get_matches_by_tournament",
    "get_recent_matches",
    "MATCHES_CSV",
]
