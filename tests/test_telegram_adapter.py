"""Objective 9.1 Telegram adapter tests (offline, no network, no Supabase).

Covers §21: webhook security, idempotency, linking, identity, entitlements,
commands, bet-route non-exposure, formatter, sender factory, HTTP boundary,
store contract, and source-level security contracts.

Conventions mirror the billing suites: stdlib-only core under test, fakes
for store/sender/entitlements/runners, asyncio driven via asyncio.run so no
pytest plugin is required, and FastAPI stubbed when unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import telegram_adapter as ta
from telegram_adapter import (
    Runners,
    TelegramIdentity,
    TelegramError,
    chunk_message,
    escape_markdown_v2,
    format_matches,
    format_predictions,
    format_status,
    hash_link_token,
    mint_link_token,
    parse_update,
    process_update,
    verify_webhook_secret,
)

ROOT = Path(__file__).resolve().parent.parent


def run(coro):
    return asyncio.run(coro)


# --------------------------------------------------------------------------
# Fakes (model the SQL semantics: UNIQUE arbiter, atomic conditional write).
# --------------------------------------------------------------------------

class FakeStore(ta.TelegramStore):
    """In-memory store with the same concurrency contract as the SQL one."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.claims = {}          # update_id -> telegram_user_id
        self.completed = {}       # update_id -> (status, error_code)
        self.by_telegram = {}     # telegram_user_id -> account row
        self.by_user = {}         # user_id -> account row
        self.tokens = {}          # token_hash -> {user_id, expires, consumed}
        self.touches = []

    def claim_update(self, update_id, telegram_user_id):
        with self._lock:
            if update_id in self.claims:
                return False
            self.claims[update_id] = telegram_user_id
            return True

    def complete_update(self, update_id, status, error_code=None):
        with self._lock:
            self.completed[update_id] = (status, error_code)

    def find_account(self, telegram_user_id):
        with self._lock:
            row = self.by_telegram.get(telegram_user_id)
            return dict(row) if row else None

    def find_account_by_user(self, user_id):
        with self._lock:
            row = self.by_user.get(user_id)
            return dict(row) if row else None

    def link_account(self, user_id, telegram_user_id, chat_id, username):
        with self._lock:
            existing = self.by_telegram.get(telegram_user_id)
            if existing is not None:
                if existing["user_id"] == user_id:
                    return "linked"
                return "telegram_taken"
            if user_id in self.by_user:
                return "user_taken"
            row = {"user_id": user_id, "telegram_user_id": telegram_user_id,
                   "chat_id": chat_id, "username": username}
            self.by_telegram[telegram_user_id] = row
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
            if tok is None or tok["consumed"] or tok["expires"] <= now:
                return None
            return tok["user_id"]

    def consume_link_token(self, token_hash, now):
        with self._lock:
            tok = self.tokens.get(token_hash)
            if tok is None or tok["consumed"] or tok["expires"] <= now:
                return None
            tok["consumed"] = True
            return tok["user_id"]

    def touch_account(self, telegram_user_id, chat_id, username):
        with self._lock:
            self.touches.append((telegram_user_id, chat_id, username))


class FakeSender(ta.TelegramSender):
    def __init__(self, fail=False) -> None:
        self.sent = []
        self.fail = fail

    async def send_message(self, chat_id, text):
        if self.fail:
            return False
        self.sent.append((chat_id, text))
        return True


def starter_identity(user_id="user-1"):
    return TelegramIdentity(user_id=user_id, plan="starter",
                            capabilities=frozenset({
                                "dashboard", "match_intelligence",
                                "predictions", "teams", "players"}))


def growth_identity(user_id="user-1"):
    return TelegramIdentity(user_id=user_id, plan="growth",
                            capabilities=frozenset({
                                "dashboard", "match_intelligence",
                                "predictions", "teams", "players",
                                "value_bets", "acca_builder", "portfolio",
                                "ai_strategy_analysis"}))


def make_update(update_id=1, sender=111, chat=111, text="/help",
                username="someone"):
    return json.dumps({
        "update_id": update_id,
        "message": {"message_id": 9,
                    "from": {"id": sender, "username": username},
                    "chat": {"id": chat, "type": "private"},
                    "text": text},
    }).encode("utf-8")


def link_sender(store, sender=111, user_id="user-1", chat=111):
    store.by_telegram[sender] = {"user_id": user_id,
                                 "telegram_user_id": sender,
                                 "chat_id": chat, "username": "someone"}
    store.by_user[user_id] = store.by_telegram[sender]


# --------------------------------------------------------------------------
# Webhook security.
# --------------------------------------------------------------------------

class TestWebhookSecurity:
    def test_valid_secret_accepted(self):
        assert verify_webhook_secret("s3cret", "s3cret") is True

    def test_missing_secret_rejected(self):
        assert verify_webhook_secret(None, "s3cret") is False
        assert verify_webhook_secret("", "s3cret") is False

    def test_invalid_secret_rejected(self):
        assert verify_webhook_secret("wrong", "s3cret") is False

    def test_missing_server_secret_fails_closed(self):
        assert verify_webhook_secret("anything", "") is False
        assert verify_webhook_secret("anything", None) is False

    def test_length_mismatch_rejected(self):
        assert verify_webhook_secret("short", "a-much-longer-secret") is False

    def test_non_string_rejected(self):
        assert verify_webhook_secret(12345, "s3cret") is False
        assert verify_webhook_secret(b"s3cret", "s3cret") is False

    def test_constant_time_comparison(self):
        source = (ROOT / "telegram_adapter.py").read_text()
        assert "hmac.compare_digest" in source

    def test_secret_failure_touches_no_state(self):
        store, sender = FakeStore(), FakeSender()
        with pytest.raises(TelegramError):
            run(process_update(
                store, sender, raw_body=make_update(),
                secret_valid=False,
                identity_fn=lambda uid: starter_identity(uid)))
        assert store.claims == {}
        assert store.completed == {}
        assert sender.sent == []

    def test_malformed_body_rejected_without_claim(self):
        store, sender = FakeStore(), FakeSender()
        with pytest.raises(TelegramError):
            run(process_update(
                store, sender, raw_body=b"not json",
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid)))
        assert store.claims == {}

    def test_update_without_identity_claims_nothing(self):
        store, sender = FakeStore(), FakeSender()
        body = json.dumps({"update_id": 5, "message": {}}).encode()
        with pytest.raises(TelegramError):
            run(process_update(
                store, sender, raw_body=body, secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid)))
        assert store.claims == {}


# --------------------------------------------------------------------------
# Idempotency.
# --------------------------------------------------------------------------

class TestIdempotency:
    def test_first_update_processed(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/help"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "processed"
        assert store.completed[1][0] == "processed"
        assert len(sender.sent) == 1

    def test_duplicate_sends_nothing_and_executes_nothing(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        calls = []

        def _count():
            calls.append(1)
            return []

        runners = Runners(fetch_predictions=_count)
        body = make_update(update_id=7, text="/predictions")
        first = run(process_update(
            store, sender, raw_body=body, secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid), runners=runners))
        second = run(process_update(
            store, sender, raw_body=body, secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid), runners=runners))
        assert first.outcome == "processed"
        assert second.outcome == "duplicate"
        assert calls == [1]
        assert len(sender.sent) == 1
        assert store.completed[7][0] == "processed"

    def test_concurrent_duplicate_claim_is_safe(self):
        store = FakeStore()
        results = []
        barrier = threading.Barrier(8)

        def worker():
            barrier.wait()
            results.append(store.claim_update(42, 111))

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(results) == [False] * 7 + [True]

    def test_failed_processing_has_deterministic_state(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)

        def _boom():
            raise RuntimeError("domain exploded")

        runners = Runners(fetch_predictions=_boom)
        with pytest.raises(TelegramError):
            run(process_update(
                store, sender,
                raw_body=make_update(update_id=9, text="/predictions"),
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid),
                runners=runners))
        assert store.completed[9] == ("failed", "handler_error")

    def test_parse_update_extracts_routing_fields(self):
        parsed = parse_update(json.loads(
            make_update(update_id=3, sender=44, chat=45,
                        text="/link ABC xyz", username="nick")))
        assert (parsed.update_id, parsed.telegram_user_id, parsed.chat_id,
                parsed.username) == (3, 44, 45, "nick")
        assert parsed.command == "/link" and parsed.args == ("ABC", "xyz")

    def test_bot_mention_suffix_stripped(self):
        parsed = parse_update({"update_id": 1,
                               "message": {"from": {"id": 1},
                                           "chat": {"id": 1},
                                           "text": "/start@FootyEdgeBot"}})
        assert parsed.command == "/start"


# --------------------------------------------------------------------------
# Linking.
# --------------------------------------------------------------------------

class TestLinking:
    def _token(self, store, user_id="user-1", ttl=900):
        code, digest = mint_link_token()
        store.store_link_token(
            digest, user_id,
            datetime.now(timezone.utc) + timedelta(seconds=ttl))
        return code, digest

    def test_valid_token_links(self):
        store, sender = FakeStore(), FakeSender()
        code, _digest = self._token(store)
        result = run(process_update(
            store, sender,
            raw_body=make_update(update_id=1, sender=111, text=f"/link {code}"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "processed"
        assert store.find_account(111)["user_id"] == "user-1"

    def test_token_stored_hashed_only(self):
        store, _sender = FakeStore(), FakeSender()
        code, digest = self._token(store)
        assert digest == hashlib.sha256(code.encode()).hexdigest()
        assert len(code) >= 32  # 192-bit entropy in urlsafe encoding
        for stored in store.tokens:
            assert code not in stored
        assert store.tokens[digest]["user_id"] == "user-1"

    def test_token_cannot_be_reused(self):
        store, sender = FakeStore(), FakeSender()
        code, _digest = self._token(store)
        first = make_update(update_id=1, sender=111, text=f"/link {code}")
        second = make_update(update_id=2, sender=111, text=f"/link {code}")
        run(process_update(store, sender, raw_body=first, secret_valid=True,
                           identity_fn=lambda uid: starter_identity(uid)))
        result = run(process_update(
            store, sender, raw_body=second, secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.completed[2] == ("ignored", "link_invalid")

    def test_expired_token_rejected(self):
        store, sender = FakeStore(), FakeSender()
        code, _digest = self._token(store, ttl=-1)
        result = run(process_update(
            store, sender,
            raw_body=make_update(update_id=1, sender=111, text=f"/link {code}"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"

    def test_malformed_token_rejected(self):
        store, sender = FakeStore(), FakeSender()
        result = run(process_update(
            store, sender, raw_body=make_update(update_id=1, sender=111,
                                                text="/link "),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.completed[1][1] in ("link_help", "link_malformed")

    def test_link_without_code_shows_help(self):
        store, sender = FakeStore(), FakeSender()
        result = run(process_update(
            store, sender, raw_body=make_update(update_id=1, text="/link"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert any("/link <code>" in text for _, text in sender.sent)

    def test_taken_telegram_mapping_refuses_without_hijack(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store, sender=111, user_id="user-B")
        code, _digest = self._token(store, user_id="user-A")
        result = run(process_update(
            store, sender,
            raw_body=make_update(update_id=1, sender=111, text=f"/link {code}"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "link_telegram_taken")
        # Attacker's sender still maps to user-B; user-A unbound; and the
        # refused link did NOT burn user-A's one-time code.
        assert store.find_account(111)["user_id"] == "user-B"
        assert store.find_account_by_user("user-A") is None
        assert store.tokens[_digest]["consumed"] is False

    def test_user_taken_refuses_second_device(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store, sender=111, user_id="user-1")
        code, _digest = self._token(store, user_id="user-1")
        result = run(process_update(
            store, sender,
            raw_body=make_update(update_id=2, sender=222, text=f"/link {code}"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.find_account(222) is None

    def test_idempotent_relink_same_mapping(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store, sender=111, user_id="user-1")
        code, _digest = self._token(store, user_id="user-1")
        result = run(process_update(
            store, sender,
            raw_body=make_update(update_id=3, sender=111, text=f"/link {code}"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "processed"
        assert store.find_account(111)["user_id"] == "user-1"

    def test_hash_lookup_is_deterministic(self):
        assert hash_link_token("abc") == hashlib.sha256(b"abc").hexdigest()
        assert hash_link_token("") is None
        assert hash_link_token(None) is None
        assert hash_link_token("x" * 300) is None


# --------------------------------------------------------------------------
# Identity.
# --------------------------------------------------------------------------

class TestIdentity:
    def test_username_cannot_substitute_for_identity(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store, sender=111, user_id="victim")
        # Attacker reuses the victim's username but has a fresh sender id.
        result = run(process_update(
            store, sender,
            raw_body=make_update(update_id=1, sender=999, username="victim",
                                 text="/status"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "unlinked")

    def test_unlinked_cannot_access_protected_commands(self):
        store, sender = FakeStore(), FakeSender()
        for command in ("/status", "/today", "/matches", "/predictions"):
            result = run(process_update(
                store, sender,
                raw_body=make_update(update_id=hash(command) % 10**6,
                                     text=command),
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid)))
            assert result.outcome == "ignored"

    def test_linked_resolves_exactly_one_user(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store, sender=111, user_id="user-9")
        seen = []
        run(process_update(
            store, sender, raw_body=make_update(text="/status"),
            secret_valid=True,
            identity_fn=lambda uid: seen.append(uid) or starter_identity(uid)))
        assert seen == ["user-9"]

    def test_identity_lookup_failure_is_safe(self):
        # 9.3D.3: missing identity must stay user-visible with a terminal
        # state (ignored/identity_missing), never a silent strand at
        # "received" and never a bare raise.
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/status"),
            secret_valid=True, identity_fn=lambda uid: None))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "identity_missing")
        assert len(sender.sent) == 1
        assert "Link your FootyEdge account first" in sender.sent[0][1]
        for secret in ("user-1", "auth.users", "Traceback", "SELECT"):
            assert secret not in sender.sent[0][1]

    def test_identity_missing_on_linked_start_is_answered(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/start"),
            secret_valid=True, identity_fn=lambda uid: None))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "identity_missing")
        assert len(sender.sent) == 1

    def test_corrupt_mapping_is_answered_without_leak(self):
        store, sender = FakeStore(), FakeSender()
        store.by_telegram[111] = {"user_id": 12345,  # non-string: corrupt
                                  "telegram_user_id": 111}
        result = run(process_update(
            store, sender, raw_body=make_update(text="/status"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "identity_missing")
        assert len(sender.sent) == 1

    def test_post_claim_telegram_error_reaches_terminal_state(self):
        # A TelegramError raised after a successful claim must still
        # complete the update (failed) instead of stranding "received".
        store, sender = FakeStore(), FakeSender()
        link_sender(store)

        def _raise(uid):
            raise TelegramError("boom")

        store.find_account = _raise  # type: ignore[method-assign]
        with pytest.raises(TelegramError):
            run(process_update(
                store, sender, raw_body=make_update(text="/status"),
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid)))
        assert store.completed[1] == ("failed", "handler_error")
        assert sender.sent == []

    def test_link_invalid_logs_digest_prefix_only(self, caplog):
        # 9.3D.4B: lookup failure logs event + update_id + 12-hex-char
        # presented-digest prefix; never the plaintext code or full hash.
        # User-facing behavior is unchanged.
        store, sender = FakeStore(), FakeSender()
        code = "fresh-code-AbCDrone-9_4"
        full = hashlib.sha256(code.encode("utf-8")).hexdigest()
        with caplog.at_level(logging.WARNING, logger="telegram_adapter"):
            result = run(process_update(
                store, sender,
                raw_body=make_update(text=f"/link {code}"),
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "link_invalid")
        assert len(sender.sent) == 1
        assert "expired, already used, or unknown" in sender.sent[0][1]
        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert "telegram_link_invalid" in joined
        assert full[:12] in joined
        assert code not in joined
        assert full not in joined


# --------------------------------------------------------------------------
# Entitlements.
# --------------------------------------------------------------------------

class TestEntitlements:
    def test_starter_commands_allowed(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        runners = Runners(fetch_today=lambda: [],
                          fetch_matches=lambda: [],
                          fetch_predictions=lambda: [])
        for command in ("/today", "/matches", "/predictions"):
            result = run(process_update(
                store, sender,
                raw_body=make_update(
                    update_id=abs(hash(command)) % 10**6, text=command),
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid),
                runners=runners))
            assert result.outcome == "processed", command

    def test_missing_capability_denied_without_execution(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        calls = []
        runners = Runners(
            fetch_predictions=lambda: calls.append(1) or [])
        result = run(process_update(
            store, sender, raw_body=make_update(text="/predictions"),
            secret_valid=True,
            identity_fn=lambda uid: TelegramIdentity(
                user_id=uid, plan="starter", capabilities=frozenset()),
            runners=runners))
        assert result.outcome == "ignored"
        assert store.completed[1] == ("ignored", "capability_denied")
        assert calls == []
        assert any("plan" in text for _, text in sender.sent)

    def test_no_growth_reachable_command_in_v1(self):
        allowed = {"match_intelligence", "predictions", None}
        assert set(ta.COMMAND_CAPABILITIES.values()) <= allowed

    def test_plan_never_read_from_message(self):
        source = (ROOT / "telegram_adapter.py").read_text()
        # Plan/identity flow only through the server-side identity object.
        assert "parsed.plan" not in source
        assert 'payload["plan"]' not in source
        assert "identity.plan" in source


# --------------------------------------------------------------------------
# Commands.
# --------------------------------------------------------------------------

class TestCommands:
    def _run(self, text, sender=111, linked=True, update_id=1):
        store, snd = FakeStore(), FakeSender()
        if linked:
            link_sender(store, sender=sender)
        result = run(process_update(
            store, snd,
            raw_body=make_update(update_id=update_id, sender=sender,
                                 text=text),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid),
            runners=Runners(
                fetch_today=lambda: [{"home_team": "A", "away_team": "B",
                                      "league": "X"}],
                fetch_matches=lambda: [{"home_team": "A", "away_team": "B"}],
                fetch_predictions=lambda: [{"home_team": "A", "away_team": "B",
                                            "best_bet_selection": "Home",
                                            "best_bet_odds": 2.0}])))
        return result, snd

    def test_start_unlinked(self):
        result, snd = self._run("/start", linked=False)
        assert result.outcome == "ignored"
        assert any("link" in text.lower() for _, text in snd.sent)

    def test_start_linked(self):
        result, snd = self._run("/start")
        assert result.outcome == "processed"
        assert any("Welcome back" in text for _, text in snd.sent)

    def test_help_lists_only_supported(self):
        result, snd = self._run("/help", linked=False)
        assert result.outcome == "processed"
        body = snd.sent[0][1]
        for command in ta.SUPPORTED_COMMANDS:
            assert command in body
        for command in ("/bet", "/payment", "/subscribe", "/admin"):
            assert command not in body

    def test_status_shows_plan(self):
        result, snd = self._run("/status")
        assert result.outcome == "processed"
        assert any("starter" in text for _, text in snd.sent)

    def test_today_matches_predictions(self):
        for command in ("/today", "/matches", "/predictions"):
            result, snd = self._run(command)
            assert result.outcome == "processed", command
            assert len(snd.sent) == 1

    def test_unknown_command_safe(self):
        result, snd = self._run("/frobnicate")
        assert result.outcome == "ignored"
        assert len(snd.sent) == 1

    def test_portfolio_rejected_exactly_as_before(self):
        # 9.3D.3 scope lock: /portfolio stays outside the V1 command set
        # with the exact unknown-command reply; no portfolio surface added.
        for linked in (True, False):
            result, snd = self._run("/portfolio", linked=linked)
            assert result.outcome == "ignored"
            assert snd.sent[0][1] == ("I don't recognize that command. "
                                       "Try /help for what I can do.")

    def test_deferred_command_safe(self):
        for command in ("/valuebets", "/acca", "/bet", "/admin"):
            result, snd = self._run(command)
            assert result.outcome == "ignored", command

    def test_plain_text_safe(self):
        result, _snd = self._run("hello there")
        assert result.outcome == "ignored"


# --------------------------------------------------------------------------
# Bet-route non-exposure regression.
# --------------------------------------------------------------------------

class TestBetNonExposure:
    def test_adapter_has_no_bet_data_access(self):
        source = (ROOT / "telegram_adapter.py").read_text()
        assert "user_bets" not in source
        assert "record_bet" not in source
        assert "get_user_bets" not in source

    def test_command_tables_exclude_bets_payments_admin(self):
        for command in ta.SUPPORTED_COMMANDS:
            lowered = command.lower()
            assert "bet" not in lowered
            assert "pay" not in lowered
            assert "subscrib" not in lowered
            assert "admin" not in lowered

    def test_runners_have_no_bet_capability(self):
        runners = Runners()
        assert not hasattr(runners, "fetch_bets")
        assert not hasattr(runners, "record_bet")
        assert not hasattr(runners, "fetch_portfolio")

    def test_bet_command_never_reaches_domain(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        calls = []
        runners = Runners(
            fetch_today=lambda: calls.append("today") or [],
            fetch_matches=lambda: calls.append("matches") or [],
            fetch_predictions=lambda: calls.append("predictions") or [])
        result = run(process_update(
            store, sender, raw_body=make_update(text="/bet Arsenal"),
            secret_valid=True,
            identity_fn=lambda uid: growth_identity(uid), runners=runners))
        assert result.outcome == "ignored"
        assert calls == []
        assert store.completed[1][0] == "ignored"


# --------------------------------------------------------------------------
# Formatter.
# --------------------------------------------------------------------------

class TestFormatter:
    def test_escape_markdown_v2(self):
        assert escape_markdown_v2("a_b*c[d]") == r"a\_b\*c\[d\]"

    def test_short_message_single_chunk(self):
        assert chunk_message("hello") == ["hello"]

    def test_long_message_chunked_within_limit(self):
        text = "\n".join(f"line-{i:04d}-" + "x" * 100 for i in range(100))
        chunks = chunk_message(text)
        assert len(chunks) > 1
        assert all(len(chunk) <= 4000 for chunk in chunks)
        assert "\n".join(chunks) == text

    def test_overlong_line_hard_split(self):
        chunks = chunk_message("y" * 9000)
        assert len(chunks) == 3
        assert all(len(chunk) <= 4000 for chunk in chunks)

    def test_format_status_linked_and_unlinked(self):
        assert "starter" in format_status("starter", True)
        assert "link" in format_status("starter", False).lower()

    def test_format_matches_and_predictions(self):
        assert "A vs B" in format_matches([{"home_team": "A",
                                           "away_team": "B"}])
        assert "No matches" in format_matches([])
        assert "A vs B" in format_predictions(
            [{"home_team": "A", "away_team": "B",
              "best_bet_selection": "Home", "best_bet_odds": 2.0}])
        assert "No predictions" in format_predictions([])

    def test_send_failure_recorded_deterministically(self):
        store, sender = FakeStore(), FakeSender(fail=True)
        link_sender(store)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/help"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid)))
        assert result.outcome == "processed"
        assert store.completed[1] == ("processed", "send_failed")
        assert sender.sent == []


# --------------------------------------------------------------------------
# Sender factory.
# --------------------------------------------------------------------------

class TestSenderFactory:
    def test_missing_token_fails_closed(self):
        with pytest.raises(TelegramError):
            ta.build_sender("")

    def test_unknown_transport_rejected(self):
        with pytest.raises(TelegramError):
            ta.build_sender("tok", transport="pigeon")

    def test_httpx_sender_constructible_offline(self):
        sender = ta.build_sender("tok", transport="httpx")
        assert isinstance(sender, ta.TelegramSender)

    def test_ptb_or_httpx_auto_selects(self):
        # PTB is not installed in this environment; auto must fall back.
        sender = ta.build_sender("tok", transport="auto")
        assert isinstance(sender, ta.TelegramSender)


# --------------------------------------------------------------------------
# HTTP boundary (FastAPI stubbed when unavailable, mirroring billing tests).
# --------------------------------------------------------------------------

def _load_telegram_api():
    try:
        import telegram_api  # noqa: F401
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

        import telegram_api  # noqa: F401
    return sys.modules["telegram_api"]


class _Cells(dict):
    """Minimal supabase-py query-builder fake for store tests."""

    def __init__(self, tables):
        super().__init__()
        self._tables = tables
        self._table = None
        self._op = None
        self._payload = None
        self._filters = []

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
                if kind in ("gt", "lt"):
                    if current is None:
                        return False
                    if kind == "gt" and not str(current) > str(value):
                        return False
                    if kind == "lt" and not str(current) < str(value):
                        return False
            return True

        return [row for row in rows if keep(row)]

    def execute(self):
        if self._op[0] == "insert":
            table = self._tables.setdefault(self._table, [])
            _enforce_uniques(self._table, table, self._op[1])
            table.append(dict(self._op[1]))
            return types.SimpleNamespace(data=[dict(self._op[1])])
        if self._op[0] == "select":
            return types.SimpleNamespace(
                data=[dict(row) for row in self._rows()])
        if self._op[0] == "update":
            matched = self._rows()
            for row in matched:
                row.update(self._op[1])
            return types.SimpleNamespace(data=[dict(row) for row in matched])
        raise AssertionError("unsupported op")


_UNIQUE_KEYS = {
    "telegram_updates": [["telegram_update_id"]],
    "telegram_accounts": [["telegram_user_id"], ["user_id"]],
    "telegram_link_tokens": [["token_hash"]],
}


def _enforce_uniques(table, rows, payload):
    for keys in _UNIQUE_KEYS.get(table, []):
        for row in rows:
            if all(str(row.get(key)) == str(payload.get(key))
                   for key in keys):
                raise Exception(
                    "duplicate key value violates unique constraint (23505)")


class FakeRequest:
    def __init__(self, body, headers=None):
        self._body = body
        self.headers = headers or {}

    async def body(self):
        return self._body


@pytest.fixture(scope="module")
def api_module():
    return _load_telegram_api()


class TestWebhookEndpoint:
    def _api(self, monkeypatch, secret="whsec", token="bottok"):
        module = _load_telegram_api()
        monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", secret)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
        tables: dict = {}
        fake = _Cells(tables)

        class _ApiStub:
            @staticmethod
            def get_supabase_client():
                return fake

        monkeypatch.setitem(sys.modules, "api", _ApiStub())
        sender = FakeSender()
        monkeypatch.setattr(module, "build_sender", lambda _tok: sender)
        module.telegram_identity = lambda _db, uid: starter_identity(uid)
        return module, sender, tables

    def test_valid_secret_processes(self, api_module, monkeypatch):
        module, sender, _tables = self._api(monkeypatch)
        request = FakeRequest(make_update(update_id=1, text="/help"),
                              {"x-telegram-bot-api-secret-token": "whsec"})
        result = run(module.telegram_webhook(request))
        assert result == {"status": "processed"}
        assert len(sender.sent) == 1

    def test_missing_secret_rejected_without_state(self, api_module,
                                                   monkeypatch):
        module, sender, tables = self._api(monkeypatch)
        request = FakeRequest(make_update(), {})
        with pytest.raises(Exception) as exc:
            run(module.telegram_webhook(request))
        assert getattr(exc.value, "status_code", None) == 401
        assert tables.get("telegram_updates", []) == []
        assert sender.sent == []

    def test_invalid_secret_rejected(self, api_module, monkeypatch):
        module, _sender, _tables = self._api(monkeypatch)
        request = FakeRequest(make_update(),
                              {"x-telegram-bot-api-secret-token": "nope"})
        with pytest.raises(Exception) as exc:
            run(module.telegram_webhook(request))
        assert getattr(exc.value, "status_code", None) == 401

    def test_malformed_body_rejected(self, api_module, monkeypatch):
        module, _sender, _tables = self._api(monkeypatch)
        request = FakeRequest(b"{{{",
                              {"x-telegram-bot-api-secret-token": "whsec"})
        with pytest.raises(Exception) as exc:
            run(module.telegram_webhook(request))
        assert getattr(exc.value, "status_code", None) == 400

    def test_missing_bot_token_fails_closed(self, api_module, monkeypatch):
        module, sender, tables = self._api(monkeypatch, token="")
        request = FakeRequest(make_update(),
                              {"x-telegram-bot-api-secret-token": "whsec"})
        with pytest.raises(Exception) as exc:
            run(module.telegram_webhook(request))
        assert getattr(exc.value, "status_code", None) == 503
        assert tables.get("telegram_updates", []) == []

    def test_duplicate_delivery_single_send(self, api_module, monkeypatch):
        module, sender, _tables = self._api(monkeypatch)
        headers = {"x-telegram-bot-api-secret-token": "whsec"}
        body = make_update(update_id=11, text="/help")
        first = run(module.telegram_webhook(FakeRequest(body, headers)))
        second = run(module.telegram_webhook(FakeRequest(body, headers)))
        assert (first, second) == ({"status": "processed"},
                                   {"status": "duplicate"})
        assert len(sender.sent) == 1

    def test_link_token_route_mints_hash_only(self, api_module, monkeypatch):
        module, _sender, tables = self._api(monkeypatch)
        import billing_api
        monkeypatch.setattr(billing_api, "_supabase_auth_user",
                            lambda _auth: ("user-7", "a@b.c"))
        result = run(module.mint_link_token_route("Bearer jwt"))
        assert "code" in result and result["expires_in_seconds"] == 900
        rows = tables.get("telegram_link_tokens", [])
        assert len(rows) == 1
        assert rows[0]["token_hash"] == hashlib.sha256(
            result["code"].encode()).hexdigest()
        assert result["code"] not in json.dumps(rows)
        assert rows[0]["user_id"] == "user-7"

    def test_link_token_route_rejects_unauthenticated(self, api_module,
                                                      monkeypatch):
        module, _sender, _tables = self._api(monkeypatch)
        import billing_api

        def _deny(_auth):
            raise billing_api.HTTPException(status_code=401,
                                            detail="Authentication required")

        monkeypatch.setattr(billing_api, "_supabase_auth_user", _deny)
        with pytest.raises(Exception) as exc:
            run(module.mint_link_token_route(None))
        assert getattr(exc.value, "status_code", None) == 401


class TestStoreContract:
    def _store(self):
        return {"telegram_updates": [], "telegram_accounts": [],
                "telegram_link_tokens": []}

    def test_supabase_claim_and_duplicate(self, api_module):
        store = api_module.SupabaseTelegramStore(_Cells(self._store()))
        assert store.claim_update(1, 111) is True
        assert store.claim_update(1, 111) is False

    def test_supabase_consume_atomic(self, api_module):
        tables = self._store()
        store = api_module.SupabaseTelegramStore(_Cells(tables))
        now = datetime.now(timezone.utc)
        store.store_link_token("h", "user-1", now + timedelta(seconds=60))
        assert store.consume_link_token("h", now) == "user-1"
        assert store.consume_link_token("h", now) is None

    def test_supabase_consume_rejects_expired(self, api_module):
        tables = self._store()
        store = api_module.SupabaseTelegramStore(_Cells(tables))
        now = datetime.now(timezone.utc)
        store.store_link_token("h", "user-1", now - timedelta(seconds=1))
        assert store.consume_link_token("h", now) is None

    def test_supabase_link_conflicts(self, api_module):
        tables = self._store()
        store = api_module.SupabaseTelegramStore(_Cells(tables))
        assert store.link_account("u1", 111, 111, None) == "linked"
        assert store.link_account("u1", 111, 111, None) == "linked"
        assert store.link_account("u2", 111, 111, None) == "telegram_taken"
        assert store.link_account("u1", 222, 222, None) == "user_taken"


class TestSourceContracts:
    @staticmethod
    def _top_imports(name):
        import ast
        tree = ast.parse((ROOT / name).read_text())
        found = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        return found

    def test_no_fastapi_import_in_core(self):
        assert "fastapi" not in self._top_imports("telegram_adapter.py")

    def test_no_ptb_import_at_module_load(self):
        # PTB is used only as a lazily constructed Bot API client (see
        # build_sender); importing it at module load would couple tests
        # and startup to an optional dependency.
        assert "telegram" not in self._top_imports("telegram_adapter.py")

    def test_no_competing_webhook_server(self):
        # No PTB server primitives may be *used*; mentioning the forbidden
        # pattern in a prohibition comment/docstring is allowed.
        for name in ("telegram_adapter.py", "telegram_api.py"):
            source = (ROOT / name).read_text()
            assert "run_webhook(" not in source
            assert "ApplicationBuilder" not in source
            assert "Updater(" not in source

    def test_router_registered_in_api(self):
        source = (ROOT / "api.py").read_text()
        assert "telegram_api" in source
        assert "telegram_router" in source

    def test_webhook_route_path(self):
        source = (ROOT / "telegram_api.py").read_text()
        assert "/api/webhooks/telegram" in source
        assert "/api/telegram/link-token" in source


# --------------------------------------------------------------------------
# Objective 9.2: application-integration reconciliation.
# --------------------------------------------------------------------------

NESTED_PAYLOAD = {
    "response": [
        {"fixture": {"id": "m1", "date": "2026-10-06T19:00:00Z"},
         "teams": {"home": {"name": "Arsenal", "id": None, "logo": None},
                   "away": {"name": "Chelsea", "id": None, "logo": None}},
         "league": {"name": "Premier League", "id": "soccer_epl"},
         "goals": {"home": None, "away": None},
         "status": {"long": "Upcoming"},
         "live_odds": {}},
        {"fixture": {"id": "m2", "date": "2026-10-06T21:00:00Z"},
         "teams": {"home": {"name": "Real Madrid", "id": None},
                   "away": {"name": "Barcelona", "id": None}},
         "league": {"name": "La Liga", "id": "soccer_spain"},
         "goals": {"home": None, "away": None},
         "status": {"long": "Upcoming"}},
    ]
}


def _normalize():
    return _load_telegram_api().normalize_provider_matches


class TestAsyncRunnerSupport:
    def test_async_fetcher_is_awaited(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        calls = []

        async def _async_fetch():
            calls.append(1)
            return [{"home_team": "A", "away_team": "B"}]

        runners = Runners(fetch_predictions=_async_fetch)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/predictions"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid), runners=runners))
        assert result.outcome == "processed"
        assert calls == [1]
        assert any("A vs B" in text for _, text in sender.sent)

    def test_sync_fetcher_still_supported(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        runners = Runners(fetch_predictions=lambda: [
            {"home_team": "A", "away_team": "B"}])
        result = run(process_update(
            store, sender, raw_body=make_update(text="/predictions"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid), runners=runners))
        assert result.outcome == "processed"


class TestProviderNormalization:
    def test_nested_shape_normalized(self):
        rows = _normalize()(NESTED_PAYLOAD)
        assert rows == [
            {"home_team": "Arsenal", "away_team": "Chelsea",
             "league": "Premier League", "kickoff": "2026-10-06T19:00:00Z"},
            {"home_team": "Real Madrid", "away_team": "Barcelona",
             "league": "La Liga", "kickoff": "2026-10-06T21:00:00Z"},
        ]

    def test_empty_response_yields_empty(self):
        assert _normalize()({"response": []}) == []

    def test_malformed_shapes_yield_empty(self):
        assert _normalize()(None) == []
        assert _normalize()([]) == []
        assert _normalize()({}) == []
        assert _normalize()({"response": None}) == []
        assert _normalize()({"response": [None, "junk", 42]}) == []

    def test_missing_keys_yield_none_teams(self):
        assert _normalize()({"response": [{}]}) == [
            {"home_team": None, "away_team": None,
             "league": "", "kickoff": ""}]

    def test_no_invented_data(self):
        rows = _normalize()(NESTED_PAYLOAD)
        text = format_matches(rows)
        assert "Arsenal vs Chelsea" in text
        assert "Real Madrid vs Barcelona" in text


class TestTodayEndToEnd:
    def test_today_uses_normalized_provider_source(self):
        # Fixtures are dated to the current UTC day: /today only keeps
        # kickoffs on today's date (regression: future fixtures must not
        # appear). The date is computed at runtime so this never goes stale.
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {"response": [
            {"fixture": {"id": "m1", "date": f"{today}T19:00:00Z"},
             "teams": {"home": {"name": "Arsenal", "id": None, "logo": None},
                       "away": {"name": "Chelsea", "id": None}},
             "league": {"name": "Premier League", "id": "soccer_epl"},
             "goals": {"home": None, "away": None},
             "status": {"long": "Upcoming"}},
        ]}
        store, sender = FakeStore(), FakeSender()
        link_sender(store)

        async def _provider_fetch():
            return _normalize()(payload)

        runners = Runners(fetch_today=_provider_fetch)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/today"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid), runners=runners))
        assert result.outcome == "processed"
        assert any("Arsenal vs Chelsea" in text for _, text in sender.sent)

    def test_today_empty_source_safe(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        runners = Runners(fetch_today=lambda: [])
        result = run(process_update(
            store, sender, raw_body=make_update(text="/today"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid), runners=runners))
        assert result.outcome == "processed"
        assert any("No matches" in text for _, text in sender.sent)

    def test_today_fetcher_failure_is_failed_outcome(self):
        store, sender = FakeStore(), FakeSender()
        link_sender(store)

        def _boom():
            raise RuntimeError("provider down")

        runners = Runners(fetch_today=_boom)
        with pytest.raises(TelegramError):
            run(process_update(
                store, sender, raw_body=make_update(text="/today"),
                secret_valid=True,
                identity_fn=lambda uid: starter_identity(uid),
                runners=runners))
        assert store.completed[1] == ("failed", "handler_error")


# --------------------------------------------------------------------------
# Objective 9.3D.9: Telegram match-date semantics.
# --------------------------------------------------------------------------

class TestTodayDateFiltering:
    @staticmethod
    def _window():
        def row(home, away, kickoff):
            return {"home_team": home, "away_team": away,
                    "league": "EPL", "kickoff": kickoff}

        return [
            row("A", "B", "2026-10-07T11:30:00Z"),
            row("C", "D", "2026-10-07T12:00:00+02:00"),
            row("E", "F", "2026-10-08T00:30:00+02:00"),
            row("G", "H", "2026-10-10T14:00:00Z"),
            row("I", "J", "2026-10-11T14:00:00Z"),
            row("K", "L", "2026-10-07T00:30:00+02:00"),
            row("M", "N", ""),
            row("O", "P", "not-a-date"),
            row("Q", "R", None),
            row("S", "T", "2026-10-07T12:00:00"),
        ]

    def test_today_keeps_only_requested_utc_date(self):
        kept = ta.filter_matches_by_utc_date(self._window(), "2026-10-07")
        assert [(m["home_team"], m["away_team"]) for m in kept] == [
            ("A", "B"), ("C", "D"), ("E", "F"), ("S", "T")]

    def test_no_match_day_yields_empty(self):
        future_only = [m for m in self._window()
                       if m["home_team"] in ("G", "H", "I", "J")]
        assert ta.filter_matches_by_utc_date(future_only, "2026-10-07") == []
        assert format_matches([], heading="Today's matches:") == \
            "No matches scheduled for today."

    def test_matches_heading_truthful(self):
        text = format_matches(
            [{"home_team": "G", "away_team": "H", "league": "EPL",
              "kickoff": "2026-10-10T14:00:00Z"}],
            heading="Upcoming matches:")
        assert text.startswith("Upcoming matches:")
        assert "Today's matches:" not in text

    def test_non_list_input_yields_empty(self):
        assert ta.filter_matches_by_utc_date(None, "2026-10-07") == []
        assert ta.filter_matches_by_utc_date("junk", "2026-10-07") == []

    def test_today_matches_distinction_same_fixture_set(self):
        # Dates are derived from the runtime UTC day so the test can never
        # go stale, yet never depends on which calendar day it is.
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        rows = [
            {"home_team": "Home", "away_team": "Way", "league": "EPL",
             "kickoff": f"{today}T12:00:00Z"},
            {"home_team": "Future", "away_team": "Club", "league": "EPL",
             "kickoff": f"{tomorrow}T12:00:00Z"},
        ]

        store, sender = FakeStore(), FakeSender()
        link_sender(store)
        result = run(process_update(
            store, sender, raw_body=make_update(text="/today"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid),
            runners=Runners(fetch_today=lambda: rows,
                            fetch_matches=lambda: rows)))
        assert result.outcome == "processed"
        body = sender.sent[0][1]
        assert "Home vs Way" in body
        assert "Future vs Club" not in body
        assert "Today's matches:" in body

        store2, sender2 = FakeStore(), FakeSender()
        link_sender(store2)
        result2 = run(process_update(
            store2, sender2, raw_body=make_update(text="/matches"),
            secret_valid=True,
            identity_fn=lambda uid: starter_identity(uid),
            runners=Runners(fetch_today=lambda: rows,
                            fetch_matches=lambda: rows)))
        assert result2.outcome == "processed"
        body2 = sender2.sent[0][1]
        assert "Home vs Way" in body2
        assert "Future vs Club" in body2
        assert body2.startswith("Upcoming matches:")
        assert "Today's matches:" not in body2
