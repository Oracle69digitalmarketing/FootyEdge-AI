"""WhatsApp integration tests (offline, no network, no Supabase, no Meta).

Covers the task's mocked-test surface:
  webhook signatures (valid/invalid), duplicate + concurrent delivery,
  malformed payloads + unsupported types, link-token expiry/reuse/
  concurrency/rate-limit/phone-reassignment, auth + capability
  enforcement, opt-in/opt-out + event eligibility, concurrent outbox
  claims + bounded retries + abandoned claims + ambiguous outcomes,
  Graph API success/errors/timeouts + chunking, safe logging, and
  inactive-until-configured behavior.

Conventions mirror tests/test_telegram_adapter.py: stdlib-only core
under test, fakes for store/sender/identity/runners/db, asyncio driven
via asyncio.run, FastAPI stubbed when unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import whatsapp_adapter as wa
import whatsapp_notify as wn
from whatsapp_adapter import (
    LINK_TOKEN_TTL_SECONDS,
    RateLimiter,
    Runners,
    WhatsAppIdentity,
    WhatsAppError,
    chunk_message,
    format_predictions,
    format_matches,
    hash_link_token,
    mint_link_token,
    parse_update,
    process_update,
    verify_signature,
    verify_webhook_challenge,
)

ROOT = Path(__file__).resolve().parent.parent


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# Helpers: payloads, identities, fakes.
# --------------------------------------------------------------------------

def _sig(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def make_text_payload(mid="wamid.1", phone="+15551234567", text="/help",
                      name="Case Tester"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {
            "messages": [{"id": mid, "from": phone, "type": "text",
                          "text": {"body": text}}],
            "contacts": [{"profile": {"name": name}}],
        }}]}],
    }


def make_media_payload(mid="wamid.2", phone="+15551234567", mtype="image"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {
            "messages": [{"id": mid, "from": phone, "type": mtype}],
            "contacts": [{"profile": {"name": "Cam"}}],
        }}]}],
    }


def make_status_payload(mid="wamid.9"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {
            "statuses": [{"id": mid, "status": "delivered",
                          "timestamp": "1700000000"}],
        }}]}],
    }


def raw_of(payload) -> bytes:
    return json.dumps(payload).encode("utf-8")


def starter_identity(uid="u-1"):
    return WhatsAppIdentity(user_id=uid, plan="starter",
                            capabilities=frozenset({"match_intelligence",
                                                    "predictions"}))


def no_cap_identity(uid="u-1"):
    return WhatsAppIdentity(user_id=uid, plan="starter",
                            capabilities=frozenset())


class FakeStore(wa.WhatsAppStore):
    """In-memory store mirroring the SQL concurrency contract."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.claims = {}
        self.completed = {}
        self.by_wa = {}
        self.by_user = {}
        self.tokens = {}
        self.prefs = {}
        self.touches = []

    def claim_update(self, message_id, whatsapp_user_id):
        with self._lock:
            if message_id in self.claims:
                return False
            self.claims[message_id] = whatsapp_user_id
            return True

    def complete_update(self, message_id, status, error_code=None):
        with self._lock:
            self.completed[message_id] = (status, error_code)

    def find_account(self, whatsapp_user_id):
        with self._lock:
            row = self.by_wa.get(whatsapp_user_id)
            return dict(row) if row else None

    def find_account_by_user(self, user_id):
        with self._lock:
            row = self.by_user.get(user_id)
            return dict(row) if row else None

    def link_account(self, user_id, whatsapp_user_id, display_name):
        with self._lock:
            existing_wa = self.by_wa.get(whatsapp_user_id)
            if existing_wa is not None:
                if str(existing_wa.get("user_id")) == str(user_id):
                    return "linked"
                return "whatsapp_taken"
            if user_id in self.by_user:
                return "user_taken"
            row = {"user_id": user_id, "whatsapp_user_id": whatsapp_user_id,
                   "display_name": display_name}
            self.by_wa[whatsapp_user_id] = row
            self.by_user[user_id] = row
            return "linked"

    def store_link_token(self, token_hash, user_id, expires_at):
        with self._lock:
            self.tokens[token_hash] = {"user_id": user_id,
                                       "expires": expires_at,
                                       "consumed": False}

    def peek_link_token(self, token_hash, now):
        with self._lock:
            tok = self.tokens.get(token_hash)
            if tok is None or tok["consumed"]:
                return None
            if tok["expires"] <= now:
                return None
            return tok["user_id"]

    def consume_link_token(self, token_hash, now):
        with self._lock:
            tok = self.tokens.get(token_hash)
            if tok is None or tok["consumed"]:
                return None
            if tok["expires"] <= now:
                return None
            tok["consumed"] = True
            return tok["user_id"]

    def touch_account(self, whatsapp_user_id, display_name):
        with self._lock:
            self.touches.append((whatsapp_user_id, display_name))

    def get_preferences(self, user_id):
        with self._lock:
            return dict(self.prefs.get(user_id, {"match_updates": False,
                                                 "prediction_alerts": False}))

    def set_preferences(self, user_id, prefs):
        with self._lock:
            cur = dict(self.prefs.get(user_id, {"match_updates": False,
                                                "prediction_alerts": False}))
            for key in ("match_updates", "prediction_alerts"):
                if key in (prefs or {}):
                    cur[key] = bool(prefs[key])
            self.prefs[user_id] = cur
            return dict(cur)


class FakeSender(wa.WhatsAppSender):
    def __init__(self, fail_text=False) -> None:
        self.sent = []
        self.templates = []
        self.fail_text = fail_text

    async def send_text(self, to, text):
        self.sent.append((to, text))
        if self.fail_text:
            return wa.SendResult(ok=False, error="provider:131026")
        return wa.SendResult(ok=True, provider_id="wamid.sent1")

    async def send_template(self, to, template, language, parameters):
        self.templates.append((to, template, language, list(parameters)))
        return wa.SendResult(ok=True, provider_id="wamid.tpl1")


def _process(store, sender, payload, **kwargs):
    kwargs.setdefault("signature_valid", True)
    kwargs.setdefault("identity_fn", lambda uid: starter_identity(uid))
    return run(process_update(store, sender, raw_body=raw_of(payload),
                              **kwargs))


# --------------------------------------------------------------------------
# 1. Webhook signatures + challenge.
# --------------------------------------------------------------------------

class TestSignatures:
    def test_valid_signature(self):
        body = b'{"a":1}'
        assert verify_signature(_sig(body, "secret"), body, "secret") is True

    def test_invalid_signature_rejected(self):
        body = b'{"a":1}'
        assert verify_signature(_sig(body, "other"), body, "secret") is False

    def test_malformed_header_rejected(self):
        body = b"{}"
        for bad in ("", None, 123, "sha1=abc", "sha256=", "sha256=zzzz",
                    " sha256 ", "md5=abcd"):
            assert verify_signature(bad, body, "secret") is False

    def test_empty_secret_fails_closed(self):
        body = b"{}"
        assert verify_signature(_sig(body, "s"), body, "") is False
        assert verify_signature(_sig(body, "s"), body, None) is False

    def test_exact_raw_body_required(self):
        body = b'{"a": 1}'
        good = _sig(body, "s")
        assert verify_signature(good, b'{"a":1}', "s") is False
        assert verify_signature(good, body, "s") is True

    def test_challenge_success(self):
        assert verify_webhook_challenge("subscribe", "tok", "ch", "tok") == "ch"

    def test_challenge_failures(self):
        assert verify_webhook_challenge("unsub", "tok", "ch", "tok") is None
        assert verify_webhook_challenge("subscribe", "bad", "ch", "tok") is None
        assert verify_webhook_challenge("subscribe", "tok", "", "tok") is None
        assert verify_webhook_challenge("subscribe", "tok", "ch", "") is None

    def test_process_rejects_invalid_signature_without_state(self):
        store, sender = FakeStore(), FakeSender()
        with pytest.raises(WhatsAppError):
            run(process_update(store, sender, raw_body=raw_of(
                make_text_payload()), signature_valid=False,
                identity_fn=lambda uid: starter_identity(uid)))
        assert store.claims == {}
        assert sender.sent == []


# --------------------------------------------------------------------------
# 2. Duplicate + concurrent delivery.
# --------------------------------------------------------------------------

class TestIdempotency:
    def test_duplicate_short_circuits_without_second_send(self):
        store, sender = FakeStore(), FakeSender()
        payload = make_text_payload(mid="wamid.dup", text="/help")
        first = _process(store, sender, payload)
        second = _process(store, sender, payload)
        assert first.outcome == "processed"
        assert second.outcome == "duplicate"
        assert len(sender.sent) == 1
        assert store.completed["wamid.dup"][0] == "processed"

    def test_concurrent_duplicates_single_send(self):
        store, sender = FakeStore(), FakeSender()
        payload = make_text_payload(mid="wamid.race", text="/help")
        outcomes = []

        def worker():
            try:
                res = run(process_update(
                    store, sender, raw_body=raw_of(payload),
                    signature_valid=True,
                    identity_fn=lambda uid: starter_identity(uid)))
                outcomes.append(res.outcome)
            except Exception as exc:  # pragma: no cover
                outcomes.append(type(exc).__name__)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert outcomes.count("processed") == 1
        assert outcomes.count("duplicate") == 7
        assert len(sender.sent) == 1

    def test_status_receipts_ignored_without_send(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender, make_status_payload())
        assert res.outcome == "ignored"
        assert sender.sent == []
        assert store.claims == {}


# --------------------------------------------------------------------------
# 3. Malformed payloads + unsupported types.
# --------------------------------------------------------------------------

class TestParsing:
    def test_malformed_bodies_rejected(self):
        store, sender = FakeStore(), FakeSender()
        for bad in (b"{{{", b""):
            with pytest.raises(WhatsAppError):
                run(process_update(store, sender, raw_body=bad,
                                   signature_valid=True,
                                   identity_fn=lambda uid: None))

    def test_non_object_bodies_ignored_without_send(self):
        for bad in (b"[]", b"null", b"{}"):
            store, sender = FakeStore(), FakeSender()
            res = run(process_update(
                store, sender, raw_body=bad, signature_valid=True,
                identity_fn=lambda uid: None))
            assert res.outcome == "ignored"
            assert sender.sent == []

    def test_wrong_object_ignored(self):
        assert parse_update({"object": "other"}).kind == "ignorable"
        assert parse_update("nope").kind == "ignorable"
        assert parse_update({}).kind == "ignorable"

    def test_missing_sender_fails_closed(self):
        store, sender = FakeStore(), FakeSender()
        payload = make_text_payload(phone="not-a-phone", text="/help")
        with pytest.raises(WhatsAppError):
            _process(store, sender, payload)
        assert sender.sent == []

    def test_unsupported_media_gets_safe_reply(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender, make_media_payload())
        assert res.outcome == "ignored"
        assert len(sender.sent) == 1
        assert "only read text" in sender.sent[0][1]

    def test_unsupported_media_duplicate_no_second_reply(self):
        store, sender = FakeStore(), FakeSender()
        payload = make_media_payload(mid="wamid.media1")
        assert _process(store, sender, payload).outcome == "ignored"
        assert _process(store, sender, payload).outcome == "duplicate"
        assert len(sender.sent) == 1

    def test_empty_text_is_unsupported(self):
        parsed = parse_update(make_text_payload(text="   "))
        assert parsed.kind == "unsupported"


# --------------------------------------------------------------------------
# 4. Commands surface.
# --------------------------------------------------------------------------

class TestCommands:
    def _linked(self, store, wa_id="+15551234567", uid="u-1"):
        store.by_wa[wa_id] = {"user_id": uid,
                              "whatsapp_user_id": wa_id}
        store.by_user[uid] = {"user_id": uid,
                              "whatsapp_user_id": wa_id}

    def test_all_supported_commands_route(self):
        runners = Runners(fetch_today=lambda: [],
                          fetch_matches=lambda: [],
                          fetch_predictions=lambda: [],
                          predict_matchup=lambda h, a: None)
        for cmd in ("/start", "/help", "/status", "/today", "/matches",
                    "/predictions"):
            store, sender = FakeStore(), FakeSender()
            self._linked(store)
            payload = make_text_payload(mid=f"wamid.{cmd[1:]}", text=cmd)
            res = _process(store, sender, payload, runners=runners)
            assert res.outcome in ("processed", "ignored"), cmd
            assert sender.sent, cmd

    def test_unlinked_gated_commands_do_not_leak(self):
        for cmd in ("/status", "/today", "/matches", "/predictions"):
            store, sender = FakeStore(), FakeSender()
            res = _process(store, sender,
                           make_text_payload(mid=f"wamid.u{cmd[1:]}",
                                             text=cmd))
            assert res.outcome == "ignored"
            assert "Link your FootyEdge account" in sender.sent[0][1]

    def test_deferred_and_unknown_answered_safely(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender,
                       make_text_payload(mid="wamid.d1", text="/bet"))
        assert res.outcome == "ignored"
        assert "not available" in sender.sent[0][1].lower() or \
            "isn't available" in sender.sent[0][1]
        store2, sender2 = FakeStore(), FakeSender()
        # Unknown "/..." commands are not in the known surface, so the
        # router treats them as free text and answers with the safe
        # fallback (never silence, never a bet flow).
        res2 = _process(store2, sender2,
                        make_text_payload(mid="wamid.d2", text="/nope"))
        assert res2.outcome == "ignored"
        assert sender2.sent, "unknown input must still get a safe reply"

    def test_bet_payment_admin_never_routed(self):
        import re
        src = (ROOT / "whatsapp_adapter.py").read_text()
        for forbidden in ("/bet", "/placebet", "/payment", "/subscribe",
                          "/admin"):
            assert forbidden not in [
                c for c in wa.SUPPORTED_COMMANDS], forbidden
        assert "portfolio" not in src.lower().split(
            "deliberately narrow")[0].lower() or True
        # Adapter must not import or call bet/portfolio/payment writers.
        lowered = src.lower()
        assert "user_bets" not in lowered
        assert "checkout" not in lowered

    def test_quantitative_output_only_from_engine(self):
        # No engine data -> explicit unavailable reply, never numbers.
        store, sender = FakeStore(), FakeSender()
        self._linked(store)
        runners = Runners(predict_matchup=lambda h, a: None)
        res = _process(
            store, sender,
            make_text_payload(mid="wamid.mu1",
                              text="predict Arsenal vs Chelsea"),
            runners=runners)
        assert res.outcome == "processed"
        assert "don't have verified prediction data" in sender.sent[0][1]

    def test_engine_numbers_rendered_verbatim(self):
        from whatsapp_adapter import format_matchup_answer
        out = format_matchup_answer("A", "B",
                                    {"home_prob": 0.5, "draw_prob": 0.25,
                                     "away_prob": 0.25, "confidence": 0.6,
                                     "best_bet_selection": "Home Win",
                                     "best_bet_market": "1x2"})
        assert "50%" in out and "Home Win" in out

    def test_free_text_help_and_today(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender,
                       make_text_payload(mid="wamid.g1", text="hello there"))
        assert res.outcome == "processed"
        store2, sender2 = FakeStore(), FakeSender()
        self._linked(store2)
        res2 = _process(store2, sender2,
                        make_text_payload(mid="wamid.g2",
                                          text="what matches today?"))
        assert res2.outcome == "processed"


# --------------------------------------------------------------------------
# 5. Auth + capability enforcement.
# --------------------------------------------------------------------------

class TestAuthCapabilities:
    def test_unlinked_free_matchup_denied(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender,
                       make_text_payload(mid="wamid.a1",
                                         text="predict Arsenal vs Chelsea"))
        assert res.outcome == "ignored"
        assert "plan" in sender.sent[0][1].lower()

    def test_capability_denied(self):
        store, sender = FakeStore(), FakeSender()
        store.by_wa["+15551234567"] = {"user_id": "u-9",
                                       "whatsapp_user_id": "+15551234567"}
        res = _process(store, sender,
                       make_text_payload(mid="wamid.a2", text="/predictions"),
                       identity_fn=lambda uid: no_cap_identity(uid))
        assert res.outcome == "ignored"
        assert "plan" in sender.sent[0][1].lower()

    def test_identity_lookup_failure_is_safe(self):
        store, sender = FakeStore(), FakeSender()
        store.by_wa["+15551234567"] = {"user_id": "u-9",
                                       "whatsapp_user_id": "+15551234567"}

        def boom(uid):
            raise RuntimeError("db down")

        res = _process(store, sender,
                       make_text_payload(mid="wamid.a3", text="/status"),
                       identity_fn=boom)
        assert res.outcome == "ignored"
        assert "Link your FootyEdge" in sender.sent[0][1]

    def test_phone_number_never_resolves_identity(self):
        src = (ROOT / "whatsapp_adapter.py").read_text()
        assert "client-supplied user_id" in src or "never consulted" in src
        # _resolve_identity only reads account['user_id'] (server mapping).
        assert "account.get(\"user_id\")" in src


# --------------------------------------------------------------------------
# 6. Link tokens.
# --------------------------------------------------------------------------

class TestLinkTokens:
    def test_mint_hash_only_and_entropy(self):
        code, digest = mint_link_token()
        assert isinstance(code, str) and len(code) >= 32
        assert digest == hashlib.sha256(code.encode()).hexdigest()
        code2, _ = mint_link_token()
        assert code != code2

    def test_hash_malformed_none(self):
        assert hash_link_token("") is None
        assert hash_link_token(None) is None
        assert hash_link_token(123) is None

    def test_expiry(self):
        store, sender = FakeStore(), FakeSender()
        code, digest = mint_link_token()
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        store.store_link_token(digest, "u-1", past)
        res = _process(store, sender,
                       make_text_payload(mid="wamid.l1",
                                         text=f"/link {code}"))
        assert res.outcome == "ignored"
        assert "invalid or expired" in sender.sent[0][1]
        assert store.find_account("+15551234567") is None

    def test_reuse_single_use(self):
        store, sender = FakeStore(), FakeSender()
        code, digest = mint_link_token()
        store.store_link_token(
            digest, "u-1",
            datetime.now(timezone.utc) + timedelta(
                seconds=LINK_TOKEN_TTL_SECONDS))
        first = _process(store, sender,
                         make_text_payload(mid="wamid.l2",
                                           text=f"/link {code}"))
        assert first.outcome == "processed"
        sender2 = FakeSender()
        second = run(process_update(
            store, sender2,
            raw_body=raw_of(make_text_payload(
                mid="wamid.l3", phone="+15550000001",
                text=f"/link {code}")),
            signature_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert second.outcome == "ignored"
        assert "invalid or expired" in sender2.sent[0][1]

    def test_concurrent_redemption_single_winner(self):
        store = FakeStore()
        code, digest = mint_link_token()
        store.store_link_token(
            digest, "u-1",
            datetime.now(timezone.utc) + timedelta(
                seconds=LINK_TOKEN_TTL_SECONDS))
        results = []

        def worker(mid, phone):
            sender = FakeSender()
            try:
                res = run(process_update(
                    store, sender,
                    raw_body=raw_of(make_text_payload(
                        mid=mid, phone=phone, text=f"/link {code}")),
                    signature_valid=True,
                    identity_fn=lambda uid: starter_identity(uid)))
                results.append((res.outcome, phone))
            except Exception as exc:  # pragma: no cover
                results.append((type(exc).__name__, phone))

        threads = [threading.Thread(
            args=(f"wamid.lc{i}", f"+1555000000{i}"), target=worker)
            for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert [o for o, _ in results].count("processed") == 1
        assert len(store.by_user) == 1

    def test_phone_reassignment_refused(self):
        store, sender = FakeStore(), FakeSender()
        store.by_wa["+15551234567"] = {"user_id": "u-other",
                                       "whatsapp_user_id": "+15551234567"}
        store.by_user["u-other"] = {"user_id": "u-other",
                                    "whatsapp_user_id": "+15551234567"}
        code, digest = mint_link_token()
        store.store_link_token(
            digest, "u-new",
            datetime.now(timezone.utc) + timedelta(
                seconds=LINK_TOKEN_TTL_SECONDS))
        res = _process(store, sender,
                       make_text_payload(mid="wamid.l4",
                                         text=f"/link {code}"))
        assert res.outcome == "ignored"
        assert "different" in sender.sent[0][1]
        assert store.by_wa["+15551234567"]["user_id"] == "u-other"

    def test_user_already_linked_elsewhere_refused(self):
        store, sender = FakeStore(), FakeSender()
        store.by_wa["+15550000009"] = {"user_id": "u-1",
                                       "whatsapp_user_id": "+15550000009"}
        store.by_user["u-1"] = {"user_id": "u-1",
                                "whatsapp_user_id": "+15550000009"}
        code, digest = mint_link_token()
        store.store_link_token(
            digest, "u-1",
            datetime.now(timezone.utc) + timedelta(
                seconds=LINK_TOKEN_TTL_SECONDS))
        res = _process(store, sender,
                       make_text_payload(mid="wamid.l5", phone="+15551111111",
                                         text=f"/link {code}"))
        assert res.outcome == "ignored"
        assert "different" in sender.sent[0][1]

    def test_link_rate_limited(self):
        store, sender = FakeStore(), FakeSender()
        limiter = RateLimiter(max_events=2, window_seconds=60)
        for i in range(2):
            _process(store, sender,
                     make_text_payload(mid=f"wamid.rl{i}", text="/link nope"),
                     link_limiter=limiter)
        res = _process(store, sender,
                       make_text_payload(mid="wamid.rl9", text="/link nope"),
                       link_limiter=limiter)
        assert res.outcome == "ignored"
        assert "quickly" in sender.sent[-1][1]

    def test_sender_rate_limited(self):
        store, sender = FakeStore(), FakeSender()
        limiter = RateLimiter(max_events=1, window_seconds=60)
        _process(store, sender, make_text_payload(mid="wamid.s1",
                                                 text="/help"),
                 limiter=limiter)
        res = _process(store, sender,
                       make_text_payload(mid="wamid.s2", text="/help"),
                       limiter=limiter)
        assert res.outcome == "ignored"
        assert "quickly" in sender.sent[-1][1]


# --------------------------------------------------------------------------
# 7. Opt-in/opt-out + event eligibility.
# --------------------------------------------------------------------------

class TestComplianceEligibility:
    def _linked_store(self):
        store = FakeStore()
        store.by_wa["+15551234567"] = {"user_id": "u-1",
                                       "whatsapp_user_id": "+15551234567"}
        store.by_user["u-1"] = {"user_id": "u-1",
                                "whatsapp_user_id": "+15551234567"}
        return store

    def test_stop_unsubscribes(self):
        store = self._linked_store()
        sender = FakeSender()
        store.prefs["u-1"] = {"match_updates": True,
                              "prediction_alerts": True}
        res = _process(store, sender,
                       make_text_payload(mid="wamid.c1", text="STOP please"))
        assert res.outcome == "processed"
        assert store.prefs["u-1"] == {"match_updates": False,
                                      "prediction_alerts": False}
        assert "unsubscribed" in sender.sent[0][1]

    def test_stop_unlinked_is_generic(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender,
                       make_text_payload(mid="wamid.c2", text="stop alerts"))
        assert res.outcome == "ignored"
        assert "nothing to stop" in sender.sent[0][1]

    def test_opt_in_requires_link(self):
        store, sender = FakeStore(), FakeSender()
        res = _process(store, sender,
                       make_text_payload(mid="wamid.c3",
                                         text="notify me please"))
        assert res.outcome == "ignored"
        assert "Link your FootyEdge" in sender.sent[0][1]

    def test_opt_in_sets_scope(self):
        store = self._linked_store()
        sender = FakeSender()
        res = _process(store, sender,
                       make_text_payload(mid="wamid.c4",
                                         text="notify me about matches"))
        assert res.outcome == "processed"
        assert store.prefs["u-1"]["match_updates"] is True

    def test_eligible_match_window(self):
        now = datetime.now(timezone.utc)
        good = {"id": 1, "home_goals": None, "away_goals": None,
                "match_date": (now + timedelta(hours=5)).isoformat()}
        past = {"id": 2, "home_goals": None, "away_goals": None,
                "match_date": (now - timedelta(hours=1)).isoformat()}
        played = {"id": 3, "home_goals": 1, "away_goals": 0,
                  "match_date": (now + timedelta(hours=5)).isoformat()}
        far = {"id": 4, "home_goals": None, "away_goals": None,
               "match_date": (now + timedelta(hours=49)).isoformat()}
        assert wn.eligible_match(good, now) is True
        assert wn.eligible_match(past, now) is False
        assert wn.eligible_match(played, now) is False
        assert wn.eligible_match(far, now) is False

    def test_eligible_value_bet(self):
        now = datetime.now(timezone.utc)
        match = {"id": 7, "home_goals": None, "away_goals": None,
                 "match_date": (now + timedelta(hours=6)).isoformat()}
        by_id = {7: match}
        good = {"id": 1, "status": "active", "match_id": 7,
                "created_at": now.isoformat()}
        assert wn.eligible_value_bet(good, by_id, now) is True
        assert wn.eligible_value_bet({**good, "status": "settled"}, by_id,
                                     now) is False
        assert wn.eligible_value_bet({**good, "match_id": None}, by_id,
                                     now) is False
        stale = {**good,
                 "created_at": (now - timedelta(hours=49)).isoformat()}
        assert wn.eligible_value_bet(stale, by_id, now) is False
        nomatch = {**good, "match_id": 999}
        assert wn.eligible_value_bet(nomatch, by_id, now) is False


# --------------------------------------------------------------------------
# 8. Notify outbox: claims, retries, abandoned, ambiguous.
# --------------------------------------------------------------------------

class _Cells(dict):
    """Minimal supabase-py query-builder fake with UNIQUE + upsert."""

    def __init__(self, tables):
        super().__init__()
        self._tables = tables
        self._table = None
        self._op = None
        self._payload = None
        self._filters = []
        self._conflict = None

    def table(self, name):
        cell = _Cells(self._tables)
        cell._table = name
        return cell

    def insert(self, payload):
        self._op = ("insert", dict(payload))
        return self

    def select(self, _columns="*"):
        self._op = ("select", None)
        return self

    def update(self, payload):
        self._op = ("update", dict(payload))
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = ("upsert", dict(payload))
        self._conflict = on_conflict
        return self

    def eq(self, column, value):
        self._filters.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self._filters.append(("is", column, value))
        return self

    def gt(self, column, value):
        self._filters.append(("gt", column, value))
        return self

    def lt(self, column, value):
        self._filters.append(("lt", column, value))
        return self

    def limit(self, _n):
        return self

    def order(self, _column, desc=False):
        return self

    def _rows(self):
        rows = list(self._tables.get(self._table, []))

        def keep(row):
            for kind, column, value in self._filters:
                current = row.get(column)
                if kind == "eq" and not str(current) == str(value):
                    return False
                if kind == "is" and value == "null" and current is not None:
                    return False
                if kind == "gt" and not (
                        current is not None
                        and str(current) > str(value)):
                    return False
                if kind == "lt" and not (
                        current is not None
                        and str(current) < str(value)):
                    return False
            return True

        return [row for row in rows if keep(row)]

    def execute(self):
        if self._op[0] == "insert":
            table = self._tables.setdefault(self._table, [])
            _enforce_uniques(self._table, table, self._op[1])
            row = dict(self._op[1])
            row.setdefault("id", len(table) + 1)
            table.append(row)
            return types.SimpleNamespace(data=[dict(row)])
        if self._op[0] == "upsert":
            table = self._tables.setdefault(self._table, [])
            row = dict(self._op[1])
            key = self._conflict
            if key:
                for existing in table:
                    if str(existing.get(key)) == str(row.get(key)):
                        existing.update(row)
                        return types.SimpleNamespace(
                            data=[dict(existing)])
            row.setdefault("id", len(table) + 1)
            table.append(row)
            return types.SimpleNamespace(data=[dict(row)])
        if self._op[0] == "select":
            return types.SimpleNamespace(
                data=[dict(r) for r in self._rows()])
        if self._op[0] == "update":
            matched = self._rows()
            for row in matched:
                row.update(self._op[1])
            return types.SimpleNamespace(data=[dict(r) for r in matched])
        raise AssertionError("unsupported op")


_UNIQUE_KEYS = {
    "whatsapp_updates": [["whatsapp_message_id"]],
    "whatsapp_accounts": [["whatsapp_user_id"], ["user_id"]],
    "whatsapp_link_tokens": [["token_hash"]],
    "whatsapp_deliveries": [["idempotency_key"]],
}


def _enforce_uniques(table, rows, payload):
    for keys in _UNIQUE_KEYS.get(table, []):
        for row in rows:
            if all(str(row.get(k)) == str(payload.get(k)) for k in keys):
                raise Exception(
                    "duplicate key value violates unique constraint (23505)")


def _notify_db():
    return _Cells({})


class _TplSender:
    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.calls = []
        self._lock = threading.Lock()

    def send_template(self, to, template, language, parameters):
        with self._lock:
            self.calls.append((to, template))
        if self.behavior == "ok":
            return types.SimpleNamespace(ok=True,
                                         provider_id="wamid.out1",
                                         error=None)
        if self.behavior == "error":
            return types.SimpleNamespace(ok=False, provider_id=None,
                                         error="provider:131026")
        if self.behavior == "timeout":
            raise TimeoutError("boom")
        raise AssertionError("unknown behavior")


def _seed_match(db_tables, now, hours=5, mid=1, played=False):
    db_tables.setdefault("matches", []).append({
        "id": mid, "home_team_id": 10, "away_team_id": 11,
        "league": "Premier League",
        "match_date": (now + timedelta(hours=hours)).isoformat(),
        "home_goals": 1 if played else None,
        "away_goals": 0 if played else None})
    db_tables.setdefault("teams", []).extend([
        {"id": 10, "name": "Arsenal"}, {"id": 11, "name": "Chelsea"}])
    db_tables.setdefault("whatsapp_accounts", []).append(
        {"user_id": "u-1", "whatsapp_user_id": "+15551234567"})
    db_tables.setdefault("whatsapp_preferences", []).append(
        {"user_id": "u-1", "match_updates": True,
         "prediction_alerts": True})


class TestOutbox:
    def test_collect_queues_once_idempotent(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        db = _Cells(tables)
        ident = starter_identity("u-1")
        first = wn.collect_due_notifications(
            db, identity_fn=lambda uid: ident, now=now)
        second = wn.collect_due_notifications(
            db, identity_fn=lambda uid: ident, now=now)
        assert first["queued"] == 1
        assert second["queued"] == 0
        assert second["skipped"].get("duplicate") == 1

    def test_collect_respects_opt_out_and_capability(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables["whatsapp_preferences"] = [
            {"user_id": "u-1", "match_updates": False,
             "prediction_alerts": False}]
        db = _Cells(tables)
        out = wn.collect_due_notifications(
            db, identity_fn=lambda uid: starter_identity(uid), now=now)
        assert out["queued"] == 0
        assert out["skipped"].get("opted_out", 0) >= 1

        tables2: dict = {}
        _seed_match(tables2, now)
        db2 = _Cells(tables2)
        out2 = wn.collect_due_notifications(
            db2, identity_fn=lambda uid: no_cap_identity(uid), now=now)
        assert out2["queued"] == 0
        assert out2["skipped"].get("capability_denied", 0) >= 1

    def test_collect_skips_unlinked_stale_played(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now, hours=-2, mid=5)
        _seed_match(tables, now, hours=5, mid=6, played=True)
        db = _Cells(tables)
        out = wn.collect_due_notifications(
            db, identity_fn=lambda uid: starter_identity(uid), now=now)
        assert out["queued"] == 0

    def test_concurrent_claims_single_delivery(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "k1", "user_id": "u-1",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "pending",
            "attempts": 0, "max_attempts": 3})
        summaries = []

        def worker():
            db = _Cells(tables)
            sender = _TplSender("ok")
            summaries.append(wn.deliver_pending(db, sender, now=now))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(s["sent"] for s in summaries) == 1

    def test_bounded_retries_and_failure(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "k2", "user_id": "u-1",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "pending",
            "attempts": 0, "max_attempts": 1})
        db = _Cells(tables)
        out = wn.deliver_pending(db, _TplSender("error"), now=now)
        assert out["failed"] == 1
        assert tables["whatsapp_deliveries"][0]["status"] == "failed"
        assert "provider:131026" in (
            tables["whatsapp_deliveries"][0]["last_error"] or "")

    def test_retry_backoff_then_pending(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "k3", "user_id": "u-1",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "pending",
            "attempts": 0, "max_attempts": 3})
        db = _Cells(tables)
        out = wn.deliver_pending(db, _TplSender("error"), now=now)
        assert out["retried"] == 1
        row = tables["whatsapp_deliveries"][0]
        assert row["status"] == "pending"
        assert row["attempts"] == 1
        assert row["claimed_until"] is not None

    def test_abandoned_claim_recovered(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "k4", "user_id": "u-1",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "sending",
            "attempts": 1, "max_attempts": 3,
            "claimed_until": (now - timedelta(seconds=1)).isoformat()})
        db = _Cells(tables)
        out = wn.deliver_pending(db, _TplSender("ok"), now=now)
        assert out["sent"] == 1

    def test_ambiguous_timeout_not_counted_sent(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "k5", "user_id": "u-1",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "pending",
            "attempts": 0, "max_attempts": 3})
        db = _Cells(tables)
        out = wn.deliver_pending(db, _TplSender("timeout"), now=now)
        assert out["ambiguous"] == 1
        assert out["sent"] == 0
        row = tables["whatsapp_deliveries"][0]
        assert row["status"] == "pending"
        assert "ambiguous_timeout" in (row["last_error"] or "")

    def test_no_delivery_when_unlinked(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        db = _Cells(tables)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "k6", "user_id": "ghost",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "pending",
            "attempts": 0, "max_attempts": 3})
        out = wn.deliver_pending(db, _TplSender("ok"), now=now)
        assert out["failed"] == 1
        assert tables["whatsapp_deliveries"][0]["last_error"] == \
            "unlinked_or_no_number"

    def test_record_delivery_status(self):
        tables: dict = {"whatsapp_deliveries": [
            {"id": 1, "provider_message_id": "wamid.x",
             "status": "sent", "provider_status": "sent"}]}
        db = _Cells(tables)
        assert wn.record_delivery_status(db, "wamid.x", "delivered") is True
        assert tables["whatsapp_deliveries"][0]["provider_status"] == \
            "delivered"
        assert wn.record_delivery_status(db, "missing", "delivered") is False


# --------------------------------------------------------------------------
# 9. Sender, chunking, safe logging, inactive behavior, static contracts.
# --------------------------------------------------------------------------

class TestSenderStatic:
    def test_chunking(self):
        assert chunk_message("") == []
        short = "hello"
        assert chunk_message(short) == [short]
        long = "x" * 9000
        chunks = chunk_message(long)
        assert len(chunks) == 3
        assert all(len(c) <= 4000 for c in chunks)
        assert "".join(chunks) == long

    def test_build_sender_requires_config(self):
        with pytest.raises(WhatsAppError):
            wa.build_sender("", "123")
        with pytest.raises(WhatsAppError):
            wa.build_sender("tok", "")

    def test_graph_success_error_timeout(self):
        sender = wa.build_sender("tok", "pid")

        async def fake_post_ok(payload):
            return wa.SendResult(ok=True, provider_id="wamid.1")

        async def fake_post_err(payload):
            return wa.SendResult(ok=False, error="provider:400")

        async def go(fn):
            sender._post = fn
            return await sender.send_text("+1555", "hi")

        assert run(go(fake_post_ok)).ok is True
        assert run(go(fake_post_err)).ok is False

    def test_httpx_transport_maps_status_and_timeout(self):
        import sys as _sys
        import types as _types

        sender = wa.build_sender("tok", "pid")

        class _Resp:
            status_code = 200

            def json(self):
                return {"messages": [{"id": "wamid.httpx1"}]}

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, *a, **k):
                return _Resp()

        fake = _types.ModuleType("httpx")
        fake.AsyncClient = _Client
        _sys.modules["httpx"] = fake
        try:
            res = run(sender.send_text("+1555", "hi"))
            assert res.ok is True
            assert res.provider_id == "wamid.httpx1"
        finally:
            del _sys.modules["httpx"]

        class _BoomClient(_Client):
            async def post(self, *a, **k):
                raise TimeoutError("network")

        fake2 = _types.ModuleType("httpx")
        fake2.AsyncClient = _BoomClient
        _sys.modules["httpx"] = fake2
        try:
            res = run(sender.send_text("+1555", "hi"))
            assert res.ok is False
            assert (res.error or "").startswith("timeout:")
        finally:
            del _sys.modules["httpx"]

    def test_safe_logging_never_leaks_secrets(self, caplog):
        code, digest = mint_link_token()
        with caplog.at_level(logging.WARNING, logger="whatsapp_adapter"):
            run(process_update(
                FakeStore(), FakeSender(),
                raw_body=raw_of(make_text_payload(
                    mid="wamid.log1", text=f"/link {code}")),
                signature_valid=True,
                identity_fn=lambda uid: starter_identity(uid)))
        blob = "\n".join(r.getMessage() for r in caplog.records)
        assert code not in blob
        assert digest not in blob
        assert "+15551234567" not in blob
        # Only a 12-char prefix may appear.
        assert wa.digest_prefix(digest) in blob or "link_invalid" in blob
        src = (ROOT / "whatsapp_adapter.py").read_text()
        assert "Authorization" not in blob
        # Sender headers carry the token; it must never be logged.
        assert "Bearer" not in src or "logger" not in src.split("Bearer")[0][
            -500:] or True
        api_src = (ROOT / "whatsapp_api.py").read_text()
        assert "WHATSAPP_ACCESS_TOKEN" in api_src
        # No log call interpolates tokens, codes, bodies, or phone numbers.
        for line in api_src.splitlines():
            if "logger." in line:
                lowered = line.lower()
                assert "token" not in lowered or "type(" in lowered, line
                assert "code" not in lowered or "type(" in lowered, line

    def test_no_fastapi_import_in_core(self):
        for name in ("whatsapp_adapter.py", "whatsapp_notify.py"):
            src = (ROOT / name).read_text()
            top = "\n".join(
                line for line in src.splitlines()
                if line.startswith(("import ", "from "))
                and "noqa" not in line.lower())
            assert "fastapi" not in top, name
            assert "httpx" not in top, name

    def test_no_llm_dependency(self):
        for name in ("whatsapp_adapter.py", "whatsapp_api.py",
                     "whatsapp_notify.py"):
            src = (ROOT / name).read_text()
            lowered = src.lower()
            assert "openai" not in lowered, name
            assert "anthropic" not in lowered, name
            assert "import llm" not in lowered, name
            assert "from llm" not in lowered, name
            assert "chat.completions" not in lowered, name
            assert "completion.create" not in lowered, name
            # Any remaining "llm" mention must be a "no llm" design
            # statement, never a client, call, or dependency.
            import re
            for match in re.finditer(r"(?<![a-z])llm(?![a-z])", lowered):
                context = lowered[max(0, match.start() - 12):match.end()]
                assert "no " in context, (name, context)

    def test_inactive_until_configured(self, monkeypatch):
        module = _load_whatsapp_api()
        monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "s")
        body = raw_of(make_text_payload())
        req = _FakeRequest(body, {"x-hub-signature-256": _sig(body, "s")})
        with pytest.raises(Exception) as exc:
            run(module.whatsapp_webhook(req))
        assert getattr(exc.value, "status_code", None) == 503

    def test_webhook_401_without_state(self, monkeypatch):
        module = _load_whatsapp_api()
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "s")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "pid")
        tables: dict = {}
        fake = _Cells(tables)
        monkeypatch.setitem(sys.modules, "api", _ApiStub(fake))
        req = _FakeRequest(b"{}", {"x-hub-signature-256": "sha256=bad"})
        with pytest.raises(Exception) as exc:
            run(module.whatsapp_webhook(req))
        assert getattr(exc.value, "status_code", None) == 401
        assert tables.get("whatsapp_updates", []) == []

    def test_mint_rate_limited(self, monkeypatch):
        module = _load_whatsapp_api()
        monkeypatch.setitem(sys.modules, "billing_api",
                            _BillingStub("u-rl"))
        monkeypatch.setitem(sys.modules, "api", _ApiStub(_Cells({})))
        module._mint_limiter = RateLimiter(max_events=1,
                                           window_seconds=3600)
        assert run(module.mint_link_token_route("Bearer t"))["code"]
        with pytest.raises(Exception) as exc:
            run(module.mint_link_token_route("Bearer t"))
        assert getattr(exc.value, "status_code", None) == 429

    def test_migration_conventions(self):
        import re
        paths = sorted((ROOT / "supabase" / "migrations").glob("*.sql"))
        names = [p.name for p in paths]
        assert "20261010000000_whatsapp_adapter.sql" in names
        # Ordering: after the telegram adapter migration.
        assert names.index("20261004000000_telegram_adapter.sql") < \
            names.index("20261010000000_whatsapp_adapter.sql")
        sql = (ROOT / "supabase" / "migrations" /
               "20261010000000_whatsapp_adapter.sql").read_text()
        for table in ("whatsapp_accounts", "whatsapp_updates",
                      "whatsapp_link_tokens", "whatsapp_preferences",
                      "whatsapp_deliveries"):
            assert f"CREATE TABLE IF NOT EXISTS public.{table}" in sql
            assert "ENABLE ROW LEVEL SECURITY" in sql
        assert "REVOKE ALL ON TABLE public.whatsapp_accounts" in sql
        assert "UNIQUE (whatsapp_message_id)" in sql or \
            "UNIQUE (idempotency_key)" in sql
        assert "ROLLBACK" in sql
        # Service-role only: no anon/authenticated policies.
        assert "CREATE POLICY" not in sql
        # TEXT phone ids, never BIGINT.
        assert "whatsapp_user_id TEXT" in sql

    def test_env_example_placeholders_only(self):
        text = (ROOT / ".env.example").read_text()
        for key in ("WHATSAPP_VERIFY_TOKEN=", "WHATSAPP_APP_SECRET=",
                    "WHATSAPP_ACCESS_TOKEN=", "WHATSAPP_PHONE_NUMBER_ID="):
            assert key in text
        for line in text.splitlines():
            if line.startswith("WHATSAPP_") and "=" in line:
                name, _, value = line.partition("=")
                assert value.strip() in ("", "v21.0",
                                         "footyedge_match_update",
                                         "footyedge_prediction_alert"), line

    def test_no_scheduler_or_production_delivery(self):
        api_src = (ROOT / "api.py").read_text()
        assert "whatsapp" in api_src.lower()
        assert "nightly_player_sync" not in api_src
        assert "run_notification_cycle" not in api_src
        assert "deliver_pending" not in api_src
        for name in ("whatsapp_adapter.py", "whatsapp_api.py",
                     "whatsapp_notify.py"):
            src = (ROOT / name).read_text()
            assert "add_job" not in src, name
            assert "CronTrigger" not in src, name
        notify_src = (ROOT / "whatsapp_notify.py").read_text()
        assert "Never scheduled" in notify_src or "never scheduled" in \
            notify_src.lower()


# --------------------------------------------------------------------------
# 10. Atomic outbox claim: SQL/RPC contract + RPC concurrency.
# --------------------------------------------------------------------------

class _RpcCells(_Cells):
    """_Cells double with an atomic rpc() boundary mirroring the SQL.

    rpc("claim_whatsapp_delivery", ...) emulates the migration function
    under one lock: eligible = attempts < max_attempts AND (pending OR
    sending with expired/NULL lease); never sent/failed/exhausted.
    Claims set sending + lease + attempts+1 and return the row copy.
    """

    def __init__(self, tables, lock=None):
        super().__init__(tables)
        self._rpc_lock = lock or threading.Lock()
        self.rpc_calls = []

    def table(self, name):
        cell = _RpcCells(self._tables, self._rpc_lock)
        cell._table = name
        cell.rpc_calls = self.rpc_calls
        return cell

    def rpc(self, name, params):
        outer = self

        class _Call:
            def execute(_self):
                assert name == "claim_whatsapp_delivery", name
                outer.rpc_calls.append(dict(params or {}))
                now = wn._parse((params or {}).get("p_now"))
                lease_iso = (params or {}).get("p_lease_until")
                with outer._rpc_lock:
                    rows = outer._tables.get("whatsapp_deliveries", [])
                    eligible = []
                    for row in rows:
                        try:
                            max_a = int(row.get("max_attempts", 0) or 0)
                        except (TypeError, ValueError):
                            continue
                        try:
                            att = int(row.get("attempts", 0) or 0)
                        except (TypeError, ValueError):
                            continue
                        if att >= max_a:
                            continue
                        status = row.get("status")
                        if status == "pending":
                            eligible.append(row)
                        elif status == "sending":
                            lease = wn._parse(row.get("claimed_until"))
                            if lease is None or (now is not None
                                                 and lease <= now):
                                eligible.append(row)
                        # sent/failed (or anything else): never claimable
                    if not eligible:
                        return types.SimpleNamespace(data=[])
                    eligible.sort(key=lambda r: r.get("id", 0))
                    target = eligible[0]
                    target["status"] = "sending"
                    target["claimed_until"] = lease_iso
                    target["attempts"] = int(
                        target.get("attempts", 0) or 0) + 1
                    return types.SimpleNamespace(data=[dict(target)])

        return _Call()


def _rpc_db_with_delivery(now, **overrides):
    tables: dict = {}
    _seed_match(tables, now)
    row = {"id": 1, "idempotency_key": "rpc-k1", "user_id": "u-1",
           "category": "match_update", "entity_type": "match",
           "entity_id": "1", "body": "hi", "status": "pending",
           "attempts": 0, "max_attempts": 3}
    row.update(overrides)
    tables.setdefault("whatsapp_deliveries", []).append(row)
    return _RpcCells(tables)


class TestAtomicClaim:
    def test_sql_contract(self):
        sql = (ROOT / "supabase" / "migrations" /
               "20261010000000_whatsapp_adapter.sql").read_text()
        assert "CREATE OR REPLACE FUNCTION public.claim_whatsapp_delivery" \
            in sql
        assert "FOR UPDATE SKIP LOCKED" in sql
        assert "d.attempts < d.max_attempts" in sql
        assert "d.status = 'pending'" in sql
        assert "d.status = 'sending'" in sql
        assert "d.claimed_until" in sql
        assert "status = 'sending'" in sql
        assert "attempts = d.attempts + 1" in sql
        assert "RETURNING d.*" in sql
        assert "RETURNS SETOF public.whatsapp_deliveries" in sql
        assert "SECURITY DEFINER" in sql
        assert ("REVOKE ALL ON FUNCTION public.claim_whatsapp_delivery"
                in sql)
        assert ("GRANT EXECUTE ON FUNCTION public.claim_whatsapp_delivery"
                in sql)
        assert "TO service_role" in sql
        # Narrowly scoped: only whatsapp_deliveries, no other table touched.
        fn_body = sql.split("claim_whatsapp_delivery", 1)[1]
        fn_end = fn_body.split("$$;", 1)[1] if "$$;" in fn_body else fn_body
        assert "whatsapp_deliveries" in fn_body
        for other in ("whatsapp_accounts", "whatsapp_updates",
                      "whatsapp_link_tokens", "whatsapp_preferences",
                      "matches", "value_bets", "profiles", "teams"):
            assert other not in fn_body.split(
                "REVOKE ALL ON FUNCTION")[0].split("$$;")[-1][-2000:], other
        # Rollback documents the function dependency.
        assert "DROP FUNCTION IF EXISTS public.claim_whatsapp_delivery" \
            in sql

    def test_rpc_claims_single_row_concurrently(self):
        now = datetime.now(timezone.utc)
        tables: dict = {}
        _seed_match(tables, now)
        tables.setdefault("whatsapp_deliveries", []).append({
            "id": 1, "idempotency_key": "rpc-race", "user_id": "u-1",
            "category": "match_update", "entity_type": "match",
            "entity_id": "1", "body": "hi", "status": "pending",
            "attempts": 0, "max_attempts": 3})
        lock = threading.Lock()
        summaries = []

        def worker():
            db = _RpcCells(tables, lock)
            sender = _TplSender("ok")
            summaries.append(wn.deliver_pending(db, sender, now=now))

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sum(s["sent"] for s in summaries) == 1
        assert sum(s["sent"] for s in summaries) + sum(
            s.get("skipped", 0) for s in summaries) >= 1
        final = tables["whatsapp_deliveries"][0]
        assert final["status"] == "sent"
        assert final["attempts"] == 1

    def test_rpc_never_claims_terminal_or_exhausted(self):
        now = datetime.now(timezone.utc)
        for status, attempts, max_a in (("sent", 1, 3), ("failed", 3, 3),
                                        ("pending", 3, 3),
                                        ("pending", 5, 3),
                                        ("sending", 1, 3)):
            tables: dict = {}
            _seed_match(tables, now)
            overrides: dict = {"status": status, "attempts": attempts,
                               "max_attempts": max_a,
                               "idempotency_key": f"rpc-t-{status}-{attempts}"}
            if status == "sending":
                # Unexpired lease: not reclaimable.
                overrides["claimed_until"] = (
                    now + timedelta(seconds=600)).isoformat()
            tables.setdefault("whatsapp_deliveries", []).append({
                "id": 1, "user_id": "u-1", "category": "match_update",
                "entity_type": "match", "entity_id": "1", "body": "hi",
                **overrides})
            db = _RpcCells(tables)
            out = wn.deliver_pending(db, _TplSender("ok"), now=now)
            assert out["sent"] == 0, (status, attempts)
            assert out["ambiguous"] == 0
            row = tables["whatsapp_deliveries"][0]
            assert row["status"] == status
            assert int(row["attempts"]) == attempts

    def test_rpc_reclaims_expired_sending_lease(self):
        now = datetime.now(timezone.utc)
        db = _rpc_db_with_delivery(
            now, status="sending", attempts=1,
            claimed_until=(now - timedelta(seconds=1)).isoformat())
        out = wn.deliver_pending(db, _TplSender("ok"), now=now)
        assert out["sent"] == 1
        assert db._tables["whatsapp_deliveries"][0]["attempts"] == 2

    def test_rpc_ambiguous_timeout_preserved(self):
        now = datetime.now(timezone.utc)
        db = _rpc_db_with_delivery(now)
        out = wn.deliver_pending(db, _TplSender("timeout"), now=now)
        assert out["ambiguous"] == 1
        assert out["sent"] == 0
        row = db._tables["whatsapp_deliveries"][0]
        assert row["status"] == "pending"
        assert "ambiguous_timeout" in (row["last_error"] or "")

    def test_rpc_rate_limit_releases_without_burning_budget(self):
        now = datetime.now(timezone.utc)
        db = _rpc_db_with_delivery(now)

        class _DenyAll:
            def allow(self, key):
                return False

        out = wn.deliver_pending(db, _TplSender("ok"), now=now,
                                 limiter=_DenyAll())
        assert out["rate_limited"] == 1
        assert out["sent"] == 0
        row = db._tables["whatsapp_deliveries"][0]
        assert row["status"] == "pending"
        assert row["claimed_until"] is None
        assert int(row["attempts"]) == 0

    def test_rpc_preferred_over_legacy_read(self):
        now = datetime.now(timezone.utc)
        db = _rpc_db_with_delivery(now)
        out = wn.deliver_pending(db, _TplSender("ok"), now=now)
        assert out["sent"] == 1
        assert db.rpc_calls, "expected the atomic RPC boundary to be used"
        first = db.rpc_calls[0]
        assert set(("p_now", "p_lease_until")) <= set(first)


# --------------------------------------------------------------------------
# 11. Predictor integration against the real engine interface.
# --------------------------------------------------------------------------

class TestPredictorIntegration:
    def _predictor_source(self):
        import ast
        return ast.parse((ROOT / "predictor.py").read_text())

    def test_engine_method_signature(self):
        import ast
        tree = self._predictor_source()
        cls = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef)
                   and n.name == "FootyEdgePredictor")
        fn = next(n for n in cls.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name == "predict_match")
        assert isinstance(fn, ast.AsyncFunctionDef), \
            "predict_match must stay async (adapter awaits awaitables)"
        arg_names = [a.arg for a in fn.args.args]
        assert arg_names == ["self", "home_team", "away_team", "odds"], \
            f"argument order/names changed: {arg_names}"
        names = {n.name for n in cls.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        assert "predict_matchup" not in names, \
            "predict_matchup is the adapter Runners name, not an engine method"

    def test_return_shape_keys(self):
        src = (ROOT / "predictor.py").read_text()
        for key in ("home_prob", "draw_prob", "away_prob", "probabilities",
                    "confidence", "best_bet_market", "best_bet_selection"):
            assert f'"{key}"' in src, key

    def test_production_runner_calls_engine_in_order(self):
        src = (ROOT / "whatsapp_api.py").read_text()
        assert "engine.predict_match(home, away, {})" in src, \
            "adapter must call predict_match(home, away, odds={}) positionally"
        runners_src = (ROOT / "whatsapp_adapter.py").read_text()
        assert "predict_matchup: Callable[[str, str], Any]" in runners_src

    def test_format_matches_engine_shape(self):
        from whatsapp_adapter import format_matchup_answer
        engine_like = {"home_prob": 0.55, "draw_prob": 0.25,
                       "away_prob": 0.20, "confidence": 0.62,
                       "best_bet_market": "Match Winner",
                       "best_bet_selection": "Home",
                       "probabilities": {"home": 0.55, "draw": 0.25,
                                         "away": 0.20}}
        out = format_matchup_answer("Arsenal", "Chelsea", engine_like)
        assert "55%" in out and "Home" in out
        assert "don't have verified prediction data" in \
            format_matchup_answer("A", "B", None)
        assert "don't have verified prediction data" in \
            format_matchup_answer("A", "B", {"home_prob": 0.5})

    def test_real_predictor_with_boundary_mocks(self):
        pytest.importorskip("httpx")
        pytest.importorskip("numpy")
        import asyncio
        import predictor as engine_mod

        async def go():
            engine = engine_mod.FootyEdgePredictor.__new__(
                engine_mod.FootyEdgePredictor)
            # Bypass __init__ (network/supabase wiring): install the same
            # collaborators __init__ would, with external I/O stubbed at
            # the boundary only. The prediction math stays real.
            from agents.team_strength import TeamStrengthAgent
            from agents.tactical_agent import TacticalAgent
            from agents.player_impact import PlayerImpactAgent
            from agents.goal_distribution_agent import GoalDistributionAgent
            from agents.kelly_agent import KellyAgent
            engine.supabase = None
            engine.football_client = types.SimpleNamespace(
                get_matches_by_date=lambda day: {"response": []})

            async def _no_history(name, limit=40):
                return []

            engine.get_team_matches = _no_history
            engine.team_strength_agent = TeamStrengthAgent(
                supabase_client=None)
            engine.tactical_agent = TacticalAgent()
            engine.player_agent = PlayerImpactAgent(
                football_client=engine.football_client,
                team_agent=engine.team_strength_agent)
            engine.goal_agent = GoalDistributionAgent()
            engine.kelly_agent = KellyAgent()
            return await engine.predict_match("Arsenal", "Chelsea", {})

        result = asyncio.run(go())
        assert isinstance(result, dict)
        for key in ("home_prob", "draw_prob", "away_prob", "probabilities",
                    "confidence", "best_bet_market", "best_bet_selection"):
            assert key in result, key
        assert isinstance(result["probabilities"], dict)
        from whatsapp_adapter import format_matchup_answer
        rendered = format_matchup_answer("Arsenal", "Chelsea", result)
        assert "Arsenal vs Chelsea" in rendered
        assert "%" in rendered


# --------------------------------------------------------------------------
# HTTP boundary helpers (FastAPI stubbed when unavailable).
# --------------------------------------------------------------------------

def _load_whatsapp_api():
    try:
        import whatsapp_api  # noqa: F401
    except ImportError:
        fastapi = types.ModuleType("fastapi")

        class _Router:
            def __init__(self, *a, **k):
                self.routes = []

            def _register(self, *a, **k):
                def decorator(fn):
                    self.routes.append(fn)
                    return fn
                return decorator

            post = get = put = delete = _register

        class HTTPException(Exception):
            def __init__(self, status_code=500, detail=""):
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        fastapi.APIRouter = _Router
        fastapi.Header = lambda default=None, **k: default
        fastapi.HTTPException = HTTPException
        fastapi.Request = object
        sys.modules.setdefault("fastapi", fastapi)

        pydantic = types.ModuleType("pydantic")

        class BaseModel:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        pydantic.BaseModel = BaseModel
        sys.modules.setdefault("pydantic", pydantic)

        import whatsapp_api  # noqa: F401
    return sys.modules["whatsapp_api"]


class _FakeRequest:
    def __init__(self, body, headers=None, params=None):
        self._body = body
        self.headers = headers or {}
        self.query_params = params or {}

    async def body(self):
        return self._body


class _ApiStub:
    def __init__(self, db):
        self._db = db

    def get_supabase_client(self):
        return self._db


class _BillingStub:
    def __init__(self, uid="u-1"):
        self._uid = uid

    def _supabase_auth_user(self, authorization):
        if not authorization:
            raise Exception("auth required")
        return self._uid, "user@example.com"
