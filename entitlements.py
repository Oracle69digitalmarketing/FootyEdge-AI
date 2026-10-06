"""FootyEdge server-authoritative entitlement resolution (Objective 8F).

This module derives effective access from authenticated identity +
authoritative subscription/profile state. It is the SINGLE source of truth
for backend enforcement. Frontend checks are UX only.

Role and Plan are INDEPENDENT dimensions:
  - Role: owner | admin | user  (administrative authority)
  - Plan: starter | growth | business | enterprise (product entitlement)

A subscription row MAY NOT exist -> fallback to Starter.
Unknown plan/status -> fail closed (Starter, no paid entitlements).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, List, Optional, Set

if TYPE_CHECKING:  # stdlib-only at runtime; Supabase client type only
    from supabase import Client
else:
    Client = Any  # type: ignore[assignment,misc]

logger = logging.getLogger("entitlements")

try:  # FastAPI only needed for route dependencies; keep module stdlib-only
    from fastapi import Depends, Header, HTTPException
except Exception:  # pragma: no cover - import-time fallback for offline tests
    def Header(default=None, **kwargs):  # type: ignore[no-redef]
        return default

    def Depends(dep=None, **kwargs):  # type: ignore[no-redef]
        return dep

    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int = 500, detail: Any = None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail


def _get_supabase_client():
    """Local import to avoid a hard api<->entitlements cycle at startup."""
    try:
        from api import get_supabase_client
        return get_supabase_client
    except Exception:
        return None

# =============================================================================
# Role Model (administrative authority, independent of subscription)
# =============================================================================

Role = str  # 'owner' | 'admin' | 'user'
VALID_ROLES: FrozenSet[str] = frozenset({"owner", "admin", "user"})

# Plans (commercial tiers)
Plan = str  # 'starter' | 'growth' | 'business' | 'enterprise'
VALID_PLANS: FrozenSet[str] = frozenset({"starter", "growth", "business", "enterprise"})

# Subscription statuses (from 8E migration CHECK constraint)
VALID_STATUSES: FrozenSet[str] = frozenset({
    "trialing", "active", "past_due", "paused", "canceled", "expired"
})

# =============================================================================
# Capability Vocabulary (central, typed)
# =============================================================================

# Implemented capabilities (have backend enforcement today)
CAP_DASHBOARD = "dashboard"
CAP_MATCH_INTELLIGENCE = "match_intelligence"
CAP_PREDICTIONS = "predictions"
CAP_VALUE_BETS = "value_bets"
CAP_TEAMS = "teams"
CAP_PLAYERS = "players"
CAP_ACCA_BUILDER = "acca_builder"
CAP_PORTFOLIO = "portfolio"
CAP_AI_STRATEGY_ANALYSIS = "ai_strategy_analysis"

# Planned capabilities (Business/Enterprise - not yet implemented)
CAP_API_ACCESS = "api_access"
CAP_DATA_EXPORT = "data_export"
CAP_MULTIPLE_SEATS = "multiple_seats"
CAP_ORGANIZATION_CONTROLS = "organization_controls"

# All known capabilities (for validation)
ALL_CAPABILITIES: FrozenSet[str] = frozenset({
    CAP_DASHBOARD,
    CAP_MATCH_INTELLIGENCE,
    CAP_PREDICTIONS,
    CAP_VALUE_BETS,
    CAP_TEAMS,
    CAP_PLAYERS,
    CAP_ACCA_BUILDER,
    CAP_PORTFOLIO,
    CAP_AI_STRATEGY_ANALYSIS,
    CAP_API_ACCESS,
    CAP_DATA_EXPORT,
    CAP_MULTIPLE_SEATS,
    CAP_ORGANIZATION_CONTROLS,
})

# Implemented capabilities (actually enforced in backend)
IMPLEMENTED_CAPABILITIES: FrozenSet[str] = frozenset({
    CAP_DASHBOARD,
    CAP_MATCH_INTELLIGENCE,
    CAP_PREDICTIONS,
    CAP_VALUE_BETS,
    CAP_TEAMS,
    CAP_PLAYERS,
    CAP_ACCA_BUILDER,
    CAP_PORTFOLIO,
    CAP_AI_STRATEGY_ANALYSIS,
})

# =============================================================================
# Plan -> Capability Matrix (explicit, central)
# =============================================================================

# Starter: core football intelligence
STARTER_CAPS: FrozenSet[str] = frozenset({
    CAP_DASHBOARD,
    CAP_MATCH_INTELLIGENCE,
    CAP_PREDICTIONS,
    CAP_TEAMS,
    CAP_PLAYERS,
    # CAP_ACCA_BUILDER and CAP_PORTFOLIO are controlled by usage,
    # not hard-gated here. The matrix represents hard capability gates.
})

# Growth: Starter + deeper analysis capabilities
GROWTH_CAPS: FrozenSet[str] = frozenset({
    *STARTER_CAPS,
    CAP_VALUE_BETS,
    CAP_ACCA_BUILDER,
    CAP_PORTFOLIO,
    CAP_AI_STRATEGY_ANALYSIS,
})

# Business: Growth + commercial capabilities (planned)
BUSINESS_CAPS: FrozenSet[str] = frozenset({
    *GROWTH_CAPS,
    # Planned, not yet implemented:
    # CAP_API_ACCESS,
    # CAP_DATA_EXPORT,
    # CAP_MULTIPLE_SEATS,
    # CAP_ORGANIZATION_CONTROLS,
})

# Enterprise: Custom (treated as Business for implemented caps)
ENTERPRISE_CAPS: FrozenSet[str] = frozenset(BUSINESS_CAPS)

PLAN_CAPABILITIES: Dict[Plan, FrozenSet[str]] = {
    "starter": STARTER_CAPS,
    "growth": GROWTH_CAPS,
    "business": BUSINESS_CAPS,
    "enterprise": ENTERPRISE_CAPS,
}

# =============================================================================
# Subscription Status -> Paid Entitlement Semantics
# =============================================================================

# Which statuses grant PAID-PLAN capabilities?
# Only 'active' and 'trialing' confer full paid entitlements.
# 'past_due' is conservative: no paid entitlements (grace handled by webhook).
# 'paused', 'canceled', 'expired' -> no paid entitlements.
# Canceled with current_period_end > now: handled by period-end check in resolver.

PAID_ENTITLEMENT_STATUSES: FrozenSet[str] = frozenset({"active", "trialing"})

# =============================================================================
# Data Structures
# =============================================================================

@dataclass(frozen=True)
class SubscriptionInfo:
    """Authoritative subscription row (or None-equivalent)."""
    plan: Plan
    status: str
    provider: Optional[str]
    provider_customer_id: Optional[str]
    provider_subscription_id: Optional[str]
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]

    @property
    def is_paid_status(self) -> bool:
        return self.status in PAID_ENTITLEMENT_STATUSES

    @property
    def has_valid_period(self) -> bool:
        """Whether the current period end is in the future."""
        if self.current_period_end is None:
            return False
        return self.current_period_end > datetime.now(timezone.utc)

    @property
    def effective_plan(self) -> Plan:
        """
        Determine the effective plan for entitlement purposes.

        Rules:
        - If no subscription row -> starter
        - If unknown plan -> starter (fail closed)
        - If paid status (active/trialing) -> declared plan
        - If canceled but period valid -> declared plan (access through period)
        - Otherwise -> starter
        """
        if self.plan not in VALID_PLANS:
            logger.warning("entitlements: unknown plan %r -> starter", self.plan)
            return "starter"

        if self.is_paid_status:
            return self.plan

        if self.status == "canceled" and self.has_valid_period:
            # Canceled but paid period hasn't ended -> keep plan access
            return self.plan

        # past_due, paused, expired, canceled (period ended) -> starter
        return "starter"

    @property
    def paid_capabilities(self) -> FrozenSet[str]:
        """Capabilities granted by the paid plan (if any)."""
        eff = self.effective_plan
        if eff == "starter":
            return frozenset()
        return PLAN_CAPABILITIES.get(eff, frozenset())


@dataclass(frozen=True)
class EntitlementResult:
    """Complete effective access for one user."""
    user_id: str
    email: str
    role: Role
    subscription: Optional[SubscriptionInfo]
    plan: Plan
    capabilities: FrozenSet[str]

    def has(self, capability: str) -> bool:
        return capability in self.capabilities

    def has_any(self, *capabilities: str) -> bool:
        return any(c in self.capabilities for c in capabilities)

    def requires_role(self, *roles: Role) -> bool:
        return self.role in roles

    def is_owner(self) -> bool:
        return self.role == "owner"

    def is_admin(self) -> bool:
        return self.role in ("owner", "admin")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "role": self.role,
            "plan": self.plan,
            "subscription_status": self.subscription.status if self.subscription else None,
            "capabilities": sorted(self.capabilities),
        }


# =============================================================================
# Resolution Logic
# =============================================================================

def resolve_role_from_profile(supabase: Client, user_id: str) -> Role:
    """
    Read authoritative role from profiles table.
    Returns 'user' if not found or invalid (fail closed).
    """
    try:
        res = supabase.table("profiles").select("role").eq("id", user_id).limit(1).execute()
        rows = res.data or []
        if rows:
            role = str(rows[0].get("role", "user"))
            if role in VALID_ROLES:
                return role
    except Exception as exc:
        logger.warning("entitlements: profile role lookup failed: %s", type(exc).__name__)
    return "user"


def fetch_subscription(supabase: Client, user_id: str) -> Optional[SubscriptionInfo]:
    """
    Fetch authoritative subscription row for a user.
    Returns None if no row exists (-> starter fallback).
    """
    try:
        res = supabase.table("subscriptions").select(
            "plan,status,provider,provider_customer_id,provider_subscription_id,"
            "current_period_start,current_period_end"
        ).eq("user_id", user_id).limit(1).execute()
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        return SubscriptionInfo(
            plan=str(row.get("plan", "starter")),
            status=str(row.get("status", "expired")),
            provider=row.get("provider"),
            provider_customer_id=row.get("provider_customer_id"),
            provider_subscription_id=row.get("provider_subscription_id"),
            current_period_start=_parse_dt(row.get("current_period_start")),
            current_period_end=_parse_dt(row.get("current_period_end")),
        )
    except Exception as exc:
        logger.warning("entitlements: subscription lookup failed: %s", type(exc).__name__)
        return None


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def resolve_entitlements(supabase: Client, user_id: str, email: str) -> EntitlementResult:
    """
    Main entry point: compute effective access for an authenticated user.

    Steps:
    1. Read role from profiles (authoritative)
    2. Read subscription row (authoritative)
    3. Determine effective plan (with status/period semantics)
    4. Combine role + plan capabilities
    5. Return explicit entitlements
    """
    role = resolve_role_from_profile(supabase, user_id)
    subscription = fetch_subscription(supabase, user_id)

    if subscription is None:
        plan = "starter"
        paid_caps = frozenset()
    else:
        plan = subscription.effective_plan
        paid_caps = subscription.paid_capabilities

    # Starter capabilities always included
    all_caps = set(STARTER_CAPS) | paid_caps

    # Role-based administrative capabilities are NOT in the capability set.
    # They are checked separately via .is_owner() / .is_admin()

    return EntitlementResult(
        user_id=user_id,
        email=email,
        role=role,
        subscription=subscription,
        plan=plan,
        capabilities=frozenset(all_caps),
    )


# =============================================================================
# FastAPI Dependency Helpers
# =============================================================================

async def get_current_user(
    authorization: Optional[str],
    supabase: Client,
) -> tuple[str, str]:
    """
    Derive (user_id, email) from Supabase JWT.
    Mirrors the pattern in billing_api._supabase_auth_user.
    """
    import httpx
    import os

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    base = (os.environ.get("SUPABASE_URL", "") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY") or ""
    if not base or not key:
        logger.warning("entitlements: Supabase backend config missing")
        raise HTTPException(status_code=502, detail="Service unavailable")

    try:
        resp = httpx.get(
            f"{base}/auth/v1/user",
            headers={"apikey": key, "Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
    except Exception as exc:
        logger.warning("entitlements: identity lookup failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Service unavailable")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        body = resp.json()
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required")
    user_id = str(body.get("id") or "")
    email = str(body.get("email") or "")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id, email


def require_capability(capability: str):
    """
    FastAPI dependency factory: require a specific capability.
    Returns a dependency that resolves entitlements and checks the capability.
    """
    if capability not in ALL_CAPABILITIES:
        raise ValueError(f"Unknown capability: {capability}")

    async def _check(
        authorization: Optional[str] = Header(default=None),
    ) -> EntitlementResult:
        factory = _get_supabase_client()
        supabase = factory() if factory is not None else None
        user_id, email = await get_current_user(authorization, supabase)
        result = resolve_entitlements(supabase, user_id, email)
        if not result.has(capability):
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "FEATURE_NOT_ENTITLED", "feature": capability}},
            )
        return result

    return _check


def require_role(*roles: Role):
    """
    FastAPI dependency factory: require administrative role.
    Distinct from plan capabilities.
    """
    async def _check(
        authorization: Optional[str] = Header(default=None),
    ) -> EntitlementResult:
        factory = _get_supabase_client()
        supabase = factory() if factory is not None else None
        user_id, email = await get_current_user(authorization, supabase)
        result = resolve_entitlements(supabase, user_id, email)
        if not result.requires_role(*roles):
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "ROLE_REQUIRED", "required": list(roles)}},
            )
        return result

    return _check


async def get_entitlements(
    authorization: Optional[str] = Header(default=None),
) -> EntitlementResult:
    """
    FastAPI dependency: resolve full entitlements for the current user.
    Does not enforce any capability; returns the full result for inline checks.
    """
    factory = _get_supabase_client()
    supabase = factory() if factory is not None else None
    user_id, email = await get_current_user(authorization, supabase)
    return resolve_entitlements(supabase, user_id, email)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "Role",
    "Plan",
    "VALID_ROLES",
    "VALID_PLANS",
    "VALID_STATUSES",
    "ALL_CAPABILITIES",
    "IMPLEMENTED_CAPABILITIES",
    "CAP_DASHBOARD",
    "CAP_MATCH_INTELLIGENCE",
    "CAP_PREDICTIONS",
    "CAP_VALUE_BETS",
    "CAP_TEAMS",
    "CAP_PLAYERS",
    "CAP_ACCA_BUILDER",
    "CAP_PORTFOLIO",
    "CAP_AI_STRATEGY_ANALYSIS",
    "CAP_API_ACCESS",
    "CAP_DATA_EXPORT",
    "CAP_MULTIPLE_SEATS",
    "CAP_ORGANIZATION_CONTROLS",
    "STARTER_CAPS",
    "GROWTH_CAPS",
    "BUSINESS_CAPS",
    "ENTERPRISE_CAPS",
    "PLAN_CAPABILITIES",
    "PAID_ENTITLEMENT_STATUSES",
    "SubscriptionInfo",
    "EntitlementResult",
    "resolve_entitlements",
    "require_capability",
    "require_role",
    "get_entitlements",
]