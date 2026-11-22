"""Owner/admin operational HTTP boundary.

Thin FastAPI wrapper over admin_billing.py (framework-agnostic, unit
tested). Every endpoint independently enforces administrative
authorization via entitlements.require_role("owner", "admin"):

    JWT -> authenticated user -> authoritative profiles.role lookup
        -> owner/admin? YES -> execute / NO -> 403 ROLE_REQUIRED

Reads use the existing service-role server client (never the browser
key). No endpoint writes, creates, updates or deletes any user, role,
plan or subscription state (the only exception is the probe's own
append-only audit row, which records that the probe happened): there is
no "set plan", no "set active", no renewal extension and no manual
billing mutation of any kind. Webhook synchronization (8E) remains the
only writer of subscription state.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from admin_billing import (
    DEFAULT_LIMIT,
    compute_overview,
    filter_profiles,
    normalize_search_term,
    profile_account_view,
    sanitize_activity_event,
    sanitize_admin_action,
    sanitize_event,
    sanitize_subscription,
    usage_summary,
    ADMIN_PROBE_ACTION,
    record_admin_probe,
)
)
from account_activity import (
    ADMIN_PROBE_ACTION,
    record_admin_probe,
)
from entitlements import EntitlementResult, require_role

from account_activity import (
    ADMIN_PROBE_ACTION,
    record_admin_probe,
)

logger = logging.getLogger("admin_api")

router = APIRouter()
ADMIN_GUARD = require_role("owner", "admin")


def _like_escape(term: str) -> str:
    """Escape ILIKE wildcards so a search term stays a literal.

    Quote `"` terminates a PostgREST uri-encoded param value, so it is
    stripped; the remaining wildcard characters are backslash-escaped
    for a standard ILIKE pattern. (The API edge additionally strips any
    quote and strips control characters in normalize_search_term.)
    """
    return (
        term.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
        .replace('"', "")
    )


def _db():
    """Existing service-role server client (lazy: avoids import cycle)."""
    from api import get_supabase_client  # noqa: E402

    return get_supabase_client()


def _read_table(table: str, columns: str, limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    """Bounded service-role read. Fail closed with a safe message."""
    try:
        res = (
            _db()
            .table(table)
            .select(columns)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [r for r in (res.data or []) if isinstance(r, dict)]
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("admin: %s read failed: %s", table, type(exc).__name__)
        raise HTTPException(status_code=502, detail="Service unavailable")


@router.get("/api/admin/billing/overview")
async def billing_overview(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
) -> Dict[str, Any]:
    """Real aggregate counts derived from actual records only."""
    profiles = _read_table("profiles", "id,created_at", DEFAULT_LIMIT)
    subscriptions = _read_table(
        "subscriptions",
        "user_id,plan,status,current_period_end",
        DEFAULT_LIMIT,
    )
    return compute_overview(profiles, subscriptions)


@router.get("/api/admin/billing/users")
async def billing_users(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
    limit: int = DEFAULT_LIMIT,
    q: Optional[str] = Query(default=None, description="Case-insensitive substring match on email or full name"),
) -> Dict[str, Any]:
    """Per-user commercial/account state (sanitized, read-only).

    Optional bounded search (``q``) over email and full name; every row
    carries the authoritative registration date, a trailing-7-day "new"
    flag, and the stored account status. A malformed ``q`` is a 422
    (never an unbounded fallback list).
    """
    bound = max(1, min(limit, DEFAULT_LIMIT))
    try:
        term = normalize_search_term(q)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid search term")

    columns = "id,email,full_name,role,created_at"
    seen: Dict[Any, Dict[str, Any]] = {}
    if term:
        # Two single-filter ilike queries (email, then full_name) merged
        # server-side: avoids version-dependent PostgREST `or=(...)`
        # grouping and keeps each filter a standard single operator.
        # The term is ilike-escaped so %/_ stay literal (and any quote
        # was already stripped at the API edge).
        pattern = f"%{_like_escape(term)}%"
        for column in ("email", "full_name"):
            try:
                res = (
                    _db()
                    .table("profiles")
                    .select(columns)
                    .ilike(column, pattern)
                    .order("created_at", desc=True)
                    .limit(bound)
                    .execute()
                )
                rows = [r for r in (res.data or []) if isinstance(r, dict)]
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning("admin: user search failed: %s", type(exc).__name__)
                raise HTTPException(status_code=502, detail="Service unavailable")
            for r in rows:
                if r.get("id") not in seen:
                    seen[r.get("id")] = r
    else:
        profiles = _read_table("profiles", columns, bound)
        for r in profiles:
            if r.get("id") not in seen:
                seen[r.get("id")] = r
    profiles = list(seen.values())
    # Stable newest-first order (ISO created_at; string compare fallback).
    profiles.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)
    profiles = profiles[:bound]
    subscriptions = _read_table(
        "subscriptions",
        "user_id,plan,status,provider,current_period_start,current_period_end",
        bound,
    )
    by_user = {s.get("user_id"): s for s in subscriptions if s.get("user_id") is not None}
    return {
        "users": [
            profile_account_view(p, by_user.get(p.get("id"))) for p in profiles
        ],
        "count": len(profiles),
    }


@router.get("/api/admin/activity")
async def admin_activity(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Recent real account activity (sanitized, read-only).

    Rows come from public.account_events, which is appended only by the
    signup trigger and by real, server-observed API events. Nothing here
    synthesizes activity.
    """
    bound = max(1, min(limit, DEFAULT_LIMIT))
    rows = _read_table(
        "account_events",
        "id,user_id,event_type,source,dedupe_key,created_at",
        bound,
    )
    return {"events": [sanitize_activity_event(r) for r in rows], "count": len(rows)}


@router.get("/api/admin/actions")
async def admin_actions(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Admin action audit trail (sanitized, read-only).

    Rows come from public.admin_actions, appended server-side for
    sensitive admin accesses (this probe endpoint) and any future
    state-changing admin action. The raw provider `payload` column does
    not exist on this table; targets are bounded descriptors.
    """
    bound = max(1, min(limit, DEFAULT_LIMIT))
    rows = _read_table(
        "admin_actions",
        "id,actor_id,actor_label,action,target,created_at",
        bound,
    )
    return {"actions": [sanitize_admin_action(r) for r in rows], "count": len(rows)}


@router.post("/api/admin/billing/usage/probe")
@router.get("/api/admin/billing/usage/probe")
async def admin_usage_probe(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
) -> Dict[str, Any]:
    """Admin authorization probe.

    POST is the primary shape (an admin "checks whether they can
    administer"); GET is provided so a browser link works without a
    preflight. Both call the same guarded handler: no body is read, no
    state is mutated except one append-only audit row recording this
    access, and the response is a stable capability descriptor.
    """
    # Record the sensitive admin access (append-only, best-effort).
    record_admin_probe(
        _ent.user_id,
        action=ADMIN_PROBE_ACTION,
        target="/api/admin/billing/usage/probe",
    )
    return {
        "authorized": True,
        "role": _ent.role,
        "user_id": _ent.user_id,
        "probe": "admin.authorization",
    }


@router.get("/api/admin/billing/usage")
async def billing_usage(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Honest usage-monitoring state.

    Per-user counts are derived from real ``account_events`` rows
    (server-observed feature calls). When nothing has been recorded,
    the activity list is empty — counts are never invented. Commercial
    API metering (plan-based rate limits) remains disabled.
    """
    bound = max(1, min(limit, DEFAULT_LIMIT))
    rows = _read_table(
        "account_events",
        "id,user_id,event_type,source,dedupe_key,created_at",
        bound,
    )
    sanitized = [sanitize_activity_event(r) for r in rows]
    summary = usage_summary(sanitized)
    # Honest note: the read is bounded by `limit`, so the counts are
    # "up to the most recent `limit` events" — not a full-history total.
    summary["note"] = f"Counts cover the most recent {bound} recorded events (bounded read)."
    return summary


@router.get("/api/admin/billing/subscriptions")
async def billing_subscriptions(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Actual subscription records (whitelisted columns, read-only)."""
    bound = max(1, min(limit, DEFAULT_LIMIT))
    rows = _read_table(
        "subscriptions",
        "id,user_id,plan,status,provider,provider_customer_id,"
        "provider_subscription_id,current_period_start,current_period_end,"
        "created_at,updated_at",
        bound,
    )
    return {"subscriptions": [sanitize_subscription(r) for r in rows], "count": len(rows)}


@router.get("/api/admin/billing/events")
async def billing_events(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Sanitized provider-event metadata (read-only, no raw payloads)."""
    bound = max(1, min(limit, DEFAULT_LIMIT))
    rows = _read_table(
        "subscription_events",
        "id,subscription_id,provider,provider_event_id,event_type,"
        "processing_status,error_code,created_at,processed_at",
        bound,
    )
    return {"events": [sanitize_event(r) for r in rows], "count": len(rows)}


__all__ = ["router"]
