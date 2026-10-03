"""Regression tests for generate_deterministic_id() team IDs.

The helper lives in prediction_pipeline.py, whose module-level imports
require the full application stack (soccerdata, supabase, ...). To keep
these tests dependency-free, the function's exact AST node is loaded
from the production file and executed in isolation with the real
team_identity policy injected -- no mocks, no reimplementation.

The pipeline shim must delegate to team_identity (no duplicated SHA-256
implementation); the canonical algorithm itself is locked by
tests/test_canonical_identity.py.
"""
import ast
from pathlib import Path

from team_identity import generate_canonical_id

PG_BIGINT_MIN = -(2 ** 63)
PG_BIGINT_MAX = 2 ** 63 - 1

_PIPELINE_PATH = Path(__file__).resolve().parent.parent / "prediction_pipeline.py"


def _load_generate_deterministic_id():
    source = _PIPELINE_PATH.read_text()
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "generate_deterministic_id":
            node_source = ast.get_source_segment(source, node)
            # No duplicated SHA implementation in the pipeline: delegation only.
            assert "sha256" not in node_source
            assert "hexdigest" not in node_source
            assert "generate_canonical_id" in node_source
            namespace = {"generate_canonical_id": generate_canonical_id}
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


def test_shim_matches_canonical_policy():
    for name in _SAMPLE_TEAMS:
        assert generate_deterministic_id(name) == generate_canonical_id(name)


def test_fixture_path_uses_db_resolver():
    source = _PIPELINE_PATH.read_text()
    module = ast.parse(source)
    run_node = next(
        node for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline"
    )
    run_source = ast.get_source_segment(source, run_node)
    assert "ensure_fixture_teams" in run_source
    assert "generate_deterministic_id(" not in run_source
