"""8G owner/admin operational HTTP boundary (read-only).

Thin FastAPI wrapper over admin_billing.py (framework-agnostic, unit
tested). Every endpoint independently enforces administrative
authorization via entitlements.require_role("owner", "admin"):

    JWT -> authenticated user -> authoritative profiles.role lookup
        -> owner/admin? YES -> execute / NO -> 403 ROLE_REQUIRED

Reads use the existing service-role server client (never the browser
key). No endpoint writes, creates, updates or deletes anything: there
is no "set plan", no "set active", no renewal extension and no manual
billing mutation of any kind. Webhook synchronization (8E) remains the
only writer of subscription state.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from admin_billing import (
    DEFAULT_LIMIT,
    compute_overview,
    sanitize_event,
    sanitize_subscription,
    usage_summary,
    user_commercial_view,
)
from entitlements import EntitlementResult, require_role

logger = logging.getLogger("admin_api")

router = APIRouter()
ADMIN_GUARD = require_role("owner", "admin")


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
) -> Dict[str, Any]:
    """Per-user commercial/account state (sanitized, read-only)."""
    bound = max(1, min(limit, DEFAULT_LIMIT))
    profiles = _read_table("profiles", "id,email,role,created_at", bound)
    subscriptions = _read_table(
        "subscriptions",
        "user_id,plan,status,provider,current_period_start,current_period_end",
        bound,
    )
    by_user = {s.get("user_id"): s for s in subscriptions if s.get("user_id") is not None}
    return {
        "users": [
            user_commercial_view(p, by_user.get(p.get("id"))) for p in profiles
        ],
        "count": len(profiles),
    }


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


@router.get("/api/admin/billing/usage")
async def billing_usage(
    _ent: EntitlementResult = Depends(ADMIN_GUARD),
) -> Dict[str, Any]:
    """Honest usage-monitoring state (metering not yet enabled)."""
    return usage_summary()


__all__ = ["router"]
