"""Objective 8G: owner/admin commercial-operations tests.

Offline only. No network, no Supabase, no FastAPI, no Paystack.
Tests target admin_billing.py (stdlib-only pure logic) plus a static
structural scan of admin_api.py (FastAPI is not installed in this
environment, so the router is verified by source inspection: every
endpoint must carry the owner/admin guard and no write operations).

Maps 1:1 to the 8G test plan: authorization (1-6), subscription
visibility (7-10), events (11-13), metrics (14-17), security (18-22),
plus router structure (23-24).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import admin_billing  # noqa: E402
from admin_billing import (  # noqa: E402
    AdminDenied,
    admin_request,
    authorize_admin,
    compute_overview,
    sanitize_event,
    sanitize_subscription,
    usage_summary,
    user_commercial_view,
)
from entitlements import EntitlementResult  # noqa: E402


def _ent(role):
    return EntitlementResult(
        user_id="u1",
        email="u1@example.com",
        role=role,
        subscription=None,
        plan="starter",
        capabilities=frozenset({"dashboard"}),
    )


def _profile(uid="u1", role="user", email="u1@example.com"):
    return {"id": uid, "email": email, "role": role,
            "created_at": "2026-09-01T00:00:00+00:00"}


def _sub(uid="u1", plan="growth", status="active"):
    return {
        "id": 7,
        "user_id": uid,
        "plan": plan,
        "status": status,
        "provider": "paystack",
        "provider_customer_id": "CUS_x",
        "provider_subscription_id": "SUB_x",
        "current_period_start": "2026-09-01T00:00:00+00:00",
        "current_period_end": "2026-10-01T00:00:00+00:00",
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Authorization (1-6)
# ---------------------------------------------------------------------------

def test_1_owner_can_access():
    assert authorize_admin(_ent("owner")) is not None


def test_2_admin_can_access():
    assert authorize_admin(_ent("admin")) is not None


def test_3_user_receives_403():
    with pytest.raises(AdminDenied) as exc:
        authorize_admin(_ent("user"))
    assert exc.value.status == 403


def test_4_unauthenticated_receives_401():
    with pytest.raises(AdminDenied) as exc:
        authorize_admin(None)
    assert exc.value.status == 401


def test_5_body_role_cannot_elevate():
    with pytest.raises(AdminDenied) as exc:
        admin_request(_ent("user"), body={"role": "owner"})
    assert exc.value.status == 403


def test_6_query_role_cannot_elevate():
    with pytest.raises(AdminDenied) as exc:
        admin_request(_ent("user"), query={"role": "admin"})
    assert exc.value.status == 403


# ---------------------------------------------------------------------------
# Subscription visibility (7-10)
# ---------------------------------------------------------------------------

def test_7_correct_subscriptions_returned():
    out = sanitize_subscription(_sub(plan="business", status="active"))
    assert out["plan"] == "business"
    assert out["status"] == "active"
    assert out["provider"] == "paystack"
    assert out["user_id"] == "u1"


def test_8_plan_status_values_are_authoritative():
    view = user_commercial_view(_profile(), _sub(plan="growth", status="active"))
    assert view["effective_plan"] == "growth"
    assert view["subscription_status"] == "active"
    # Unknown plan fails closed to Starter (8F semantics reused, not invented).
    view = user_commercial_view(_profile(), _sub(plan="platinum", status="active"))
    assert view["effective_plan"] == "starter"
    # Non-paid status falls back to Starter even with a paid plan label.
    view = user_commercial_view(_profile(), _sub(plan="growth", status="past_due"))
    assert view["effective_plan"] == "starter"
    assert view["subscription_status"] == "past_due"


def test_9_period_dates_preserved_verbatim():
    sub = _sub()
    view = user_commercial_view(_profile(), sub)
    assert view["current_period_start"] == "2026-09-01T00:00:00+00:00"
    assert view["current_period_end"] == "2026-10-01T00:00:00+00:00"


def test_10_missing_subscription_handled_as_starter():
    view = user_commercial_view(_profile(), None)
    assert view["effective_plan"] == "starter"
    assert view["subscription_status"] is None
    assert view["provider"] is None


# ---------------------------------------------------------------------------
# Events (11-13)
# ---------------------------------------------------------------------------

def _event():
    return {
        "id": 3,
        "subscription_id": 7,
        "provider": "paystack",
        "provider_event_id": "evt_abc123",
        "event_type": "subscription.create",
        "payload": {"data": {"secret": "must-never-leave"}},
        "processing_status": "processed",
        "error_code": None,
        "created_at": "2026-09-02T00:00:00+00:00",
        "processed_at": "2026-09-02T00:00:01+00:00",
    }


def test_11_events_visible_to_authorized_roles_only():
    out = sanitize_event(_event())
    assert out["event_type"] == "subscription.create"
    assert out["processing_status"] == "processed"
    assert out["provider_event_id"] == "evt_abc123"
    assert authorize_admin(_ent("owner")) is not None
    assert authorize_admin(_ent("admin")) is not None


def test_12_user_cannot_read_event_payloads():
    with pytest.raises(AdminDenied):
        admin_request(_ent("user"))
    out = sanitize_event(_event())
    assert "payload" not in out
    assert "secret" not in str(out)


def test_13_event_state_not_editable_through_read_path():
    row = _event()
    out = sanitize_event(row)
    out["processing_status"] = "tampered"
    assert row["processing_status"] == "processed"  # input untouched
    writers = [n for n in dir(admin_billing)
               if any(v in n for v in ("update", "insert", "delete", "upsert",
                                       "set_", "write", "mutate", "cancel",
                                       "extend", "activate"))]
    assert writers == []


# ---------------------------------------------------------------------------
# Metrics (14-17)
# ---------------------------------------------------------------------------

def test_14_user_counts_from_actual_records():
    profiles = [_profile("u1"), _profile("u2"), _profile("u3", role="owner")]
    subs = [_sub("u1"), _sub("u2", plan="business")]
    over = compute_overview(profiles, subs)
    assert over["total_users"] == 3
    assert over["users_with_subscriptions"] == 2


def test_15_plan_counts_from_actual_subscriptions():
    profiles = [_profile("u1"), _profile("u2"), _profile("u3")]
    subs = [_sub("u1", plan="growth", status="active"),
            _sub("u2", plan="growth", status="past_due")]
    over = compute_overview(profiles, subs)
    # past_due growth counts as Starter (effective, not declared).
    assert over["plan_counts"]["growth"] == 1
    assert over["plan_counts"]["starter"] == 2


def test_16_status_counts_accurate():
    profiles = [_profile("u1"), _profile("u2")]
    subs = [_sub("u1", status="active"), _sub("u2", status="canceled")]
    over = compute_overview(profiles, subs)
    assert over["status_counts"] == {"active": 1, "canceled": 1}
    assert over["subscriptions_total"] == 2


def test_17_unavailable_usage_is_honest():
    assert usage_summary() == {
        "metering_enabled": False,
        "message": "Usage metering is not yet enabled.",
    }


# ---------------------------------------------------------------------------
# Security (18-22)
# ---------------------------------------------------------------------------

def test_18_no_subscription_mutation_api_exists():
    mutators = [n for n in dir(admin_billing)
                if any(v in n for v in ("set_plan", "set_active", "update",
                                        "insert", "delete", "upsert", "create",
                                        "cancel", "renew", "extend", "refund",
                                        "adjust", "activate", "deactivate"))]
    assert mutators == []


def test_19_role_not_modifiable_through_admin_module():
    # Only the read-side role allowlist constant may be public; the
    # private _valid_role is a fail-closed display validator, not a writer.
    public_role_names = [n for n in dir(admin_billing)
                         if "role" in n.lower() and not n.startswith("_")]
    # Only read-side role constants exist (the guard allowlist plus the
    # re-exported 8F vocabulary); there is no role setter anywhere.
    assert public_role_names == ["OWNER_ADMIN_ROLES", "VALID_ROLES"]
    # Authorization ignores any client-supplied role claim by construction.
    with pytest.raises(AdminDenied):
        admin_request(_ent("user"), body={"role": "owner"},
                      query={"role": "owner"})


def test_20_subscription_state_immutable_via_read_path():
    sub = _sub()
    before = dict(sub)
    sanitize_subscription(sub)
    user_commercial_view(_profile(), sub)
    compute_overview([_profile()], [sub])
    assert sub == before


def test_21_frontend_only_access_never_authorizes():
    # A UX claim of ownership with no server-resolved entitlement.
    with pytest.raises(AdminDenied) as exc:
        admin_request(None, body={"role": "owner"}, query={"role": "owner"})
    assert exc.value.status == 401


SECRET_FRAGMENTS = ("secret", "service_role", "authorization_code",
                    "access_token", "password", "payload", "sk_test",
                    "sk_live", "apikey", "api_key")


def test_22_no_secrets_in_api_outputs():
    outputs = [
        sanitize_subscription(_sub()),
        sanitize_event(_event()),
        user_commercial_view(_profile(), _sub()),
        compute_overview([_profile()], [_sub()]),
        usage_summary(),
    ]
    blob = str(outputs).lower()
    for frag in SECRET_FRAGMENTS:
        assert frag not in blob, frag


# ---------------------------------------------------------------------------
# Router structure (23-24): admin_api.py without importing FastAPI
# ---------------------------------------------------------------------------

def _router_source():
    return (ROOT / "admin_api.py").read_text()


def test_23_every_admin_endpoint_guarded():
    src = _router_source()
    # Five read endpoints, each independently guarded owner/admin.
    assert src.count('Depends(ADMIN_GUARD)') >= 5
    assert 'require_role("owner", "admin")' in src
    for route in ("/api/admin/billing/overview",
                  "/api/admin/billing/users",
                  "/api/admin/billing/subscriptions",
                  "/api/admin/billing/events",
                  "/api/admin/billing/usage"):
        assert route in src


def test_24_router_performs_no_writes():
    src = _router_source()
    for token in (".insert(", ".update(", ".delete(", ".upsert(",
                  "set_plan", "set_active", "request.body"):
        assert token not in src, token
    # The raw provider `payload` column is never selected or accessed
    # (it appears only in prose as "payloads", never as a code token).
    assert '"payload"' not in src and "'payload'" not in src
