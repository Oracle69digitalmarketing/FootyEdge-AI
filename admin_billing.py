"""8G owner/admin commercial operations: pure, framework-agnostic logic.

Stdlib only at import time (same pattern as billing.py /
subscription_service.py / entitlements.py) so unit tests run with no
network, no Supabase, no FastAPI and no Paystack.

Hierarchy (never reversed):

    Paystack -> verified webhook -> subscription_events -> subscriptions
        -> entitlements -> Owner Console (operational view only)

This module NEVER mutates billing state. There is intentionally no
"set plan" / "set active" / renewal / cancellation / balance helper
anywhere in this file: the default operational posture is read-only,
and manual billing overrides are a prohibited invention per 8G -- if
such a requirement ever exists it must be specified separately, not
implemented here.

Authorization model:
  - Roles owner/admin/user are administrative authority (profiles.role).
  - Plans are commercial tiers and NEVER authorize.
  - Every admin read goes through authorize_admin(), which consults
    ONLY the server-resolved entitlement (role looked up from the
    profiles table). Request bodies, query strings, React state, URL
    parameters and plan selection are structurally unable to confer
    authority: admin_request() accepts them and ignores them.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from entitlements import (
    VALID_PLANS,
    VALID_ROLES,
    SubscriptionInfo,
    EntitlementResult,
)

logger = logging.getLogger("admin_billing")

# Roles permitted to use the read-only operational endpoints.
# Owner gets full owner-console access; admin gets administrative read
# access. No write operations exist, so no finer RBAC is invented.
OWNER_ADMIN_ROLES: Tuple[str, ...] = ("owner", "admin")

# Hard response bounds so operational reads stay small.
DEFAULT_LIMIT = 200

# Usage metering does not exist yet (8G inspects; it does not invent).
USAGE_METERING_ENABLED = False
USAGE_NOT_METERED_MESSAGE = "Usage metering is not yet enabled."

# Only these subscription columns may ever leave the server through the
# operational endpoints. Provider customer/subscription codes are
# operational correlation IDs (not secrets) and are needed for support;
# payment secrets, authorization codes, raw webhook payloads and
# service-role credentials are never in this list.
SUBSCRIPTION_PUBLIC_KEYS: Tuple[str, ...] = (
    "id",
    "user_id",
    "plan",
    "status",
    "provider",
    "provider_customer_id",
    "provider_subscription_id",
    "current_period_start",
    "current_period_end",
    "created_at",
    "updated_at",
)

# Only this event metadata may leave the server. `payload` (raw provider
# data) is deliberately absent; `provider_event_id` is a non-secret
# content hash ("evt_" + SHA-256 hex) used as the idempotency key.
EVENT_PUBLIC_KEYS: Tuple[str, ...] = (
    "id",
    "subscription_id",
    "provider",
    "provider_event_id",
    "event_type",
    "processing_status",
    "error_code",
    "created_at",
    "processed_at",
)


class AdminDenied(Exception):
    """Safe admin-guard failure. Only `.public` may cross the HTTP boundary."""

    def __init__(self, public: str, status: int = 403, detail: str = "") -> None:
        super().__init__(public)
        self.public = public
        self.status = status
        if detail:
            logger.warning("admin: %s", detail)


def authorize_admin(
    entitlement: Optional[EntitlementResult],
    *,
    roles: Tuple[str, ...] = OWNER_ADMIN_ROLES,
) -> EntitlementResult:
    """Enforce administrative authorization for one operational read.

    Required flow: JWT -> authenticated user -> authoritative role lookup
    (profiles table, server-side) -> owner/admin? The `entitlement`
    argument IS that resolved server-side result; nothing else is
    consulted, so client-supplied role claims cannot elevate.
    """
    if entitlement is None:
        raise AdminDenied("Authentication required", status=401,
                          detail="admin read without identity")
    role = getattr(entitlement, "role", None)
    if role not in roles:
        raise AdminDenied("Forbidden", status=403,
                          detail=f"admin read denied for role {role!r}")
    return entitlement


def admin_request(
    entitlement: Optional[EntitlementResult],
    *,
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> EntitlementResult:
    """Router-level guard harness: body/query are accepted and ignored.

    Exists so tests (and reviewers) can verify the structural property
    that request-body roles and query-string roles cannot elevate
    privileges: authorization derives exclusively from the
    server-resolved entitlement.
    """
    _ = (body, query)  # deliberately unconsulted
    return authorize_admin(entitlement)


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _subscription_info(row: Optional[Dict[str, Any]]) -> Optional[SubscriptionInfo]:
    """Best-effort SubscriptionInfo for effective-plan semantics.

    Malformed rows fail closed to None (-> Starter display), never raise.
    """
    if not row:
        return None
    try:
        from entitlements import _parse_dt  # reuse central parsing
        return SubscriptionInfo(
            plan=str(row.get("plan", "starter")),
            status=str(row.get("status", "expired")),
            provider=row.get("provider"),
            provider_customer_id=row.get("provider_customer_id"),
            provider_subscription_id=row.get("provider_subscription_id"),
            current_period_start=_parse_dt(row.get("current_period_start")),
            current_period_end=_parse_dt(row.get("current_period_end")),
        )
    except Exception:
        return None


def _valid_role(value: Any) -> str:
    text = str(value) if value is not None else "user"
    return text if text in VALID_ROLES else "user"


def user_commercial_view(
    profile: Dict[str, Any],
    subscription: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """One sanitized user row for the operational Users view.

    Missing subscription -> Starter display (plan "starter", status None),
    mirroring the 8F no-row fallback. Period dates pass through verbatim;
    nothing is inferred and no renewal date is calculated.
    """
    profile = _as_dict(profile)
    info = _subscription_info(subscription)
    return {
        "user_id": profile.get("id"),
        "email": profile.get("email"),
        "role": _valid_role(profile.get("role")),
        "effective_plan": info.effective_plan if info else "starter",
        "subscription_status": info.status if info else None,
        "provider": (info.provider if info else None),
        "current_period_start": (subscription or {}).get("current_period_start"),
        "current_period_end": (subscription or {}).get("current_period_end"),
        "created_at": profile.get("created_at"),
    }


def sanitize_subscription(row: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist a subscription record for operational display."""
    row = _as_dict(row)
    return {key: row.get(key) for key in SUBSCRIPTION_PUBLIC_KEYS}


def sanitize_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist event metadata. Raw provider `payload` never leaves."""
    row = _as_dict(row)
    return {key: row.get(key) for key in EVENT_PUBLIC_KEYS}


def compute_overview(
    profiles: List[Dict[str, Any]],
    subscriptions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate real counts from actual records only.

    No estimates, no revenue/MRR/ARR, no conversion/retention/churn:
    only factual counts the database supports. Effective (not declared)
    plans are counted, so past_due/paused/expired rows contribute to
    Starter, exactly as entitlement resolution treats them.
    """
    profiles = [p for p in (profiles or []) if isinstance(p, dict)]
    subscriptions = [s for s in (subscriptions or []) if isinstance(s, dict)]

    by_user: Dict[Any, Dict[str, Any]] = {}
    for sub in subscriptions:
        uid = sub.get("user_id")
        if uid is not None and uid not in by_user:
            by_user[uid] = sub

    plan_counts: Dict[str, int] = {plan: 0 for plan in VALID_PLANS}
    for profile in profiles:
        info = _subscription_info(by_user.get(profile.get("id")))
        plan = info.effective_plan if info else "starter"
        plan_counts[plan] = plan_counts.get(plan, 0) + 1

    status_counts: Dict[str, int] = {}
    for sub in subscriptions:
        status = str(sub.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "total_users": len(profiles),
        "users_with_subscriptions": sum(
            1 for p in profiles if p.get("id") in by_user
        ),
        "starter_users": plan_counts.get("starter", 0),
        "plan_counts": {
            "starter": plan_counts.get("starter", 0),
            "growth": plan_counts.get("growth", 0),
            "business": plan_counts.get("business", 0),
            "enterprise": plan_counts.get("enterprise", 0),
        },
        "status_counts": status_counts,
        "subscriptions_total": len(subscriptions),
    }


def usage_summary() -> Dict[str, Any]:
    """Honest usage-monitoring state: metering does not exist yet."""
    return {
        "metering_enabled": USAGE_METERING_ENABLED,
        "message": USAGE_NOT_METERED_MESSAGE,
    }


__all__ = [
    "DEFAULT_LIMIT",
    "EVENT_PUBLIC_KEYS",
    "OWNER_ADMIN_ROLES",
    "SUBSCRIPTION_PUBLIC_KEYS",
    "USAGE_METERING_ENABLED",
    "USAGE_NOT_METERED_MESSAGE",
    "AdminDenied",
    "admin_request",
    "authorize_admin",
    "compute_overview",
    "sanitize_event",
    "sanitize_subscription",
    "usage_summary",
    "user_commercial_view",
]
