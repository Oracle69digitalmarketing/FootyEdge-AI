"""Verify-only discovery contracts (offline only).

No network, no database, no live provider APIs, no credentials. The
provider transport is injected; every external ID in these fixtures is
an obvious fake (9001-9006) that is never claimed as a verified
production ID.
"""

import io
import json
import tokenize
from pathlib import Path

import pytest

import verify_apifootball_teams as vfy

_REPO = Path(__file__).resolve().parent.parent
_SRC = (_REPO / "verify_apifootball_teams.py").read_text()


def _code_only():
    out = []
    toks = tokenize.generate_tokens(io.StringIO(_SRC).readline)
    for tok, val, *_ in toks:
        if tok in (tokenize.COMMENT, tokenize.STRING):
            continue
        out.append(val)
    return "".join(out)


# Fixture provider IDs: obvious fakes, never production claims.
FIX_IDS = {
    "Arsenal": "9001",
    "Barcelona": "9002",
    "Bayern Munich": "9003",
    "Liverpool": "9004",
    "Manchester City": "9005",
    "Real Madrid": "9006",
}


def _search_row(pid, name):
    return {"team": {"id": int(pid), "name": name, "country": "Fixtureland"},
            "venue": {"id": 1, "name": "Fixture Arena"}}


def _squad(pid, name, n=3):
    return {"response": [{
        "team": {"id": int(pid), "name": name},
        "players": [{"id": 1000 + i, "name": f"{name} Player {i}",
                     "age": 25, "number": i, "position": "Midfielder",
                     "photo": None} for i in range(n)],
    }]}


def _ok_transport_factory(extra_search_rows=None, echo_override=None,
                          calls=None):
    extra_search_rows = extra_search_rows or {}
    echo_override = echo_override or {}

    def _transport(path, params, timeout):
        (calls if calls is not None else []).append((path, dict(params)))
        if path == "/status":
            return ({"response": {"subscription": {"plan": "Free"}},
                     "errors": []}, 200)
        if path == "/teams":
            term = params["search"]
            rows = [_search_row(FIX_IDS[term], term)]
            rows.extend(extra_search_rows.get(term, []))
            return {"response": rows, "errors": []}, 200
        if path == "/players/squads":
            team = params["team"]
            name = echo_override.get(team, next(
                n for n, pid in FIX_IDS.items() if pid == team))
            return _squad(team, name), 200
        raise AssertionError(f"unexpected provider path {path!r}")

    return _transport


@pytest.fixture
def _key(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "fixture-key-never-real")


# --- Structural write-incapability ---


def test_banner_identifies_verify_only():
    assert vfy.BANNER == "VERIFY-ONLY — NO DATABASE WRITES"
    assert vfy.BANNER in _SRC


def test_no_database_surface_exists():
    code = _code_only().lower()
    assert "supabase" not in code
    assert "create_client" not in code
    assert "table(" not in code
    # DB mutation verbs (dict.update is the only ".update" present and is
    # covered by the table-access ban above; still, no SQL verbs at all):
    for mutation in (".insert(", ".upsert(", ".delete(", "insert into",
                      "update ", "delete from"):
        assert mutation not in code
    assert "service_role" not in code
    assert "execute(" not in code


def test_key_value_never_leaves_the_process(capsys, _key):
    report = vfy.verify_teams(transport=_ok_transport_factory())
    assert report["status"] == "complete"
    print(json.dumps(report))
    out = capsys.readouterr().out
    assert "fixture-key-never-real" not in out


def test_targets_are_the_six_canonical_teams():
    assert [(n, i) for n, i, _ in vfy.TARGETS] == [
        ("Arsenal", 221659396777490),
        ("Barcelona", 6794002167939),
        ("Bayern Munich", 18768778449461),
        ("Liverpool", 116955586910447),
        ("Man City", 149534346580314),
        ("Real Madrid", 83469380690940),
    ]
    # Provider IDs appear NOWHERE in the module: they come only from live responses.
    assert "9001" not in _SRC
    for known in ("\"42\"", "\"529\"", "\"157\"", "\"40\"", "\"50\"", "\"541\""):
        assert known not in _SRC


# --- Fail-closed behavior (fixture-backed) ---


def test_full_pass_verifies_six_with_bounded_calls(_key):
    calls = []
    report = vfy.verify_teams(transport=_ok_transport_factory(calls=calls))
    assert report["status"] == "complete"
    assert report["verified"] == 6
    assert report["provider_calls_made"] == 13  # 1 status + 6 search + 6 squad
    assert len(calls) == 13
    for entry, (_, _, provider_name) in zip(report["teams"], vfy.TARGETS):
        assert entry["status"] == "verified"
        assert entry["provider_team_id"] == FIX_IDS[provider_name]
        assert entry["provider_team_name"] == provider_name
        assert entry["squad_count"] == 3


def test_main_entrypoint_without_credential(monkeypatch, capsys):
    # main() always uses the real transport; with no key it must stop
    # before any provider call and exit nonzero. The full-pass path is
    # covered via verify_teams() with an injected transport.
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    rc = vfy.main()
    assert rc == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "VERIFY-ONLY — NO DATABASE WRITES"
    assert '"status": "stopped"' in out


def test_ambiguous_search_stops_team_without_squad_call(_key):
    calls = []
    transport = _ok_transport_factory(
        extra_search_rows={"Arsenal": [_search_row(4242, "Arsenal")]},
        calls=calls)
    report = vfy.verify_teams(transport=transport)
    assert report["status"] == "partial"
    arsenal = next(t for t in report["teams"] if t["search_term"] == "Arsenal")
    assert arsenal["status"] == "stopped"
    assert "ambiguous" in arsenal["reason"]
    assert "provider_team_id" not in arsenal
    squad_calls = [c for c in calls if c[0] == "/players/squads"]
    assert len(squad_calls) == 5  # every team except Arsenal
    assert all(p["team"] != "9001" for _, p in squad_calls)


def test_missing_search_result_stops_team(_key):
    def _transport(path, params, timeout):
        if path == "/status":
            return ({"response": {}, "errors": []}, 200)
        if path == "/teams":
            return {"response": [_search_row(7, "Unrelated FC")], "errors": []}, 200
        raise AssertionError("no squad call allowed without exact match")

    report = vfy.verify_teams(transport=_transport)
    assert report["status"] == "partial"
    assert report["verified"] == 0
    assert all(t["status"] == "stopped" for t in report["teams"])


def test_squad_echo_mismatch_stops_team(_key):
    transport = _ok_transport_factory(echo_override={"9001": "Arsenal Reserves"})
    report = vfy.verify_teams(transport=transport)
    arsenal = next(t for t in report["teams"] if t["search_term"] == "Arsenal")
    assert arsenal["status"] == "stopped"
    assert "mismatch" in arsenal["reason"]
    assert report["status"] == "partial"


def test_rate_limited_search_stops_team(_key):
    def _transport(path, params, timeout):
        if path == "/status":
            return ({"response": {}, "errors": []}, 200)
        if path == "/teams":
            return ({"response": []}, 429)
        raise AssertionError("no squad call allowed after rate limit")

    report = vfy.verify_teams(transport=_transport)
    assert all(t["reason"] == "rate_limited" for t in report["teams"])


def test_missing_key_makes_zero_calls(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

    def _exploding(path, params, timeout):
        raise AssertionError("no provider call without credential")

    report = vfy.verify_teams(transport=_exploding)
    assert report["status"] == "stopped"
    assert report["key_present"] is False
    assert report["provider_calls_made"] == 0


def test_status_errors_stop_everything(_key):
    calls = []

    def _transport(path, params, timeout):
        calls.append(path)
        return ({"response": {}, "errors": {"plan": "blocked"}}, 200)

    report = vfy.verify_teams(transport=_transport)
    assert report["status"] == "stopped"
    assert calls == ["/status"]


# --- Non-wiring / scope guards ---


def test_not_wired_into_scheduler_cron_or_pipeline():
    assert "verify_apifootball" not in (_REPO / "api.py").read_text()
    assert "verify_apifootball" not in (_REPO / "prediction_pipeline.py").read_text()
    assert "verify_apifootball" not in (_REPO / "render.yaml").read_text()
    assert "verify_apifootball" not in (_REPO / "player_sync.py").read_text()
    render = (_REPO / "render.yaml").read_text()
    assert 'startCommand: "python prediction_pipeline.py"' in render


def test_report_contains_no_credential(_key):
    report = vfy.verify_teams(transport=_ok_transport_factory())
    assert "fixture-key-never-real" not in json.dumps(report)
    code = _code_only()
    assert code.count("API_FOOTBALL_KEY") <= 3  # KEY_VAR, presence check, message
