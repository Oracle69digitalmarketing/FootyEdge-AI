"""FootyEdge Telegram transport adapter (Objective 9.1).

Thin channel layer only. Responsibilities:

  telegram_adapter.py   -> webhook-secret check, update parsing, link-token
                           minting, command routing, entitlement gating,
                           response formatting, send orchestration (this file)
  telegram_api.py       -> FastAPI boundary only (raw body, headers, status
                           codes, service-role store wiring); no business logic

The adapter NEVER: resolves identity from usernames/names/emails, accepts a
client-supplied user_id, mutates subscriptions, infers plans, generates
predictions/EV/Kelly, touches bets/portfolios, or handles payments/admin.

Stdlib only at import time (same pattern as billing.py /
subscription_service.py) so unit tests run with no network, no Supabase,
no FastAPI and no python-telegram-bot. Outbound delivery goes through an
injectable async sender; production prefers python-telegram-bot's Bot API
client and falls back to httpx (both constructed lazily, never imported
at module load).

Update identity: Telegram's `update_id` is the delivery key. The store
claims it atomically (UNIQUE constraint arbiter); byte-identical
redeliveries collide and short-circuit to "duplicate" with no re-execution
and no second response.

Link tokens: 192-bit cryptographically random codes; only the SHA-256 hex
is persisted. Tokens are short-lived, bound to one FootyEdge user_id, and
consumed atomically (single conditional write). Plaintext never touches
the database and never crosses the Telegram channel except inside the
user's own `/link <code>` message.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger("telegram_adapter")

# Telegram Bot API per-message text limit. Chunk below it.
TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CHUNK_SIZE = 4000

# Link-token lifetime. Short by design: the code is a bearer credential
# until consumed.
LINK_TOKEN_TTL_SECONDS = 900
LINK_TOKEN_BYTES = 24  # 192 bits of entropy (>= 128-bit requirement)

# Initial command surface (9.1). Anything else is default-deny: unknown
# commands get a safe informational reply, deferred commands get a
# "not available" reply. Bet/payment/subscribe/admin commands MUST NEVER
# appear here (see module docstring and the regression tests).
SUPPORTED_COMMANDS = (
    "/start",
    "/help",
    "/link",
    "/status",
    "/today",
    "/matches",
    "/predictions",
)

# Recognized but intentionally unimplemented in 9.1. Answered, never routed.
DEFERRED_COMMANDS = (
    "/valuebets",
    "/acca",
    "/players",
    "/teams",
    "/analyze",
    "/bet",
    "/placebet",
    "/payment",
    "/subscribe",
    "/admin",
)

# Command -> required FootyEdge capability (None = linked-or-not public
# flow; link state is still checked where the command needs identity).
COMMAND_CAPABILITIES: Dict[str, Optional[str]] = {
    "/start": None,
    "/help": None,
    "/link": None,
    "/status": None,
    "/today": "match_intelligence",
    "/matches": "match_intelligence",
    "/predictions": "predictions",
}


class TelegramError(Exception):
    """Safe adapter failure. Only `.public` may reach a user/HTTP caller."""

    def __init__(self, public: str, detail: str = "",
                 retryable: bool = False) -> None:
        super().__init__(public)
        self.public = public
        self.retryable = retryable
        if detail:
            logger.warning("telegram: %s", detail)


# --------------------------------------------------------------------------
# Webhook secret validation (constant-time, fail closed).
# --------------------------------------------------------------------------

def verify_webhook_secret(provided: Any, expected: Any) -> bool:
    """Compare the Telegram secret-token header against server config.

    Rejects missing/empty/mismatched/non-string values. Uses
    hmac.compare_digest so timing reveals nothing about the secret.
    """
    if not expected or not isinstance(expected, (str, bytes)):
        return False
    if not provided or not isinstance(provided, str):
        return False
    exp = expected.encode("utf-8") if isinstance(expected, str) else bytes(expected)
    got = provided.encode("utf-8")
    if not exp or len(got) != len(exp):
        return False
    return hmac.compare_digest(got, exp)


# --------------------------------------------------------------------------
# Update parsing (no I/O).
# --------------------------------------------------------------------------

@dataclass
class ParsedUpdate:
    update_id: Optional[int] = None
    telegram_user_id: Optional[int] = None
    chat_id: Optional[int] = None
    username: Optional[str] = None
    text: str = ""
    command: Optional[str] = None
    args: Tuple[str, ...] = ()


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_update(payload: Any) -> ParsedUpdate:
    """Normalize one Telegram update into routing fields.

    The Telegram username is extracted for display/audit only and MUST
    NEVER be used as identity (see process_update: identity comes solely
    from the server-side telegram_accounts mapping).
    """
    payload = _as_dict(payload)
    raw_uid = payload.get("update_id")
    update_id = raw_uid if isinstance(raw_uid, int) and not isinstance(raw_uid, bool) else None

    message = _as_dict(payload.get("message")) or _as_dict(payload.get("edited_message"))
    sender = _as_dict(message.get("from"))
    chat = _as_dict(message.get("chat"))
    from_id = sender.get("id")
    chat_id = chat.get("id")
    telegram_user_id = from_id if isinstance(from_id, int) and not isinstance(from_id, bool) else None
    chat_id = chat_id if isinstance(chat_id, int) and not isinstance(chat_id, bool) else None
    username = sender.get("username")
    username = str(username) if isinstance(username, str) and username else None
    text = message.get("text", "")
    text = text if isinstance(text, str) else ""

    command: Optional[str] = None
    args: Tuple[str, ...] = ()
    stripped = text.strip()
    if stripped.startswith("/"):
        head, _, rest = stripped.partition(" ")
        # Strip an optional "@BotName" suffix: "/start@FootyEdgeBot".
        head = head.split("@", 1)[0].lower()
        command = head or None
        args = tuple(rest.split()) if rest.strip() else ()

    return ParsedUpdate(
        update_id=update_id,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        username=username,
        text=text,
        command=command,
        args=args,
    )


# --------------------------------------------------------------------------
# Link tokens (hash-only persistence).
# --------------------------------------------------------------------------

def mint_link_token() -> Tuple[str, str]:
    """Return (plaintext code, sha256 hex). Persist ONLY the hash."""
    code = secrets.token_urlsafe(LINK_TOKEN_BYTES)
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
    return code, digest


def hash_link_token(code: Any) -> Optional[str]:
    """Hash a presented code for lookup. None when malformed."""
    if not isinstance(code, str) or not code or len(code) > 256:
        return None
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Identity + capability surface (injected; production wires entitlements).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TelegramIdentity:
    """Server-resolved FootyEdge identity for one linked Telegram account."""
    user_id: str
    plan: str
    capabilities: FrozenSet[str] = field(default_factory=frozenset)


IdentityFn = Callable[[str], Optional[TelegramIdentity]]
"""Resolve a FootyEdge user_id to its identity, or None on lookup failure."""


@dataclass
class Runners:
    """Existing application/domain callables the adapter may invoke.

    Deliberately narrow: read-only match/prediction fetches only. There is
    intentionally no bet/portfolio/payment/admin runner anywhere in this
    module, so Telegram structurally cannot reach those capabilities.

    Fetchers may be plain (synchronous) or async callables; the adapter
    awaits awaitables so both the sync Supabase client and the async
    football client can be reused without adapter-side duplication.
    """
    fetch_today: Callable[[], Any] = lambda: []
    fetch_matches: Callable[[], Any] = lambda: []
    fetch_predictions: Callable[[], Any] = lambda: []


async def _resolve_fetcher(fetcher: Callable[[], Any]) -> List[Dict[str, Any]]:
    """Run one capability fetcher, awaiting it only if it is async."""
    import inspect

    result = fetcher()
    if inspect.isawaitable(result):
        result = await result
    return result if isinstance(result, list) else []


# --------------------------------------------------------------------------
# Persistence boundary (fake in tests, Supabase in production).
# --------------------------------------------------------------------------

class TelegramStore(ABC):
    """Server-side Telegram state. All writes are service-role only.

    claim_update() MUST be atomic: concurrent duplicate deliveries of the
    same update_id must let exactly one claim succeed. The production
    implementation relies on UNIQUE(telegram_update_id): one INSERT wins,
    losers observe the conflict and report claimed=False. A SELECT-then-
    INSERT check-then-act race is NOT acceptable here.
    """

    @abstractmethod
    def claim_update(self, update_id: int,
                     telegram_user_id: Optional[int]) -> bool:
        """Atomically claim a delivery. False = already recorded (duplicate)."""

    @abstractmethod
    def complete_update(self, update_id: int, status: str,
                        error_code: Optional[str] = None) -> None:
        """Mark a claimed update processed/ignored/failed."""

    @abstractmethod
    def find_account(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """Read-only lookup by Telegram sender id. None when unlinked."""

    @abstractmethod
    def find_account_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Read-only lookup by FootyEdge user id. None when not linked."""

    @abstractmethod
    def link_account(self, user_id: str, telegram_user_id: int,
                     chat_id: Optional[int],
                     username: Optional[str]) -> str:
        """Bind telegram_user_id to user_id.

        Returns "linked" (new or idempotent same-mapping refresh),
        "telegram_taken" (id bound to a different user: refuse, no hijack),
        or "user_taken" (user bound to a different Telegram id: refuse).
        Must never silently rebind an existing mapping.
        """

    @abstractmethod
    def store_link_token(self, token_hash: str, user_id: str,
                         expires_at: datetime) -> None:
        """Persist a token hash. Plaintext must never reach this method."""

    @abstractmethod
    def peek_link_token(self, token_hash: str,
                        now: datetime) -> Optional[str]:
        """Read-only validity check: user_id for a live token, else None.

        Never consumes. Lets the caller refuse conflicts (already-linked
        sender or user) WITHOUT burning the one-time code.
        """

    @abstractmethod
    def consume_link_token(self, token_hash: str,
                           now: datetime) -> Optional[str]:
        """Atomically consume one valid token, returning its user_id.

        Returns None for unknown, expired, or already-consumed tokens.
        The check-and-consume must be a single atomic step.
        """

    @abstractmethod
    def touch_account(self, telegram_user_id: int,
                      chat_id: Optional[int],
                      username: Optional[str]) -> None:
        """Best-effort last_seen/chat/username refresh. Never raises."""


# --------------------------------------------------------------------------
# Outbound delivery boundary.
# --------------------------------------------------------------------------

class TelegramSender(ABC):
    """Async Telegram Bot API delivery. Fake in tests."""

    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> bool:
        """Deliver one chunk. Returns True on accepted delivery."""


def build_sender(token: str, transport: str = "auto") -> TelegramSender:
    """Construct the production sender. Token stays server-side.

    Prefers python-telegram-bot's Bot API client when importable
    (asyncio-native; used as a client only, never Application/run_webhook,
    since FastAPI already owns the HTTP server and event loop). Falls back
    to httpx (already a backend dependency) when PTB is unavailable.
    """
    if not token:
        raise TelegramError("Telegram is not configured",
                            "sender built without bot token")
    if transport in ("auto", "ptb"):
        try:
            from telegram import Bot as _PtbBot  # local import: optional dep

            return _PtbSender(_PtbBot(token=token))
        except ImportError:
            if transport == "ptb":
                raise TelegramError("Telegram is not configured",
                                    "python-telegram-bot unavailable")
    if transport in ("auto", "httpx"):
        return _HttpxSender(token)
    raise TelegramError("Telegram is not configured",
                        f"unknown sender transport {transport!r}")


class _PtbSender(TelegramSender):
    def __init__(self, bot: Any) -> None:
        self._bot = bot

    async def send_message(self, chat_id: int, text: str) -> bool:
        try:
            await self._bot.send_message(chat_id=chat_id, text=text)
        except Exception as exc:
            logger.warning("telegram: send failed: %s", type(exc).__name__)
            return False
        return True


class _HttpxSender(TelegramSender):
    def __init__(self, token: str) -> None:
        self._token = token

    async def send_message(self, chat_id: int, text: str) -> bool:
        import httpx  # local import: only needed on this code path

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{self._token}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                )
        except Exception as exc:
            logger.warning("telegram: send failed: %s", type(exc).__name__)
            return False
        if resp.status_code >= 400:
            logger.warning("telegram: send rejected: %s", resp.status_code)
            return False
        try:
            return bool(resp.json().get("ok", False))
        except Exception:
            return False


# --------------------------------------------------------------------------
# Telegram-safe formatting (adapter-side only; domain stays channel-neutral).
# --------------------------------------------------------------------------

def escape_markdown_v2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    special = set(r"_*[]()~`>#+-=|{}.!")
    return "".join(("\\" + ch) if ch in special else ch for ch in (text or ""))


def chunk_message(text: str, limit: int = TELEGRAM_CHUNK_SIZE) -> List[str]:
    """Split outbound text into Telegram-safe chunks.

    Prefers newline boundaries; hard-splits overlong lines. Never returns
    an empty list.
    """
    text = text or ""
    if len(text) <= limit:
        return [text]
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append("\n".join(current))
                current, current_len = [], 0
            chunks.append(line[:limit])
            line = line[limit:]
        addition = len(line) + (1 if current else 0)
        if current_len + addition > limit:
            chunks.append("\n".join(current))
            current, current_len = [], 0
        current.append(line)
        current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks or [text[:limit]]


def format_status(plan: str, linked: bool) -> str:
    if not linked:
        return ("FootyEdge AI on Telegram.\n"
                "Your Telegram account is not linked yet.\n"
                "Link it with /link <code> from your FootyEdge account.")
    return (f"Linked to FootyEdge AI.\nPlan: {plan}\n"
            "Use /today, /matches or /predictions.")


def format_matches(matches: List[Dict[str, Any]],
                   heading: str = "Today's matches:") -> str:
    """Format a match list under an explicit heading.

    The heading is caller-supplied so "/today" and "/matches" can never
    share a misleading label: "/today" always means the current UTC date
    (filtered upstream), "/matches" the upcoming provider window.
    """
    if not matches:
        if heading.startswith("Upcoming"):
            return "No upcoming matches found right now. Check back soon."
        return "No matches scheduled for today."
    lines = [heading]
    for match in matches[:20]:
        home = match.get("home_team", "?")
        away = match.get("away_team", "?")
        league = match.get("league", "")
        kickoff = match.get("match_date", match.get("kickoff", ""))
        head = f"{home} vs {away}"
        tail = " ".join(part for part in (league, kickoff) if part)
        lines.append(f"- {head}" + (f" ({tail})" if tail else ""))
    return "\n".join(lines)


def _parse_kickoff_day(value: Any) -> Optional[str]:
    """UTC calendar date (YYYY-MM-DD) of a kickoff value, or None.

    Accepts ISO-8601 with "Z" or explicit offsets; naive timestamps are
    read as UTC. Unparseable or missing values yield None: callers drop
    such rows instead of inventing a date.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def filter_matches_by_utc_date(matches: Any, day: str) -> List[Dict[str, Any]]:
    """Keep normalized matches kicking off on UTC calendar date `day`.

    Operates on the normalized contract (kickoff timestamp, with legacy
    match_date accepted). Rows without a usable kickoff are dropped, never
    dated by guesswork. Non-list input yields [].
    """
    if not isinstance(matches, list):
        return []
    kept: List[Dict[str, Any]] = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        raw = match.get("match_date", match.get("kickoff", ""))
        if _parse_kickoff_day(raw) == day:
            kept.append(match)
    return kept


def format_predictions(predictions: List[Dict[str, Any]]) -> str:
    if not predictions:
        return "No predictions available right now. Check back soon."
    lines = ["Latest predictions:"]
    for pred in predictions[:10]:
        home = pred.get("home_team", "?")
        away = pred.get("away_team", "?")
        pick = pred.get("best_bet_selection", pred.get("selection", ""))
        odds = pred.get("best_bet_odds", pred.get("odds", ""))
        head = f"{home} vs {away}"
        detail = str(pick) if pick else ""
        if odds not in ("", None):
            detail = f"{detail} @ {odds}".strip(" @")
        lines.append(f"- {head}" + (f": {detail}" if detail else ""))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Orchestration (single verified delivery).
# --------------------------------------------------------------------------

@dataclass
class ProcessResult:
    outcome: str  # processed | ignored | duplicate | failed
    update_id: Any = None
    command: Optional[str] = None


_UNLINKED_MESSAGE = ("Link your FootyEdge account first: open FootyEdge, "
                     "generate a link code, then send /link <code> here.")
_UNKNOWN_MESSAGE = ("I don't recognize that command. Try /help for "
                    "what I can do.")
_DEFERRED_MESSAGE = ("That isn't available on Telegram yet. Account, "
                     "billing and advanced features stay in the FootyEdge app.")
_DENIED_MESSAGE = ("Your current plan doesn't include that on Telegram. "
                   "See /status for your plan.")


async def process_update(
    store: TelegramStore,
    sender: TelegramSender,
    *,
    raw_body: bytes,
    secret_valid: bool,
    identity_fn: IdentityFn,
    runners: Optional[Runners] = None,
) -> ProcessResult:
    """Route one verified Telegram delivery. See module docstring.

    The caller (FastAPI boundary) must validate the webhook secret first;
    `secret_valid=False` refuses before any state is touched. Order inside:
    parse -> claim (atomic) -> route -> link/entitle (read-only) -> ONE
    execution -> send -> complete. Duplicates short-circuit with no send.
    """
    import json

    runners = runners or Runners()
    if not secret_valid:
        raise TelegramError("Invalid webhook secret",
                            "telegram delivery without valid secret")

    try:
        payload = json.loads(bytes(raw_body).decode("utf-8"))
    except Exception:
        raise TelegramError("Invalid update payload", "unparseable update body",
                            retryable=False)

    parsed = parse_update(payload)
    if parsed.update_id is None or parsed.telegram_user_id is None:
        # No delivery identity or no sender: nothing to claim or answer.
        raise TelegramError("Invalid update payload",
                            "update without update_id/sender",
                            retryable=False)

    claimed = False
    try:
        claimed = store.claim_update(parsed.update_id, parsed.telegram_user_id)
    except Exception as exc:
        raise TelegramError("Update processing failed",
                            f"claim failed: {type(exc).__name__}")
    if not claimed:
        return ProcessResult(outcome="duplicate", update_id=parsed.update_id)

    async def _answer(text: str, outcome: str,
                      error_code: Optional[str] = None) -> ProcessResult:
        sent = False
        if parsed.chat_id is not None:
            for chunk in chunk_message(text):
                sent = await sender.send_message(parsed.chat_id, chunk)
                if not sent:
                    break
        try:
            store.complete_update(parsed.update_id, outcome,
                                  error_code if sent else "send_failed")
        except Exception as exc:
            raise TelegramError("Update processing failed",
                                f"complete failed: {type(exc).__name__}")
        return ProcessResult(outcome=outcome, update_id=parsed.update_id,
                             command=parsed.command)

    try:
        store.touch_account(parsed.telegram_user_id, parsed.chat_id,
                            parsed.username)
    except Exception:
        pass  # best-effort presence only; never fail a delivery on it

    command = parsed.command
    try:
        if command is None:
            return await _answer(_UNKNOWN_MESSAGE, "ignored",
                                 error_code="no_command")
        if command not in SUPPORTED_COMMANDS:
            return await _answer(_DEFERRED_MESSAGE if command in DEFERRED_COMMANDS
                                 else _UNKNOWN_MESSAGE, "ignored",
                                 error_code="unsupported_command")

        if command == "/help":
            return await _answer(
                "FootyEdge AI commands:\n/start - welcome\n/help - this list\n"
                "/link <code> - connect your FootyEdge account\n/status - plan status\n"
                "/today - today's matches\n/matches - upcoming matches\n/predictions - latest predictions",
                "processed")

        if command == "/link":
            return await _handle_link(store, parsed, _answer)

        account = store.find_account(parsed.telegram_user_id)
        if command == "/start":
            if account is None:
                return await _answer(
                    "Welcome to FootyEdge AI.\n" + _UNLINKED_MESSAGE,
                    "ignored", error_code="unlinked")
            try:
                identity = _resolve_identity(identity_fn, account)
            except TelegramError:
                # Missing/unresolvable identity must stay user-visible:
                # answer the safe unlinked flow instead of raising silently
                # (which stranded the update at "received" with no reply).
                return await _answer(_UNLINKED_MESSAGE, "ignored",
                                     error_code="identity_missing")
            return await _answer(
                f"Welcome back to FootyEdge AI.\nPlan: {identity.plan}\n"
                "Try /status, /today or /predictions. /help lists commands.",
                "processed")

        # Remaining commands require a linked account. Identity here is the
        # server-side mapping only: usernames, names, emails, message text
        # and any client-supplied user_id are never consulted.
        if account is None:
            return await _answer(_UNLINKED_MESSAGE, "ignored",
                                 error_code="unlinked")
        try:
            identity = _resolve_identity(identity_fn, account)
        except TelegramError:
            # Same guarantee as above: terminal state plus a safe reply,
            # never a silent strand. No internals leak into the message.
            return await _answer(_UNLINKED_MESSAGE, "ignored",
                                 error_code="identity_missing")

        if command == "/status":
            return await _answer(format_status(identity.plan, True), "processed")

        required = COMMAND_CAPABILITIES.get(command)
        if required is not None and required not in identity.capabilities:
            return await _answer(_DENIED_MESSAGE, "ignored",
                                 error_code="capability_denied")

        if command in ("/today", "/matches"):
            fetcher = runners.fetch_today if command == "/today" else runners.fetch_matches
            matches = await _resolve_fetcher(fetcher)
            if command == "/today":
                # The provider ignores the requested date and returns its
                # upcoming-odds window, so filter to the current UTC date
                # here: future fixtures must never be labeled as today's.
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                matches = filter_matches_by_utc_date(matches, today)
                return await _answer(
                    format_matches(matches, heading="Today's matches:"),
                    "processed")
            return await _answer(
                format_matches(matches, heading="Upcoming matches:"),
                "processed")
        if command == "/predictions":
            return await _answer(format_predictions(
                await _resolve_fetcher(runners.fetch_predictions)),
                "processed")

        return await _answer(_UNKNOWN_MESSAGE, "ignored",
                             error_code="unreachable_command")
    except TelegramError:
        # A handled failure must still leave a durable terminal state.
        # Previously this bare re-raise skipped complete_update entirely,
        # stranding claimed updates at "received" with no user response.
        # Pre-claim failures (secret/parse/claim) have no row: skip those.
        if claimed:
            try:
                store.complete_update(parsed.update_id, "failed",
                                      "handler_error")
            except Exception:
                pass
        raise
    except Exception as exc:
        try:
            store.complete_update(parsed.update_id, "failed", "handler_error")
        except Exception:
            pass
        raise TelegramError("Update processing failed",
                            f"handler failed: {type(exc).__name__}")


async def _handle_link(store: TelegramStore, parsed: ParsedUpdate,
                       answer: Callable[..., Awaitable[ProcessResult]]
                       ) -> ProcessResult:
    """Secure one-time link: /link <code> binds sender to a FootyEdge user."""
    if not parsed.args:
        return await answer(
            "To link: open FootyEdge, generate a one-time code, then send "
            "/link <code> here. Codes expire quickly and work only once.",
            "ignored", error_code="link_help")
    digest = hash_link_token(parsed.args[0])
    if digest is None:
        return await answer("That code doesn't look valid. Generate a fresh "
                            "code in FootyEdge and try /link <code> again.",
                            "ignored", error_code="link_malformed")
    now = datetime.now(timezone.utc)
    user_id = store.peek_link_token(digest, now)
    if user_id is None:
        # Diagnostic only (9.3D.4B): non-reversible 12-hex-char prefix of
        # the presented digest for safe correlation. Never log the
        # plaintext code or the full digest.
        logger.warning("telegram_link_invalid update_id=%s digest_prefix=%s",
                       parsed.update_id, digest[:12])
        return await answer("That code is expired, already used, or unknown. "
                            "Generate a fresh code in FootyEdge and try again.",
                            "ignored", error_code="link_invalid")
    # Conflict pre-check BEFORE consuming, so a refused link never burns
    # the one-time code. consume+link below re-enforce atomically.
    existing_sender = store.find_account(parsed.telegram_user_id)
    if existing_sender is not None:
        if str(existing_sender.get("user_id")) == str(user_id):
            return await answer("This Telegram account is already linked. "
                                "Try /status.", "processed")
        return await answer("This Telegram account is already linked to a "
                            "different FootyEdge user. Linking refused.",
                            "ignored", error_code="link_telegram_taken")
    existing_user = store.find_account_by_user(user_id)
    if existing_user is not None:
        return await answer("That FootyEdge account is already linked to a "
                            "different Telegram account. Unlink it first.",
                            "ignored", error_code="link_user_taken")
    consumed = store.consume_link_token(digest, now)
    if consumed is None or str(consumed) != str(user_id):
        # Same diagnostic as above: presented digest prefix only.
        logger.warning("telegram_link_invalid update_id=%s digest_prefix=%s",
                       parsed.update_id, digest[:12])
        return await answer("That code is expired, already used, or unknown. "
                            "Generate a fresh code in FootyEdge and try again.",
                            "ignored", error_code="link_invalid")
    outcome = store.link_account(user_id, parsed.telegram_user_id,
                                 parsed.chat_id, parsed.username)
    if outcome == "linked":
        return await answer("Linked! Your Telegram account is now connected "
                            "to FootyEdge. Try /status.", "processed")
    if outcome == "telegram_taken":
        return await answer("This Telegram account is already linked to a "
                            "different FootyEdge user. Linking refused.",
                            "ignored", error_code="link_telegram_taken")
    return await answer("That FootyEdge account is already linked to a "
                        "different Telegram account. Unlink it first.",
                        "ignored", error_code="link_user_taken")


def _resolve_identity(identity_fn: IdentityFn,
                      account: Dict[str, Any]) -> TelegramIdentity:
    user_id = account.get("user_id")
    if not user_id or not isinstance(user_id, str):
        raise TelegramError("Account linking required",
                            "mapping without FootyEdge user",
                            retryable=False)
    try:
        identity = identity_fn(user_id)
    except Exception as exc:
        raise TelegramError("Update processing failed",
                            f"identity lookup failed: {type(exc).__name__}")
    if identity is None:
        raise TelegramError("Account linking required",
                            "identity lookup returned nothing",
                            retryable=False)
    return identity


__all__ = [
    "COMMAND_CAPABILITIES",
    "DEFERRED_COMMANDS",
    "LINK_TOKEN_BYTES",
    "LINK_TOKEN_TTL_SECONDS",
    "ProcessResult",
    "ParsedUpdate",
    "Runners",
    "SUPPORTED_COMMANDS",
    "TELEGRAM_CHUNK_SIZE",
    "TELEGRAM_MESSAGE_LIMIT",
    "TelegramError",
    "TelegramIdentity",
    "TelegramSender",
    "TelegramStore",
    "build_sender",
    "chunk_message",
    "escape_markdown_v2",
    "filter_matches_by_utc_date",
    "format_matches",
    "format_predictions",
    "format_status",
    "hash_link_token",
    "mint_link_token",
    "parse_update",
    "process_update",
    "verify_webhook_secret",
]
