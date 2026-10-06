"""FootyEdge billing foundation: provider abstraction + server-authoritative plans.

Test mode only. No checkout UI, no webhooks processing, no subscription
state mutation (8E owns durable state). No live calls in unit tests.

Design notes:
- Pure standard library at import time. HTTP is performed through an
  injectable transport so tests never touch the network and the module
  never requires a Paystack SDK (httpx, already a backend dependency, is
  used by the default transport only).
- Paystack amount contract (verified): amounts are integer KOBO
  (smallest NGN unit), so Growth NGN 5,000 -> 500000 and Business
  NGN 15,000 -> 1500000. Provider plan codes come from the environment,
  never from source or from the browser.
- The server chooses the plan configuration. Client-submitted amounts,
  prices, currencies and intervals are never accepted.
"""

from __future__ import annotations

import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("billing")

PAYSTACK_API_BASE = "https://api.paystack.co"


class BillingError(Exception):
    """Safe, user-facing billing failure. `public` is the only client text."""

    def __init__(self, public: str, detail: str = "") -> None:
        super().__init__(public)
        self.public = public
        if detail:
            # Server-side diagnostics only; never returned to the browser.
            logger.warning("billing: %s", detail)


class BillingNotConfigured(BillingError):
    def __init__(self, detail: str = "missing billing configuration") -> None:
        super().__init__("Payment initialization failed", detail)


# --------------------------------------------------------------------------
# Commercial plan configuration (server-authoritative).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanConfig:
    plan: str
    amount_kobo: int
    currency: str = "NGN"
    interval: str = "monthly"
    provider_plan_code_env: str = ""


PAID_PLANS: Dict[str, PlanConfig] = {
    "growth": PlanConfig(plan="growth", amount_kobo=500_000,
                         provider_plan_code_env="PAYSTACK_GROWTH_PLAN_CODE"),
    "business": PlanConfig(plan="business", amount_kobo=1_500_000,
                           provider_plan_code_env="PAYSTACK_BUSINESS_PLAN_CODE"),
}

# Plans that must never produce a Paystack recurring checkout.
NON_BILLABLE_PLANS = ("starter", "enterprise")


def resolve_plan(plan: str) -> PlanConfig:
    """Validate the requested plan and return its server-side configuration."""
    key = (plan or "").strip().lower()
    if key in NON_BILLABLE_PLANS or key not in PAID_PLANS:
        raise BillingError("Invalid plan", f"rejected plan request: {plan!r}")
    return PAID_PLANS[key]


def provider_plan_code(config: PlanConfig) -> str:
    """Read the provider plan code from the environment. Fail closed."""
    code = os.environ.get(config.provider_plan_code_env, "").strip()
    if not code:
        raise BillingNotConfigured(
            f"missing env {config.provider_plan_code_env} for plan {config.plan}")
    if _looks_placeholder(code):
        raise BillingNotConfigured(
            f"invalid env {config.provider_plan_code_env} for plan {config.plan}")
    return code


def paystack_secret() -> str:
    """Server-side secret only. Never VITE_-prefixed, never returned."""
    secret = os.environ.get("PAYSTACK_SECRET_KEY", "").strip()
    if not secret:
        raise BillingNotConfigured("missing env PAYSTACK_SECRET_KEY")
    return secret


# --------------------------------------------------------------------------
# Paystack environment validation (8.3 §12). Explicit declaration only:
# PAYSTACK_MODE=test|live, with the secret prefix required to match the
# declared mode. No defaults, no live->test fallback, no client input.
# --------------------------------------------------------------------------

PAYSTACK_MODES = ("test", "live")

_MODE_SECRET_PREFIX = {"test": "sk_test_", "live": "sk_live_"}

# Fragments that mark a configured value as an unreplaced placeholder.
_PLACEHOLDER_FRAGMENTS = ("placeholder", "example", "xxx", "changeme",
                          "your_", "todo", "<", ">", "replace")


def _looks_placeholder(value: str) -> bool:
    lowered = (value or "").strip().lower()
    if not lowered:
        return True
    return any(frag in lowered for frag in _PLACEHOLDER_FRAGMENTS)


def paystack_mode() -> str:
    """Declared Paystack environment. Missing/unknown fails closed."""
    mode = os.environ.get("PAYSTACK_MODE", "").strip().lower()
    if mode not in PAYSTACK_MODES:
        raise BillingNotConfigured("missing or invalid env PAYSTACK_MODE")
    return mode


def validate_paystack_config() -> str:
    """Validate the full Paystack environment for the declared mode.

    Returns the mode when everything matches. Raises BillingNotConfigured
    (safe public message, diagnostics server-side only) otherwise. Never
    includes secret values in any message.
    """
    mode = paystack_mode()
    secret = paystack_secret()
    if not secret.startswith(_MODE_SECRET_PREFIX[mode]):
        raise BillingNotConfigured(
            f"PAYSTACK_SECRET_KEY does not match PAYSTACK_MODE={mode}")
    for plan in ("growth", "business"):
        # Plan-code presence + placeholder rejection (fail closed).
        provider_plan_code(PAID_PLANS[plan])
    return mode


def new_reference(prefix: str = "footyedge") -> str:
    """Unique, non-sequential transaction reference (no secrets, no IDs)."""
    return f"{prefix}_{uuid.uuid4().hex}"


# --------------------------------------------------------------------------
# Provider abstraction. Paystack implements it; Flutterwave can later.
# --------------------------------------------------------------------------

HttpPost = Callable[..., Any]
HttpGet = Callable[..., Any]


@dataclass
class CheckoutResult:
    authorization_url: str
    reference: str
    plan: str


class PaymentProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def initialize_subscription_checkout(
        self, *, email: str, config: PlanConfig, reference: str
    ) -> CheckoutResult:
        """Start a checkout. Must NOT mark any subscription active."""

    @abstractmethod
    def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """Return a safe subset of the verified transaction."""

    @abstractmethod
    def get_subscription(self, subscription_code: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def cancel_subscription(self, subscription_code: str) -> Dict[str, Any]:
        ...


def _httpx_post(url: str, *, headers: Dict[str, str],
                payload: Dict[str, Any], timeout: float = 20.0) -> Dict[str, Any]:
    import httpx  # local import: keeps this module importable without deps

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:
        raise BillingError("Payment provider unavailable",
                           f"provider POST failed: {type(exc).__name__}")
    return _decode_provider_response(resp)


def _httpx_get(url: str, *, headers: Dict[str, str],
               timeout: float = 20.0) -> Dict[str, Any]:
    import httpx  # local import: keeps this module importable without deps

    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
    except Exception as exc:
        raise BillingError("Payment provider unavailable",
                           f"provider GET failed: {type(exc).__name__}")
    return _decode_provider_response(resp)


def _decode_provider_response(resp: Any) -> Dict[str, Any]:
    try:
        body = resp.json()
    except Exception:
        raise BillingError("Payment provider unavailable",
                           f"non-JSON provider response: {getattr(resp, 'status_code', '?')}")
    if getattr(resp, "status_code", 500) >= 400 or not body.get("status"):
        # Never forward provider internals; log a redacted hint only.
        message = ""
        if isinstance(body, dict):
            message = str(body.get("message", ""))[:120]
        raise BillingError("Payment initialization failed",
                           f"provider rejected request: {message}")
    data = body.get("data")
    return data if isinstance(data, dict) else {}


class PaystackProvider(PaymentProvider):
    """Paystack implementation (test mode first). Secrets stay server-side."""

    name = "paystack"

    def __init__(self, secret: str,
                 http_post: HttpPost = _httpx_post,
                 http_get: HttpGet = _httpx_get) -> None:
        if not secret:
            raise BillingNotConfigured("empty Paystack secret")
        self._secret = secret
        self._post = http_post
        self._get = http_get

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._secret}",
                "Content-Type": "application/json"}

    def initialize_subscription_checkout(
        self, *, email: str, config: PlanConfig, reference: str
    ) -> CheckoutResult:
        if not email or "@" not in email:
            raise BillingError("Invalid plan", "checkout without account email")
        data = self._post(
            f"{PAYSTACK_API_BASE}/transaction/initialize",
            headers=self._headers(),
            payload={"email": email,
                     "amount": config.amount_kobo,
                     "currency": config.currency,
                     "plan": provider_plan_code(config),
                     "reference": reference},
        )
        url = data.get("authorization_url", "")
        ref = data.get("reference", "")
        if not url or not ref:
            raise BillingError("Payment initialization failed",
                               "provider init missing authorization_url/reference")
        return CheckoutResult(authorization_url=url, reference=ref,
                              plan=config.plan)

    def verify_transaction(self, reference: str) -> Dict[str, Any]:
        if not reference:
            raise BillingError("Payment initialization failed",
                               "verify without reference")
        data = self._get(
            f"{PAYSTACK_API_BASE}/transaction/verify/{reference}",
            headers=self._headers(),
        )
        # Safe subset only: status + amounts + plan reference. No auth data.
        return {"status": data.get("status"),
                "reference": data.get("reference", reference),
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "plan": (data.get("plan") or {}).get("plan_code")
                if isinstance(data.get("plan"), dict) else None}

    def get_subscription(self, subscription_code: str) -> Dict[str, Any]:
        data = self._get(
            f"{PAYSTACK_API_BASE}/subscription/{subscription_code}",
            headers=self._headers(),
        )
        return {"subscription_code": data.get("subscription_code",
                                              subscription_code),
                "status": data.get("status"),
                "plan": (data.get("plan") or {}).get("plan_code")
                if isinstance(data.get("plan"), dict) else None}

    def cancel_subscription(self, subscription_code: str) -> Dict[str, Any]:
        data = self._post(
            f"{PAYSTACK_API_BASE}/subscription/disable",
            headers=self._headers(),
            payload={"code": subscription_code, "token": subscription_code},
        )
        return {"subscription_code": subscription_code,
                "disabled": bool(data)}


# --------------------------------------------------------------------------
# Server-side checkout orchestration (framework-agnostic, fully testable).
# --------------------------------------------------------------------------

@dataclass
class CheckoutRequest:
    user_id: Optional[str]
    email: Optional[str]
    plan: str


def build_provider(secret: Optional[str] = None) -> PaystackProvider:
    # Full environment validation first: mode declaration, secret/mode
    # match, and real plan codes. A caller-supplied secret is still
    # accepted for tests/transports, but the declared environment must
    # be coherent regardless.
    validate_paystack_config()
    return PaystackProvider(secret if secret else paystack_secret())


def prepare_checkout(request: CheckoutRequest,
                     provider: Optional[PaymentProvider] = None
                     ) -> Dict[str, str]:
    """Validate identity + plan server-side, then initialize checkout.

    Returns ONLY safe browser fields. Never marks a subscription active;
    durable state belongs to 8E webhook synchronization.
    """
    if not request.user_id or not request.email:
        raise BillingError("Authentication required",
                           "checkout without server-derived identity")
    config = resolve_plan(request.plan)
    active = provider or build_provider()
    result = active.initialize_subscription_checkout(
        email=request.email, config=config, reference=new_reference())
    return {"authorization_url": result.authorization_url,
            "reference": result.reference, "plan": result.plan}


# --------------------------------------------------------------------------
# Provisional subscription rows (8.3 §8, bootstrap fix).
# --------------------------------------------------------------------------

# A provisional row marks "checkout initialized, provider confirmation
# pending". It uses status "expired" (a non-entitling state: the 8F
# resolver maps expired -> starter with zero paid capabilities) because
# the CHECK constraint admits no dedicated pending state and no new
# state may be invented in Objective 8. NULL provider identifiers mean
# "not yet bound to any provider customer/subscription".
PROVISIONAL_STATUS = "expired"


def build_provisional_row(user_id: str, plan: str,
                          reference: Optional[str] = None) -> Dict[str, Any]:
    """Build the provisional subscription row for an authenticated checkout.

    Caller must pass the SERVER-DERIVED user_id (from the verified JWT),
    never a browser-supplied id, and a plan already accepted by
    resolve_plan(). Grants zero paid capabilities by construction.
    Persistence (service-role upsert, insert-only) lives in billing_api.

    `reference` is the `footyedge_<uuid4hex>` transaction reference the
    server minted and the provider echoed at initialization (8.3.1 §A):
    the only authoritative checkout<->provider correlation token. It is
    stored as an audit/anti-replay token for the future server-side
    verify-based binder; the webhook NEVER matches on it and it never
    identifies a user on its own.
    """
    key = (plan or "").strip().lower()
    if key not in PAID_PLANS:
        raise BillingError("Invalid plan",
                           f"provisional row refused for plan {plan!r}")
    if not user_id:
        raise BillingError("Authentication required",
                           "provisional row without server-derived identity")
    return {"user_id": user_id,
            "plan": key,
            "status": PROVISIONAL_STATUS,
            "provider": "paystack",
            "provider_customer_id": None,
            "provider_subscription_id": None,
            "provider_reference": reference,
            "current_period_start": None,
            "current_period_end": None}


__all__ = [
    "BillingError",
    "BillingNotConfigured",
    "CheckoutRequest",
    "CheckoutResult",
    "PAID_PLANS",
    "PAYSTACK_MODES",
    "NON_BILLABLE_PLANS",
    "PROVISIONAL_STATUS",
    "PaymentProvider",
    "PaystackProvider",
    "build_provider",
    "build_provisional_row",
    "new_reference",
    "paystack_mode",
    "prepare_checkout",
    "provider_plan_code",
    "paystack_secret",
    "resolve_plan",
    "validate_paystack_config",
]
