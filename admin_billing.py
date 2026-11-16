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

import datetime as _dt
import logging
import re
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

# ---------------------------------------------------------------------------
# Account administration (users listing: search, recency, status)
# ---------------------------------------------------------------------------

# Search terms are bounded and sanitized before reaching the database
# filter; anything else fails closed (no filter / 422 at the API edge).
SEARCH_MAX_LEN = 120
SEARCH_ILLEGAL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# "Registered within the previous 7 days" window (both endpoints included:
# a profile whose created_at lies in [now-7d, now] is flagged as new).
NEW_USER_WINDOW_DAYS = 7

# Activity feed shape: the /api/account_events table is written by the
# signup trigger and by real, server-observed feature calls. These are
# genuine observations, never estimates.
ACTIVITY_PUBLIC_KEYS: Tuple[str, ...] = (
    "id",
    "user_id",
    "event_type",
    "source",
    "dedupe_key",
    "created_at",
)

ADMIN_ACTION_PUBLIC_KEYS: Tuple[str, ...] = (
    "id",
    "actor_id",
    "actor_label",
    "action",
    "target",
    "created_at",
)

# Which recorded event types count as "genuine usage" for the users
# listing. `account.registered` is registration, not usage; admin actions
# live in a separate table.
USAGE_EVENT_TYPES: Tuple[str, ...] = (
    "usage.predict_requested",
    "usage.bet_recorded",
    "usage.strategy_analyzed",
    "usage.acca_generated",
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


def usage_summary(events: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Honest usage-monitoring state from recorded account events.

    ``events`` are sanitized ``account_events`` rows (server-observed,
    appended only by the signup trigger and real API call sites). Only
    the genuine usage event types are counted, per user. When nothing
    has been recorded, the activity list is empty — counts are never
    invented. Commercial API metering (plan-based rate limits) remains
    disabled: that mode is not implemented, and nothing here fakes it.
    """
    events = [e for e in (events or []) if isinstance(e, dict)]
    counts: Dict[Any, int] = {}
    last_by: Dict[Any, Any] = {}
    for ev in events:
        if ev.get("event_type") not in USAGE_EVENT_TYPES:
            continue
        uid = ev.get("user_id")
        if uid is None:
            continue
        counts[uid] = counts.get(uid, 0) + 1
        stamp = _parse_dt(ev.get("created_at"))
        prev = last_by.get(uid)
        if prev is None or (stamp is not None and (prev[0] is None or stamp > prev[0])):
            last_by[uid] = (stamp, ev.get("created_at"))

    activity = [
        {
            "user_id": uid,
            "event_count": counts[uid],
            "last_event_at": last_by[uid][1] if uid in last_by else None,
        }
        for uid in sorted(
            counts, key=lambda u: (counts[u], u), reverse=True
        )
    ]
    return {
        "metering_enabled": USAGE_METERING_ENABLED,
        "message": USAGE_NOT_METERED_MESSAGE,
        "activity_available": True,
        "total_usage_events": sum(counts.values()),
        "activity": activity,
    }


# ---------------------------------------------------------------------------
# Users-list helpers (pure; no I/O). The API layer performs the bounded
# database reads; these functions shape, validate and flag rows.
# ---------------------------------------------------------------------------

def _parse_dt(value: Any) -> Optional[_dt.datetime]:
    """Reuse the central parser (identical semantics to entitlements)."""
    from entitlements import _parse_dt as _central  # local: keep one source

    return _central(value)


def normalize_search_term(query: Any) -> Optional[str]:
    """Validate and normalize a user search term. Fail closed.

    Returns None when no filter should be applied (missing/blank term).
    Raises ValueError when a non-blank term is malformed (wrong type,
    over SEARCH_MAX_LEN, or contains control characters) — the API edge
    maps that to 422, never to an unbounded or injected filter.
    """
    if query is None:
        return None
    if not isinstance(query, str):
        raise ValueError("search must be a string")
    term = query.strip()
    if not term:
        return None
    if len(term) > SEARCH_MAX_LEN:
        raise ValueError("search term too long")
    if SEARCH_ILLEGAL_CHARS.search(term):
        raise ValueError("search term contains illegal characters")
    return term


def filter_profiles(
    profiles: List[Dict[str, Any]], term: Optional[str]
) -> List[Dict[str, Any]]:
    """Case-insensitive substring match on email or full_name.

    The database-side equivalent is an ILIKE over the same normalized
    term; this pure version exists so the exact matching semantics are
    unit-testable offline. term=None -> unfiltered (stable order).
    """
    profiles = [p for p in (profiles or []) if isinstance(p, dict)]
    if not term:
        return profiles
    needle = term.lower()
    out = []
    for p in profiles:
        hay = " ".join(
            str(p.get(k) or "").lower() for k in ("email", "full_name")
        )
        if needle in hay:
            out.append(p)
    return out


def registration_recency(
    profile: Dict[str, Any], now: Optional[_dt.datetime] = None
) -> bool:
    """True when created_at lies within the trailing 7-day window.

    Missing or unparseable created_at -> False (a profile without an
    authoritative registration timestamp is never flagged as new).
    """
    created = _parse_dt((profile or {}).get("created_at"))
    if created is None:
        return False
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.timezone.utc)
    return (now - created) <= _dt.timedelta(days=NEW_USER_WINDOW_DAYS)


def profile_account_view(
    profile: Dict[str, Any],
    subscription: Optional[Dict[str, Any]],
    *,
    now: Optional[_dt.datetime] = None,
) -> Dict[str, Any]:
    """One admin-facing user row: commercial view + registration facts.

    Adds:
      registered_at        authoritative profiles.created_at (verbatim)
      registered_recently  trailing-7-day flag (see registration_recency)
      account_status       the authoritative stored role — the only
                           account-status fact the profiles row carries.
                           Authentication-state facts (email
                           verification, bans) live in auth.users and are
                           intentionally NOT inferred or fetched here;
                           they are reported as unavailable rather than
                           guessed (see ACCOUNT_STATE_UNAVAILABLE).
    """
    profile = _as_dict(profile)
    base = user_commercial_view(profile, subscription)
    base["registered_at"] = profile.get("created_at")
    base["registered_recently"] = registration_recency(profile, now=now)
    base["account_status"] = _valid_role(profile.get("role"))
    return base


# Authentication-state fields are not retrievable on this read path; the
# string is a deliberate "not available" marker, not a status value.
ACCOUNT_STATE_UNAVAILABLE = "unavailable"


def sanitize_activity_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist one account_events row. No free-text payload column
    exists on the table, so nothing sensitive can ride along."""
    row = _as_dict(row)
    out = {key: row.get(key) for key in ACTIVITY_PUBLIC_KEYS}
    if out.get("user_id") is not None:
        out["user_id"] = str(out["user_id"])
    return out


def sanitize_admin_action(row: Dict[str, Any]) -> Dict[str, Any]:
    """Whitelist one admin_actions row (actor/action/target/created_at).

    Targets are bounded non-credential descriptors by construction (the
    writers only store migration labels, event names and role strings);
    anything present still passes through a no-secret scan below.
    """
    row = _as_dict(row)
    out = {key: row.get(key) for key in ADMIN_ACTION_PUBLIC_KEYS}
    if out.get("actor_id") is not None:
        out["actor_id"] = str(out["actor_id"])
    if out.get("target") is not None:
        text = str(out["target"])[:200]
        lowered = text.lower()
        for frag in ("secret", "key", "token", "password", "bearer "):
            if frag in lowered:
                text = "[redacted]"
                break
        out["target"] = text
    return out


__all__ = [
    "ACCOUNT_STATE_UNAVAILABLE",
    "ACTIVITY_PUBLIC_KEYS",
    "ADMIN_ACTION_PUBLIC_KEYS",
    "DEFAULT_LIMIT",
    "EVENT_PUBLIC_KEYS",
    "NEW_USER_WINDOW_DAYS",
    "OWNER_ADMIN_ROLES",
    "SEARCH_MAX_LEN",
    "SUBSCRIPTION_PUBLIC_KEYS",
    "USAGE_METERING_ENABLED",
    "USAGE_NOT_METERED_MESSAGE",
    "USAGE_EVENT_TYPES",
    "AdminDenied",
    "admin_request",
    "authorize_admin",
    "compute_overview",
    "filter_profiles",
    "normalize_search_term",
    "profile_account_view",
    "registration_recency",
    "sanitize_activity_event",
    "sanitize_admin_action",
    "sanitize_event",
    "sanitize_subscription",
    "usage_summary",
    "user_commercial_view",
]
