"""Objective 8F: server-authoritative entitlement resolution tests.

Offline only. No network, no real credentials, no live Supabase calls.

Covers the full entitlement matrix:
  - plan -> capability mapping (starter / growth / business / enterprise)
  - missing subscription row -> starter fallback
  - unknown plan / unknown status -> fail closed to starter
  - paid statuses (active, trialing) grant the declared plan
  - past_due / paused / expired grant nothing paid
  - canceled keeps the plan only while current_period_end is in the future
  - role (owner/admin/user) is independent of plan and fails closed to user
  - resolve_entitlements end-to-end over a stub Supabase client
  - EntitlementResult helpers and dependency-factory validation
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import entitlements  # noqa: E402
from entitlements import (  # noqa: E402
    ALL_CAPABILITIES,
    BUSINESS_CAPS,
    CAP_ACCA_BUILDER,
    CAP_AI_STRATEGY_ANALYSIS,
    CAP_API_ACCESS,
    CAP_DASHBOARD,
    CAP_MATCH_INTELLIGENCE,
    CAP_PLAYERS,
    CAP_PORTFOLIO,
    CAP_PREDICTIONS,
    CAP_TEAMS,
    CAP_VALUE_BETS,
    ENTERPRISE_CAPS,
    GROWTH_CAPS,
    IMPLEMENTED_CAPABILITIES,
    PLAN_CAPABILITIES,
    STARTER_CAPS,
    EntitlementResult,
    SubscriptionInfo,
    fetch_subscription,
    require_capability,
    require_role,
    resolve_entitlements,
    resolve_role_from_profile,
)


# ---------------------------------------------------------------------------
# Stub Supabase (mirrors the contract used by entitlements.py only)
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)
        self._filters = []
        self._limit = None

    def select(self, _cols):
        return self

    def eq(self, column, value):
        self._filters.append((column, value))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = [
            r for r in self._rows
            if all(r.get(col) == val for col, val in self._filters)
        ]
        if self._limit is not None:
            rows = rows[: self._limit]
        return _Result(rows)


class _Table:
    def __init__(self, rows):
        self.rows = rows

    def select(self, cols):
        return _Query(self.rows).select(cols)


class FakeSupabase:
    """Minimal stub: profiles (id, role) + subscriptions (user_id, ...)."""

    def __init__(self, profiles=None, subscriptions=None):
        self._tables = {
            "profiles": _Table(profiles or []),
            "subscriptions": _Table(subscriptions or []),
        }

    def table(self, name):
        return self._tables[name]


def _sub(plan="growth", status="active", end=None, **overrides):
    row = {
        "user_id": "u1",
        "plan": plan,
        "status": status,
        "provider": "paystack",
        "provider_customer_id": "CUS_x",
        "provider_subscription_id": "SUB_x",
        "current_period_start": None,
        "current_period_end": end,
    }
    row.update(overrides)
    return row


def _future(days=5):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past(days=5):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _info(plan="growth", status="active", end=None):
    return SubscriptionInfo(
        plan=plan,
        status=status,
        provider="paystack",
        provider_customer_id="CUS_x",
        provider_subscription_id="SUB_x",
        current_period_start=None,
        current_period_end=(
            datetime.fromisoformat(end.replace("Z", "+00:00")) if end else None
        ),
    )


# ---------------------------------------------------------------------------
# Plan -> capability matrix
# ---------------------------------------------------------------------------

def test_starter_matrix_is_core_intelligence():
    assert STARTER_CAPS == frozenset({
        CAP_DASHBOARD,
        CAP_MATCH_INTELLIGENCE,
        CAP_PREDICTIONS,
        CAP_TEAMS,
        CAP_PLAYERS,
    })
    for cap in STARTER_CAPS:
        assert cap in IMPLEMENTED_CAPABILITIES


def test_growth_adds_paid_analysis_caps():
    assert GROWTH_CAPS == STARTER_CAPS | frozenset({
        CAP_VALUE_BETS,
        CAP_ACCA_BUILDER,
        CAP_PORTFOLIO,
        CAP_AI_STRATEGY_ANALYSIS,
    })


def test_business_and_enterprise_match_growth_for_implemented_caps():
    # Planned commercial caps (api_access, data_export, ...) are designed
    # but not enforced yet, so business/enterprise resolve to growth today.
    assert BUSINESS_CAPS == GROWTH_CAPS
    assert ENTERPRISE_CAPS == GROWTH_CAPS
    assert CAP_API_ACCESS in ALL_CAPABILITIES
    assert CAP_API_ACCESS not in IMPLEMENTED_CAPABILITIES


def test_plan_capabilities_map_covers_all_plans():
    assert set(PLAN_CAPABILITIES) == {"starter", "growth", "business", "enterprise"}
    assert PLAN_CAPABILITIES["starter"] == STARTER_CAPS
    assert PLAN_CAPABILITIES["growth"] == GROWTH_CAPS


def test_require_capability_rejects_unknown():
    with pytest.raises(ValueError):
        require_capability("not_a_real_capability")


def test_dependency_factories_return_callables():
    assert callable(require_capability(CAP_PREDICTIONS))
    assert callable(require_role("owner", "admin"))


# ---------------------------------------------------------------------------
# Subscription status semantics (pure SubscriptionInfo level)
# ---------------------------------------------------------------------------

def test_active_grants_declared_plan():
    info = _info(plan="growth", status="active")
    assert info.effective_plan == "growth"
    assert info.paid_capabilities == GROWTH_CAPS


def test_trialing_grants_declared_plan():
    info = _info(plan="growth", status="trialing")
    assert info.effective_plan == "growth"
    assert CAP_VALUE_BETS in info.paid_capabilities


def test_past_due_grants_nothing_paid():
    info = _info(plan="growth", status="past_due")
    assert info.effective_plan == "starter"
    assert info.paid_capabilities == frozenset()


def test_paused_grants_nothing_paid():
    info = _info(plan="business", status="paused")
    assert info.effective_plan == "starter"


def test_expired_grants_nothing_paid():
    info = _info(plan="growth", status="expired")
    assert info.effective_plan == "starter"


def test_canceled_with_future_period_keeps_plan():
    info = _info(plan="growth", status="canceled", end=_future())
    assert info.effective_plan == "growth"
    assert CAP_VALUE_BETS in info.paid_capabilities


def test_canceled_with_past_period_falls_to_starter():
    info = _info(plan="growth", status="canceled", end=_past())
    assert info.effective_plan == "starter"
    assert info.paid_capabilities == frozenset()


def test_canceled_without_period_falls_to_starter():
    info = _info(plan="growth", status="canceled", end=None)
    assert info.effective_plan == "starter"


def test_unknown_plan_fails_closed():
    info = _info(plan="platinum", status="active")
    assert info.effective_plan == "starter"
    assert info.paid_capabilities == frozenset()


def test_unknown_status_fails_closed():
    info = _info(plan="growth", status="weird_status")
    assert info.effective_plan == "starter"
    assert info.paid_capabilities == frozenset()


# ---------------------------------------------------------------------------
# Role resolution (independent of plan)
# ---------------------------------------------------------------------------

def test_role_owner_admin_user_passthrough():
    for role in ("owner", "admin", "user"):
        db = FakeSupabase(profiles=[{"id": "u1", "role": role}])
        assert resolve_role_from_profile(db, "u1") == role


def test_role_missing_profile_defaults_to_user():
    db = FakeSupabase(profiles=[])
    assert resolve_role_from_profile(db, "u1") == "user"


def test_role_unknown_value_defaults_to_user():
    db = FakeSupabase(profiles=[{"id": "u1", "role": "superuser"}])
    assert resolve_role_from_profile(db, "u1") == "user"


def test_role_lookup_failure_defaults_to_user():
    class Broken:
        def table(self, _name):
            raise RuntimeError("db down")

    assert resolve_role_from_profile(Broken(), "u1") == "user"


# ---------------------------------------------------------------------------
# fetch_subscription
# ---------------------------------------------------------------------------

def test_fetch_subscription_none_when_no_row():
    db = FakeSupabase(subscriptions=[])
    assert fetch_subscription(db, "u1") is None


def test_fetch_subscription_parses_row():
    db = FakeSupabase(subscriptions=[_sub(plan="growth", status="active", end=_future())])
    info = fetch_subscription(db, "u1")
    assert info is not None
    assert info.plan == "growth"
    assert info.status == "active"
    assert info.has_valid_period is True


def test_fetch_subscription_lookup_failure_returns_none():
    class Broken:
        def table(self, _name):
            raise RuntimeError("db down")

    assert fetch_subscription(Broken(), "u1") is None


# ---------------------------------------------------------------------------
# resolve_entitlements end-to-end
# ---------------------------------------------------------------------------

def test_no_subscription_means_starter_with_core_caps():
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "user"}],
        subscriptions=[],
    )
    res = resolve_entitlements(db, "u1", "u1@example.com")
    assert res.plan == "starter"
    assert res.capabilities == STARTER_CAPS
    assert res.has(CAP_PREDICTIONS)
    assert not res.has(CAP_VALUE_BETS)
    assert not res.has(CAP_AI_STRATEGY_ANALYSIS)


def test_active_growth_gets_full_growth_caps():
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "user"}],
        subscriptions=[_sub(plan="growth", status="active", end=_future())],
    )
    res = resolve_entitlements(db, "u1", "u1@example.com")
    assert res.plan == "growth"
    assert res.capabilities == GROWTH_CAPS
    assert res.has(CAP_VALUE_BETS)
    assert res.has(CAP_ACCA_BUILDER)
    assert res.has(CAP_PORTFOLIO)
    assert res.has(CAP_AI_STRATEGY_ANALYSIS)
    assert res.has_any("nope", CAP_VALUE_BETS)
    assert not res.has_any("nope", "also_nope")


def test_past_due_growth_falls_back_to_starter_caps():
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "user"}],
        subscriptions=[_sub(plan="growth", status="past_due", end=_future())],
    )
    res = resolve_entitlements(db, "u1", "u1@example.com")
    assert res.plan == "starter"
    assert res.capabilities == STARTER_CAPS


def test_role_is_independent_of_paid_plan():
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "owner"}],
        subscriptions=[],
    )
    res = resolve_entitlements(db, "u1", "owner@example.com")
    assert res.role == "owner"
    assert res.plan == "starter"  # role never upgrades the plan
    assert res.is_owner()
    assert res.is_admin()
    assert res.requires_role("owner", "admin")
    assert res.requires_role("owner")
    assert not res.requires_role("admin")


def test_admin_role_helpers():
    db = FakeSupabase(profiles=[{"id": "u1", "role": "admin"}])
    res = resolve_entitlements(db, "u1", "a@example.com")
    assert res.is_admin()
    assert not res.is_owner()
    assert res.requires_role("owner", "admin")


def test_plain_user_has_no_admin_rights():
    db = FakeSupabase(profiles=[{"id": "u1", "role": "user"}])
    res = resolve_entitlements(db, "u1", "u@example.com")
    assert not res.is_owner()
    assert not res.is_admin()
    assert not res.requires_role("owner", "admin")


def test_paid_owner_keeps_both_dimensions():
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "owner"}],
        subscriptions=[_sub(plan="business", status="active", end=_future())],
    )
    res = resolve_entitlements(db, "u1", "o@example.com")
    assert res.role == "owner"
    assert res.plan == "business"
    assert res.has(CAP_VALUE_BETS)


def test_to_dict_shape():
    res = EntitlementResult(
        user_id="u1",
        email="u@example.com",
        role="user",
        subscription=None,
        plan="starter",
        capabilities=frozenset({CAP_PREDICTIONS}),
    )
    d = res.to_dict()
    assert d == {
        "user_id": "u1",
        "email": "u@example.com",
        "role": "user",
        "plan": "starter",
        "subscription_status": None,
        "capabilities": [CAP_PREDICTIONS],
    }


def test_matrix_all_statuses_snapshot():
    """One parametrized sweep over every known status for growth."""
    cases = {
        "trialing": "growth",
        "active": "growth",
        "past_due": "starter",
        "paused": "starter",
        "expired": "starter",
    }
    for status, expected_plan in cases.items():
        db = FakeSupabase(
            profiles=[{"id": "u1", "role": "user"}],
            subscriptions=[_sub(plan="growth", status=status, end=_future())],
        )
        res = resolve_entitlements(db, "u1", "u@example.com")
        assert res.plan == expected_plan, status
    # canceled is period-dependent: covered explicitly above.
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "user"}],
        subscriptions=[_sub(plan="growth", status="canceled", end=_future())],
    )
    assert resolve_entitlements(db, "u1", "u@example.com").plan == "growth"
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "user"}],
        subscriptions=[_sub(plan="growth", status="canceled", end=_past())],
    )
    assert resolve_entitlements(db, "u1", "u@example.com").plan == "starter"


# ---------------------------------------------------------------------------
# Owner preview (server-enforced, test access without paid subscription)
# ---------------------------------------------------------------------------


def _owner_db(role="owner", sub=None):
    return FakeSupabase(
        profiles=[{"id": "u1", "role": role}],
        subscriptions=[sub] if sub is not None else [],
    )


def test_owner_without_subscription_remains_commercially_starter():
    res = resolve_entitlements(_owner_db(), "u1", "o@example.com")
    assert res.role == "owner"
    assert res.plan == "starter"
    assert res.subscription is None
    assert res.owner_preview is True


def test_owner_preview_grants_implemented_caps_only():
    res = resolve_entitlements(_owner_db(), "u1", "o@example.com")
    assert res.has(CAP_PORTFOLIO)
    assert res.has(CAP_ACCA_BUILDER)
    assert res.has(CAP_VALUE_BETS)
    assert res.has(CAP_AI_STRATEGY_ANALYSIS)
    for planned in (CAP_API_ACCESS, "data_export",
                    "multiple_seats", "organization_controls"):
        assert not res.has(planned), planned
    assert set(res.capabilities) <= set(ALL_CAPABILITIES)


def test_plain_starter_cannot_access_paid_caps():
    db = FakeSupabase(profiles=[{"id": "u1", "role": "user"}])
    res = resolve_entitlements(db, "u1", "u@example.com")
    assert res.plan == "starter"
    assert res.owner_preview is False
    assert not res.has(CAP_PORTFOLIO)
    assert not res.has(CAP_ACCA_BUILDER)


def test_admin_without_subscription_gets_no_preview():
    res = resolve_entitlements(_owner_db(role="admin"), "u1", "a@example.com")
    assert res.role == "admin"
    assert res.plan == "starter"
    assert res.owner_preview is False
    assert not res.has(CAP_PORTFOLIO)
    assert res.is_admin()  # administrative rights unaffected


def test_preview_never_mutates_subscription_state():
    sub = _sub(plan="growth", status="expired", end=_past())
    before = dict(sub)
    db = FakeSupabase(profiles=[{"id": "u1", "role": "owner"}],
                      subscriptions=[sub])
    res = resolve_entitlements(db, "u1", "o@example.com")
    assert res.plan == "starter"  # expired stays starter
    assert res.owner_preview is True
    assert db.table("subscriptions").rows == [before]
    assert res.subscription is not None
    assert res.subscription.plan == "growth"
    assert res.subscription.status == "expired"


def test_preview_derives_only_from_server_role():
    # Same subscription, different roles: only owner previews.
    sub = _sub(plan="starter", status="active", end=_future())
    for role, expected in (("owner", True), ("admin", False), ("user", False)):
        db = FakeSupabase(profiles=[{"id": "u1", "role": role}],
                          subscriptions=[dict(sub)])
        res = resolve_entitlements(db, "u1", "x@example.com")
        assert res.owner_preview is expected, role


def test_planned_caps_denied_even_for_paid_owner():
    db = FakeSupabase(
        profiles=[{"id": "u1", "role": "owner"}],
        subscriptions=[_sub(plan="business", status="active", end=_future())],
    )
    res = resolve_entitlements(db, "u1", "o@example.com")
    assert res.plan == "business"
    assert res.owner_preview is True
    assert not res.has(CAP_API_ACCESS)
