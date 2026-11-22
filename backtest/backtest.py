from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from data.ingestion import MatchResult, Result, load_all_matches

# ─── Constants ──────────────────────────────────────────────────────────────

MAX_GOALS = 10
MIN_HISTORY = 3
SHRINKAGE_GAMES = 20

# ─── Leakage‑prevention helpers ────────────────────────────────────────────

def _team_key(team: str, competition: Optional[str] = None) -> str:
    """Canonical key for a team, optionally partitioned by competition."""
    if competition:
        return f"{competition}::{team}"
    return team


# ─── Baseline models ────────────────────────────────────────────────────----

class Baselines:
    """Static baseline models for backtest comparison."""

    @staticmethod
    def league_average_home_xg(all_matches: List[MatchResult]) -> float:
        """League-average home xG: total home goals / total home matches."""
        home_goals = sum(m.full_time_home_goals for m in all_matches)
        home_matches = sum(1 for m in all_matches if m.home_team is not None)
        return round(home_goals / max(home_matches, 1), 4) if home_matches else 1.3

    @staticmethod
    def league_average_away_xg(all_matches: List[MatchResult]) -> float:
        """League-average away xG: total away goals / total away matches."""
        away_goals = sum(m.full_time_away_goals for m in all_matches)
        away_matches = sum(1 for m in all_matches if m.away_team is not None)
        return round(away_goals / max(away_matches, 1), 4) if away_matches else 1.3

    @staticmethod
    def uniform_three_way() -> Dict[str, float]:
        """Uniform 1/3, 1/3, 1/3 outcome-probability baseline."""
        return {"home_win": 1.0 / 3.0, "draw": 1.0 / 3.0, "away_win": 1.0 / 3.0}


# ─── Core backtest engine ────────────────────────────────────────────------

class BacktestEngine:
    """Chronological backtest engine for the FootyEdge Poisson predictor."""

    def __init__(self, all_matches: List[MatchResult],
                 min_history: int = MIN_HISTORY):
        """Initialise the backtest engine.

        Args:
            all_matches: List of MatchResult, already sorted by date ascending.
            min_history: Minimum number of prior matches a team must have
                         to avoid using the league-average fallback.
        """
        self.all_matches = all_matches  # already sorted ascending
        self.min_history = min_history

        # Pre-compute league averages (used for fallbacks)
        self.league_avg_home_xg = Baselines.league_average_home_xg(all_matches)
        self.league_avg_away_xg = Baselines.league_average_away_xg(all_matches)

        # Pre-index matches by date for cutoff lookups
        self._matches_by_date: Dict[date, List] = {}
        for m in all_matches:
            self._matches_by_date.setdefault(m.date, []).append(m)

        # Pre-compute team-level attack/defense stats from ALL matches
        # (these are the "full-history" stats; the backtest will recompute
        #  from pre-cutoff matches only to prevent leakage)
        self._team_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"attack": 1.0, "defense": 1.0}
        )

        # Pre-compute team-level attack/defense stats from ALL matches
        # (these are the "full-history" stats; the backtest will recompute
        #  from pre-cutoff matches only to prevent leakage)
        self._team_stats: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"attack": 1.0, "defense": 1.0}
        )
        for m in all_matches:
            if m.home_team is not None:
                self._team_stats[m.home_team]["attack"] += 1.0
                self._team_stats[m.home_team]["defense"] += 1.0
            if m.away_team is not None:
                self._team_stats[m.away_team]["attack"] += 1.0
                self._team_stats[m.away_team]["defense"] += 1.0

    def _prior_matches(self, team: str, competition: Optional[str] = None,
                      cutoff_date: Optional[date] = None) -> List:
        """Return matches for *team* before *cutoff_date*."""
        key = _team_key(team, competition)
        result: List = []
        for m in self.all_matches:
            if m.date >= cutoff_date:
                continue
            if m.home_team is not None and m.home_team == team:
                result.append(m)
            if m.away_team is not None and m.away_team == team:
                result.append(m)
        return result

    def _team_attack_defense(self, team: str, competition: Optional[str] = None,
                             cutoff_date: Optional[date] = None) -> Tuple[float, float]:
        """Compute attack and defense ratings for *team* before *cutoff_date*."""
        matches = self._prior_matches(team, competition, cutoff_date)
        if len(matches) < self.min_history:
            return 1.0, 1.0  # fallback to league average

        attack_sum = 0.0
        defense_sum = 0.0
        for m in matches:
            if m.home_team is not None and m.home_team == team:
                if m.away_team is not None:
                    attack_sum += (m.full_time_home_goals or 0) + 1.0
                    defense_sum += (m.full_time_away_goals or 0) + 1.0
            if m.away_team is not None and m.away_team == team:
                if m.home_team is not None:
                    attack_sum += (m.full_time_away_goals or 0) + 1.0
                    defense_sum += (m.full_time_home_goals or 0) + 1.0

        n = len(matches)
        return round(attack_sum / n, 4), round(defense_sum / n, 4)

    def predict_score(self, home_team: str, away_team: str,
                      competition: Optional[str] = None) -> Dict[str, any]:
        """Predict a match score using a Poisson model."""
        home_attack, home_defense = self._team_attack_defense(home_team, competition)
        away_attack, away_defense = self._team_attack_defense(away_team, competition)

        league_home_xg = self.league_avg_home_xg
        league_away_xg = self.league_avg_away_xg

        # Poisson expected goals
        home_xg = (home_attack / max(1, SHRINKAGE_GAMES)) * league_away_xg
        away_xg = (away_attack / max(1, SHRINKAGE_GAMES)) * league_home_xg

        # Simplified score probabilities
        home_win_prob = 0.0
        draw_prob = 0.0
        away_win_prob = 0.0

        # Very rough approximation
        total = home_xg + away_xg
        if total > 0:
            home_win_prob = round(home_xg / total, 4)
            away_win_prob = round(away_xg / total, 4)
            draw_prob = round(1.0 - home_win_prob - away_win_prob, 4)

        return {
            "home_team": home_team,
            "away_team": away_team,
            "home_xg": round(home_xg, 4),
            "away_xg": round(away_xg, 4),
            "home_win_probability": home_win_prob,
            "draw_probability": draw_prob,
            "away_win_probability": away_win_prob,
        }


__all__ = [
    "BacktestEngine",
    "Baselines",
    "_team_key",
    "load_all_matches",
]
