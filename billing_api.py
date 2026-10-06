"""Billing HTTP boundary (Paystack). Thin FastAPI wrapper.

All pricing/validation logic lives in billing.py (framework-agnostic and
unit-tested). This module only: extracts the caller's Supabase JWT,
derives the user identity server-side, and maps safe errors to HTTP.

Mode is declared by PAYSTACK_MODE (test|live); no live billing is
activated by this objective. No checkout marks a subscription active.
Webhook sync belongs to 8E.
"""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from billing import (
    BillingError,
    CheckoutRequest,
    build_provider,
    build_provisional_row,
    prepare_checkout,
)
from subscription_service import (
    ApplyResult,
    SubscriptionStore,
    SubscriptionUpdate,
    WebhookError,
    process_paystack_event,
    verify_paystack_signature,
)

logger = logging.getLogger("billing_api")

router = APIRouter()


class CheckoutBody(BaseModel):
    plan: str


def _supabase_auth_user(authorization: Optional[str]) -> tuple[str, str]:
    """Derive (user_id, email) from the caller's Supabase JWT.

    Never trusts browser-supplied user identity. Uses the existing
    SUPABASE_URL / service-key environment (no new credentials).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    base = (os.environ.get("SUPABASE_URL", "") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY") or ""
    if not base or not key:
        logger.warning("billing: Supabase backend config missing")
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    import httpx  # local import: only needed on this code path

    try:
        resp = httpx.get(f"{base}/auth/v1/user",
                         headers={"apikey": key, "Authorization": f"Bearer {token}"},
                         timeout=15.0)
    except Exception as exc:
        logger.warning("billing: identity lookup failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")
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


@router.post("/api/billing/checkout")
async def billing_checkout(body: CheckoutBody,
                           authorization: Optional[str] = Header(default=None)):
    """Initialize a Paystack checkout for growth/business.

    Mode is declared by PAYSTACK_MODE (test|live); the secret prefix must
    match the mode. On successful initialization a provisional,
    non-entitling subscription row is recorded for the authenticated
    user (insert-only: never downgrades an existing row) so the first
    webhook has a local row to adopt. The checkout itself never marks a
    subscription active.
    """
    user_id, email = _supabase_auth_user(authorization)
    try:
        result = prepare_checkout(
            CheckoutRequest(user_id=user_id, email=email, plan=body.plan),
            provider=build_provider(),
        )
    except BillingError as exc:
        status = 401 if exc.public == "Authentication required" else (
            502 if exc.public == "Payment provider unavailable" else 400)
        raise HTTPException(status_code=status, detail=exc.public)
    _record_provisional_row(user_id, body.plan, result["reference"])
    return result


def _record_provisional_row(user_id: str, plan: str,
                            reference: Optional[str] = None) -> None:
    """Best-effort provisional row for checkout->webhook correlation.

    Insert-only (ignores conflicts on user_id): an existing subscription
    row — active or otherwise — is never modified here. A persistence
    failure is logged server-side and does NOT fail the checkout, which
    already succeeded at the provider; the webhook then falls back to
    ignored/uncorrelated rather than guessing identity.
    """
    try:
        row = build_provisional_row(user_id, plan, reference)
    except BillingError as exc:
        logger.warning("billing: provisional row refused: %s", exc.public)
        return
    try:
        from api import get_supabase_client  # noqa: E402
        (get_supabase_client().table("subscriptions")
         .upsert(row, on_conflict="user_id", ignore_duplicates=True)
         .execute())
    except Exception as exc:
        logger.warning("billing: provisional row not recorded: %s",
                       type(exc).__name__)


@router.post("/api/webhooks/paystack")
async def paystack_webhook(request: Request):
    """Verified Paystack webhook -> durable subscription state (8E).

    Sequence: raw body -> HMAC -> parse/validate -> correlate (read-only)
    -> decide -> ONE atomic write -> 2xx. Anything else fails closed with a
    stable public error string and no state mutation.

    2xx is returned for processed, ignored and duplicate deliveries: none of
    those is worth a provider retry. Retryable failures answer 502 and
    deterministic rejections answer 400, so Paystack stops retrying garbage.
    """
    raw = await request.body()
    signature = request.headers.get("x-paystack-signature")
    secret = os.environ.get("PAYSTACK_SECRET_KEY", "")
    if not verify_paystack_signature(raw, signature, secret):
        # No mutation of any kind has occurred at this point.
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Lazy import avoids a hard api<->billing_api cycle at startup; the
    # service client is the existing service-role pattern (never browser).
    from api import get_supabase_client  # noqa: E402
    store = SupabaseSubscriptionStore(get_supabase_client())
    try:
        result = process_paystack_event(store, raw_body=bytes(raw))
    except WebhookError as exc:
        raise HTTPException(status_code=502 if exc.retryable else 400,
                            detail=exc.public)
    # No internal row id is echoed back to the provider.
    return {"status": result.outcome}


class SupabaseSubscriptionStore(SubscriptionStore):
    """Service-role backed store for the single atomic webhook write.

    apply_event() is ONE RPC call to public.apply_paystack_event (8E
    migration): the event claim, the subscription update and the event
    completion share one database transaction, so a partial application is
    impossible. The function is SECURITY DEFINER and executable only by
    service_role; RLS on the tables denies ordinary users entirely.
    """

    _SUBSCRIPTION_COLUMNS = ("id,status,provider,provider_customer_id,"
                             "provider_subscription_id,current_period_start,"
                             "current_period_end")

    def __init__(self, client: Any) -> None:
        self._db = client

    def _find(self, provider: str, column: str,
              code: str) -> Optional[Dict[str, Any]]:
        res = self._db.table("subscriptions").select(
            self._SUBSCRIPTION_COLUMNS).eq(
            "provider", provider).eq(column, code).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None

    def find_by_provider_subscription(self, provider: str,
                                      code: str) -> Optional[Dict[str, Any]]:
        return self._find(provider, "provider_subscription_id", code)

    def find_by_provider_customer(self, provider: str,
                                  code: str) -> Optional[Dict[str, Any]]:
        return self._find(provider, "provider_customer_id", code)

    def apply_event(self, *, provider: str, provider_event_id: str,
                    event_type: str, payload: Dict[str, Any],
                    subscription_id: Any = None,
                    processing_status: str = "processed",
                    error_code: Optional[str] = None,
                    update: Optional[SubscriptionUpdate] = None,
                    provider_occurred_at: Optional[str] = None,
                    provider_sequence: Optional[str] = None) -> ApplyResult:
        fields = update or SubscriptionUpdate()
        params: Dict[str, Any] = {
            "p_provider": provider,
            "p_provider_event_id": provider_event_id,
            "p_event_type": event_type,
            "p_payload": payload,
            "p_processing_status": processing_status,
            "p_error_code": (error_code or None) and error_code[:64],
            "p_subscription_id": subscription_id,
            # Only a whitelisted, non-empty update reaches the database.
            "p_apply_subscription": not fields.is_empty() and subscription_id is not None,
            "p_new_status": fields.new_status,
            "p_provider_customer_id": fields.provider_customer_id,
            "p_provider_subscription_id": fields.provider_subscription_id,
            "p_current_period_start": fields.current_period_start,
            "p_current_period_end": fields.current_period_end,
            # Ordering metadata only; NULL-tolerant stale-event guard.
            "p_provider_occurred_at": provider_occurred_at,
            "p_provider_sequence": provider_sequence,
        }
        res = self._db.rpc("apply_paystack_event", params).execute()
        rows = res.data or []
        if not rows:
            raise WebhookError("Webhook processing failed",
                               "apply_paystack_event returned no row")
        row = rows[0] or {}
        return ApplyResult(event_id=row.get("event_id"),
                           inserted=bool(row.get("inserted")))

