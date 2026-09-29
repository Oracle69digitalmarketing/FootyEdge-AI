"""P0 numerical tests for KellyAgent.calculate_stake(probability, odds)."""
import pytest

from agents.kelly_agent import KellyAgent


def test_non_positive_edge_returns_zero():
    agent = KellyAgent()
    assert KellyAgent().calculate_stake(0.4, 2.0) == 0.0
    assert agent.calculate_stake(0.5, 1.9) == 0.0


def test_positive_fractional_kelly_results():
    agent = KellyAgent()
    assert agent.calculate_stake(0.6, 2.0) == pytest.approx(5.0)
    assert agent.calculate_stake(0.55, 2.5) == pytest.approx(6.25)


def test_invalid_degenerate_inputs_return_zero():
    agent = KellyAgent()
    assert agent.calculate_stake(0.5, 1.0) == 0.0
    assert agent.calculate_stake(0.5, 0.5) == 0.0
    assert agent.calculate_stake(0, 2.0) == 0.0
    assert agent.calculate_stake(-0.1, 2.0) == 0.0


def test_deterministic_repeatability():
    agent = KellyAgent()
    first = agent.calculate_stake(0.6, 2.0)
    second = agent.calculate_stake(0.6, 2.0)
    assert first == second
