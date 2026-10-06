"""Telegram HTTP boundary (transport adapter). Thin FastAPI wrapper.

All transport logic lives in telegram_adapter.py (framework-agnostic and
unit-tested). This module only: validates the webhook secret header,
hands the raw delivery to the adapter, wires the service-role Supabase
store, resolves server-side identity/entitlements, and maps safe errors
to HTTP. No business logic, no predictions, no bets, no payments.

The adapter is implementation-complete but INACTIVE until a bot token and
webhook secret are configured and a webhook is registered out-of-band
(separately authorized; never performed here).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request

from entitlements import resolve_entitlements
from telegram_adapter import (
    LINK_TOKEN_TTL_SECONDS,
    Runners,
    TelegramIdentity,
    TelegramSender,
    TelegramStore,
    TelegramError,
    build_sender,
    mint_link_token,
    process_update,
)

logger = logging.getLogger("telegram_api")

router = APIRouter()


def _webhook_secret() -> str:
    """Server-side webhook secret. Never logged, never returned."""
    return os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")


def _bot_token() -> str:
    """Server-side bot token. Never logged, never returned."""
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/api/webhooks/telegram")
async def telegram_webhook(request: Request):
    """Verified Telegram delivery -> adapter processing.

    Sequence: raw body -> secret gate -> parse/claim (atomic) -> link and
    entitlement resolution (read-only) -> permitted read-only capability
    -> formatted send -> 2xx. Duplicates and ignored commands also answer
    2xx: none of those is worth a Telegram retry. Retryable failures
    answer 502, deterministic rejections answer 400/401.
    """
    raw = await request.body()
    provided = request.headers.get("x-telegram-bot-api-secret-token")
    secret_valid = _secret_valid(provided)
    if not secret_valid:
        # No mutation of any kind has occurred at this point.
        raise HTTPException(status_code=401, detail="Invalid webhook secret")
    if not _bot_token():
        raise HTTPException(status_code=503, detail="Telegram is not configured")

    from api import get_supabase_client  # noqa: E402  (lazy: avoids import cycle)

    store = SupabaseTelegramStore(get_supabase_client())
    sender = build_sender(_bot_token())
    try:
        result = await process_update(
            store,
            sender,
            raw_body=bytes(raw),
            secret_valid=True,
            identity_fn=lambda user_id: telegram_identity(
                get_supabase_client(), user_id),
            runners=_production_runners(get_supabase_client()),
        )
    except TelegramError as exc:
        raise HTTPException(status_code=502 if exc.retryable else 400,
                            detail=exc.public)
    return {"status": result.outcome}


def _secret_valid(provided: Optional[str]) -> bool:
    """Webhook gate. The comparison itself lives in the tested adapter."""
    from telegram_adapter import verify_webhook_secret  # noqa: E402

    return verify_webhook_secret(provided, _webhook_secret())


@router.post("/api/telegram/link-token")
async def mint_link_token_route(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """Mint a one-time Telegram linking code for the authenticated caller.

    Identity comes exclusively from the caller's Supabase JWT (server-side
    lookup); no user_id is accepted from the request. Returns the plaintext
    code once — only its hash is persisted. The plaintext is never stored
    and never logged.
    """
    from billing_api import _supabase_auth_user  # noqa: E402  (reuse: single auth layer)

    user_id, _email = _supabase_auth_user(authorization)
    code, digest = mint_link_token()
    from api import get_supabase_client  # noqa: E402

    SupabaseTelegramStore(get_supabase_client()).store_link_token(
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


def telegram_identity(supabase: Any, user_id: str) -> Optional[TelegramIdentity]:
    """Server-side identity for one FootyEdge user (adapter identity_fn).

    Email is read server-side from profiles (never supplied by Telegram).
    Lookup failure yields None, which the adapter treats as unlinked.
    """
    try:
        res = supabase.table("profiles").select("email").eq(
            "id", user_id).limit(1).execute()
        rows = res.data or []
        email = str((rows[0] or {}).get("email", "")) if rows else ""
        if not email:
            logger.warning("telegram: identity without email")
            return None
        result = resolve_entitlements(supabase, user_id, email)
        return TelegramIdentity(user_id=user_id, plan=result.plan,
                                capabilities=frozenset(result.capabilities))
    except Exception as exc:
        logger.warning("telegram: identity lookup failed: %s",
                       type(exc).__name__)
        return None


def _production_runners(supabase: Any) -> Runners:
    """Wire read-only domain fetches. Lazy api imports avoid a cycle."""
    def _fetch_today() -> List[Dict[str, Any]]:
        from api import football_client  # noqa: E402

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return list(football_client.get_matches_by_date(day) or [])

    def _fetch_matches() -> List[Dict[str, Any]]:
        from api import football_client  # noqa: E402

        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return list(football_client.get_matches_by_date(day) or [])

    def _fetch_predictions() -> List[Dict[str, Any]]:
        res = supabase.table("predictions").select("*").order(
            "created_at", desc=True).limit(10).execute()
        return [dict(row) for row in (res.data or [])]

    return Runners(fetch_today=_fetch_today, fetch_matches=_fetch_matches,
                   fetch_predictions=_fetch_predictions)


class SupabaseTelegramStore(TelegramStore):
    """Service-role backed Telegram state.

    claim_update() is one INSERT against UNIQUE(telegram_update_id): the
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

    def claim_update(self, update_id: int,
                     telegram_user_id: Optional[int]) -> bool:
        try:
            self._db.table("telegram_updates").insert({
                "telegram_update_id": update_id,
                "telegram_user_id": telegram_user_id,
                "processing_status": "received",
            }).execute()
        except Exception as exc:
            if self._is_conflict(exc):
                return False
            raise
        return True

    def complete_update(self, update_id: int, status: str,
                        error_code: Optional[str] = None) -> None:
        row: Dict[str, Any] = {"processing_status": status,
                               "processed_at": _utcnow_iso()}
        if error_code is not None:
            row["error_code"] = error_code[:64]
        self._db.table("telegram_updates").update(row).eq(
            "telegram_update_id", update_id).execute()

    def find_account(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        res = self._db.table("telegram_accounts").select("*").eq(
            "telegram_user_id", telegram_user_id).limit(1).execute()
        rows = res.data or []
        return dict(rows[0]) if rows else None

    def find_account_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        res = self._db.table("telegram_accounts").select("*").eq(
            "user_id", user_id).limit(1).execute()
        rows = res.data or []
        return dict(rows[0]) if rows else None

    def link_account(self, user_id: str, telegram_user_id: int,
                     chat_id: Optional[int],
                     username: Optional[str]) -> str:
        existing_tg = self.find_account(telegram_user_id)
        if existing_tg is not None:
            if str(existing_tg.get("user_id")) == str(user_id):
                self.touch_account(telegram_user_id, chat_id, username)
                return "linked"
            return "telegram_taken"
        existing_user = self.find_account_by_user(user_id)
        if existing_user is not None:
            return "user_taken"
        try:
            self._db.table("telegram_accounts").insert({
                "user_id": user_id,
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": chat_id,
                "telegram_username": username,
                "status": "linked",
            }).execute()
        except Exception as exc:
            if self._is_conflict(exc):
                # Lost a race: re-read to classify deterministically.
                return self.link_account(user_id, telegram_user_id, chat_id,
                                         username)
            raise
        return "linked"

    def store_link_token(self, token_hash: str, user_id: str,
                         expires_at: datetime) -> None:
        self._db.table("telegram_link_tokens").insert({
            "token_hash": token_hash,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
        }).execute()

    def peek_link_token(self, token_hash: str,
                          now: datetime) -> Optional[str]:
        res = self._db.table("telegram_link_tokens").select(
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
        res = self._db.table("telegram_link_tokens").update(
            {"consumed_at": now.isoformat()}).eq(
            "token_hash", token_hash).is_(
            "consumed_at", "null").gt(
            "expires_at", now.isoformat()).execute()
        rows = res.data or []
        if not rows:
            return None
        return str(rows[0].get("user_id"))

    def touch_account(self, telegram_user_id: int,
                      chat_id: Optional[int],
                      username: Optional[str]) -> None:
        try:
            row: Dict[str, Any] = {"last_seen_at": _utcnow_iso()}
            if chat_id is not None:
                row["telegram_chat_id"] = chat_id
            if username is not None:
                row["telegram_username"] = username
            self._db.table("telegram_accounts").update(row).eq(
                "telegram_user_id", telegram_user_id).execute()
        except Exception as exc:
            logger.warning("telegram: touch failed: %s", type(exc).__name__)


__all__ = ["router", "telegram_identity"]
