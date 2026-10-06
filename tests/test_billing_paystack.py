"""8D payment tests: stdlib only, mocked provider transport, no network."""
import os

import pytest

import billing
from billing import (
    BillingError,
    BillingNotConfigured,
    CheckoutRequest,
    PaystackProvider,
    build_provisional_row,
    prepare_checkout,
    resolve_plan,
    validate_paystack_config,
)


class FakeTransport:
    """Stands in for Paystack HTTPS. Records what the server WOULD send."""

    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, url, *, headers, payload, timeout=20.0):
        assert "Bearer " in headers.get("Authorization", "")
        assert "sk_test_" not in str(payload) and "sk_live_" not in str(payload)
        self.posts.append({"url": url, "payload": dict(payload)})
        return {"authorization_url": "https://pay.test/authorize/abc",
                "reference": payload["reference"]}

    def get(self, url, *, headers, timeout=20.0):
        self.gets.append(url)
        return {"status": "success", "reference": "footyedge_x",
                "amount": 500000, "currency": "NGN",
                "plan": {"plan_code": "PLN_test_growth"}}


@pytest.fixture()
def env(monkeypatch):
    # Clearly fake, scanner-safe secrets (8.3 §25): the `sk_test_` /
    # `sk_live_` prefix is required so PAYSTACK_MODE validation can be
    # exercised, but underscore-separated short words guarantee no
    # 8+ consecutive alphanumeric run, so the repo's own secret-pattern
    # scan (and real scanners) will not flag them.
    monkeypatch.setenv("PAYSTACK_MODE", "test")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_unit_only_no_real_key")
    monkeypatch.setenv("PAYSTACK_GROWTH_PLAN_CODE", "PLN_test_growth")
    monkeypatch.setenv("PAYSTACK_BUSINESS_PLAN_CODE", "PLN_test_business")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    return monkeypatch


def provider(env):  # noqa: ARG001 - fixture ensures env, arg documents it
    t = FakeTransport()
    p = PaystackProvider(os.environ["PAYSTACK_SECRET_KEY"],
                         http_post=t.post, http_get=t.get)
    return p, t


# --- plan validation -------------------------------------------------------
def test_starter_rejected():
    with pytest.raises(BillingError):
        resolve_plan("starter")


def test_enterprise_rejected():
    with pytest.raises(BillingError):
        resolve_plan("enterprise")


def test_unknown_rejected():
    with pytest.raises(BillingError):
        resolve_plan("platinum")


def test_growth_business_accepted():
    assert resolve_plan("growth").plan == "growth"
    assert resolve_plan("business").plan == "business"


# --- price integrity -------------------------------------------------------
def test_server_pricing_kobo():
    assert resolve_plan("growth").amount_kobo == 500_000
    assert resolve_plan("business").amount_kobo == 1_500_000
    assert resolve_plan("growth").currency == "NGN"


def test_client_cannot_override_amount(env):
    p, t = provider(env)
    out = prepare_checkout(CheckoutRequest(user_id="u1", email="u@x.io",
                                           plan="growth"), provider=p)
    sent = t.posts[0]["payload"]
    assert sent["amount"] == 500_000  # server value, never client value
    assert sent["plan"] == "PLN_test_growth"  # env code, never client code
    assert "amount" not in out and "plan" in out  # safe response only


# --- authentication --------------------------------------------------------
def test_unauthenticated_rejected(env):
    p, _ = provider(env)
    with pytest.raises(BillingError) as exc:
        prepare_checkout(CheckoutRequest(user_id="", email="",
                                         plan="growth"), provider=p)
    assert exc.value.public == "Authentication required"


def test_identity_is_caller_supplied_server_side(env):
    """The orchestration layer uses the resolved identity it is given
    (the FastAPI boundary derives it from the verified JWT)."""
    p, t = provider(env)
    prepare_checkout(CheckoutRequest(user_id="auth-users-id-9",
                                     email="real@x.io", plan="business"),
                     provider=p)
    assert t.posts[0]["payload"]["email"] == "real@x.io"


# --- configuration fails closed --------------------------------------------
def test_missing_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("PAYSTACK_SECRET_KEY", raising=False)
    with pytest.raises(BillingError):
        billing.build_provider()


def test_missing_plan_code_fails_closed(env):
    env.delenv("PAYSTACK_BUSINESS_PLAN_CODE")
    p, _ = provider(env)
    with pytest.raises(BillingError) as exc:
        prepare_checkout(CheckoutRequest(user_id="u", email="u@x.io",
                                         plan="business"), provider=p)
    assert "PLN_" not in exc.value.public
    assert "sk_test" not in exc.value.public


def test_provider_errors_hide_internals(env):
    def bad_post(url, *, headers, payload, timeout=20.0):
        return {"status": False, "message": "Invalid key\nsecret=sk_live_X"}

    p = PaystackProvider(os.environ["PAYSTACK_SECRET_KEY"], http_post=bad_post,
                         http_get=FakeTransport().get)
    with pytest.raises(BillingError) as exc:
        prepare_checkout(CheckoutRequest(user_id="u", email="u@x.io",
                                         plan="growth"), provider=p)
    assert "sk_live" not in str(exc.value.public)
    assert "sk_live" not in str(exc.value)


# --- abstraction isolation --------------------------------------------------
def test_application_depends_on_interface(env):
    class LaterProvider(billing.PaymentProvider):
        name = "later"

        def initialize_subscription_checkout(self, *, email, config, reference):
            return billing.CheckoutResult(
                authorization_url="https://later.test/c", reference=reference,
                plan=config.plan)

        def verify_transaction(self, reference):
            return {"status": "success", "reference": reference}

        def get_subscription(self, code):
            return {"subscription_code": code}

        def cancel_subscription(self, code):
            return {"subscription_code": code, "disabled": True}

    out = prepare_checkout(CheckoutRequest(user_id="u", email="u@x.io",
                                           plan="growth"),
                           provider=LaterProvider())
    assert out["plan"] == "growth"
    assert out["authorization_url"].startswith("https://")


# --- checkout response + plan boundaries ------------------------------------
def test_checkout_response_shape(env):
    p, _ = provider(env)
    out = prepare_checkout(CheckoutRequest(user_id="u", email="u@x.io",
                                           plan="growth"), provider=p)
    assert set(out) == {"authorization_url", "reference", "plan"}
    assert "active" not in str(out).lower()


def test_verify_returns_safe_subset(env):
    p, _ = provider(env)
    got = p.verify_transaction("footyedge_x")
    assert set(got) <= {"status", "reference", "amount", "currency", "plan"}
    assert "authorization" not in str(got).lower()


def test_references_unique():
    refs = {billing.new_reference() for _ in range(200)}
    assert len(refs) == 200
    assert all(r.startswith("footyedge_") for r in refs)


# --- environment validation (8.3 §12) --------------------------------------

def test_validate_config_accepts_matching_test_mode(env):
    assert validate_paystack_config() == "test"


def test_missing_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("PAYSTACK_MODE", "")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_unit_only_no_real_key")
    with pytest.raises(BillingNotConfigured):
        validate_paystack_config()


def test_unknown_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("PAYSTACK_MODE", "sandbox")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_unit_only_no_real_key")
    with pytest.raises(BillingNotConfigured):
        validate_paystack_config()


def test_live_secret_with_test_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("PAYSTACK_MODE", "test")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_live_unit_only_no_real_key")
    with pytest.raises(BillingNotConfigured) as exc:
        validate_paystack_config()
    assert "sk_live_unit_only_no_real_key" not in str(exc.value.public)
    assert "sk_live_unit_only_no_real_key" not in str(exc.value)


def test_test_secret_with_live_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("PAYSTACK_MODE", "live")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_test_unit_only_no_real_key")
    with pytest.raises(BillingNotConfigured):
        validate_paystack_config()


def test_live_mode_accepts_matching_live_secret(monkeypatch):
    monkeypatch.setenv("PAYSTACK_MODE", "live")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_live_unit_only_no_real_key")
    monkeypatch.setenv("PAYSTACK_GROWTH_PLAN_CODE", "PLN_live_growth")
    monkeypatch.setenv("PAYSTACK_BUSINESS_PLAN_CODE", "PLN_live_business")
    assert validate_paystack_config() == "live"


def test_empty_secret_fails_closed(monkeypatch):
    monkeypatch.setenv("PAYSTACK_MODE", "test")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "")
    with pytest.raises(BillingNotConfigured):
        validate_paystack_config()


def test_placeholder_plan_code_fails_closed(env):
    env.setenv("PAYSTACK_GROWTH_PLAN_CODE", "PLN_placeholder_replace_me")
    with pytest.raises(BillingNotConfigured):
        validate_paystack_config()


def test_example_plan_code_fails_closed(env):
    env.setenv("PAYSTACK_BUSINESS_PLAN_CODE", "your_plan_code_here")
    with pytest.raises(BillingNotConfigured):
        validate_paystack_config()


def test_build_provider_validates_environment(env):
    env.setenv("PAYSTACK_MODE", "")
    with pytest.raises(BillingNotConfigured):
        billing.build_provider()


# --- provisional rows (8.3 §8) ----------------------------------------------

def test_provisional_row_is_non_entitling():
    row = build_provisional_row("user-123", "growth")
    assert row["user_id"] == "user-123"
    assert row["plan"] == "growth"
    assert row["status"] == billing.PROVISIONAL_STATUS
    assert row["provider"] == "paystack"
    assert row["provider_customer_id"] is None
    assert row["provider_subscription_id"] is None
    assert row["provider_reference"] is None
    assert row["current_period_start"] is None
    assert row["current_period_end"] is None


def test_provisional_row_carries_echoed_reference():
    # The initialize response echoes OUR minted reference; persisting it
    # is the only authoritative checkout<->provider token (8.3.1 §A).
    # It is an audit/anti-replay token, never a user identity key.
    row = build_provisional_row("user-123", "growth",
                                reference="footyedge_abc123")
    assert row["provider_reference"] == "footyedge_abc123"


def test_provisional_row_reference_is_optional():
    assert build_provisional_row("u", "growth")["provider_reference"] is None


def test_provisional_row_grants_zero_paid_caps():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from entitlements import SubscriptionInfo
    row = build_provisional_row("user-123", "business")
    info = SubscriptionInfo(
        plan=row["plan"], status=row["status"], provider=row["provider"],
        provider_customer_id=None, provider_subscription_id=None,
        current_period_start=None, current_period_end=None)
    assert info.effective_plan == "starter"
    assert info.paid_capabilities == frozenset()


def test_provisional_row_rejects_unbillable_plan():
    with pytest.raises(BillingError):
        build_provisional_row("user-123", "starter")
    with pytest.raises(BillingError):
        build_provisional_row("user-123", "enterprise")
    with pytest.raises(BillingError):
        build_provisional_row("user-123", "platinum")


def test_provisional_row_rejects_missing_identity():
    with pytest.raises(BillingError) as exc:
        build_provisional_row("", "growth")
    assert exc.value.public == "Authentication required"
