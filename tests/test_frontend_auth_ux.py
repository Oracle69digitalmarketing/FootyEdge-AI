"""Objective 9.3D.7: frontend auth/entitlement UX contracts.

Follows the repo's source-contract + logic-mirror precedent (no JS runner
present): static assertions over the TSX sources plus a Python mirror of
the exact HTTP-status classification table. No secrets, no network.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SIGNIN = SRC / "components" / "product" / "SignInCard.tsx"
API_ERROR = SRC / "lib" / "apiError.ts"
DASHBOARD = SRC / "pages" / "PredictionsDashboard.tsx"
VALUE_BETS = SRC / "components" / "ValueBets.tsx"
TEAMS = SRC / "components" / "TeamsList.tsx"
PLAYERS = SRC / "components" / "PlayersList.tsx"
ACCESS = SRC / "lib" / "access.ts"
APP = SRC / "App.tsx"

SESSION_EXPIRED = "Your session has expired. Please sign in again."
PLAN_FORBIDDEN = "Your current plan does not include this feature."
SERVICE_UNAVAILABLE = ("The service is temporarily unavailable. "
                       "Please try again later.")
CONNECTION_ERROR = ("Could not reach the server. Please check your "
                    "connection and try again.")


def classify_status(status: int) -> str:
    """Python mirror of apiError.ts messageForStatus()."""
    if status == 401:
        return SESSION_EXPIRED
    if status == 403:
        return PLAN_FORBIDDEN
    if status == 429:
        return "Too many requests. Please wait a moment and try again."
    if status >= 500:
        return SERVICE_UNAVAILABLE
    return f"Request failed (status {status}). Please try again later."


class TestStatusClassification:
    def test_401_is_session_expiry(self):
        assert classify_status(401) == SESSION_EXPIRED

    def test_403_is_plan_entitlement(self):
        assert classify_status(403) == PLAN_FORBIDDEN

    def test_401_and_403_differ(self):
        assert classify_status(401) != classify_status(403)

    def test_429_is_retry_later(self):
        assert "wait a moment" in classify_status(429)

    def test_5xx_is_unavailable(self):
        assert classify_status(500) == SERVICE_UNAVAILABLE
        assert classify_status(503) == SERVICE_UNAVAILABLE

    def test_other_status_is_generic_not_auth(self):
        assert "sign in" not in classify_status(404).lower()
        assert "404" in classify_status(404)

    def test_source_table_matches_mirror(self):
        source = API_ERROR.read_text()
        for marker in (SESSION_EXPIRED, PLAN_FORBIDDEN,
                       SERVICE_UNAVAILABLE, CONNECTION_ERROR,
                       "messageForStatus", "messageForFailure",
                       "isNetworkFailure"):
            assert marker in source, marker

    def test_components_share_one_classifier(self):
        for path in (DASHBOARD, VALUE_BETS, TEAMS, PLAYERS):
            assert "messageForStatus" in path.read_text(), path.name


class TestSignupUx:
    @staticmethod
    def _source() -> str:
        return SIGNIN.read_text()

    def test_duplicate_submission_prevented(self):
        source = self._source()
        assert "if (busy) return;" in source
        assert "disabled={busy" in source

    def test_loading_state(self):
        assert "Loader2" in self._source()

    def test_session_signup_transitions(self):
        source = self._source()
        assert "data.session" in source
        assert "opening FootyEdge" in source

    def test_confirmation_guidance_without_session(self):
        source = self._source()
        assert "data.user" in source
        assert "Check your email to confirm your account" in source

    def test_signup_error_visible(self):
        source = self._source()
        assert 'role="alert"' in source
        assert "setError" in source

    def test_no_automatic_sign_in_after_signup(self):
        # Exactly one password sign-in call, in the sign-in branch only.
        assert self._source().count("signInWithPassword") == 1

    def test_notice_cleared_on_mode_toggle(self):
        assert "setNotice(null)" in self._source()


class TestDashboardResilience:
    @staticmethod
    def _source() -> str:
        return DASHBOARD.read_text()

    def test_per_feed_error_states(self):
        source = self._source()
        for marker in ("predError", "accaError", "ledgerError",
                       "setPredError", "setAccaError", "setLedgerError"):
            assert marker in source, marker

    def test_no_global_auth_blanket(self):
        assert "fetchError" not in self._source()

    def test_acca_denial_is_plan_message(self):
        source = self._source()
        assert "messageForStatus(accaRes.status)" in source

    def test_predictions_survive_acca_rejection(self):
        # Independent branches: predictions state is set from its own
        # response regardless of the acca outcome (no shared early-return
        # that wipes all three feeds on one rejection).
        source = self._source()
        assert "setPredictions(parsed.data)" in source or \
            "setPredictions(" in source
        assert "const rejected = " not in source


class TestPlanPresentation:
    def test_no_starter_default_claim(self):
        for path in (ACCESS, APP):
            assert "Starter (default)" not in path.read_text(), path.name
        assert "(default)" not in ACCESS.read_text()

    def test_server_authority_disclosed(self):
        assert "server-gated" in APP.read_text()
        assert "checked server-side" in APP.read_text()

    def test_no_fabricated_paid_entitlement(self):
        assert "planIsPlaceholder" in APP.read_text()


class TestCrashSafety:
    def test_array_guards_on_every_list(self):
        for path in (DASHBOARD, VALUE_BETS, TEAMS, PLAYERS):
            assert "Array.isArray" in path.read_text(), path.name

    def test_no_truthy_object_into_array_state(self):
        for path in (DASHBOARD, VALUE_BETS, TEAMS, PLAYERS):
            assert "|| []" not in path.read_text(), path.name

    def test_acca_object_guard(self):
        source = DASHBOARD.read_text()
        assert "typeof accaData" in source
        assert "Array.isArray((accaData" in source

    def test_malformed_json_guarded(self):
        for path in (DASHBOARD, VALUE_BETS, TEAMS, PLAYERS):
            source = path.read_text()
            assert "BAD_RESPONSE_MESSAGE" in source, path.name
