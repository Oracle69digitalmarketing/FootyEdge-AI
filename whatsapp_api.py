"""WhatsApp HTTP boundary (transport adapter). Thin FastAPI wrapper.

All transport logic lives in whatsapp_adapter.py (framework-agnostic and
unit-tested). This module only: answers webhook verification challenges,
validates the HMAC signature header, hands the raw delivery to the
adapter, wires the service-role Supabase store, resolves server-side
identity/entitlements, and maps safe errors to HTTP. No business logic,
no predictions, no bets, no payments.

The adapter is implementation-complete but INACTIVE until an access
token, phone-number id, app secret and verify token are configured and
a webhook is registered out-of-band (separately authorized; never
performed here).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request

from entitlements import resolve_entitlements
from whatsapp_adapter import (
    LINK_TOKEN_TTL_SECONDS,
    RateLimiter,
    Runners,
    WhatsAppIdentity,
    WhatsAppSender,
    WhatsAppStore,
    WhatsAppError,
    build_sender,
    mint_link_token,
    process_update,
    verify_signature,
    verify_webhook_challenge,
)

logger = logging.getLogger("whatsapp_api")

router = APIRouter()

_limiter = RateLimiter()

# Link-token minting: max 5 codes per user per hour (single process).
# Redemption attempts (/link messages) are additionally bounded by the
# per-sender delivery limiter (20/min) plus a stricter link-attempt
# limiter enforced in the adapter (10 per 10 min per sender).
LINK_MINT_COUNT = 5
LINK_MINT_WINDOW_SECONDS = 3600

_mint_limiter = RateLimiter(max_events=LINK_MINT_COUNT,
                            window_seconds=LINK_MINT_WINDOW_SECONDS)

_link_limiter = RateLimiter(max_events=10, window_seconds=600)


def _verify_token() -> str:
    """Server-side webhook verify token. Never logged, never returned."""
    return os.environ.get("WHATSAPP_VERIFY_TOKEN", "")


def _app_secret() -> str:
    """Server-side Meta app secret for HMAC. Never logged, never returned."""
    return os.environ.get("WHATSAPP_APP_SECRET", "")


def _access_token() -> str:
    """Server-side Cloud API token. Never logged, never returned."""
    return os.environ.get("WHATSAPP_ACCESS_TOKEN", "")


def _phone_number_id() -> str:
    """Server-side sender number id. Never logged, never returned."""
    return os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def _api_version() -> str:
    return os.environ.get("WHATSAPP_API_VERSION", "") or "v21.0"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/api/webhooks/whatsapp")
async def whatsapp_verify(request: Request):
    """Meta webhook verification challenge (query params, no auth).

    Echoes hub.challenge only when hub.mode == subscribe and the
    verify token matches server config. Anything else is 403.
    """
    params = dict(request.query_params)
    challenge = verify_webhook_challenge(
        params.get("hub.mode"), params.get("hub.verify_token"),
        params.get("hub.challenge"), _verify_token())
    if challenge is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    from fastapi.responses import PlainTextResponse  # noqa: E402

    return PlainTextResponse(challenge)


@router.post("/api/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """Verified WhatsApp delivery -> adapter processing.

    Sequence: raw body -> HMAC gate -> parse/claim (atomic) -> link and
    entitlement resolution (read-only) -> permitted read-only capability
    or deterministic assistant reply -> formatted send -> 2xx.
    Duplicates, status receipts and ignored commands also answer 2xx:
    none of those is worth a Meta retry. Retryable failures answer 502,
    deterministic rejections answer 400/401.
    """
    raw = await request.body()
    signature_valid = verify_signature(
        request.headers.get("x-hub-signature-256"), bytes(raw),
        _app_secret())
    if not signature_valid:
        # No mutation of any kind has occurred at this point.
        raise HTTPException(status_code=401, detail="Invalid signature")
    if not _access_token() or not _phone_number_id():
        raise HTTPException(status_code=503,
                            detail="WhatsApp is not configured")

    from api import get_supabase_client  # noqa: E402  (lazy: avoids import cycle)

    store = SupabaseWhatsAppStore(get_supabase_client())
    sender = build_sender(_access_token(), _phone_number_id(),
                          _api_version())
    try:
        result = await process_update(
            store,
            sender,
            raw_body=bytes(raw),
            signature_valid=True,
            identity_fn=lambda user_id: whatsapp_identity(
                get_supabase_client(), user_id),
            runners=_production_runners(get_supabase_client()),
            limiter=_limiter,
            link_limiter=_link_limiter,
        )
    except WhatsAppError as exc:
        raise HTTPException(status_code=502 if exc.retryable else 400,
                            detail=exc.public)
    return {"status": result.outcome}


@router.post("/api/whatsapp/link-token")
async def mint_link_token_route(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Mint a one-time WhatsApp linking code for the authenticated caller.

    Identity comes exclusively from the caller's Supabase JWT (server-side
    lookup); no user_id is accepted from the request. Returns the plaintext
    code once — only its hash is persisted. The plaintext is never stored
    and never logged. Bounded to LINK_MINT_COUNT per user per hour (429
    when exceeded); the bound is per-process like the delivery limiter.
    """
    from billing_api import _supabase_auth_user  # noqa: E402  (reuse: single auth layer)

    user_id, _email = _supabase_auth_user(authorization)
    if not _mint_limiter.allow(f"mint:{user_id}"):
        raise HTTPException(status_code=429,
                            detail="Too many link codes requested")
    code, digest = mint_link_token()
    from api import get_supabase_client  # noqa: E402

    SupabaseWhatsAppStore(get_supabase_client()).store_link_token(
        digest, user_id,
        datetime.fromtimestamp(
            datetime.now(timezone.utc).timestamp() + LINK_TOKEN_TTL_SECONDS,
            tz=timezone.utc,
        ),
    )
    return {
        "code": code,
        "expires_in_seconds": LINK_TOKEN_TTL_SECONDS,
    }


def whatsapp_identity(supabase: Any, user_id: str) -> Optional[WhatsAppIdentity]:
    """Server-side identity for one FootyEdge user (adapter identity_fn).

    Email is read server-side from profiles (never supplied by WhatsApp).
    Lookup failure yields None, which the adapter treats as unlinked.
    """
    try:
        res = supabase.table("profiles").select("email").eq(
            "id", user_id).limit(1).execute()
        rows = res.data or []
        email = str((rows[0] or {}).get("email", "")) if rows else ""
        if not email:
            logger.warning("whatsapp: identity without email")
            return None
        result = resolve_entitlements(supabase, user_id, email)
        return WhatsAppIdentity(user_id=user_id, plan=result.plan,
                                capabilities=frozenset(result.capabilities))
    except Exception as exc:
        logger.warning("whatsapp: identity lookup failed: %s",
                       type(exc).__name__)
        return None


def normalize_provider_matches(response: Any) -> List[Dict[str, Any]]:
    """Map the football provider payload to formatter-ready match dicts.

    Same contract as the Telegram boundary's normalizer: unknown shapes
    yield [] and no fixture data is invented.
    """
    if not isinstance(response, dict):
        return []
    raw = response.get("response")
    if not isinstance(raw, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for match in raw:
        if not isinstance(match, dict):
            continue
        teams = match.get("teams") if isinstance(match.get("teams"), dict) else {}
        fixture = match.get("fixture") if isinstance(match.get("fixture"), dict) else {}
        league = match.get("league") if isinstance(match.get("league"), dict) else {}
        home = teams.get("home") if isinstance(teams.get("home"), dict) else {}
        away = teams.get("away") if isinstance(teams.get("away"), dict) else {}
        normalized.append({
            "home_team": home.get("name"),
            "away_team": away.get("name"),
            "league": league.get("name", ""),
            "kickoff": fixture.get("date", ""),
        })
    return normalized


def _production_runners(supabase: Any, predictor: Any = None) -> Runners:
    """Wire read-only domain fetches. Lazy api imports avoid a cycle."""
    async def _fetch_today() -> List[Dict[str, Any]]:
        from api import football_client  # noqa: E402

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            return normalize_provider_matches(
                await football_client.get_matches_by_date(day))
        except Exception as exc:
            logger.warning("whatsapp: today fetch failed: %s",
                           type(exc).__name__)
            return []

    async def _fetch_matches() -> List[Dict[str, Any]]:
        from api import football_client  # noqa: E402

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            return normalize_provider_matches(
                await football_client.get_matches_by_date(day))
        except Exception as exc:
            logger.warning("whatsapp: matches fetch failed: %s",
                           type(exc).__name__)
            return []

    def _fetch_predictions() -> List[Dict[str, Any]]:
        res = supabase.table("predictions").select("*").order(
            "created_at", desc=True).limit(10).execute()
        return [dict(row) for row in (res.data or [])]

    async def _predict_matchup(home: str, away: str) -> Optional[Dict[str, Any]]:
        engine = predictor
        if engine is None:
            try:
                from predictor import FootyEdgePredictor  # noqa: E402

                engine = FootyEdgePredictor()
            except Exception as exc:
                logger.warning("whatsapp: predictor unavailable: %s",
                               type(exc).__name__)
                return None
        try:
            result = engine.predict_match(home, away, {})
            import inspect as _inspect

            if _inspect.isawaitable(result):
                result = await result
        except Exception as exc:
            logger.warning("whatsapp: matchup failed: %s",
                           type(exc).__name__)
            return None
        return result if isinstance(result, dict) else None

    return Runners(fetch_today=_fetch_today, fetch_matches=_fetch_matches,
                   fetch_predictions=_fetch_predictions,
                   predict_matchup=_predict_matchup)


class SupabaseWhatsAppStore(WhatsAppStore):
    """Service-role backed WhatsApp state.

    claim_update() is one INSERT against UNIQUE(whatsapp_message_id): the
    constraint is the concurrency arbiter, so duplicate deliveries (even
    concurrent ones, even across restarts/workers) collapse to
    claimed=False. consume_link_token() is one conditional UPDATE, so a
    token can never be consumed twice.
    """

    def __init__(self, client: Any) -> None:
        self._db = client

    @staticmethod
    def _is_conflict(exc: Exception) -> bool:
        text = f"{type(exc).__name__} {exc}".lower()
        return ("duplicate" in text or "already exists" in text
                or "23505" in text or "unique" in text)

    def claim_update(self, message_id: str,
                     whatsapp_user_id: Optional[str]) -> bool:
        try:
            self._db.table("whatsapp_updates").insert({
                "whatsapp_message_id": message_id,
                "whatsapp_user_id": whatsapp_user_id,
                "processing_status": "received",
            }).execute()
        except Exception as exc:
            if self._is_conflict(exc):
                return False
            raise
        return True

    def complete_update(self, message_id: str, status: str,
                        error_code: Optional[str] = None) -> None:
        row: Dict[str, Any] = {"processing_status": status,
                               "processed_at": _utcnow_iso()}
        if error_code is not None:
            row["error_code"] = error_code[:64]
        self._db.table("whatsapp_updates").update(row).eq(
            "whatsapp_message_id", message_id).execute()

    def find_account(self, whatsapp_user_id: str) -> Optional[Dict[str, Any]]:
        res = self._db.table("whatsapp_accounts").select("*").eq(
            "whatsapp_user_id", whatsapp_user_id).limit(1).execute()
        rows = res.data or []
        return dict(rows[0]) if rows else None

    def find_account_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        res = self._db.table("whatsapp_accounts").select("*").eq(
            "user_id", user_id).limit(1).execute()
        rows = res.data or []
        return dict(rows[0]) if rows else None

    def link_account(self, user_id: str, whatsapp_user_id: str,
                     display_name: Optional[str]) -> str:
        existing_wa = self.find_account(whatsapp_user_id)
        if existing_wa is not None:
            if str(existing_wa.get("user_id")) == str(user_id):
                self.touch_account(whatsapp_user_id, display_name)
                return "linked"
            return "whatsapp_taken"
        existing_user = self.find_account_by_user(user_id)
        if existing_user is not None:
            return "user_taken"
        try:
            self._db.table("whatsapp_accounts").insert({
                "user_id": user_id,
                "whatsapp_user_id": whatsapp_user_id,
                "display_name": display_name,
                "status": "linked",
            }).execute()
        except Exception as exc:
            if self._is_conflict(exc):
                # Lost a race: re-read to classify deterministically.
                return self.link_account(user_id, whatsapp_user_id,
                                         display_name)
            raise
        return "linked"

    def store_link_token(self, token_hash: str, user_id: str,
                         expires_at: datetime) -> None:
        self._db.table("whatsapp_link_tokens").insert({
            "token_hash": token_hash,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
        }).execute()

    def peek_link_token(self, token_hash: str,
                        now: datetime) -> Optional[str]:
        res = self._db.table("whatsapp_link_tokens").select(
            "user_id,expires_at,consumed_at").eq(
            "token_hash", token_hash).limit(1).execute()
        rows = res.data or []
        if not rows:
            return None
        row = rows[0] or {}
        if row.get("consumed_at") is not None:
            return None
        try:
            expires = datetime.fromisoformat(
                str(row.get("expires_at")).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            return None
        return str(row.get("user_id"))

    def consume_link_token(self, token_hash: str,
                           now: datetime) -> Optional[str]:
        res = self._db.table("whatsapp_link_tokens").update(
            {"consumed_at": now.isoformat()}).eq(
            "token_hash", token_hash).is_(
            "consumed_at", "null").gt(
            "expires_at", now.isoformat()).execute()
        rows = res.data or []
        if not rows:
            return None
        return str(rows[0].get("user_id"))

    def touch_account(self, whatsapp_user_id: str,
                      display_name: Optional[str]) -> None:
        try:
            row: Dict[str, Any] = {"last_seen_at": _utcnow_iso()}
            if display_name is not None:
                row["display_name"] = display_name
            self._db.table("whatsapp_accounts").update(row).eq(
                "whatsapp_user_id", whatsapp_user_id).execute()
        except Exception as exc:
            logger.warning("whatsapp: touch failed: %s", type(exc).__name__)

    _PREF_COLUMNS = ("match_updates", "prediction_alerts")

    def get_preferences(self, user_id: str) -> Dict[str, bool]:
        try:
            res = self._db.table("whatsapp_preferences").select(
                "match_updates,prediction_alerts").eq(
                "user_id", user_id).limit(1).execute()
        except Exception as exc:
            logger.warning("whatsapp: prefs read failed: %s",
                           type(exc).__name__)
            raise
        rows = res.data or []
        if not rows:
            return {key: False for key in self._PREF_COLUMNS}
        row = rows[0] or {}
        return {key: bool(row.get(key, False))
                for key in self._PREF_COLUMNS}

    def set_preferences(self, user_id: str,
                        prefs: Dict[str, bool]) -> Dict[str, bool]:
        current = self.get_preferences(user_id)
        merged = dict(current)
        for key in self._PREF_COLUMNS:
            if key in (prefs or {}):
                merged[key] = bool(prefs[key])
        try:
            self._db.table("whatsapp_preferences").upsert(
                {"user_id": user_id, **merged},
                on_conflict="user_id").execute()
        except Exception as exc:
            logger.warning("whatsapp: prefs write failed: %s",
                           type(exc).__name__)
            raise
        return merged


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["router", "whatsapp_identity", "normalize_provider_matches"]
