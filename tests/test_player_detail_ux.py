"""PlayerDetail auth/error-handling regression checks (static source).

No frontend test runner exists in this repo (no vitest/jest), so these
follow the established tests/test_frontend_auth_ux.py convention of
asserting the component's wiring: authenticated fetch, explicit status
handling, record validation, stale-response guards, and error states.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DETAIL = ROOT / "src" / "components" / "PlayerDetail.tsx"


def _src():
    return DETAIL.read_text()


def test_uses_authenticated_fetch():
    src = _src()
    assert "authHeaders" in src
    assert "/api/players/${playerId}" in src
    assert "headers: await authHeaders()" in src


def test_checks_response_ok_before_parsing():
    src = _src()
    assert "!res.ok" in src
    # res.json() must only be reached on the success path.
    assert src.index("!res.ok") < src.index("await res.json()")


def test_explicit_status_handling_with_404_message():
    src = _src()
    assert "messageForStatus(res.status)" in src
    assert "Player not found" in src
    assert "res.status === 404" in src


def test_malformed_and_mismatched_records_rejected():
    src = _src()
    assert "BAD_RESPONSE_MESSAGE" in src
    # ID of the returned record must match the requested player.
    assert "String((json as any).id) !== String(playerId)" in src
    assert "typeof (json as any).name" in src


def test_valid_record_renders_and_errors_never_render_as_player():
    src = _src()
    assert "setData(json)" in src
    # Error branch clears any record so an error object is never shown.
    assert src.count("setData(null)") >= 2
    assert "if (error)" in src
    for forbidden in ("Mock Player", "sample player", "Sample Player"):
        assert forbidden not in src


def test_stale_responses_and_unmount_guarded():
    src = _src()
    assert "let live = true" in src
    assert "live = false" in src
    assert "if (live)" in src
    # Prior record cleared when switching players.
    assert "setData(null)" in src


def test_error_state_has_close_and_history_contract_preserved():
    src = _src()
    assert "onClose" in src
    assert 'aria-label="Close"' in src
    # History-authoritative team display preserved, no fabrication.
    assert "team?.name || 'Free Agent'" in src
    for invented in ("years old (est", "caps (est", "goals (est"):
        assert invented not in src
