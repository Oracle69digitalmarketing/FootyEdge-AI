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
    date: Optional[str] = None  # will be populated from MatchDate
    home_team: Optional[str] = None  # will be populated from HomeTeam
    away_team: Optional[str] = None  # will be populated from AwayTeam
    full_time_home_goals: Optional[int] = None  # will be populated from FTHome
    full_time_away_goals: Optional[int] = None  # will be populated from FTAway
    home_team_odds: Optional[float] = None  # will be populated from OddHome
    away_team_odds: Optional[float] = None  # will be populated from OddAway
    tournament: Optional[str] = None  # will be populated from tournament column


@dataclass
class Result:
    """Metadata result from load_all_matches()."""
    date_range: Tuple[Optional[str], Optional[str]]
    errors: int
    loaded: int


def _safe_int(value: Optional[str]) -> Optional[int]:
    """Parse a string to int; return None on failure."""
    if value is None or value.strip() == "":
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _safe_float(value: Optional[str]) -> Optional[float]:
    """Parse a string to float; return None on failure."""
    if value is None or value.strip() == "":
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


_CACHE: Optional[Tuple[List[MatchResult], Result]] = None


def clear_cache() -> None:
    """Test/utility hook: drop the in-memory CSV cache."""
    global _CACHE
    _CACHE = None


def load_all_matches() -> Tuple[List[MatchResult], Result]:
    """Load all matches from the immutable CSV source.

    Returns:
        (matches, result) where matches is a list of MatchResult and result
        contains metadata about the load operation.

    The 230K-row CSV is expensive to parse (~10s), so the parsed dataset is
    memoised in-process. The CSV is immutable (STRICT: no file modification),
    so caching never hides stale data.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    matches: List[MatchResult] = []
    errors: int = 0

    if not MATCHES_CSV.exists():
        return (matches, Result(date_range=(None, None), errors=0, loaded=0))

    with open(MATCHES_CSV, "r", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        for row in reader:
            try:
                date_val = row.get("MatchDate", "")
                home = row.get("HomeTeam", "")
                away = row.get("AwayTeam", "")
                home_goals = _safe_int(row.get("FTHome", ""))
                away_goals = _safe_int(row.get("FTAway", ""))
                home_odds = _safe_float(row.get("OddHome", ""))
                away_odds = _safe_float(row.get("OddAway", ""))
                tournament = row.get("tournament", row.get("Division", ""))

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

    _CACHE = (matches, Result(date_range=date_range, errors=errors, loaded=len(matches)))
    return _CACHE


def get_matches_by_tournament(tournament: str) -> List[MatchResult]:
    """Return matches filtered by tournament name."""
    all_matches, _ = load_all_matches()
    return [m for m in all_matches if m.tournament == tournament]


def _parse_date(value: Optional[str]):
    """Parse a YYYY-MM-DD string into a datetime.date, or None."""
    from datetime import date as _date
    if not value:
        return None
    try:
        _y, _m, _d = value.split("-")
        return _date(int(_y), int(_m), int(_d))
    except Exception:
        return None


def get_recent_matches(days: int = 30) -> List[MatchResult]:
    """Return matches from the most recent *days* days."""
    from datetime import date as _date, timedelta
    cutoff = _date.today() - timedelta(days=days)
    all_matches, _ = load_all_matches()
    return [m for m in all_matches if _parse_date(m.date) is not None and _parse_date(m.date) >= cutoff]


__all__ = [
    "MatchResult",
    "Result",
    "load_all_matches",
    "clear_cache",
    "get_matches_by_tournament",
    "get_recent_matches",
    "MATCHES_CSV",
]
