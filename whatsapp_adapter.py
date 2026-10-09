"""FootyEdge WhatsApp transport adapter.

Thin channel layer only. Responsibilities:

  whatsapp_adapter.py   -> webhook verification + HMAC validation, delivery
                           parsing, link-token minting, command routing,
                           entitlement gating, deterministic AI-assistant
                           routing over verified services, response
                           formatting, send orchestration (this file)
  whatsapp_api.py       -> FastAPI boundary only (challenge, raw body,
                           headers, status codes, service-role store
                           wiring); no business logic
  whatsapp_notify.py    -> opt-in notification collector + idempotent
                           outbox delivery; never scheduled here

The adapter NEVER: resolves identity from phone numbers/names, accepts a
client-supplied user_id, mutates subscriptions, infers plans, invents
fixtures/probabilities/EV/Kelly, touches bets/portfolios, or handles
payments/admin. All quantitative outputs come from existing engine
runners; anything else is an explicit unavailable-data reply.

Stdlib only at import time (same pattern as telegram_adapter.py) so unit
tests run with no network, no Supabase, no FastAPI and no Meta client.
Outbound delivery goes through an injectable async sender; production
posts to the WhatsApp Cloud API over httpx (constructed lazily, never
imported at module load).

Delivery identity: Meta's message id (`wamid`) is the delivery key. The
store claims it atomically (UNIQUE constraint arbiter); byte-identical
redeliveries collide and short-circuit to "duplicate" with no
re-execution and no second response.

Link tokens: 192-bit cryptographically random codes; only the SHA-256 hex
is persisted. Tokens are short-lived, bound to one FootyEdge user_id, and
consumed atomically (single conditional write). Plaintext never touches
the database and never crosses the WhatsApp channel except inside the
user's own `/link <code>` message.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, FrozenSet, List, Optional, Tuple

logger = logging.getLogger("whatsapp_adapter")

# WhatsApp Cloud API text limits. Chunk below the practical ceiling.
WHATSAPP_MESSAGE_LIMIT = 4096
WHATSAPP_CHUNK_SIZE = 4000

# Link-token lifetime. Short by design: the code is a bearer credential
# until consumed.
LINK_TOKEN_TTL_SECONDS = 900
LINK_TOKEN_BYTES = 24  # 192 bits of entropy (>= 128-bit requirement)

# Sender phone validation: E.164-ish digits, optional leading "+".
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")

# Inbound rate limit: max messages per sender per window (sliding).
RATE_LIMIT_COUNT = 20
RATE_LIMIT_WINDOW_SECONDS = 60

# Link-redemption attempts: stricter bound on /link messages per sender
# (single process, like RateLimiter). The generic sender limiter already
# bounds all messages; this adds a tighter credential-guessing bound.
LINK_REDEEM_COUNT = 10
LINK_REDEEM_WINDOW_SECONDS = 600

# Initial command surface. Anything else is default-deny: unknown
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

# Recognized but intentionally unimplemented. Answered, never routed.
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


class WhatsAppError(Exception):
    """Safe adapter failure. Only `.public` may reach a user/HTTP caller."""

    def __init__(self, public: str, detail: str = "",
                 retryable: bool = False) -> None:
        super().__init__(public)
        self.public = public
        self.retryable = retryable
        if detail:
            logger.warning("whatsapp: %s", detail)


# --------------------------------------------------------------------------
# Webhook verification + HMAC validation (constant-time, fail closed).
# --------------------------------------------------------------------------

def verify_webhook_challenge(mode: Any, token: Any, challenge: Any,
                             expected_token: Any) -> Optional[str]:
    """Validate a Meta webhook verification request.

    Returns the challenge string to echo iff mode == "subscribe" and the
    token matches server config (constant-time). Anything else -> None.
    """
    if not expected_token or not isinstance(expected_token, (str, bytes)):
        return None
    if mode != "subscribe":
        return None
    if not isinstance(token, (str, bytes)) or not token:
        return None
    if not isinstance(challenge, str) or not challenge:
        return None
    if hmac.compare_digest(_to_bytes(token), _to_bytes(expected_token)):
        return challenge
    return None


def _to_bytes(value: Any) -> bytes:
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8")


def verify_signature(signature_header: Any, raw_body: bytes,
                     app_secret: Any) -> bool:
    """Validate Meta's X-Hub-Signature-256 header over the raw body.

    Expected form: "sha256=<hex hmac-sha256(raw_body, app_secret)>".
    Rejects missing/empty/malformed/non-string values and empty server
    secrets. Uses hmac.compare_digest so timing reveals nothing.
    """
    if not app_secret or not isinstance(app_secret, (str, bytes)):
        return False
    if not isinstance(signature_header, str) or not signature_header:
        return False
    prefix, sep, hexdigest = signature_header.partition("=")
    if not sep or prefix.strip().lower() != "sha256" or not hexdigest:
        return False
    try:
        presented = bytes.fromhex(hexdigest.strip())
    except ValueError:
        return False
    expected = hmac.new(_to_bytes(app_secret), bytes(raw_body or b""),
                        hashlib.sha256).digest()
    return hmac.compare_digest(presented, expected)


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


def digest_prefix(digest: str) -> str:
    """12-hex-char log prefix. Never log a full digest or a code."""
    return str(digest or "")[:12]


# --------------------------------------------------------------------------
# Identity + capability surface (injected; production wires entitlements).
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class WhatsAppIdentity:
    """Server-resolved FootyEdge identity for one linked WhatsApp account."""
    user_id: str
    plan: str
    capabilities: FrozenSet[str] = field(default_factory=frozenset)


IdentityFn = Callable[[str], Optional[WhatsAppIdentity]]
"""Resolve a FootyEdge user_id to its identity, or None on lookup failure."""


@dataclass
class Runners:
    """Existing application/domain callables the adapter may invoke.

    Deliberately narrow: read-only match/prediction fetches plus one
    matchup-prediction runner backed by the verified prediction engine.
    There is intentionally no bet/portfolio/payment/admin runner anywhere
    in this module, so WhatsApp structurally cannot reach those
    capabilities. Every numeric output in a reply MUST come from one of
    these runners; anything else is an unavailable-data reply.

    Fetchers may be plain (synchronous) or async callables; the adapter
    awaits awaitables so both the sync Supabase client and async
    engine/provider clients can be reused without duplication.
    """
    fetch_today: Callable[[], Any] = lambda: []
    fetch_matches: Callable[[], Any] = lambda: []
    fetch_predictions: Callable[[], Any] = lambda: []
    predict_matchup: Callable[[str, str], Any] = lambda h, a: None


async def _resolve_fetcher(fetcher: Callable[[], Any]) -> List[Dict[str, Any]]:
    """Run one capability fetcher, awaiting it only if it is async."""
    import inspect

    result = fetcher()
    if inspect.isawaitable(result):
        result = await result
    return result if isinstance(result, list) else []


async def _resolve_matchup(runner: Callable[[str, str], Any],
                           home: str, away: str) -> Optional[Dict[str, Any]]:
    """Run the matchup runner. Dict on success, None on any failure."""
    import inspect

    try:
        result = runner(home, away)
        if inspect.isawaitable(result):
            result = await result
    except Exception:
        return None
    return result if isinstance(result, dict) else None


# --------------------------------------------------------------------------
# Persistence boundary (fake in tests, Supabase in production).
# --------------------------------------------------------------------------

class WhatsAppStore(ABC):
    """Server-side WhatsApp state. All writes are service-role only.

    claim_update() MUST be atomic: concurrent duplicate deliveries of the
    same message id must let exactly one claim succeed. The production
    implementation relies on UNIQUE(whatsapp_message_id): one INSERT wins,
    losers observe the conflict and report claimed=False. A SELECT-then-
    INSERT check-then-act race is NOT acceptable here.
    """

    @abstractmethod
    def claim_update(self, message_id: str,
                     whatsapp_user_id: Optional[str]) -> bool:
        """Atomically claim a delivery. False = already recorded (duplicate)."""

    @abstractmethod
    def complete_update(self, message_id: str, status: str,
                        error_code: Optional[str] = None) -> None:
        """Mark a claimed update processed/ignored/failed."""

    @abstractmethod
    def find_account(self, whatsapp_user_id: str) -> Optional[Dict[str, Any]]:
        """Read-only lookup by WhatsApp sender id. None when unlinked."""

    @abstractmethod
    def find_account_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Read-only lookup by FootyEdge user id. None when not linked."""

    @abstractmethod
    def link_account(self, user_id: str, whatsapp_user_id: str,
                     display_name: Optional[str]) -> str:
        """Bind whatsapp_user_id to user_id.

        Returns "linked" (new or idempotent same-mapping refresh),
        "whatsapp_taken" (number bound to a different user: refuse, no
        hijack), or "user_taken" (user bound to a different number:
        refuse). Must never silently rebind an existing mapping.
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
    def touch_account(self, whatsapp_user_id: str,
                      display_name: Optional[str]) -> None:
        """Best-effort last_seen/display refresh. Never raises."""

    @abstractmethod
    def get_preferences(self, user_id: str) -> Dict[str, bool]:
        """Read-only opt-in flags. Missing row means fully opted out."""

    @abstractmethod
    def set_preferences(self, user_id: str,
                        prefs: Dict[str, bool]) -> Dict[str, bool]:
        """Merge opt-in flags, creating the row when absent.

        Only the known category keys are honored; anything else is
        ignored. Returns the effective flags after the write.
        """


# --------------------------------------------------------------------------
# Outbound delivery boundary.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SendResult:
    """Outcome of one Graph API send attempt."""
    ok: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


class WhatsAppSender(ABC):
    """Async WhatsApp Cloud API delivery. Fake in tests."""

    @abstractmethod
    async def send_text(self, to: str, text: str) -> SendResult:
        """Deliver one text chunk. Never raises on provider errors."""

    @abstractmethod
    async def send_template(self, to: str, template: str, language: str,
                            parameters: List[str]) -> SendResult:
        """Deliver one approved template message. Never raises."""


def build_sender(access_token: str, phone_number_id: str,
                 api_version: str = "v21.0",
                 transport: str = "httpx") -> WhatsAppSender:
    """Construct the production sender. Secrets stay server-side."""
    if not access_token or not phone_number_id:
        raise WhatsAppError("WhatsApp is not configured",
                            "sender built without token/number id")
    if transport != "httpx":
        raise WhatsAppError("WhatsApp is not configured",
                            f"unknown sender transport {transport!r}")
    return _HttpxWhatsAppSender(access_token, phone_number_id, api_version)


class _HttpxWhatsAppSender(WhatsAppSender):
    def __init__(self, token: str, number_id: str, version: str) -> None:
        self._token = token
        self._number_id = number_id
        self._version = version

    def _url(self) -> str:
        return (f"https://graph.facebook.com/{self._version}/"
                f"{self._number_id}/messages")

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json"}

    async def _post(self, payload: Dict[str, Any]) -> SendResult:
        import json as _json

        try:
            import httpx
        except ImportError:
            return SendResult(ok=False, error="transport_unavailable")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(self._url(), headers=self._headers(),
                                         content=_json.dumps(payload))
        except Exception as exc:
            return SendResult(ok=False, error=f"timeout:{type(exc).__name__}")
        try:
            body = resp.json() if hasattr(resp, "json") else {}
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        if resp.status_code < 400:
            msgs = body.get("messages")
            pid = None
            if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
                pid = msgs[0].get("id")
            return SendResult(ok=True,
                              provider_id=str(pid) if pid else None)
        err = body.get("error") if isinstance(body.get("error"), dict) else {}
        code = err.get("code")
        return SendResult(
            ok=False,
            error=f"provider:{code}" if code is not None else
            f"http:{resp.status_code}")

    async def send_text(self, to: str, text: str) -> SendResult:
        return await self._post({"messaging_product": "whatsapp", "to": to,
                                 "type": "text", "text": {"body": text}})

    async def send_template(self, to: str, template: str, language: str,
                            parameters: List[str]) -> SendResult:
        components = ([{"type": "body", "parameters": [
            {"type": "text", "text": str(p)} for p in parameters]}]
            if parameters else [])
        return await self._post(
            {"messaging_product": "whatsapp", "to": to, "type": "template",
             "template": {"name": template,
                          "language": {"code": language},
                          "components": components}})


# --------------------------------------------------------------------------
# Rate limiting (per-sender sliding window, single process).
# --------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window limiter. Inject the clock in tests.

    Single-process only: horizontally scaled workers would each enforce
    their own window. Documented limitation, not a correctness claim.
    """

    def __init__(self, max_events: int = RATE_LIMIT_COUNT,
                 window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
                 clock: Callable[[], float] | None = None) -> None:
        self._max = max_events
        self._window = window_seconds
        self._clock = clock or __import__("time").monotonic
        self._hits: Dict[str, List[float]] = {}

    def allow(self, key: str) -> bool:
        """Record one event for key. False = over the limit (not recorded)."""
        now = self._clock()
        recent = [t for t in self._hits.get(key, []) if now - t < self._window]
        if len(recent) >= self._max:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True


# --------------------------------------------------------------------------
# Delivery parsing + validation.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedUpdate:
    """One normalized inbound Meta delivery."""
    kind: str  # "message" | "status" | "unsupported" | "ignorable"
    message_id: Optional[str] = None
    wa_user_id: Optional[str] = None
    sender_name: Optional[str] = None
    message_type: Optional[str] = None
    text: Optional[str] = None
    command: Optional[str] = None
    status_update: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ProcessResult:
    """Terminal outcome of one delivery. Only safe fields."""
    outcome: str  # processed|duplicate|ignored|failed
    message_id: Optional[str] = None
    command: Optional[str] = None


def _valid_phone(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value:
        return None
    cleaned = value.strip().replace(" ", "").replace("-", "")
    if not PHONE_RE.match(cleaned):
        return None
    return cleaned


def parse_update(payload: Any) -> ParsedUpdate:
    """Normalize one Meta webhook payload. Never raises, never invents."""
    if not isinstance(payload, dict):
        return ParsedUpdate(kind="ignorable")
    if payload.get("object") != "whatsapp_business_account":
        return ParsedUpdate(kind="ignorable")
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries:
        return ParsedUpdate(kind="ignorable")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            statuses = value.get("statuses")
            if isinstance(statuses, list) and statuses:
                first = statuses[0] if isinstance(statuses[0], dict) else {}
                return ParsedUpdate(
                    kind="status",
                    message_id=(first.get("id")
                                if isinstance(first.get("id"), str) else None),
                    status_update={
                        "provider_id": first.get("id"),
                        "status": first.get("status"),
                        "timestamp": first.get("timestamp"),
                        "errors": first.get("errors"),
                    })
            messages = value.get("messages")
            if not isinstance(messages, list) or not messages:
                continue
            raw = messages[0] if isinstance(messages[0], dict) else {}
            mid = raw.get("id") if isinstance(raw.get("id"), str) else None
            sender = _valid_phone(raw.get("from"))
            mtype = raw.get("type") if isinstance(raw.get("type"), str) else None
            contacts = value.get("contacts")
            name = None
            if isinstance(contacts, list) and contacts \
                    and isinstance(contacts[0], dict):
                profile = contacts[0].get("profile")
                if isinstance(profile, dict) and isinstance(
                        profile.get("name"), str):
                    name = profile["name"][:64]
            if mtype == "text":
                text_block = raw.get("text")
                body = (text_block.get("body")
                        if isinstance(text_block, dict) else None)
                if not isinstance(body, str) or not body.strip():
                    return ParsedUpdate(kind="unsupported", message_id=mid,
                                        wa_user_id=sender, sender_name=name,
                                        message_type=mtype)
                command, free_text = _split_command(body)
                return ParsedUpdate(kind="message", message_id=mid,
                                    wa_user_id=sender, sender_name=name,
                                    message_type=mtype, text=free_text,
                                    command=command)
            if mtype in ("image", "audio", "video", "document", "location",
                         "contacts", "sticker", "interactive", "reaction",
                         "button", "order", "system"):
                return ParsedUpdate(kind="unsupported", message_id=mid,
                                    wa_user_id=sender, sender_name=name,
                                    message_type=mtype)
            return ParsedUpdate(kind="unsupported", message_id=mid,
                                wa_user_id=sender, sender_name=name,
                                message_type=mtype)
    return ParsedUpdate(kind="ignorable")


def _split_command(body: str) -> Tuple[Optional[str], Optional[str]]:
    """Split "/command rest" from free text. Plain text -> (None, text)."""
    cleaned = " ".join(body.split())
    if not cleaned.startswith("/"):
        return None, cleaned
    parts = cleaned.split(None, 1)
    head = parts[0].lower()
    if "@" in head:  # "/cmd@BotName arg" form
        head = head.split("@", 1)[0]
    rest = parts[1] if len(parts) > 1 else None
    if rest is not None:
        rest = " ".join(rest.split()) or None
    known = SUPPORTED_COMMANDS + DEFERRED_COMMANDS
    if head in known:
        return head, rest
    return None, cleaned


def chunk_message(text: str) -> List[str]:
    """Split long replies below the provider ceiling. Pure function."""
    if not isinstance(text, str) or not text:
        return []
    if len(text) <= WHATSAPP_CHUNK_SIZE:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + WHATSAPP_CHUNK_SIZE])
        start += WHATSAPP_CHUNK_SIZE
    return chunks


# --------------------------------------------------------------------------
# Reply formatting (verified data only; unknown shapes yield empty text).
# --------------------------------------------------------------------------

def format_status(plan: str, linked: bool) -> str:
    """Plan/status summary. Plan comes from server identity only."""
    state = "linked" if linked else "not linked"
    return (f"FootyEdge AI status\nPlan: {plan}\nWhatsApp: {state}\n"
            "Use /help for commands.")


def format_matches(matches: List[Any], heading: str) -> str:
    """Flat match list. Rows missing both team names are dropped."""
    lines = [heading]
    for row in matches or []:
        if not isinstance(row, dict):
            continue
        home = row.get("home_team")
        away = row.get("away_team")
        if not isinstance(home, str) or not home.strip():
            continue
        if not isinstance(away, str) or not away.strip():
            continue
        league = row.get("league") if isinstance(row.get("league"), str) else ""
        kickoff = row.get("kickoff") if isinstance(row.get("kickoff"), str) else ""
        detail = " ".join(part for part in (league, kickoff) if part).strip()
        lines.append(f"{home.strip()} vs {away.strip()}"
                     + (f" ({detail})" if detail else ""))
    if len(lines) == 1:
        return "No matches found."
    return "\n".join(lines)


def format_predictions(predictions: List[Any]) -> str:
    """Prediction list. Only engine-supplied numbers are rendered."""
    lines = ["Latest predictions:"]
    for row in predictions or []:
        if not isinstance(row, dict):
            continue
        home = row.get("home_team")
        away = row.get("away_team")
        if not isinstance(home, str) or not isinstance(away, str):
            continue
        conf = row.get("confidence")
        conf_txt = f" ({conf:.0%})" if isinstance(conf, (int, float)) else ""
        market = row.get("best_bet_market")
        selection = row.get("best_bet_selection")
        pick = f" - {selection} ({market})" if isinstance(
            selection, str) and isinstance(market, str) else ""
        lines.append(f"{home} vs {away}{conf_txt}{pick}")
    if len(lines) == 1:
        return "No predictions available."
    return "\n".join(lines)


def format_matchup_answer(home: str, away: str,
                          result: Optional[Dict[str, Any]]) -> str:
    """Matchup answer built ONLY from the engine result dict.

    None (or a result missing probabilities) is an explicit
    unavailable-data reply — never a fabricated forecast.
    """
    if not isinstance(result, dict):
        return (f"{home} vs {away}: I don't have verified prediction data "
                "for that matchup right now.")
    probs = result.get("probabilities") if isinstance(
        result.get("probabilities"), dict) else None
    home_p = result.get("home_prob", (probs or {}).get("home"))
    draw_p = result.get("draw_prob", (probs or {}).get("draw"))
    away_p = result.get("away_prob", (probs or {}).get("away"))
    if not all(isinstance(p, (int, float)) for p in (home_p, draw_p, away_p)):
        return (f"{home} vs {away}: I don't have verified prediction data "
                "for that matchup right now.")
    lines = [f"{home} vs {away}:",
             f"Home {home_p:.0%} / Draw {draw_p:.0%} / Away {away_p:.0%}"]
    best = result.get("best_bet_selection")
    market = result.get("best_bet_market")
    if isinstance(best, str) and isinstance(market, str):
        lines.append(f"Engine pick: {best} ({market})")
    conf = result.get("confidence")
    if isinstance(conf, (int, float)):
        lines.append(f"Confidence: {conf:.0%}")
    return "\n".join(lines)


# Notification categories (mirror whatsapp_preferences columns).
NOTIFY_CATEGORIES = ("match_updates", "prediction_alerts")

# Compliance intercepts: platform-consent keywords handled before any
# command routing. These are not commands; they satisfy the messaging
# policy requirement that STOP/unsubscribe always works and that opt-in
# is explicit. OUT takes precedence on ambiguous overlap (consent-
# conservative). Bare opt-in ("notify me") enables both categories;
# category words ("match", "predict"/"tip") narrow the scope.
_OPT_OUT_PATTERNS = (
    "unsubscribe", "opt out", "opt-out", "cancel alerts",
    "stop notifications", "stop alerts", "no more alerts",
)
_OPT_OUT_WORDS = ("stop", "quiet")
_OPT_IN_PATTERNS = (
    "notify me", "alerts on", "turn on alerts", "subscribe", "opt in",
    "opt-in", "start alerts",
)


def _contains_pattern(lowered: str, patterns: Tuple[str, ...]) -> bool:
    return any(pat in lowered for pat in patterns)


def _contains_word(lowered: str, words: Tuple[str, ...]) -> bool:
    tokens = set(re.findall(r"[a-z]+", lowered))
    return any(word in tokens for word in words)


def _wants_opt_out(text: str) -> bool:
    lowered = text.lower()
    return _contains_pattern(lowered, _OPT_OUT_PATTERNS) or _contains_word(
        lowered, _OPT_OUT_WORDS)


def _wants_opt_in(text: str) -> bool:
    return _contains_pattern(text.lower(), _OPT_IN_PATTERNS)


def _opt_in_scope(text: str) -> Tuple[str, ...]:
    lowered = text.lower()
    scoped = tuple(
        cat for cat, keys in (
            ("match_updates", ("match", "matches", "fixture", "game")),
            ("prediction_alerts", ("predict", "tip", "tips", "bet", "bets")),
        )
        if any(key in lowered for key in keys)
    )
    return scoped or NOTIFY_CATEGORIES


def _handle_compliance(store: WhatsAppStore,
                       parsed: ParsedUpdate) -> Optional[Tuple[str, str]]:
    """Handle consent keywords. None when the text carries no intent.

    Opt-out works for linked accounts (flags cleared, confirmed) and
    answers generically when unlinked (no state exists to clear, and no
    account information is revealed). Opt-in requires a linked account.
    Store failures raise retryable errors so Meta redelivers.
    """
    text = parsed.text or ""
    if not text.strip():
        return None
    try:
        account = store.find_account(parsed.wa_user_id or "")
    except Exception as exc:
        raise WhatsAppError("Please try again in a moment.",
                            f"compliance lookup failed: {type(exc).__name__}",
                            retryable=True)
    if _wants_opt_out(text):
        if account is None:
            return ("I don't have alerts enabled for this number, so "
                    "there is nothing to stop. Link your FootyEdge account "
                    "any time with /link."), "ignored"
        user_id = str(account.get("user_id") or "")
        if not user_id:
            return ("I don't have alerts enabled for this number."), "ignored"
        try:
            store.set_preferences(
                user_id, {cat: False for cat in NOTIFY_CATEGORIES})
        except Exception as exc:
            raise WhatsAppError("Please try again in a moment.",
                                f"opt-out failed: {type(exc).__name__}",
                                retryable=True)
        return ("Done — you're unsubscribed from FootyEdge WhatsApp "
                "alerts. Nothing further will be sent."), "processed"
    if _wants_opt_in(text):
        if account is None:
            return _UNLINKED_MESSAGE, "ignored"
        user_id = str(account.get("user_id") or "")
        if not user_id:
            return _UNLINKED_MESSAGE, "ignored"
        scope = _opt_in_scope(text)
        try:
            store.set_preferences(user_id, {cat: True for cat in scope})
        except Exception as exc:
            raise WhatsAppError("Please try again in a moment.",
                                f"opt-in failed: {type(exc).__name__}",
                                retryable=True)
        labels = " and ".join("match updates" if cat == "match_updates"
                              else "prediction alerts" for cat in scope)
        return (f"Done — you're subscribed to {labels}. Reply STOP any "
                "time to unsubscribe."), "processed"
    return None


# --------------------------------------------------------------------------
# Deterministic assistant router (no LLM; verified services only).
# --------------------------------------------------------------------------

_UNLINKED_MESSAGE = ("Link your FootyEdge account first: open FootyEdge, "
                     "generate a link code, then send /link <code> here.")
_UNKNOWN_MESSAGE = ("I don't recognize that command. Try /help for "
                    "what I can do.")
_DEFERRED_MESSAGE = ("That isn't available on WhatsApp yet. Account, "
                     "billing and advanced features stay in the FootyEdge app.")
_DENIED_MESSAGE = ("Your current plan doesn't include that on WhatsApp. "
                   "See /status for your plan.")
_UNSUPPORTED_MEDIA_MESSAGE = ("I can only read text messages. Please send "
                              "your question as text, or try /help.")
_RATE_LIMITED_MESSAGE = ("You're sending messages too quickly. Please wait "
                         "a moment and try again.")


def _detect_matchup(text: str) -> Optional[Tuple[str, str]]:
    """Detect "predict X vs Y" / "X vs Y" requests. Teams, never numbers."""
    lowered = text.lower()
    wants = any(word in lowered for word in
                ("predict", "prediction", "forecast", "odds", "who wins",
                 "bet on", "tip"))
    if " vs " not in lowered and " v " not in lowered:
        return None
    sep = " vs " if " vs " in text else " v "
    left, _, right = text.partition(sep)
    if not left or not right:
        return None
    home = " ".join(left.split()[-3:])
    away = " ".join(right.split()[:3])
    home = re.sub(r"(?i)^(predict|prediction|forecast|who wins|tip|bet on)\s+",
                  "", home).strip(" ?")
    away = away.strip(" ?")
    if not home or not away or not wants:
        return None
    return home, away


def _detect_today(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in
               ("today", "tonight", "todays", "today's", "matches today"))


def _detect_greeting(text: str) -> bool:
    first = text.lower().split(None, 1)
    return bool(first) and first[0] in (
        "hi", "hello", "hey", "yo", "morning", "evening", "afternoon")


async def answer_free_text(text: str, identity: Optional[WhatsAppIdentity],
                           runners: Runners) -> Tuple[str, str]:
    """Route one free-text message. Returns (reply, outcome).

    Deterministic router (no LLM): greeting/help/today/matchup intents
    only. Matchup forecasts come solely from runners.predict_matchup;
    anything else is an explicit unavailable-data-supported reply. The
    caller enforces entitlement for gated intents before invoking gated
    branches: matchup answers require the predictions capability.
    """
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return _UNKNOWN_MESSAGE, "ignored"
    if _detect_greeting(cleaned) or "help" in cleaned.lower():
        return ("FootyEdge AI on WhatsApp. Ask me about today's matches "
                "or a matchup like 'predict Arsenal vs Chelsea'. "
                "Commands: /today /matches /predictions /status."), "processed"
    if _detect_today(cleaned):
        return "__today__", "route_today"
    matchup = _detect_matchup(cleaned)
    if matchup is not None:
        if identity is None or "predictions" not in identity.capabilities:
            return _DENIED_MESSAGE, "ignored"
        home, away = matchup
        result = await _resolve_matchup(runners.predict_matchup, home, away)
        return format_matchup_answer(home, away, result), "processed"
    return ("I can help with today's matches and matchup forecasts from "
            "verified data. Try 'predict Arsenal vs Chelsea' or /help."), \
        "ignored"


def _resolve_identity(identity_fn: IdentityFn,
                      account: Dict[str, Any]) -> WhatsAppIdentity:
    """Resolve server identity for a linked account. Fail closed."""
    user_id = account.get("user_id") if isinstance(account, dict) else None
    if not isinstance(user_id, str) or not user_id:
        raise WhatsAppError("Link your FootyEdge account first.",
                            "account row without user_id", retryable=False)
    try:
        identity = identity_fn(str(user_id))
    except Exception as exc:
        raise WhatsAppError("Account lookup failed, please try again.",
                            f"identity_fn raised {type(exc).__name__}",
                            retryable=True)
    if identity is None:
        raise WhatsAppError("Link your FootyEdge account first.",
                            "identity_fn returned None", retryable=False)
    return identity


async def _handle_link(store: WhatsAppStore, parsed: ParsedUpdate,
                       answer: Callable[..., Any]) -> Any:
    """Secure one-time link: /link <code> binds sender to a user."""
    # parsed.text already holds the argument after "/link " (the command
    # prefix is stripped by _split_command), so the code is the first
    # whitespace-delimited token — not parts[1].
    parts = ((parsed.text or "").split(None, 1) + [None])[:2]
    code = parts[0]
    digest = hash_link_token(code) if code else None
    if digest is None:
        return await answer("Send /link followed by the code from the "
                            "FootyEdge app.", "ignored",
                            error_code="link_malformed")
    from datetime import datetime as _dt
    now = _dt.now(timezone.utc)
    user_id = None
    try:
        user_id = store.peek_link_token(digest, now)
    except Exception as exc:
        raise WhatsAppError("Link lookup failed, please try again.",
                            f"peek failed: {type(exc).__name__}",
                            retryable=True)
    if user_id is None:
        logger.warning("whatsapp: link_invalid %s", digest_prefix(digest))
        return await answer("That code is invalid or expired. Generate a "
                            "new one in the FootyEdge app.", "ignored",
                            error_code="link_invalid")
    try:
        account = store.find_account(parsed.wa_user_id or "")
    except Exception as exc:
        raise WhatsAppError("Link lookup failed, please try again.",
                            f"find failed: {type(exc).__name__}",
                            retryable=True)
    if account is not None:
        if str(account.get("user_id")) == str(user_id):
            try:
                store.consume_link_token(digest, now)
            except Exception:
                pass
            return await answer("This number is already linked to your "
                                "FootyEdge account.", "processed")
        return await answer("This number is already linked to a different "
                            "FootyEdge account.", "ignored",
                            error_code="whatsapp_taken")
    try:
        user_account = store.find_account_by_user(str(user_id))
    except Exception as exc:
        raise WhatsAppError("Link lookup failed, please try again.",
                            f"find-by-user failed: {type(exc).__name__}",
                            retryable=True)
    if user_account is not None:
        return await answer("Your account is already linked to a different "
                            "number.", "ignored", error_code="user_taken")
    try:
        consumed = store.consume_link_token(digest, now)
    except Exception as exc:
        raise WhatsAppError("Link failed, please try again.",
                            f"consume failed: {type(exc).__name__}",
                            retryable=True)
    if consumed is None or str(consumed) != str(user_id):
        return await answer("That code is invalid or expired. Generate a "
                            "new one in the FootyEdge app.", "ignored",
                            error_code="link_invalid")
    try:
        outcome = store.link_account(str(user_id), parsed.wa_user_id or "",
                                     parsed.sender_name)
    except Exception as exc:
        raise WhatsAppError("Link failed, please try again.",
                            f"link failed: {type(exc).__name__}",
                            retryable=True)
    if outcome == "linked":
        return await answer("Linked! Your WhatsApp number is now connected "
                            "to your FootyEdge account. Try /status.",
                            "processed")
    return await answer("This number is already linked to a different "
                        "FootyEdge account.", "ignored",
                        error_code="whatsapp_taken")


async def process_update(
    store: WhatsAppStore,
    sender: WhatsAppSender,
    *,
    raw_body: bytes,
    signature_valid: bool,
    identity_fn: IdentityFn,
    runners: Optional[Runners] = None,
    limiter: Optional[RateLimiter] = None,
    link_limiter: Optional[RateLimiter] = None,
) -> ProcessResult:
    """Route one verified WhatsApp delivery. See module docstring.

    The caller (FastAPI boundary) must validate the HMAC signature
    first; `signature_valid=False` refuses before any state is touched.
    Order inside: parse -> claim (atomic) -> route -> link/entitle
    (read-only) -> ONE execution -> send -> complete. Duplicates
    short-circuit with no send. Status receipts update delivery state
    without ever sending a reply.
    """
    import json

    runners = runners or Runners()
    if not signature_valid:
        raise WhatsAppError("Invalid webhook signature",
                            "delivery without valid signature")

    try:
        payload = json.loads(bytes(raw_body).decode("utf-8"))
    except Exception:
        raise WhatsAppError("Invalid update payload", "unparseable body",
                            retryable=False)

    parsed = parse_update(payload)
    if parsed.kind == "ignorable":
        return ProcessResult(outcome="ignored")
    if parsed.kind == "status":
        return ProcessResult(outcome="ignored",
                             message_id=parsed.message_id)
    if parsed.message_id is None or parsed.wa_user_id is None:
        # No delivery identity or no sender: nothing to claim or answer.
        # (Invalid phone numbers fail closed here: no reply target.)
        raise WhatsAppError("Invalid update payload",
                            "update without message_id/sender",
                            retryable=False)
    if parsed.kind == "unsupported":
        claimed = False
        try:
            claimed = store.claim_update(parsed.message_id,
                                         parsed.wa_user_id)
        except Exception as exc:
            raise WhatsAppError("Update processing failed",
                                f"claim failed: {type(exc).__name__}")
        if not claimed:
            return ProcessResult(outcome="duplicate",
                                 message_id=parsed.message_id)
        sent_ok = True
        try:
            result = await sender.send_text(
                parsed.wa_user_id, _UNSUPPORTED_MEDIA_MESSAGE)
            sent_ok = bool(result.ok)
        except Exception:
            sent_ok = False
        try:
            store.complete_update(
                parsed.message_id, "ignored",
                None if sent_ok else "send_failed")
        except Exception as exc:
            raise WhatsAppError("Update processing failed",
                                f"complete failed: {type(exc).__name__}")
        return ProcessResult(outcome="ignored",
                             message_id=parsed.message_id)

    claimed = False
    try:
        claimed = store.claim_update(parsed.message_id, parsed.wa_user_id)
    except Exception as exc:
        raise WhatsAppError("Update processing failed",
                            f"claim failed: {type(exc).__name__}")
    if not claimed:
        return ProcessResult(outcome="duplicate",
                             message_id=parsed.message_id)

    async def _answer(text: str, outcome: str,
                      error_code: Optional[str] = None) -> ProcessResult:
        sent = False
        for chunk in chunk_message(text):
            try:
                result = await sender.send_text(parsed.wa_user_id or "", chunk)
                sent = bool(result.ok)
            except Exception:
                sent = False
            if not sent:
                break
        try:
            store.complete_update(parsed.message_id, outcome,
                                  error_code if sent else "send_failed")
        except Exception as exc:
            raise WhatsAppError("Update processing failed",
                                f"complete failed: {type(exc).__name__}")
        return ProcessResult(outcome=outcome, message_id=parsed.message_id,
                             command=parsed.command)

    if limiter is not None and not limiter.allow(parsed.wa_user_id or ""):
        return await _answer(_RATE_LIMITED_MESSAGE, "ignored",
                             error_code="rate_limited")

    try:
        store.touch_account(parsed.wa_user_id, parsed.sender_name)
    except Exception:
        pass  # best-effort presence only; never fail a delivery on it

    command = parsed.command
    try:
        if command is None and parsed.kind == "message":
            # Consent intercepts run before any other routing: STOP and
            # opt-in keywords are platform-policy obligations, not
            # commands, and must work regardless of link state.
            compliance = _handle_compliance(store, parsed)
            if compliance is not None:
                reply_text, reply_outcome = compliance
                return await _answer(reply_text, reply_outcome)
        if command is None:
            # Free text: resolve link state first so gated intents
            # (today, matchup forecasts) enforce the same link and
            # capability rules as commands. Public intents (greeting,
            # help) answer regardless.
            account = None
            identity = None
            try:
                account = store.find_account(parsed.wa_user_id)
            except Exception as exc:
                raise WhatsAppError("Account lookup failed, try again.",
                                    f"find failed: {type(exc).__name__}",
                                    retryable=True)
            if account is not None:
                try:
                    identity = _resolve_identity(identity_fn, account)
                except WhatsAppError:
                    identity = None
            text = parsed.text or ""
            reply, route = await answer_free_text(text, identity, runners)
            if route == "route_today":
                if account is None:
                    return await _answer(_UNLINKED_MESSAGE, "ignored",
                                         error_code="unlinked")
                if identity is None:
                    return await _answer(_UNLINKED_MESSAGE, "ignored",
                                         error_code="identity_missing")
                if "match_intelligence" not in identity.capabilities:
                    return await _answer(_DENIED_MESSAGE, "ignored",
                                         error_code="capability_denied")
                matches = await _resolve_fetcher(runners.fetch_today)
                return await _answer(
                    format_matches(matches, heading="Today's matches:"),
                    "processed")
            return await _answer(reply, route)
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
            if link_limiter is not None and not link_limiter.allow(
                    parsed.wa_user_id or ""):
                return await _answer(_RATE_LIMITED_MESSAGE, "ignored",
                                     error_code="link_rate_limited")
            return await _handle_link(store, parsed, _answer)

        account = store.find_account(parsed.wa_user_id)
        if command == "/start":
            if account is None:
                return await _answer(
                    "Welcome to FootyEdge AI.\n" + _UNLINKED_MESSAGE,
                    "ignored", error_code="unlinked")
            try:
                identity = _resolve_identity(identity_fn, account)
            except WhatsAppError:
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
        # server-side mapping only: phone numbers, names, message text and
        # any client-supplied user_id are never consulted.
        if account is None:
            return await _answer(_UNLINKED_MESSAGE, "ignored",
                                 error_code="unlinked")
        try:
            identity = _resolve_identity(identity_fn, account)
        except WhatsAppError:
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
    except WhatsAppError:
        # A handled failure must still leave a durable terminal state.
        # Pre-claim failures (signature/parse/claim) have no row: skip those.
        if claimed:
            try:
                store.complete_update(parsed.message_id, "failed",
                                      "handler_error")
            except Exception:
                pass
        raise
    except Exception as exc:
        try:
            store.complete_update(parsed.message_id, "failed", "handler_error")
        except Exception:
            pass
        raise WhatsAppError("Update processing failed",
                            f"handler raised {type(exc).__name__}")


def filter_matches_by_utc_date(matches: List[Any], today: str) -> List[Any]:
    """Keep rows whose kickoff falls on the UTC date. Pure function."""
    kept = []
    for row in matches or []:
        if not isinstance(row, dict):
            continue
        kickoff = row.get("kickoff")
        if isinstance(kickoff, str) and kickoff[:10] == today:
            kept.append(row)
    return kept


__all__ = [
    "COMMAND_CAPABILITIES",
    "DEFERRED_COMMANDS",
    "LINK_REDEEM_COUNT",
    "LINK_REDEEM_WINDOW_SECONDS",
    "LINK_TOKEN_BYTES",
    "LINK_TOKEN_TTL_SECONDS",
    "NOTIFY_CATEGORIES",
    "ProcessResult",
    "RATE_LIMIT_COUNT",
    "RATE_LIMIT_WINDOW_SECONDS",
    "RateLimiter",
    "Runners",
    "SUPPORTED_COMMANDS",
    "SendResult",
    "WhatsAppError",
    "WhatsAppIdentity",
    "WhatsAppSender",
    "WhatsAppStore",
    "answer_free_text",
    "build_sender",
    "chunk_message",
    "digest_prefix",
    "filter_matches_by_utc_date",
    "format_matches",
    "format_matchup_answer",
    "format_predictions",
    "format_status",
    "hash_link_token",
    "mint_link_token",
    "parse_update",
    "process_update",
    "verify_signature",
    "verify_webhook_challenge",
]
