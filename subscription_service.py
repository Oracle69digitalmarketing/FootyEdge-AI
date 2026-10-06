"""8E webhook state synchronization (Paystack, test mode).

Responsibilities:
  billing.py                -> provider HTTP behavior (Paystack API calls)
  subscription_service.py   -> signature verification, event identity,
                               correlation, state-transition decisions,
                               idempotent orchestration (this file)
  billing_api.py            -> HTTP boundary only (raw body, headers,
                               status codes); no business logic

No live calls, no secrets in code, no frontend pricing changes.

Provider event identity: Paystack sends no stable top-level webhook event
ID, so provider_event_id is "evt_" + SHA-256 hex of the EXACT raw delivery
bytes. Byte-identical redeliveries collide (duplicate detected); distinct
deliveries never do. Not a timestamp, not random.

Ordering (8.3): Paystack sends no stable top-level event sequence, so
stale-event protection is NULL-tolerant. When the application finds an
authoritative provider timestamp in the payload (`data.created_at`, then
`data.paid_at`, then `data.transaction_date`), it is forwarded as
provider_occurred_at and compared against the subscription's
last_applied_occurred_at marker (Python fast-path plus an atomic guard
inside public.apply_paystack_event). A provably older event is recorded
as ignored/stale_event and never overwrites newer state. When either
side is NULL, arrival order wins (pre-8.3 behavior, except terminal
states which are additionally guarded by the transition table).

Atomicity: one delivery needs three writes (claim the event id, apply the
transition, complete the event). They are issued as ONE call into
SubscriptionStore.apply_event, which the Supabase implementation backs with
the SQL function public.apply_paystack_event -- three PostgREST round trips
would be three transactions and a crash between them would permanently
strand the event id with the subscription never updated.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("billing_webhook")

PROVIDER = "paystack"

# Events with explicit state semantics. Anything else is recorded and
# ignored (never mutates subscription state, never grants access).
SUPPORTED_EVENTS = (
    "subscription.create",
    "subscription.not_renew",
    "subscription.disable",
    "subscription.expiring_cards",
    "invoice.create",
    "invoice.update",
    "invoice.payment_failed",
    "charge.success",
)

# invoice.update data statuses treated as authoritative good standing.
INVOICE_PAID_STATUSES = ("success", "paid")


class WebhookError(Exception):
    """Public, safe webhook failure. Only `.public` leaves the server."""

    def __init__(self, public: str, detail: str = "",
                 retryable: bool = True) -> None:
        super().__init__(public)
        self.public = public
        self.retryable = retryable
        if detail:
            logger.warning("webhook: %s", detail)


# --------------------------------------------------------------------------
# Signature verification (raw bytes only, constant-time).
# --------------------------------------------------------------------------

def verify_paystack_signature(raw_body: Any, signature: Any,
                              secret: Any) -> bool:
    """HMAC-SHA512 of the exact raw body. Fail closed on any anomaly."""
    if not secret or not isinstance(secret, (str, bytes)):
        return False
    if not signature or not isinstance(signature, str):
        return False
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    if not isinstance(raw_body, (bytes, bytearray)) or not raw_body:
        return False
    key = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    if not key:
        return False
    try:
        expected = hmac.new(key, bytes(raw_body), hashlib.sha512).hexdigest()
    except Exception:
        return False
    if len(signature) != len(expected):
        return False
    return hmac.compare_digest(signature, expected)


def paystack_event_identity(raw_body: Any) -> str:
    """Durable deduplication key for one delivery. See module docstring."""
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    return "evt_" + hashlib.sha256(bytes(raw_body)).hexdigest()


# --------------------------------------------------------------------------
# Event parsing / correlation helpers (no I/O).
# --------------------------------------------------------------------------

def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def extract_refs(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Return (subscription_code, customer_code) from known Paystack paths.

    subscription.create/disable/not_renew carry the subscription object as
    `data`; invoice events nest it under `data.subscription`. Email is
    NEVER used for correlation (see process function).
    """
    data = _as_dict(payload.get("data"))
    sub = _as_dict(data.get("subscription"))
    code = data.get("subscription_code") or sub.get("subscription_code")
    customer = _as_dict(data.get("customer")) or _as_dict(sub.get("customer"))
    customer_code = customer.get("customer_code")
    return (str(code) if code else None,
            str(customer_code) if customer_code else None)


def parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        text = value.replace("Z", "+00:00")
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


# Provider timestamp fields consulted for ordering, in priority order.
# Only these documented Paystack object timestamps are used; nothing is
# inferred from amounts, emails, names, or delivery timing.
PROVIDER_TIME_FIELDS = ("created_at", "paid_at", "transaction_date")


def extract_provider_time(data: Dict[str, Any]) -> Optional[datetime]:
    """Best-effort authoritative provider timestamp for ordering.

    Returns None when no listed field is present and parseable; callers
    treat None as "no ordering information" (arrival-wins), never as
    epoch zero.
    """
    data = _as_dict(data)
    for field in PROVIDER_TIME_FIELDS:
        moment = parse_dt(data.get(field))
        if moment is not None:
            return moment
    return None


def extract_provider_sequence(data: Dict[str, Any]) -> Optional[str]:
    """Best-effort provider sequence token, if the payload carries one.

    No documented Paystack webhook sequence field is currently observed,
    so this returns None (column stays NULL) until one is. Never
    synthesized from hashes or timestamps.
    """
    return None


@dataclass
class Transition:
    """Decision for one correlated event. `status=None` mutates nothing."""
    status: Optional[str] = None
    fields: Dict[str, Any] = field(default_factory=dict)
    outcome: str = "processed"  # processed | ignored


def decide_transition(current_status: Optional[str], event_type: str,
                      data: Dict[str, Any],
                      now: Optional[datetime] = None,
                      stored_period_end: Any = None) -> Transition:
    """Pure state machine. Conservative by design; see 8E report table."""
    moment = now or datetime.now(timezone.utc)

    if event_type == "subscription.create":
        fields: Dict[str, Any] = {"status": "active"}
        sub_code, customer_code = extract_refs({"data": data})
        if sub_code:
            fields["provider_subscription_id"] = sub_code
        if customer_code:
            fields["provider_customer_id"] = customer_code
        fields["provider"] = PROVIDER
        nxt = parse_dt(data.get("next_payment_date"))
        if nxt is not None:
            fields["current_period_end"] = nxt.isoformat()
        # current_period_start is intentionally NEVER populated here
        # (8.3.1 §B): no field in the supported webhook payloads is
        # authoritative for the billing-period start. `data.created_at`
        # is a record timestamp also used for ordering, not a period
        # semantic; `paid_at`/`transaction_date` are payment timestamps.
        # The column stays NULL (COALESCE preserves any stored value)
        # and the entitlement resolver never depends on it.
        return Transition(status="active", fields=fields)

    if event_type == "invoice.payment_failed":
        # Conservative: past_due only from a good-standing state. Never
        # escalate canceled/expired, never revoke on a transient failure.
        if current_status in ("active", "trialing"):
            return Transition(status="past_due",
                              fields={"status": "past_due"})
        return Transition(outcome="ignored")

    if event_type == "invoice.update":
        # Only an authoritative paid invoice restores good standing, and
        # only from a non-terminal state. A canceled/expired/paused row
        # is NEVER resurrected by an invoice: only a fresh
        # subscription.create may reactivate it (8.3 §5, mandatory).
        if str(data.get("status", "")).lower() in INVOICE_PAID_STATUSES:
            if current_status in ("past_due", "trialing"):
                return Transition(status="active", fields={"status": "active"})
            if current_status == "active":
                return Transition(outcome="processed")
            return Transition(outcome="ignored")
        return Transition(outcome="ignored")

    if event_type == "charge.success":
        # Payment confirmation only. Period/state authority stays with
        # subscription and invoice events; never mutated here.
        return Transition(outcome="processed")

    if event_type == "subscription.not_renew":
        # Renewal is off but the paid period still stands: preserve access,
        # keep the event payload for later reconciliation. No new status
        # is invented and nothing is revoked or extended.
        return Transition(outcome="processed")

    if event_type == "subscription.disable":
        # Actual provider-side disablement. Do not revoke access that was
        # already paid for: a stored future period end wins.
        end = parse_dt(stored_period_end) if stored_period_end else None
        if end is not None and end > moment:
            return Transition(outcome="processed")
        return Transition(status="canceled", fields={"status": "canceled"})

    if event_type == "subscription.expiring_cards":
        return Transition(outcome="processed")

    return Transition(outcome="ignored")


# --------------------------------------------------------------------------
# Persistence boundary (fake in tests, Supabase RPC in production).
# --------------------------------------------------------------------------

# The only subscription columns a provider event may ever write.
# decide_transition returns a free-form dict; this whitelist is what
# actually reaches the database, so no provider payload can smuggle in
# other columns (user_id, role, plan, ... are unreachable from here).
UPDATABLE_COLUMNS = (
    "status",
    "provider",
    "provider_customer_id",
    "provider_subscription_id",
    "current_period_start",
    "current_period_end",
)


@dataclass
class SubscriptionUpdate:
    """Whitelisted columns to apply. Every field is optional; None = leave
    the stored value alone (COALESCE in SQL)."""

    new_status: Optional[str] = None
    provider: Optional[str] = None
    provider_customer_id: Optional[str] = None
    provider_subscription_id: Optional[str] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None

    def is_empty(self) -> bool:
        return (self.new_status is None and self.provider is None
                and self.provider_customer_id is None
                and self.provider_subscription_id is None
                and self.current_period_start is None
                and self.current_period_end is None)


def build_update(fields: Dict[str, Any]) -> SubscriptionUpdate:
    """Narrow a Transition's field dict to the whitelisted columns."""
    return SubscriptionUpdate(
        new_status=fields.get("status"),
        provider=fields.get("provider"),
        provider_customer_id=fields.get("provider_customer_id"),
        provider_subscription_id=fields.get("provider_subscription_id"),
        current_period_start=fields.get("current_period_start"),
        current_period_end=fields.get("current_period_end"),
    )


class SubscriptionStore(ABC):
    """Persistence surface for idempotent webhook processing.

    apply_event() MUST be atomic: the idempotency claim, the subscription
    update and the event completion either all land or none do. The
    production implementation is the single-call SQL function
    public.apply_paystack_event (see the 8E migration); splitting it into
    separate client calls would leave events stuck in 'received' after a
    partial failure and silently lose subscription updates.
    """

    @abstractmethod
    def find_by_provider_subscription(self, provider: str,
                                      code: str) -> Optional[Dict[str, Any]]:
        """Read-only lookup by provider subscription code."""

    @abstractmethod
    def find_by_provider_customer(self, provider: str,
                                  code: str) -> Optional[Dict[str, Any]]:
        """Read-only lookup by provider customer code."""

    @abstractmethod
    def apply_event(self, *, provider: str, provider_event_id: str,
                    event_type: str, payload: Dict[str, Any],
                    subscription_id: Any = None,
                    processing_status: str = "processed",
                    error_code: Optional[str] = None,
                    update: Optional[SubscriptionUpdate] = None,
                    provider_occurred_at: Optional[str] = None,
                    provider_sequence: Optional[str] = None) -> "ApplyResult":
        """Record the event and apply `update` in ONE atomic step.

        Returns inserted=False when (provider, provider_event_id) already
        existed, in which case nothing at all was written.

        provider_occurred_at/provider_sequence are ordering metadata only
        (ISO string / opaque token, both nullable); the production RPC
        enforces the stale-event guard atomically from them.
        """


@dataclass
class ApplyResult:
    event_id: Any = None
    inserted: bool = True


@dataclass
class ProcessResult:
    outcome: str  # processed | ignored | duplicate | failed
    event_id: Any = None
    subscription_id: Any = None
    status: Optional[str] = None


def _apply(store: SubscriptionStore, *, identity: str, event_type: str,
           payload: Dict[str, Any], subscription_id: Any = None,
           status: str = "processed",
           error_code: Optional[str] = None,
           update: Optional[SubscriptionUpdate] = None,
           provider_occurred_at: Optional[str] = None,
           provider_sequence: Optional[str] = None) -> ProcessResult:
    """Single atomic write. Any store failure rolls the whole thing back."""
    try:
        applied = store.apply_event(
            provider=PROVIDER, provider_event_id=identity,
            event_type=event_type, payload=payload,
            subscription_id=subscription_id, processing_status=status,
            error_code=error_code, update=update,
            provider_occurred_at=provider_occurred_at,
            provider_sequence=provider_sequence)
    except Exception as exc:
        # Nothing was persisted (the boundary is atomic), so this delivery
        # leaves no trace and a retryable redelivery starts from scratch.
        raise WebhookError("Webhook processing failed",
                           f"{type(exc).__name__} while recording {event_type}")
    if not applied.inserted:
        return ProcessResult(outcome="duplicate", event_id=applied.event_id)
    return ProcessResult(outcome=status, event_id=applied.event_id)


def process_paystack_event(
    store: SubscriptionStore, *, raw_body: bytes,
    now: Optional[Callable[[], datetime]] = None,
) -> ProcessResult:
    """Idempotent orchestration for one VERIFIED delivery.

    Caller must verify the HMAC signature first. Order of operations:
    parse -> validate -> correlate (read-only) -> decide -> ONE atomic
    write. An already-recorded (provider, provider_event_id) short-circuits
    to "duplicate" without touching any subscription. Unknown or
    uncorrelated events are recorded as ignored and never grant, create or
    revoke anything. Failures raise WebhookError so the route returns a
    retryable non-2xx.
    """
    import json

    clock = now or (lambda: datetime.now(timezone.utc))
    identity = paystack_event_identity(raw_body)

    try:
        payload = json.loads(bytes(raw_body).decode("utf-8"))
    except Exception:
        _apply(store, identity=identity, event_type="malformed",
               payload={"raw": "unparseable"}, status="failed",
               error_code="malformed_json")
        raise WebhookError("Invalid webhook payload", "unparseable JSON body",
                           retryable=False)

    if not isinstance(payload, dict):
        _apply(store, identity=identity, event_type="malformed",
               payload={"raw": "non-object JSON body"}, status="failed",
               error_code="non_object_json")
        raise WebhookError("Invalid webhook payload", "non-object JSON body",
                           retryable=False)

    event_type = payload.get("event")
    if not isinstance(event_type, str) or not event_type.strip():
        _apply(store, identity=identity, event_type="missing",
               payload={"keys": sorted(payload.keys())}, status="failed",
               error_code="missing_event")
        raise WebhookError("Invalid webhook payload", "missing event field",
                           retryable=False)
    event_type = event_type.strip()

    # Correlation is a READ-ONLY lookup. Nothing is written until the single
    # atomic apply below, so a lookup failure leaves no partial state.
    data = _as_dict(payload.get("data"))
    sub_code, customer_code = extract_refs(payload)

    row = None
    try:
        if sub_code:
            row = store.find_by_provider_subscription(PROVIDER, sub_code)
        if row is None and customer_code and event_type == "subscription.create":
            # A first authoritative event may adopt the identity of a
            # subscription the checkout flow already recorded for that
            # customer. Email is never a correlation key.
            row = store.find_by_provider_customer(PROVIDER, customer_code)
    except Exception as exc:
        raise WebhookError("Webhook processing failed",
                           f"correlation lookup failed: {type(exc).__name__}")

    known = event_type in SUPPORTED_EVENTS
    if not known or row is None:
        # Recorded for the audit trail and applied to nothing. An event we
        # cannot attribute to exactly one existing subscription must never
        # create one, guess one, or grant access.
        return _apply(store, identity=identity, event_type=event_type,
                      payload=payload, subscription_id=(row or {}).get("id"),
                      status="ignored",
                      error_code=("unknown_event" if not known
                                  else "uncorrelated"))

    current = row.get("status")
    occurred = extract_provider_time(data)
    occurred_iso = occurred.isoformat() if occurred is not None else None
    sequence = extract_provider_sequence(data)

    # Stale-event fast path (the RPC re-enforces this atomically for
    # production races): when ordering metadata proves this delivery is
    # older than the latest event already applied to the row, record it
    # as ignored/stale_event and change nothing. NULL on either side
    # means "no ordering information" -> arrival-wins, never stale.
    last_applied = parse_dt(row.get("last_applied_occurred_at"))
    if occurred is not None and last_applied is not None \
            and occurred < last_applied:
        return _apply(store, identity=identity, event_type=event_type,
                      payload=payload, subscription_id=row.get("id"),
                      status="ignored", error_code="stale_event",
                      provider_occurred_at=occurred_iso,
                      provider_sequence=sequence)

    decision = decide_transition(
        current, event_type, data, now=clock(),
        stored_period_end=row.get("current_period_end"))
    update = None
    new_status = current
    if decision.status is not None and (
            decision.status != current or decision.fields):
        fields = dict(decision.fields)
        fields.setdefault("status", decision.status)
        update = build_update(fields)
        new_status = decision.status

    result = _apply(store, identity=identity, event_type=event_type,
                    payload=payload, subscription_id=row.get("id"),
                    status=decision.outcome, update=update,
                    provider_occurred_at=occurred_iso,
                    provider_sequence=sequence)
    result.subscription_id = row.get("id")
    result.status = new_status
    return result


__all__ = [
    "ApplyResult",
    "INVOICE_PAID_STATUSES",
    "PROVIDER",
    "PROVIDER_TIME_FIELDS",
    "ProcessResult",
    "SUPPORTED_EVENTS",
    "SubscriptionStore",
    "SubscriptionUpdate",
    "Transition",
    "UPDATABLE_COLUMNS",
    "WebhookError",
    "build_update",
    "decide_transition",
    "extract_provider_sequence",
    "extract_provider_time",
    "extract_refs",
    "parse_dt",
    "paystack_event_identity",
    "process_paystack_event",
    "verify_paystack_signature",
]
