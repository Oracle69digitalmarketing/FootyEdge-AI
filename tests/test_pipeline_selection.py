"""P0 tests for prediction_pipeline.select_best_bet(potential_bets)."""
import pytest

from prediction_pipeline import select_best_bet


def test_no_bets_returns_none():
    assert select_best_bet([]) is None


def test_all_unpriced_bets_returns_none():
    candidates = [
        {"market": "3-Way Result", "sel": "Home Win", "prob": 0.55, "price": None},
        {"market": "3-Way Result", "sel": "Away Win", "prob": 0.20, "price": None},
        {"market": "Over/Under 2.5", "sel": "Over 2.5 Goals", "prob": 0.50, "price": None},
    ]
    assert select_best_bet(candidates) is None


def test_selects_same_best_bet_as_existing_logic():
    # EV edges: A: 0.60*1.80-1=0.08, B: 0.45*2.60-1=0.17, C: 0.52*2.00-1=0.04.
    # B wins on EV despite having the lowest raw probability.
    candidates = [
        {"market": "3-Way Result", "sel": "Home Win", "prob": 0.60, "price": 1.80},
        {"market": "3-Way Result", "sel": "Away Win", "prob": 0.45, "price": 2.60},
        {"market": "Over/Under 2.5", "sel": "Over 2.5 Goals", "prob": 0.52, "price": 2.00},
    ]
    result = select_best_bet(candidates)
    assert result is candidates[1]
    assert result["sel"] == "Away Win"


def test_mixed_priced_and_unpriced_bets():
    candidates = [
        {"market": "3-Way Result", "sel": "Home Win", "prob": 0.90, "price": None},
        {"market": "3-Way Result", "sel": "Away Win", "prob": 0.30, "price": 2.20},
        {"market": "Over/Under 2.5", "sel": "Over 2.5 Goals", "prob": 0.80, "price": 0.0},
    ]
    result = select_best_bet(candidates)
    assert result is candidates[1]
