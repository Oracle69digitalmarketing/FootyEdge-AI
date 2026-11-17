"""Server-side account-activity and admin-action recording.

Appends ONLY to public.account_events / public.admin_actions, and only
from server-observed facts:

    account.registered               (signup trigger, database side)
    session.authenticated_observed   (the API just verified a JWT for
                                       a caller)
    usage.predict_requested          (a real, entitled /api/predict call)
    usage.bet_recorded               (a real, entitled /api/bets/record call)
    usage.strategy_analyzed          (a real /api/analyze-strategy call)
    usage.acca_generated             (a real /api/acca-builder call)
    admin.*                          (admin audit: authorization probes
                                       recorded by admin_api)

Guarantees (by construction, not by convention):
  - writes go through the existing service-role client (never the
    browser key) and are best-effort: any failure is logged by type
    only and swallowed, so recording can never break the user-facing
    response or the admin read that preceded it;
  - recorded rows carry identity (user / actor id), a stable event or
    action name, a source, an optional dedupe key and an optional
    bounded target descriptor — never tokens, request payload,
    credentials or provider data;
  - every event_type / action value here is a fixed vocabulary constant
    (no free text from the client ever reaches these tables);
  - de-duplication keys collapse repeated observations (e.g. one
    session-observed row per user per UTC day) via ON CONFLICT DO
    NOTHING against the (user_id, event_type, dedupe_key) unique index.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("account_activity")

# --- fixed event vocabulary (account_events) --------------------------------
EVENT_ACCOUNT_REGISTERED = "account.registered"
EVENT_SESSION_OBSERVED = "session.authenticated_observed"
EVENT_USAGE_PREDICT = "usage.predict_requested"
EVENT_USAGE_BET = "usage.bet_recorded"
EVENT_USAGE_STRATEGY = "usage.strategy_analyzed"
EVENT_USAGE_ACCA = "usage.acca_generated"

KNOWN_EVENT_TYPES = frozenset({
    EVENT_ACCOUNT_REGISTERED,
    EVENT_SESSION_OBSERVED,
    EVENT_USAGE_PREDICT,
    EVENT_USAGE_BET,
    EVENT_USAGE_STRATEGY,
    EVENT_USAGE_ACCA,
})

SOURCE_API = "api"

# Bound for any free descriptor we allow on audit rows.
_TARGET_MAX_LEN = 200

# --- fixed action vocabulary (admin_actions) --------------------------------
ADMIN_PROBE_ACTION = "admin.auth_probe"
OWNER_PROVISIONING_ACTION = "owner_provisioning.one_shot"

KNOWN_ADMIN_ACTIONS = frozenset({
    ADMIN_PROBE_ACTION,
    OWNER_PROVISIONING_ACTION,
})


def _client() -> Any:
    """Existing service-role server client (lazy: avoids import cycle)."""
    from api import get_supabase_client  # noqa: E402

    return get_supabase_client()


def _bound_target(target: Optional[str]) -> Optional[str]:
    if target is None:
        return None
    text = str(target)[:_TARGET_MAX_LEN]
    return text or None


def record_event(
    user_id: Optional[str],
    event_type: str,
    *,
    source: str = SOURCE_API,
    dedupe_key: Optional[str] = None,
) -> bool:
    """Best-effort append to public.account_events.

    Returns True when the write was issued. Never raises: a recording
    failure is logged by exception type (never with the payload) and
    swallowed. Unknown event types and missing identities are refused
    up front (unknown vocabulary must not reach the database).
    """
    if not user_id or event_type not in KNOWN_EVENT_TYPES:
        logger.warning(
            "account_activity: refusing unknown event (type=%s)", event_type
        )
        return False
    row: Dict[str, Any] = {
        "user_id": str(user_id),
        "event_type": event_type,
        "source": source,
        "dedupe_key": (str(dedupe_key)[:256] if dedupe_key is not None else None),
    }
    try:
        (
            _client()
            .table("account_events")
            .insert(row)
            .on_conflict("user_id,event_type,dedupe_key", ignore_duplicates=True)
            .execute()
        )
        return True
    except Exception as exc:  # observability must never break the feature
        logger.warning(
            "account_activity: %s write failed: %s", event_type, type(exc).__name__
        )
        return False


def observe_session(user_id: Optional[str]) -> bool:
    """Record that the API just verified this user's JWT (once per UTC day).

    This is "authentication was observed by the API", not a login assert:
    Supabase auth happens at the edge, so the only safe server-side
    signal is a verified request bearing the user's token.
    """
    if not user_id:
        return False
    day = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    return record_event(
        user_id,
        EVENT_SESSION_OBSERVED,
        dedupe_key=f"day:{day}",
    )


def record_usage(user_id: Optional[str], capability: str) -> bool:
    """Record a real, entitled feature call (vocabulary, no payload).

    One row per real call: usage counts are the genuine number of
    observed invocations (no per-day collapsing, no estimates).
    """
    mapping = {
        "predictions": EVENT_USAGE_PREDICT,
        "portfolio": EVENT_USAGE_BET,
        "ai_strategy_analysis": EVENT_USAGE_STRATEGY,
        "acca_builder": EVENT_USAGE_ACCA,
    }
    event = mapping.get(str(capability))
    if event is None:
        return False
    return record_event(user_id, event)


def record_admin_probe(
    actor_id: Optional[str],
    *,
    action: str = ADMIN_PROBE_ACTION,
    target: Optional[str] = None,
    actor_label: Optional[str] = None,
) -> bool:
    """Append an admin-action audit row (best-effort, never raises)."""
    if action not in KNOWN_ADMIN_ACTIONS:
        logger.warning("account_activity: refusing unknown admin action %r", action)
        return False
    row: Dict[str, Any] = {
        "actor_id": str(actor_id) if actor_id else None,
        "actor_label": (str(actor_label)[:256] if actor_label else None),
        "action": action,
        "target": _bound_target(target),
    }
    try:
        (_client().table("admin_actions").insert(row).execute())
        return True
    except Exception as exc:
        logger.warning(
            "account_activity: admin_actions write failed: %s", type(exc).__name__
        )
        return False


__all__ = [
    "ADMIN_PROBE_ACTION",
    "EVENT_ACCOUNT_REGISTERED",
    "EVENT_SESSION_OBSERVED",
    "EVENT_USAGE_ACCA",
    "EVENT_USAGE_BET",
    "EVENT_USAGE_PREDICT",
    "EVENT_USAGE_STRATEGY",
    "KNOWN_ADMIN_ACTIONS",
    "KNOWN_EVENT_TYPES",
    "OWNER_PROVISIONING_ACTION",
    "SOURCE_API",
    "observe_session",
    "record_admin_probe",
    "record_event",
    "record_usage",
]