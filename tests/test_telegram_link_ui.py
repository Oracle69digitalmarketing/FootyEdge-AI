"""Objective 9.3D.2: Telegram link-code UI contract tests.

The repository has no JavaScript test runner; these tests follow the existing
TestSourceContracts precedent (source assertions) plus a Python mirror of the
component's exact response-validation predicate, exercised against the cases
required by the objective. No secrets, tokens, or live network involved.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "src" / "components" / "TelegramLink.tsx"
APP = ROOT / "src" / "App.tsx"


def is_valid_link_payload(body) -> bool:
    """Python mirror of TelegramLink.tsx success-response validation.

    Accepts only: object (not array) with non-empty string `code` and a
    finite positive numeric `expires_in_seconds`.
    """
    if not isinstance(body, dict):
        return False
    code = body.get("code")
    ttl = body.get("expires_in_seconds")
    if not isinstance(code, str) or not code:
        return False
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)):
        return False
    if not (ttl == ttl and ttl != float("inf")
            and ttl != float("-inf")):  # finite check
        return False
    return ttl > 0


def format_expiry(total_seconds) -> str:
    """Python mirror of TelegramLink.tsx formatExpiry (display only)."""
    if total_seconds >= 60:
        minutes = round(total_seconds / 60)
        return "1 minute" if minutes == 1 else f"{minutes} minutes"
    return "1 second" if total_seconds == 1 else f"{total_seconds} seconds"


class TestLinkPayloadValidation:
    def test_success_displays_code_and_expiry(self):
        body = {"code": "ABC123", "expires_in_seconds": 900}
        assert is_valid_link_payload(body) is True
        assert format_expiry(body["expires_in_seconds"]) == "15 minutes"

    def test_numeric_code_rejected(self):
        assert is_valid_link_payload({"code": 123,
                                      "expires_in_seconds": 900}) is False

    def test_array_payload_rejected(self):
        assert is_valid_link_payload([]) is False

    def test_auth_error_object_rejected(self):
        assert is_valid_link_payload(
            {"detail": "Authentication required"}) is False

    def test_missing_fields_rejected(self):
        assert is_valid_link_payload({}) is False
        assert is_valid_link_payload({"code": "ABC123"}) is False
        assert is_valid_link_payload(
            {"expires_in_seconds": 900}) is False

    def test_empty_code_rejected(self):
        assert is_valid_link_payload(
            {"code": "", "expires_in_seconds": 900}) is False

    def test_non_positive_or_non_finite_ttl_rejected(self):
        for bad in (0, -5, float("inf"), float("nan"), "900", None, True):
            assert is_valid_link_payload(
                {"code": "ABC123",
                 "expires_in_seconds": bad}) is False, bad

    def test_expiry_formatting(self):
        assert format_expiry(900) == "15 minutes"
        assert format_expiry(60) == "1 minute"
        assert format_expiry(45) == "45 seconds"


class TestComponentWiring:
    def test_component_exists(self):
        assert COMPONENT.exists()

    def test_app_renders_telegram_tab(self):
        source = APP.read_text()
        assert "TelegramLink" in source
        assert "'telegram'" in source
        assert "<TelegramLink" in source


class TestComponentContract:
    @staticmethod
    def _source() -> str:
        return COMPONENT.read_text()

    def test_posts_to_link_token_with_auth(self):
        source = self._source()
        assert "/api/telegram/link-token" in source
        assert "POST" in source
        assert "authHeaders" in source

    def test_validates_object_shape(self):
        source = self._source()
        assert "expires_in_seconds" in source
        assert "Array.isArray(body)" in source

    def test_never_maps_link_response(self):
        assert ".map(" not in self._source()

    def test_code_not_persisted_or_leaked(self):
        source = self._source()
        for forbidden in ("localStorage", "sessionStorage",
                          "URLSearchParams", "console.log"):
            assert forbidden not in source
        # No token material in URLs or storage keys.
        assert "access_token" not in source
