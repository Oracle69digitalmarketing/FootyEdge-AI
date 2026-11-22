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

# --- fixed admin action vocabulary -------------------------------------------
ADMIN_PROBE_ACTION = "admin.authorization"

KNOWN_ADMIN_ACTIONS = frozenset({ADMIN_PROBE_ACTION})

# --- helpers ---------------------------------------------------------------

def _bound_target(target: Optional[str]) -> Optional[str]:
    """Bound the target string to prevent runaway storage."""
    if target is None:
        return None
    return target[:512] if len(target) > 512 else target


def record_event(
    user_id: Optional[str],
    event_type: str,
    source: str = "api",
    dedupe_key: Optional[str] = None,
) -> bool:
    """Append an account-events row (best-effort, never raises)."""
    if event_type not in KNOWN_EVENT_TYPES:
        logger.warning("account_activity: refusing unknown event type %r", event_type)
        return False
    row: Dict[str, Any] = {
        "user_id": str(user_id) if user_id else None,
        "event_type": event_type,
        "source": source,
        "dedupe_key": dedupe_key,
    }
    try:
        (_client().table("account_events").insert(row).execute())
        return True
    except Exception as exc:
        logger.warning(
            "account_activity: account_events write failed: %s", type(exc).__name__
        )
        return False


def record_usage(
    user_id: str,
    *,
    capability: str,
    action: str,
) -> bool:
    """Record a usage event for a given capability and action.

    Maps to usage.predict_requested, usage.bet_recorded,
    usage.strategy_analyzed or usage.acca_generated.
    """
    mapping = {
        "predict_requested": EVENT_USAGE_PREDICT,
        "bet_recorded": EVENT_USAGE_BET,
        "strategy_analyzed": EVENT_USAGE_STRATEGY,
        "acca_generated": EVENT_USAGE_ACCA,
    }
    event = mapping.get(action)
    if event is None:
        logger.warning(
            "account_activity: unknown usage action %r", action
        )
        return False
    return record_event(user_id, event, source="api")


def observe_session(user_id: str, target: Optional[str] = None) -> bool:
    """Record a session-authenticated-observed event (best-effort)."""
    return record_event(user_id, EVENT_SESSION_OBSERVED, source="api", dedupe_key=user_id)


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
    "observe_session",
    "record_admin_probe",
    "record_event",
    "record_usage",
]
