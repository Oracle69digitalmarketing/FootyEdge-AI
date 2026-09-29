"""Pytest-only path setup: make the repository root importable.

Production code uses repository-root top-level imports (e.g.
``from agents.kelly_agent import KellyAgent``) and relies on the repo
root being on ``sys.path`` (as when running ``uvicorn api:app`` or
``python prediction_pipeline.py`` from the root). Pytest inserts the
test file's directory instead, so this minimal conftest prepends the
repository root for pytest collection. No application runtime impact.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
