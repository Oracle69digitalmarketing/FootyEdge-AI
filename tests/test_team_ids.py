"""Regression tests for generate_deterministic_id() team IDs.

The helper lives in prediction_pipeline.py, whose module-level imports
require the full application stack (soccerdata, supabase, ...). To keep
these tests dependency-free, the function's exact AST node is loaded
from the production file and executed in isolation -- no mocks, no
reimplementation, and the SHA-256 algorithm itself is asserted present.
"""
import ast
import hashlib
from pathlib import Path

PG_BIGINT_MIN = -(2 ** 63)
PG_BIGINT_MAX = 2 ** 63 - 1

_PIPELINE_PATH = Path(__file__).resolve().parent.parent / "prediction_pipeline.py"


def _load_generate_deterministic_id():
    source = _PIPELINE_PATH.read_text()
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "generate_deterministic_id":
            # Lock the algorithm: SHA-256 hex digest, first 12 chars, base 16.
            node_source = ast.get_source_segment(source, node)
            assert "hashlib.sha256" in node_source
            assert "hexdigest" in node_source
            assert "16" in node_source
            namespace = {"hashlib": hashlib}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(_PIPELINE_PATH), "exec"), namespace)
            return namespace["generate_deterministic_id"]
    raise AssertionError("generate_deterministic_id not found in prediction_pipeline.py")


generate_deterministic_id = _load_generate_deterministic_id()

_SAMPLE_TEAMS = ["Arsenal", "Chelsea", "Barcelona", "Bayern Munich", "PSG"]


def test_same_input_produces_same_id():
    assert generate_deterministic_id("Arsenal") == generate_deterministic_id("Arsenal")


def test_return_type_is_int():
    for name in _SAMPLE_TEAMS:
        assert isinstance(generate_deterministic_id(name), int)


def test_id_is_positive():
    for name in _SAMPLE_TEAMS:
        assert generate_deterministic_id(name) > 0


def test_id_fits_postgresql_bigint():
    for name in _SAMPLE_TEAMS:
        team_id = generate_deterministic_id(name)
        assert PG_BIGINT_MIN <= team_id <= PG_BIGINT_MAX
    # Structural bound: 12 hex chars can never exceed BIGINT range.
    assert (16 ** 12) - 1 <= PG_BIGINT_MAX


def test_different_teams_produce_deterministic_ids():
    ids = [generate_deterministic_id(name) for name in _SAMPLE_TEAMS]
    assert len(set(ids)) == len(_SAMPLE_TEAMS)
    for name, team_id in zip(_SAMPLE_TEAMS, ids):
        assert team_id == generate_deterministic_id(name)
