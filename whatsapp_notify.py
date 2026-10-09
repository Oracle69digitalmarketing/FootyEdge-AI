"""FootyEdge WhatsApp opt-in notifications (collector + idempotent outbox).

Companion to whatsapp_adapter.py / whatsapp_api.py. Responsibilities:

  whatsapp_notify.py  -> event eligibility over pipeline output tables,
                         explicit opt-in enforcement, idempotent outbox
                         writes, bounded delivery with retries, delivery
                         receipts. Triggered only by explicit invocation
                         (run_notification_cycle); nothing here registers
                         a scheduler, cron, or background worker, and
                         production delivery stays disabled until
                         separately authorized.

Notification-worthy events (documented eligibility):

  match_update (upcoming-match reminder)
    - matches row with home_goals IS NULL AND away_goals IS NULL
      (unplayed), match_date strictly in (now, now + 24h].
    - Identity: the matches.id. Stale (past/kicked-off), played, or
      out-of-window rows are ineligible — never notified.
    - A new matches row is NOT assumed notifiable; only the windowed,
      unplayed subset is.

  prediction_alert (value-bet alert)
    - value_bets row with status == 'active'. A new row is NOT assumed
      to be a new event: the pipeline inserts one row per run, so the
      event grain is (match_id, market, selection) and the outbox
      UNIQUE key deduplicates repeat runs.
    - Staleness: the linked match (via match_id) must exist, be
      unplayed, and lie in the future; rows older than 48h are stale.
      A bet without a linked match is ineligible (fail closed).
    - status != 'active' rows are never notified.

User eligibility (all required): linked WhatsApp account present,
preference flag for the category explicitly true (missing row or
false means opted out — consent defaults to disabled), and the
server-resolved capability for the category
(match_update -> match_intelligence, prediction_alert -> predictions).
Denied capabilities skip silently (not an error); ambiguous identity
fails closed per item.

Outbox lifecycle (whatsapp_deliveries):
  pending -> sending -> sent | failed, with bounded attempts and claim
  leases (claimed_until). UNIQUE(idempotency_key) is the duplicate
  arbiter: concurrent collectors collapse to one row. Production claims
  go through the atomic claim_whatsapp_delivery() RPC (SELECT ...
  FOR UPDATE SKIP LOCKED + conditional UPDATE in one call, attempts+1,
  lease set, complete row returned): two concurrent workers can never
  receive the same delivery. The in-process conditional-UPDATE path is
  retained ONLY for test doubles without an rpc() boundary and is
  documented best-effort there. Abandoned sending rows (lease expired)
  become claimable again through the same predicate — no separate
  recovery job needed. Ambiguous provider timeouts return the row to
  pending with attempts incremented and last_error set, explicitly NOT
  counted as sent: delivery is at-least-once, never claimed
  exactly-once.

Business-initiated messages leave via approved templates
(send_template); template names are configurable constants. Unknown
template shapes surface as recorded provider errors under the same
bounded retry policy — never a crash, never a silent drop.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("whatsapp_notify")

# Category -> required FootyEdge capability.
CATEGORY_CAPABILITY: Dict[str, str] = {
    "match_update": "match_intelligence",
    "prediction_alert": "predictions",
}

# Category -> whatsapp_preferences opt-in column. Delivery categories
# are singular (matching the whatsapp_deliveries CHECK constraint);
# preference columns are plural (matching the whatsapp_preferences
# table). The mapping is explicit so eligibility never reads a
# missing flag (which would fail open or always-opt-out).
CATEGORY_PREF_COLUMN: Dict[str, str] = {
    "match_update": "match_updates",
    "prediction_alert": "prediction_alerts",
}

# Category -> default approved template name (overridable per call).
DEFAULT_TEMPLATES: Dict[str, str] = {
    "match_update": "footyedge_match_update",
    "prediction_alert": "footyedge_prediction_alert",
}
TEMPLATE_LANGUAGE = "en"

# Eligibility windows.
REMINDER_WINDOW_HOURS = 24
ALERT_MAX_AGE_HOURS = 48

# Delivery bounds.
DEFAULT_MAX_ATTEMPTS = 3
CLAIM_LEASE_SECONDS = 600
BACKOFF_BASE_SECONDS = 120
BACKOFF_MAX_SECONDS = 3600
DELIVERY_BATCH_LIMIT = 100

# Production atomic-claim RPC (see supabase/migrations/
# 20261010000000_whatsapp_adapter.sql). Single-call SELECT ... FOR UPDATE
# SKIP LOCKED + conditional UPDATE; returns 0 or 1 complete delivery rows
# with attempts already incremented and the lease set.
CLAIM_RPC_NAME = "claim_whatsapp_delivery"


class _RpcUnsupported(Exception):
    """Raised when a db double exposes no rpc() boundary (tests only)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _parse(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _payload_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def match_reminder_key(match_id: Any, user_id: str) -> str:
    """Idempotency key grain: one reminder per match per user."""
    return f"wa:match_update:{match_id}:{user_id}"


def value_alert_key(match_id: Any, market: Any, selection: Any,
                    user_id: str) -> str:
    """Idempotency key grain: one alert per (match, market, selection)."""
    return f"wa:prediction_alert:{match_id}:{market}:{selection}:{user_id}"


def eligible_match(match: Any, now: datetime,
                   window_hours: int = REMINDER_WINDOW_HOURS) -> bool:
    """Whether a matches row is a notification-worthy reminder event."""
    if not isinstance(match, dict):
        return False
    if match.get("home_goals") is not None:
        return False
    if match.get("away_goals") is not None:
        return False
    kickoff = _parse(match.get("match_date"))
    if kickoff is None:
        return False
    return now < kickoff <= now + timedelta(hours=window_hours)


def eligible_value_bet(bet: Any, matches_by_id: Dict[Any, Dict[str, Any]],
                       now: datetime) -> bool:
    """Whether a value_bets row is a notification-worthy alert event."""
    if not isinstance(bet, dict):
        return False
    if bet.get("status") != "active":
        return False
    created = _parse(bet.get("created_at"))
    if created is not None and now - created > timedelta(
            hours=ALERT_MAX_AGE_HOURS):
        return False
    match_id = bet.get("match_id")
    if match_id is None:
        return False  # fail closed: cannot verify staleness
    match = matches_by_id.get(match_id)
    if not isinstance(match, dict):
        return False
    if match.get("home_goals") is not None:
        return False
    if match.get("away_goals") is not None:
        return False
    kickoff = _parse(match.get("match_date"))
    if kickoff is None or kickoff <= now:
        return False
    return True


def format_match_reminder(home: str, away: str, league: str,
                          kickoff: str) -> str:
    """Reminder text from verified row fields only. No invented data."""
    detail = " ".join(part for part in (league, kickoff) if part).strip()
    return (f"Reminder: {home} vs {away} kicks off {detail}."
            if detail else f"Reminder: {home} vs {away} is coming up.")


def format_value_alert(home: str, away: str, market: str, selection: str,
                       odds: Any, ev: Any) -> str:
    """Alert text from verified row fields only. Missing numbers omitted."""
    parts = [f"Value alert: {home} vs {away} — {selection} ({market})"]
    if isinstance(odds, (int, float)):
        parts.append(f"at {odds}")
    if isinstance(ev, (int, float)):
        parts.append(f"EV {ev:+.1%}")
    return " ".join(parts) + "."


def _is_conflict(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return ("duplicate" in text or "already exists" in text
            or "23505" in text or "unique" in text)


def set_opt_in(db: Any, user_id: str, category: str,
               enabled: bool) -> Dict[str, bool]:
    """Explicitly set one opt-in flag (upsert). Unknown categories refuse."""
    if category not in CATEGORY_CAPABILITY:
        raise ValueError(f"unknown notification category {category!r}")
    column = CATEGORY_PREF_COLUMN[category]
    row = {"user_id": user_id, column: bool(enabled)}
    db.table("whatsapp_preferences").upsert(
        row, on_conflict="user_id").execute()
    return row


def collect_due_notifications(
    db: Any,
    *,
    identity_fn: Callable[[str], Any],
    now: Optional[datetime] = None,
    reminder_window_hours: int = REMINDER_WINDOW_HOURS,
) -> Dict[str, Any]:
    """Queue due notifications into the outbox. Never sends.

    Returns {"queued": int, "skipped": {reason: count}, "errors": [...]}.
    Fail-soft per user/item: one bad row never aborts the collection.
    """
    moment = now or _now()
    summary: Dict[str, Any] = {"queued": 0, "skipped": {}, "errors": []}

    def _skip(reason: str) -> None:
        summary["skipped"][reason] = summary["skipped"].get(reason, 0) + 1

    try:
        matches = _rows_of(db.table("matches").select("*").execute())
        bets = _rows_of(db.table("value_bets").select("*").execute())
        accounts = _rows_of(db.table("whatsapp_accounts").select(
            "user_id,whatsapp_user_id").execute())
        prefs = _rows_of(db.table("whatsapp_preferences").select(
            "user_id,match_updates,prediction_alerts").execute())
    except Exception as exc:
        summary["errors"].append(f"collect_read:{type(exc).__name__}")
        return summary

    matches_by_id = {m.get("id"): m for m in matches
                     if isinstance(m, dict)}
    pref_by_user = {p.get("user_id"): p for p in prefs
                    if isinstance(p, dict)}
    identity_cache: Dict[str, Any] = {}

    def _identity(user_id: str) -> Any:
        if user_id not in identity_cache:
            try:
                identity_cache[user_id] = identity_fn(user_id)
            except Exception:
                identity_cache[user_id] = None
        return identity_cache[user_id]

    def _eligible_user(user_id: str, category: str) -> bool:
        pref_column = CATEGORY_PREF_COLUMN.get(category, category)
        flags = pref_by_user.get(user_id)
        if not isinstance(flags, dict) or not flags.get(pref_column, False):
            _skip("opted_out")
            return False
        identity = _identity(user_id)
        capabilities = getattr(identity, "capabilities", None)
        if identity is None or capabilities is None:
            _skip("identity_missing")
            return False
        if CATEGORY_CAPABILITY[category] not in capabilities:
            _skip("capability_denied")
            return False
        return True

    def _queue(key: str, user_id: str, category: str, entity_type: str,
               entity_id: Any, body: str) -> None:
        row = {"idempotency_key": key, "user_id": user_id,
               "category": category, "entity_type": entity_type,
               "entity_id": str(entity_id), "payload_hash": _payload_hash(body),
               "body": body, "status": "pending", "attempts": 0,
               "max_attempts": DEFAULT_MAX_ATTEMPTS}
        try:
            db.table("whatsapp_deliveries").insert(row).execute()
        except Exception as exc:
            if _is_conflict(exc):
                _skip("duplicate")
                return
            summary["errors"].append(f"queue:{type(exc).__name__}")
            return
        summary["queued"] += 1

    for match in matches:
        if not isinstance(match, dict):
            continue
        if not eligible_match(match, moment,
                              window_hours=reminder_window_hours):
            _skip("ineligible_match")
            continue
        names = _team_names(db, match)
        if names is None:
            _skip("missing_teams")
            continue
        home, away = names
        league = match.get("league") if isinstance(
            match.get("league"), str) else ""
        kickoff = match.get("match_date") if isinstance(
            match.get("match_date"), str) else ""
        body = format_match_reminder(home, away, league, kickoff)
        for account in accounts:
            user_id = account.get("user_id")
            if not isinstance(user_id, str) or not user_id:
                continue
            if not _eligible_user(user_id, "match_update"):
                continue
            _queue(match_reminder_key(match.get("id"), user_id), user_id,
                   "match_update", "match", match.get("id"), body)

    for bet in bets:
        if not isinstance(bet, dict):
            continue
        if not eligible_value_bet(bet, matches_by_id, moment):
            _skip("ineligible_bet")
            continue
        home = bet.get("home_team")
        away = bet.get("away_team")
        if not isinstance(home, str) or not isinstance(away, str):
            _skip("missing_teams")
            continue
        body = format_value_alert(
            home, away, str(bet.get("market")), str(bet.get("selection")),
            bet.get("odds"), bet.get("ev"))
        for account in accounts:
            user_id = account.get("user_id")
            if not isinstance(user_id, str) or not user_id:
                continue
            if not _eligible_user(user_id, "prediction_alert"):
                continue
            _queue(value_alert_key(bet.get("match_id"), bet.get("market"),
                                   bet.get("selection"), user_id),
                   user_id, "prediction_alert", "value_bet",
                   bet.get("id"), body)

    return summary


def _team_names(db: Any, match: Dict[str, Any]
                ) -> Optional[Tuple[str, str]]:
    """Resolve home/away names for a matches row. None when unverifiable."""
    try:
        teams = _rows_of(db.table("teams").select("id,name").execute())
    except Exception:
        return None
    by_id = {t.get("id"): t.get("name") for t in teams
             if isinstance(t, dict)}
    home = by_id.get(match.get("home_team_id"))
    away = by_id.get(match.get("away_team_id"))
    if not isinstance(home, str) or not home.strip():
        return None
    if not isinstance(away, str) or not away.strip():
        return None
    return home.strip(), away.strip()


def _rows_of(result: Any) -> List[Dict[str, Any]]:
    data = result.data if hasattr(result, "data") else result
    return [dict(r) for r in (data or []) if isinstance(r, dict)]


def _backoff_seconds(attempts: int) -> int:
    return min(BACKOFF_BASE_SECONDS * (2 ** max(attempts - 1, 0)),
               BACKOFF_MAX_SECONDS)


def _claimable(now: datetime, max_attempts: int) -> Callable[[Dict[str, Any]], bool]:
    def _ok(row: Dict[str, Any]) -> bool:
        if not isinstance(row, dict):
            return False
        if int(row.get("attempts", 0) or 0) >= max_attempts:
            return False
        status = row.get("status")
        if status == "pending":
            return True
        if status != "sending":
            return False
        lease = _parse(row.get("claimed_until"))
        return lease is None or lease <= now
    return _ok


def _rpc_claim_next(db: Any, now: datetime,
                      lease_until: datetime) -> Optional[Dict[str, Any]]:
    """Claim one eligible delivery via the atomic RPC. None = no work.

    Raises _RpcUnsupported when the db double exposes no rpc() boundary
    (offline fakes); the caller then uses the legacy conditional path.
    The RPC itself enforces: attempts < max_attempts, status pending or
    reclaimable sending (expired lease), never sent/failed/exhausted. It
    sets status='sending', claimed_until, attempts+1 atomically and
    returns the complete claimed row.
    """
    rpc = getattr(db, "rpc", None)
    if rpc is None:
        raise _RpcUnsupported("no rpc boundary")
    result = rpc(CLAIM_RPC_NAME, {"p_now": _iso(now),
                                  "p_lease_until": _iso(lease_until)}
                 ).execute()
    rows = _rows_of(result)
    return rows[0] if rows else None


def _settle_claimed_row(db: Any, sender: Any, row: Dict[str, Any],
                        attempts: int, moment: datetime,
                        tpl: Dict[str, str], limiter: Any,
                        summary: Dict[str, Any]) -> bool:
    """Send one already-claimed row and record the terminal transition.

    Returns True when the row counted toward the batch (sent/failed/
    retried/ambiguous). Returns False for rate_limited (claim released,
    caller should stop the cycle to avoid hot-spinning the lease).
    Phone-missing rows are marked failed (unlinked). Ambiguous provider
    timeouts return the row to pending with attempts kept and last_error
    set, explicitly NOT counted as sent: at-least-once, never
    exactly-once.
    """
    row_id = row.get("id")
    max_attempts = int(row.get("max_attempts") or DEFAULT_MAX_ATTEMPTS)
    phone = _recipient_phone(db, row.get("user_id"))
    if phone is None:
        _mark(db, row_id, {"status": "failed",
                           "last_error": "unlinked_or_no_number"})
        summary["failed"] += 1
        return True
    if limiter is not None:
        try:
            allowed = limiter.allow(f"notify:{phone}")
        except Exception:
            allowed = True
        if not allowed:
            # Release the atomic claim without burning retry budget: no
            # other worker can hold this lease, so the undo is race-free.
            # Stop the cycle here; the next cycle reclaims after backoff.
            _mark(db, row_id, {"status": "pending",
                               "claimed_until": None,
                               "attempts": max(int(attempts or 1) - 1, 0)})
            summary["rate_limited"] += 1
            return False
    template = tpl.get(row.get("category"), "")
    body = row.get("body") if isinstance(row.get("body"), str) else ""
    try:
        result = sender.send_template(phone, template,
                                      TEMPLATE_LANGUAGE, [body])
        ok = bool(getattr(result, "ok", False))
        error = getattr(result, "error", None)
        provider_id = getattr(result, "provider_id", None)
    except Exception as exc:
        error, ok, provider_id = (f"timeout:{type(exc).__name__}",
                                  False, None)
    if ok:
        _mark(db, row_id, {"status": "sent",
                           "provider_message_id": provider_id,
                           "provider_status": "sent",
                           "sent_at": _iso(moment)})
        summary["sent"] += 1
    elif isinstance(error, str) and (
            error.startswith("timeout:") or error == "transport_unavailable"):
        _mark(db, row_id, {"status": "pending",
                           "claimed_until": None,
                           "last_error": f"ambiguous_{error}"})
        summary["ambiguous"] += 1
    elif attempts >= max_attempts:
        _mark(db, row_id, {"status": "failed",
                           "claimed_until": None,
                           "last_error": str(error)[:256]})
        summary["failed"] += 1
    else:
        _mark(db, row_id, {
            "status": "pending",
            "claimed_until": _iso(
                moment + timedelta(seconds=_backoff_seconds(attempts))),
            "last_error": str(error)[:256] if error else "send_failed"})
        summary["retried"] += 1
    return True


def deliver_pending(
    db: Any,
    sender: Any,
    *,
    now: Optional[datetime] = None,
    batch_limit: int = DELIVERY_BATCH_LIMIT,
    claim_lease_seconds: int = CLAIM_LEASE_SECONDS,
    templates: Optional[Dict[str, str]] = None,
    limiter: Any = None,
) -> Dict[str, Any]:
    """Deliver claimed outbox rows via templates. Returns a summary.

    Production path: repeated atomic claim_whatsapp_delivery() RPC calls
    (one eligible row per call, attempts+1 and lease set atomically)
    until no eligible row remains or batch_limit is reached. Fallback
    path (db doubles without rpc()): legacy read-then-conditional-UPDATE
    over pending+sending candidates. Both paths share the same settle
    logic below.

    Summary keys: sent, failed, retried, ambiguous, skipped, rate_limited,
    errors. Ambiguous provider timeouts are returned to pending (attempts
    incremented, NOT counted as sent): at-least-once, never exactly-once.
    """
    moment = now or _now()
    tpl = dict(DEFAULT_TEMPLATES)
    if templates:
        tpl.update(templates)
    summary: Dict[str, Any] = {"sent": 0, "failed": 0, "retried": 0,
                               "ambiguous": 0, "skipped": 0,
                               "rate_limited": 0, "errors": []}
    if getattr(db, "rpc", None) is not None:
        claimed_count = 0
        seen_ids = set()
        while claimed_count < batch_limit:
            lease_until = moment + timedelta(seconds=claim_lease_seconds)
            try:
                row = _rpc_claim_next(db, moment, lease_until)
            except _RpcUnsupported:  # pragma: no cover - defensive
                break
            except Exception as exc:
                summary["errors"].append(f"deliver_claim:{type(exc).__name__}")
                return summary
            if row is None:
                break
            row_id = row.get("id")
            if row_id in seen_ids:
                # The RPC recycled a row settled earlier in this cycle
                # (ambiguous releases leave claimed_until NULL, hence
                # immediately reclaimable). Undo this extra claim
                # increment and defer the row to the next cycle so each
                # delivery is attempted at most once per cycle — the same
                # single-attempt guarantee as the legacy candidate loop.
                _mark(db, row_id, {
                    "status": "pending", "claimed_until": None,
                    "attempts": max(int(row.get("attempts", 1) or 1) - 1, 0)})
                break
            seen_ids.add(row_id)
            attempts = int(row.get("attempts", 0) or 0)
            counted = _settle_claimed_row(db, sender, row, attempts,
                                          moment, tpl, limiter, summary)
            if not counted:
                break  # rate_limited: claim released, defer rest
            claimed_count += 1
        return summary
    try:
        pending = _rows_of(db.table("whatsapp_deliveries").select("*").eq(
            "status", "pending").execute())
        sending = _rows_of(db.table("whatsapp_deliveries").select("*").eq(
            "status", "sending").execute())
    except Exception as exc:
        summary["errors"].append(f"deliver_read:{type(exc).__name__}")
        return summary

    candidates = sorted(pending + sending, key=lambda r: r.get("id", 0))
    claimed_count = 0
    for row in candidates:
        if claimed_count >= batch_limit:
            break
        row_id = row.get("id")
        max_attempts = int(row.get("max_attempts")
                           or DEFAULT_MAX_ATTEMPTS)
        if not _claimable(moment, max_attempts)(row):
            continue
        phone = _recipient_phone(db, row.get("user_id"))
        if phone is None:
            _mark(db, row_id, {"status": "failed",
                               "last_error": "unlinked_or_no_number"})
            summary["failed"] += 1
            continue
        if limiter is not None:
            try:
                allowed = limiter.allow(f"notify:{phone}")
            except Exception:
                allowed = True
            if not allowed:
                summary["rate_limited"] += 1
                continue
        attempts = int(row.get("attempts", 0) or 0) + 1
        lease_until = moment + timedelta(seconds=claim_lease_seconds)
        if not _conditional_claim(db, row_id, row, attempts, lease_until,
                                   max_attempts, now=moment):
            continue  # lost race: another worker claimed it
        claimed = dict(row)
        claimed["attempts"] = attempts
        _settle_claimed_row(db, sender, claimed, attempts,
                            moment, tpl, None, summary)
        # NOTE: limiter already checked pre-claim on this path, so pass
        # None to avoid double-counting the rate budget.
        claimed_count += 1
    return summary


def _recipient_phone(db: Any, user_id: Any) -> Optional[str]:
    if not isinstance(user_id, str) or not user_id:
        return None
    try:
        rows = _rows_of(db.table("whatsapp_accounts").select(
            "whatsapp_user_id").eq("user_id", user_id).limit(1).execute())
    except Exception:
        return None
    if not rows:
        return None
    phone = rows[0].get("whatsapp_user_id")
    return phone if isinstance(phone, str) and phone else None


def _conditional_claim(db: Any, row_id: Any, seen: Dict[str, Any],
                       attempts: int, lease_until: datetime,
                       max_attempts: int,
                       now: Optional[datetime] = None) -> bool:
    """Re-read then conditionally claim. False = lost race, skip.

    TEST-DOUBLES ONLY. Production uses the atomic claim_whatsapp_delivery()
    RPC (see CLAIM_RPC_NAME and _rpc_claim_next): a single SELECT ...
    FOR UPDATE SKIP LOCKED + UPDATE call is the concurrency boundary.
    This fallback preserves the same eligibility predicate
    (pending, or sending with an expired lease, attempts < max) for db
    doubles without an rpc() boundary. The re-read uses the cycle clock
    (`now`) so frozen-time tests are deterministic. The final UPDATE
    carries the expected prior status so a concurrent worker that already
    claimed the row makes this update match zero rows instead of
    overwriting its lease.
    """
    moment = now or _now()
    try:
        current = _rows_of(db.table("whatsapp_deliveries").select("*").eq(
            "id", row_id).execute())
    except Exception:
        return False
    if not current or not _claimable(moment, max_attempts)(current[0]):
        return False
    if current[0].get("status") != seen.get("status"):
        return False
    try:
        query = db.table("whatsapp_deliveries").update(
            {"status": "sending", "attempts": attempts,
             "claimed_until": _iso(lease_until)}).eq(
            "id", row_id).eq("status", seen.get("status"))
        result = query.execute()
        rows = getattr(result, "data", None) or []
        if not rows:
            return False  # lost race: status changed under us
    except Exception:
        return False
    return True


def _mark(db: Any, row_id: Any, patch: Dict[str, Any]) -> None:
    try:
        db.table("whatsapp_deliveries").update(dict(patch)).eq(
            "id", row_id).execute()
    except Exception as exc:
        logger.warning("whatsapp: outbox mark failed: %s",
                       type(exc).__name__)


def record_delivery_status(db: Any, provider_message_id: str, status: str,
                           error: Any = None) -> bool:
    """Record a Meta delivery receipt. True when a row matched.

    A failed receipt moves a sent row back to failed (with the error);
    otherwise only the provider status fields are updated. Never raises.
    """
    if not isinstance(provider_message_id, str) or not provider_message_id:
        return False
    try:
        rows = _rows_of(db.table("whatsapp_deliveries").select("*").eq(
            "provider_message_id", provider_message_id).execute())
    except Exception:
        return False
    if not rows:
        return False
    patch: Dict[str, Any] = {"provider_status": str(status)[:64]}
    if status == "failed":
        patch["status"] = "failed"
        if error is not None:
            patch["last_error"] = str(error)[:256]
    try:
        for row in rows:
            db.table("whatsapp_deliveries").update(dict(patch)).eq(
                "id", row.get("id")).execute()
    except Exception as exc:
        logger.warning("whatsapp: receipt write failed: %s",
                       type(exc).__name__)
        return False
    return True


def run_notification_cycle(
    db: Any,
    sender: Any,
    *,
    identity_fn: Callable[[str], Any],
    now: Optional[datetime] = None,
    batch_limit: int = DELIVERY_BATCH_LIMIT,
    limiter: Any = None,
) -> Dict[str, Any]:
    """Collect due notifications, then deliver. Explicit trigger only.

    Never scheduled, never automatic: callers invoke this deliberately
    (ops runbook, reviewed cron proposal). Returns
    {"collected": {...}, "delivered": {...}}.
    """
    moment = now or _now()
    collected = collect_due_notifications(db, identity_fn=identity_fn,
                                          now=moment)
    delivered = deliver_pending(db, sender, now=moment,
                                batch_limit=batch_limit, limiter=limiter)
    return {"collected": collected, "delivered": delivered}


__all__ = [
    "BACKOFF_BASE_SECONDS",
    "BACKOFF_MAX_SECONDS",
    "CATEGORY_CAPABILITY",
    "CATEGORY_PREF_COLUMN",
    "CLAIM_LEASE_SECONDS",
    "CLAIM_RPC_NAME",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_TEMPLATES",
    "DELIVERY_BATCH_LIMIT",
    "REMINDER_WINDOW_HOURS",
    "ALERT_MAX_AGE_HOURS",
    "TEMPLATE_LANGUAGE",
    "collect_due_notifications",
    "deliver_pending",
    "eligible_match",
    "eligible_value_bet",
    "format_match_reminder",
    "format_value_alert",
    "match_reminder_key",
    "record_delivery_status",
    "run_notification_cycle",
    "set_opt_in",
    "value_alert_key",
]
