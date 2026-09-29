"""P0 numerical tests for GoalDistributionAgent.calculate(h_xg, a_xg)."""
import math

import numpy as np
import pytest

from agents.goal_distribution_agent import GoalDistributionAgent


def test_finite_and_bounded_probabilities():
    dist = GoalDistributionAgent().calculate(1.6, 1.2)
    over_25 = dist.over_under["2.5"]
    for prob in (
        dist.home_win_prob,
        dist.draw_prob,
        dist.away_win_prob,
        over_25,
        dist.both_teams_score,
    ):
        assert math.isfinite(prob)
        assert 0.0 <= prob <= 1.0


def test_three_way_probabilities_sum_to_one():
    dist = GoalDistributionAgent().calculate(1.6, 1.2)
    total = dist.home_win_prob + dist.draw_prob + dist.away_win_prob
    assert total == pytest.approx(1.0, abs=1e-6)


def test_score_matrix_shape():
    default_dist = GoalDistributionAgent().calculate(1.6, 1.2)
    assert default_dist.score_matrix.shape == (10, 10)
    custom_dist = GoalDistributionAgent(max_goals=6).calculate(1.6, 1.2)
    assert custom_dist.score_matrix.shape == (6, 6)


def test_over_under_and_btts_invariants():
    dist = GoalDistributionAgent().calculate(1.6, 1.2)
    over_25 = dist.over_under["2.5"]
    under_25 = 1.0 - over_25
    assert 0.0 <= over_25 <= 1.0
    assert 0.0 <= under_25 <= 1.0
    assert 0.0 <= dist.both_teams_score <= 1.0
    assert over_25 + under_25 == pytest.approx(1.0)


def test_deterministic_repeatability():
    agent = GoalDistributionAgent()
    first = agent.calculate(1.6, 1.2)
    second = agent.calculate(1.6, 1.2)
    assert first.home_win_prob == pytest.approx(second.home_win_prob)
    assert first.draw_prob == pytest.approx(second.draw_prob)
    assert first.away_win_prob == pytest.approx(second.away_win_prob)
    assert first.over_under["2.5"] == pytest.approx(second.over_under["2.5"])
    assert first.both_teams_score == pytest.approx(second.both_teams_score)
    np.testing.assert_array_equal(first.score_matrix, second.score_matrix)
