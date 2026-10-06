"""Objective 8E: Paystack webhook verification, idempotency, correlation
and conservative subscription-state synchronization.

Offline only. No network, no real credentials, no live provider calls.

The fake store below mirrors the semantics of the production boundary
(public.apply_paystack_event): the idempotency claim, the subscription
update and the event completion are ONE atomic step, and a duplicate
(provider, provider_event_id) writes nothing at all.
"""

import hashlib
import hmac
import json
import re
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / (
    "20261001010000_subscription_events_and_webhook_state.sql")
ORDERING_MIGRATION = ROOT / "supabase" / "migrations" / (
    "20261002000000_webhook_ordering_guard.sql")
REFERENCE_MIGRATION = ROOT / "supabase" / "migrations" / (
    "20261002010000_subscription_checkout_reference.sql")
SINGLE_SIG_MIGRATION = ROOT / "supabase" / "migrations" / (
    "20261002020000_apply_paystack_event_single_signature.sql")
SUBSCRIPTIONS_MIGRATION = ROOT / "supabase" / "migrations" / (
    "20261001000000_subscriptions_and_rls.sql")

sys.path.insert(0, str(ROOT))

from subscription_service import (  # noqa: E402
    INVOICE_PAID_STATUSES,
    SUPPORTED_EVENTS,
    ApplyResult,
    SubscriptionStore,
    SubscriptionUpdate,
    UPDATABLE_COLUMNS,
    WebhookError,
    build_update,
    decide_transition,
    extract_refs,
    parse_dt,
    paystack_event_identity,
    process_paystack_event,
    verify_paystack_signature,
)

FAKE_SECRET = "test_only_secret_not_a_real_key"
NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def sign(body: bytes, secret: str = FAKE_SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()


def body_for(payload: dict) -> bytes:
    return json.dumps(payload).encode()


def delivery(payload: dict, secret: str = FAKE_SECRET) -> bytes:
    return body_for(payload)


def sub_row(**over):
    row = {
        "id": 7,
        "status": "canceled",
        "provider": "paystack",
        "provider_customer_id": None,
        "provider_subscription_id": None,
        "current_period_start": None,
        "current_period_end": None,
    }
    row.update(over)
    return row


def create_event(subscription_code="SUB_x", customer_code="CUS_x", **data):
    payload = {
        "event": "subscription.create",
        "data": {
            "subscription_code": subscription_code,
            "customer": {"customer_code": customer_code},
        },
    }
    payload["data"].update(data)
    return payload


def invoice_event(event="invoice.payment_failed", status="failed", code="SUB_x"):
    return {
        "event": event,
        "data": {
            "status": status,
            "amount": 500000,
            "subscription": {"subscription_code": code},
        },
    }


class FakeStore(SubscriptionStore):
    """In-memory twin of public.apply_paystack_event (8.3 extended form).

    Mirrors the production boundary: idempotency claim, conditional
    subscription update, event completion in ONE atomic step; duplicate
    (provider, provider_event_id) writes nothing; a provably stale event
    (both stored marker and incoming timestamp known, incoming older) is
    recorded as ignored/stale_event without touching the subscription.
    """

    def __init__(self, rows=None, fail_on_apply=False, fail_on_lookup=False):
        self.rows = [dict(r) for r in (rows or [])]
        self.events = {}
        self.applies = []
        self.lookups = []
        self.fail_on_apply = fail_on_apply
        self.fail_on_lookup = fail_on_lookup
        self._next_id = 1

    def _find(self, column, code):
        if self.fail_on_lookup:
            raise RuntimeError("lookup unavailable")
        self.lookups.append((column, code))
        for row in self.rows:
            if row.get("provider") == "paystack" and row.get(column) == code:
                return dict(row)
        return None

    def find_by_provider_subscription(self, provider, code):
        return self._find("provider_subscription_id", code)

    def find_by_provider_customer(self, provider, code):
        return self._find("provider_customer_id", code)

    def apply_event(self, *, provider, provider_event_id, event_type, payload,
                    subscription_id=None, processing_status="processed",
                    error_code=None, update=None,
                    provider_occurred_at=None, provider_sequence=None):
        from subscription_service import parse_dt as _parse_dt
        self.applies.append({
            "provider": provider, "provider_event_id": provider_event_id,
            "event_type": event_type, "subscription_id": subscription_id,
            "processing_status": processing_status, "error_code": error_code,
            "update": update,
            "provider_occurred_at": provider_occurred_at,
            "provider_sequence": provider_sequence,
        })
        if self.fail_on_apply:
            # Emulates the SQL transaction aborting: nothing is committed.
            raise RuntimeError("apply_paystack_event failed")
        key = (provider, provider_event_id)
        if key in self.events:
            return ApplyResult(event_id=self.events[key]["id"], inserted=False)
        event_id = self._next_id
        self._next_id += 1
        self.events[key] = {
            "id": event_id, "event_type": event_type,
            "processing_status": processing_status, "error_code": error_code,
            "subscription_id": subscription_id,
            "provider_occurred_at": provider_occurred_at,
        }
        if update is not None and not update.is_empty() and subscription_id is not None:
            for row in self.rows:
                if row.get("id") == subscription_id and row.get("provider") == provider:
                    # Twin of the SQL stale-event guard (NULL-tolerant).
                    incoming = _parse_dt(provider_occurred_at) \
                        if provider_occurred_at else None
                    stored = _parse_dt(row.get("last_applied_occurred_at"))
                    if incoming is not None and stored is not None \
                            and incoming < stored:
                        self.events[key]["processing_status"] = "ignored"
                        self.events[key]["error_code"] = "stale_event"
                        break
                    if update.new_status is not None:
                        row["status"] = update.new_status
                    for column in ("provider", "provider_customer_id",
                                   "provider_subscription_id",
                                   "current_period_start", "current_period_end"):
                        value = getattr(update, column)
                        if value is not None:
                            row[column] = value
                    if incoming is not None:
                        marker = stored if stored is not None and stored > incoming \
                            else incoming
                        row["last_applied_occurred_at"] = marker.isoformat()
        return ApplyResult(event_id=event_id, inserted=True)

    def status_of(self, row_id):
        return next(r["status"] for r in self.rows if r["id"] == row_id)


# ==========================================================================
# Signature verification
# ==========================================================================

class TestSignatureVerification:
    def test_valid_signature_accepted(self):
        body = delivery(create_event())
        assert verify_paystack_signature(body, sign(body), FAKE_SECRET) is True

    def test_tampered_body_rejected(self):
        body = delivery(create_event())
        tampered = body.replace(b"SUB_x", b"SUB_y")
        assert verify_paystack_signature(tampered, sign(body), FAKE_SECRET) is False

    def test_wrong_secret_rejected(self):
        body = delivery(create_event())
        assert verify_paystack_signature(body, sign(body, "other"), FAKE_SECRET) is False

    def test_missing_signature_rejected(self):
        body = delivery(create_event())
        assert verify_paystack_signature(body, None, FAKE_SECRET) is False
        assert verify_paystack_signature(body, "", FAKE_SECRET) is False

    def test_empty_body_rejected(self):
        assert verify_paystack_signature(b"", sign(b""), FAKE_SECRET) is False

    def test_missing_secret_fails_closed(self):
        body = delivery(create_event())
        assert verify_paystack_signature(body, sign(body), "") is False
        assert verify_paystack_signature(body, sign(body), None) is False

    def test_truncated_or_padded_signature_rejected(self):
        body = delivery(create_event())
        signature = sign(body)
        assert verify_paystack_signature(body, signature[:-1], FAKE_SECRET) is False
        assert verify_paystack_signature(body, signature + "0", FAKE_SECRET) is False

    def test_uppercase_signature_rejected(self):
        body = delivery(create_event())
        assert verify_paystack_signature(body, sign(body).upper(), FAKE_SECRET) is False

    def test_non_string_signature_rejected(self):
        body = delivery(create_event())
        assert verify_paystack_signature(body, b"x" * 128, FAKE_SECRET) is False

    def test_str_body_is_encoded_before_signing(self):
        text = json.dumps(create_event())
        assert verify_paystack_signature(text, sign(text.encode()), FAKE_SECRET) is True


# ==========================================================================
# Provider event identity
# ==========================================================================

class TestEventIdentity:
    def test_deterministic_for_identical_bytes(self):
        body = delivery(create_event())
        assert paystack_event_identity(body) == paystack_event_identity(body)

    def test_prefixed_sha256_hex(self):
        identity = paystack_event_identity(b"{}")
        assert identity.startswith("evt_")
        assert re.fullmatch(r"evt_[0-9a-f]{64}", identity)

    def test_distinct_deliveries_get_distinct_ids(self):
        a = paystack_event_identity(delivery(create_event()))
        b = paystack_event_identity(delivery(create_event(next_payment_date="2026-11-01T00:00:00Z")))
        assert a != b

    def test_equals_sha256_of_raw_bytes(self):
        body = b'{"event":"charge.success"}'
        assert paystack_event_identity(body) == (
            "evt_" + hashlib.sha256(body).hexdigest())

    def test_accepts_str_body(self):
        assert paystack_event_identity("{}") == paystack_event_identity(b"{}")


# ==========================================================================
# Correlation reference extraction (email is never a key)
# ==========================================================================

class TestReferenceExtraction:
    def test_subscription_create_shape(self):
        code, customer = extract_refs(create_event())
        assert (code, customer) == ("SUB_x", "CUS_x")

    def test_invoice_nested_subscription_shape(self):
        code, customer = extract_refs(invoice_event())
        assert code == "SUB_x"
        assert customer is None

    def test_missing_refs(self):
        assert extract_refs({"event": "charge.success", "data": {}}) == (None, None)

    def test_non_dict_data_tolerated(self):
        assert extract_refs({"event": "invoice.update", "data": "nope"}) == (None, None)

    def test_numeric_codes_coerced_to_str(self):
        code, _ = extract_refs({"data": {"subscription_code": 12345}})
        assert code == "12345"

    def test_email_is_never_returned_as_a_reference(self):
        _code, customer = extract_refs({
            "data": {"email": "user@example.com", "customer": {}}})
        assert customer is None


# ==========================================================================
# Pure state machine
# ==========================================================================

class TestStateMachine:
    def test_create_activates_and_binds_provider_identity(self):
        decision = decide_transition(
            "canceled", "subscription.create",
            {"subscription_code": "SUB_x", "customer": {"customer_code": "CUS_x"},
             "next_payment_date": "2026-11-01T00:00:00Z"}, now=NOW)
        assert decision.status == "active"
        assert decision.fields["provider"] == "paystack"
        assert decision.fields["provider_subscription_id"] == "SUB_x"
        assert decision.fields["provider_customer_id"] == "CUS_x"
        assert decision.fields["current_period_end"] == "2026-11-01T00:00:00+00:00"

    def test_create_without_payment_date_omits_period(self):
        decision = decide_transition(
            "canceled", "subscription.create", {"subscription_code": "SUB_x"}, now=NOW)
        assert "current_period_end" not in decision.fields

    def test_payment_failure_marks_past_due_from_active(self):
        assert decide_transition("active", "invoice.payment_failed", {},
                                 now=NOW).status == "past_due"

    def test_payment_failure_never_escalates_canceled(self):
        assert decide_transition("canceled", "invoice.payment_failed", {},
                                 now=NOW).outcome == "ignored"

    def test_payment_failure_never_escalates_expired(self):
        assert decide_transition("expired", "invoice.payment_failed", {},
                                 now=NOW).outcome == "ignored"

    def test_paid_invoice_restores_active_from_past_due(self):
        decision = decide_transition("past_due", "invoice.update",
                                     {"status": "success"}, now=NOW)
        assert decision.status == "active"

    def test_paid_invoice_from_active_is_a_no_op(self):
        decision = decide_transition("active", "invoice.update",
                                     {"status": "paid"}, now=NOW)
        assert decision.status is None and decision.outcome == "processed"

    def test_unpaid_invoice_update_is_ignored(self):
        assert decide_transition("active", "invoice.update", {"status": "failed"},
                                 now=NOW).outcome == "ignored"

    @pytest.mark.parametrize("paid", INVOICE_PAID_STATUSES)
    def test_all_authoritative_paid_statuses(self, paid):
        assert decide_transition("past_due", "invoice.update", {"status": paid},
                                 now=NOW).status == "active"

    def test_not_renew_preserves_access(self):
        decision = decide_transition("active", "subscription.not_renew", {}, now=NOW)
        assert decision.status is None and decision.outcome == "processed"

    def test_disable_preserves_a_future_paid_period(self):
        future = (NOW + timedelta(days=5)).isoformat()
        decision = decide_transition("active", "subscription.disable", {}, now=NOW,
                                     stored_period_end=future)
        assert decision.status is None and decision.outcome == "processed"

    def test_disable_cancels_after_the_paid_period(self):
        past = (NOW - timedelta(days=1)).isoformat()
        decision = decide_transition("active", "subscription.disable", {}, now=NOW,
                                     stored_period_end=past)
        assert decision.status == "canceled"

    def test_disable_cancels_with_no_known_period(self):
        assert decide_transition("active", "subscription.disable", {},
                                 now=NOW).status == "canceled"

    def test_expiring_cards_never_revokes(self):
        decision = decide_transition("active", "subscription.expiring_cards", {},
                                     now=NOW)
        assert decision.status is None and decision.outcome == "processed"

    def test_charge_success_alone_never_changes_state(self):
        decision = decide_transition("canceled", "charge.success", {}, now=NOW)
        assert decision.status is None and decision.outcome == "processed"

    def test_unknown_event_is_ignored(self):
        assert decide_transition("active", "refund.processed", {}, now=NOW).outcome == "ignored"

    def test_unparseable_date_is_tolerated(self):
        decision = decide_transition(
            "canceled", "subscription.create",
            {"subscription_code": "SUB_x", "next_payment_date": "not-a-date"}, now=NOW)
        assert decision.status == "active"
        assert "current_period_end" not in decision.fields

    def test_every_supported_event_has_an_explicit_decision(self):
        for event in SUPPORTED_EVENTS:
            decision = decide_transition("active", event, {}, now=NOW)
            assert decision.outcome in ("processed", "ignored")


# ==========================================================================
# Write-surface whitelist
# ==========================================================================

class TestUpdateWhitelist:
    def test_only_whitelisted_columns_reach_the_store(self):
        update = build_update({"status": "active", "user_id": 99, "role": "owner",
                               "id": 1, "created_at": "2020-01-01"})
        assert update.new_status == "active"
        assert not hasattr(update, "user_id")
        assert not hasattr(update, "role")

    def test_whitelist_excludes_identity_and_ownership_columns(self):
        forbidden = {"id", "user_id", "role", "created_at", "updated_at", "plan"}
        assert not (set(UPDATABLE_COLUMNS) & forbidden)

    def test_empty_update_is_detected(self):
        assert build_update({}).is_empty() is True
        assert build_update({"status": "active"}).is_empty() is False


# ==========================================================================
# Orchestration: idempotency, correlation, atomicity
# ==========================================================================

class TestOrchestration:
    def test_correlated_create_activates_subscription(self):
        store = FakeStore([sub_row(provider_customer_id="CUS_x")])
        result = process_paystack_event(store, raw_body=delivery(create_event()),
                                        now=lambda: NOW)
        assert result.outcome == "processed"
        assert result.subscription_id == 7
        assert store.status_of(7) == "active"
        assert len(store.events) == 1

    def test_correlation_prefers_subscription_code(self):
        store = FakeStore([sub_row(id=1, provider_subscription_id="SUB_x"),
                           sub_row(id=2, provider_customer_id="CUS_x")])
        result = process_paystack_event(store, raw_body=delivery(create_event()),
                                        now=lambda: NOW)
        assert result.subscription_id == 1

    def test_duplicate_delivery_mutates_nothing(self):
        store = FakeStore([sub_row(id=1, provider_subscription_id="SUB_x")])
        raw = delivery(create_event())
        first = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        second = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert first.outcome == "processed"
        assert second.outcome == "duplicate"
        assert len(store.events) == 1
        assert len(store.applies) == 2

    def test_duplicate_of_an_ignored_event_stays_ignored(self):
        store = FakeStore([])
        raw = delivery(create_event())
        assert process_paystack_event(store, raw_body=raw, now=lambda: NOW).outcome == "ignored"
        assert process_paystack_event(store, raw_body=raw, now=lambda: NOW).outcome == "duplicate"
        assert len(store.events) == 1

    def test_uncorrelated_event_creates_nothing(self):
        store = FakeStore([])
        result = process_paystack_event(store, raw_body=delivery(create_event()),
                                        now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.rows == []
        assert store.events[("paystack", paystack_event_identity(
            delivery(create_event())))]["error_code"] == "uncorrelated"

    def test_unknown_event_is_recorded_not_applied(self):
        store = FakeStore([sub_row(id=1, provider_subscription_id="SUB_x")])
        raw = delivery({"event": "refund.processed",
                        "data": {"subscription": {"subscription_code": "SUB_x"}}})
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.status_of(1) == "canceled"
        assert list(store.events.values())[0]["error_code"] == "unknown_event"

    def test_event_row_links_the_correlated_subscription(self):
        store = FakeStore([sub_row(id=3, provider_subscription_id="SUB_x")])
        process_paystack_event(store, raw_body=delivery(create_event()),
                               now=lambda: NOW)
        assert list(store.events.values())[0]["subscription_id"] == 3

    def test_invoice_events_do_not_correlate_by_customer_code(self):
        store = FakeStore([sub_row(id=1, provider_customer_id="CUS_x")])
        raw = delivery({"event": "invoice.payment_failed",
                        "data": {"status": "failed",
                                 "customer": {"customer_code": "CUS_x"}}})
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.status_of(1) == "canceled"
        assert ("provider_customer_id", "CUS_x") not in store.lookups

    def test_invoice_event_correlates_by_nested_subscription_code(self):
        store = FakeStore([sub_row(id=1, status="active", provider_subscription_id="SUB_x")])
        raw = delivery(invoice_event("invoice.payment_failed"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.status == "past_due"
        assert store.status_of(1) == "past_due"

    def test_paid_invoice_after_failure_restores_access(self):
        store = FakeStore([sub_row(id=1, status="past_due", provider_subscription_id="SUB_x")])
        raw = delivery(invoice_event("invoice.update", status="success"))
        process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert store.status_of(1) == "active"

    def test_period_end_is_preserved_when_the_event_omits_it(self):
        end = (NOW + timedelta(days=9)).isoformat()
        store = FakeStore([sub_row(id=1, status="active",
                                   provider_subscription_id="SUB_x",
                                   current_period_end=end)])
        process_paystack_event(store, raw_body=delivery(invoice_event("invoice.payment_failed")),
                               now=lambda: NOW)
        assert store.rows[0]["current_period_end"] == end

    def test_no_mutation_when_the_decision_is_a_no_op(self):
        store = FakeStore([sub_row(id=1, status="active", provider_subscription_id="SUB_x")])
        process_paystack_event(store, raw_body=delivery(invoice_event("charge.success")),
                               now=lambda: NOW)
        assert store.applies[0]["update"] is None
        assert list(store.events.values())[0]["processing_status"] == "processed"

    def test_email_only_payload_is_uncorrelated(self):
        store = FakeStore([sub_row(id=1, status="active")])
        raw = delivery({"event": "subscription.create",
                        "data": {"email": "user@example.com"}})
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.rows[0]["status"] == "active"


class TestTerminalValidationFailures:
    def test_malformed_json_is_retained_and_not_retryable(self):
        store = FakeStore([])
        raw = b"{not json"
        with pytest.raises(WebhookError) as exc:
            process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert exc.value.retryable is False
        assert list(store.events.values())[0]["error_code"] == "malformed_json"

    def test_non_object_json_is_retained(self):
        store = FakeStore([])
        with pytest.raises(WebhookError) as exc:
            process_paystack_event(store, raw_body=b"[1,2,3]", now=lambda: NOW)
        assert exc.value.retryable is False
        assert list(store.events.values())[0]["error_code"] == "non_object_json"

    def test_missing_event_field_is_retained(self):
        store = FakeStore([])
        with pytest.raises(WebhookError) as exc:
            process_paystack_event(store, raw_body=body_for({"data": {}}),
                                   now=lambda: NOW)
        assert exc.value.retryable is False
        assert list(store.events.values())[0]["error_code"] == "missing_event"

    def test_blank_event_field_is_retained(self):
        store = FakeStore([])
        with pytest.raises(WebhookError):
            process_paystack_event(store, raw_body=body_for({"event": "   "}),
                                   now=lambda: NOW)
        assert list(store.events.values())[0]["error_code"] == "missing_event"

    def test_terminal_failures_never_touch_subscriptions(self):
        store = FakeStore([sub_row(id=1, status="active", provider_subscription_id="SUB_x")])
        with pytest.raises(WebhookError):
            process_paystack_event(store, raw_body=b"", now=lambda: NOW)
        assert store.rows[0]["status"] == "active"


class TestFailureIsolation:
    def test_write_failure_leaves_no_event_and_no_mutation(self):
        store = FakeStore([sub_row(id=1, status="active", provider_subscription_id="SUB_x")],
                          fail_on_apply=True)
        with pytest.raises(WebhookError) as exc:
            process_paystack_event(store, raw_body=delivery(invoice_event()),
                                   now=lambda: NOW)
        assert exc.value.retryable is True
        assert store.events == {}
        assert store.status_of(1) == "active"

    def test_retry_after_transient_failure_is_not_blocked_by_the_event_id(self):
        store = FakeStore([sub_row(id=1, status="active", provider_subscription_id="SUB_x")],
                          fail_on_apply=True)
        raw = delivery(invoice_event())
        with pytest.raises(WebhookError):
            process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        store.fail_on_apply = False
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "processed"
        assert store.status_of(1) == "past_due"
        assert len(store.events) == 1

    def test_lookup_failure_is_retryable_and_writes_nothing(self):
        store = FakeStore([sub_row(id=1, status="active", provider_subscription_id="SUB_x")],
                          fail_on_lookup=True)
        with pytest.raises(WebhookError) as exc:
            process_paystack_event(store, raw_body=delivery(create_event()),
                                   now=lambda: NOW)
        assert exc.value.retryable is True
        assert store.events == {}
        assert store.applies == []

    def test_public_error_is_a_stable_non_secret_string(self):
        store = FakeStore([], fail_on_apply=True)
        with pytest.raises(WebhookError) as exc:
            process_paystack_event(store, raw_body=delivery(create_event()),
                                   now=lambda: NOW)
        assert exc.value.public == "Webhook processing failed"
        assert "RuntimeError" not in exc.value.public
        assert FAKE_SECRET not in exc.value.public


# ==========================================================================
# Supabase store: RPC wiring
# ==========================================================================

class _FakeQuery:
    def __init__(self, table, recorder, name):
        self._table = table
        self._recorder = recorder
        self._name = name
        self._filters = {}

    def select(self, *a, **k):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def limit(self, n):
        return self

    def execute(self):
        rows = [r for r in self._recorder.rows
                if all(r.get(k) == v for k, v in self._filters.items())]
        self._recorder.calls.append({"table": self._name, "filters": self._filters})
        return types.SimpleNamespace(data=rows)


class _FakeDb:
    def __init__(self, rows=None, rpc_rows=None):
        self.rows = rows or []
        self.calls = []
        self._rpc_rows = rpc_rows if rpc_rows is not None else [
            {"event_id": 1, "inserted": True}]

    def table(self, name):
        return _FakeQuery(name, self, name)

    def rpc(self, name, params):
        self.calls.append({"rpc": name, "params": params})
        return types.SimpleNamespace(execute=lambda: types.SimpleNamespace(
            data=[dict(r) for r in self._rpc_rows]))


def _load_billing_api():
    """Import billing_api, stubbing FastAPI/pydantic when unavailable.

    The store class under test has no framework dependency; the stubs only
    let the module import so it can be exercised offline.
    """
    try:
        import billing_api  # noqa: F401
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
        fastapi.Response = object
        sys.modules.setdefault("fastapi", fastapi)

        pydantic = types.ModuleType("pydantic")

        class BaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        pydantic.BaseModel = BaseModel
        sys.modules.setdefault("pydantic", pydantic)

        import billing_api  # noqa: F401
    return sys.modules["billing_api"]


@pytest.fixture(scope="module")
def store_cls():
    try:
        module = _load_billing_api()
    except Exception:  # pragma: no cover - environment dependent
        pytest.skip("billing_api is not importable in this environment")
    return module.SupabaseSubscriptionStore


class TestSupabaseStoreWiring:
    def test_correlation_lookup_is_scoped_to_the_provider(self, store_cls):
        db = _FakeDb(rows=[{"id": 1, "status": "active", "provider": "paystack",
                            "provider_subscription_id": "SUB_x"}])
        store = store_cls(db)
        assert store.find_by_provider_subscription("paystack", "SUB_x")["id"] == 1
        assert db.calls[0]["filters"] == {"provider": "paystack",
                                          "provider_subscription_id": "SUB_x"}
        assert store.find_by_provider_customer("paystack", "CUS_x") is None

    def test_apply_event_calls_the_atomic_rpc_once(self, store_cls):
        db = _FakeDb()
        store = store_cls(db)
        result = store.apply_event(
            provider="paystack", provider_event_id="evt_1", event_type="invoice.update",
            payload={"event": "invoice.update"}, subscription_id=7,
            processing_status="processed", error_code=None,
            update=SubscriptionUpdate(new_status="active"))
        assert result == ApplyResult(event_id=1, inserted=True)
        assert [c["rpc"] for c in db.calls] == ["apply_paystack_event"]

    def test_rpc_parameters_match_the_migration_signature(self, store_cls):
        db = _FakeDb()
        store_cls(db).apply_event(
            provider="paystack", provider_event_id="evt_1", event_type="charge.success",
            payload={}, subscription_id=7, processing_status="ignored",
            error_code="uncorrelated", update=build_update({"status": "past_due"}))
        sent = set(db.calls[0]["params"])
        # The 8.3 ordering migration extends the RPC (13 -> 15 params,
        # new ones DEFAULT NULL); the call site must match the EXTENDED
        # signature exactly.
        assert sent == set(_rpc_signature(ORDERING_MIGRATION)[0])

    def test_update_flag_is_true_only_with_a_real_update(self, store_cls):
        db = _FakeDb()
        store = store_cls(db)
        store.apply_event(provider="paystack", provider_event_id="evt_1",
                          event_type="charge.success", payload={},
                          subscription_id=7, update=SubscriptionUpdate(new_status="active"))
        assert db.calls[0]["params"]["p_apply_subscription"] is True
        db2 = _FakeDb()
        store_cls(db2).apply_event(provider="paystack", provider_event_id="evt_2",
                                   event_type="charge.success", payload={},
                                   subscription_id=7)
        assert db2.calls[0]["params"]["p_apply_subscription"] is False

    def test_uncorrelated_update_is_never_marked_as_a_write(self, store_cls):
        db = _FakeDb()
        store_cls(db).apply_event(provider="paystack", provider_event_id="evt_1",
                                  event_type="subscription.create", payload={},
                                  subscription_id=None,
                                  update=SubscriptionUpdate(new_status="active"))
        assert db.calls[0]["params"]["p_apply_subscription"] is False

    def test_error_code_is_bounded(self, store_cls):
        db = _FakeDb()
        store_cls(db).apply_event(provider="paystack", provider_event_id="evt_1",
                                  event_type="charge.success", payload={},
                                  processing_status="failed", error_code="x" * 500)
        assert len(db.calls[0]["params"]["p_error_code"]) == 64

    def test_duplicate_is_reported_from_the_rpc_result(self, store_cls):
        db = _FakeDb(rpc_rows=[{"event_id": 5, "inserted": False}])
        result = store_cls(db).apply_event(
            provider="paystack", provider_event_id="evt_1", event_type="charge.success",
            payload={})
        assert result.inserted is False and result.event_id == 5

    def test_empty_rpc_result_raises_a_retryable_error(self, store_cls):
        db = _FakeDb(rpc_rows=[])
        with pytest.raises(WebhookError) as exc:
            store_cls(db).apply_event(provider="paystack", provider_event_id="evt_1",
                                      event_type="charge.success", payload={})
        assert exc.value.retryable is True

    def test_store_never_reads_or_writes_events_directly(self, store_cls):
        source = (ROOT / "billing_api.py").read_text()
        assert 'self._db.table("subscription_events")' not in source
        assert 'self._db.table("subscriptions").update' not in source


# ==========================================================================
# Migration contract
# ==========================================================================

def _strip_comments(sql: str) -> str:
    """SQL with '--' comment lines removed."""
    return "\n".join(line for line in sql.splitlines()
                     if not line.strip().startswith("--"))


def _rpc_signature(source=None):
    """(param_names, param_types) as declared in the migration.

    DEFAULT clauses (8.3 ordering params) are stripped so the bare
    types can be compared against the REVOKE/GRANT argument lists.
    """
    sql = (source or MIGRATION).read_text()
    match = re.search(
        r"CREATE OR REPLACE FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
        r"RETURNS TABLE", sql, re.S)
    assert match, "apply_paystack_event is missing from the migration"
    names, types = [], []
    for part in match.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        name, _, rest = part.partition(" ")
        names.append(name.strip())
        bare = rest.split("DEFAULT")[0].strip().upper()
        types.append(bare)
    return names, types


class TestMigrationContract:
    def test_rpc_takes_one_parameter_per_column_it_can_write(self):
        names, _types = _rpc_signature()
        assert names == [
            "p_provider", "p_provider_event_id", "p_event_type", "p_payload",
            "p_processing_status", "p_error_code", "p_subscription_id",
            "p_apply_subscription", "p_new_status", "p_provider_customer_id",
            "p_provider_subscription_id", "p_current_period_start",
            "p_current_period_end",
        ]

    def test_rpc_is_security_definer_with_a_pinned_search_path(self):
        sql = MIGRATION.read_text()
        assert "SECURITY DEFINER" in sql
        assert "SET search_path = public" in sql

    def test_rpc_revokes_and_grant_use_the_declared_types(self):
        sql = MIGRATION.read_text()
        _names, types = _rpc_signature()
        expected = ", ".join(types)
        revoke = re.search(
            r"REVOKE ALL ON FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
            r"FROM PUBLIC, anon, authenticated", sql, re.S)
        grant = re.search(
            r"GRANT EXECUTE ON FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
            r"TO service_role", sql, re.S)
        assert revoke and grant, "missing EXECUTE hardening on the RPC"
        for text in (revoke.group(1), grant.group(1)):
            declared = [t.strip().upper() for t in text.replace("\n", " ").split(",")]
            assert declared == types

    def test_duplicate_delivery_is_absorbed_inside_the_function(self):
        sql = MIGRATION.read_text()
        assert "ON CONFLICT (provider, provider_event_id) DO NOTHING" in sql
        body = sql.split("AS $$", 1)[1]
        assert "RETURN QUERY SELECT NULL::BIGINT, false;" in body

    def test_event_table_denies_user_access(self):
        sql = MIGRATION.read_text()
        assert "ALTER TABLE public.subscription_events ENABLE ROW LEVEL SECURITY" in sql
        assert "REVOKE ALL ON TABLE public.subscription_events FROM anon, authenticated" in sql
        assert "CREATE POLICY" not in sql
        assert "GRANT" in sql and "TO anon" not in sql and "TO authenticated" not in sql

    def test_event_identity_is_unique_per_provider(self):
        sql = MIGRATION.read_text()
        assert "UNIQUE (provider, provider_event_id)" in sql

    def test_processing_statuses_are_constrained(self):
        sql = MIGRATION.read_text()
        for status in ("received", "processed", "ignored", "failed"):
            assert f"'{status}'" in sql

    def test_migration_is_additive_and_local_only(self):
        sql = MIGRATION.read_text()
        # DDL section only, comments stripped: the RPC body legitimately
        # inserts and updates rows.
        ddl = _strip_comments(sql).split("CREATE OR REPLACE FUNCTION", 1)[0].lower()
        for destructive in ("drop table", "drop column", "drop policy",
                            "truncate", "delete from", "update ",
                            "alter table public.subscriptions", "insert into"):
            assert destructive not in ddl, destructive

    def test_the_only_insert_is_inside_the_rpc(self):
        body = _strip_comments(MIGRATION.read_text()).split("AS $$", 1)[1]
        assert body.lower().count("insert into") == 1
        assert "insert into public.subscription_events" in body.lower()

    def test_no_user_selectable_view_of_event_payloads(self):
        sql = _strip_comments(MIGRATION.read_text()).lower()
        assert "create view" not in sql
        assert "grant select" not in sql

    def test_subscriptions_migration_keeps_events_out_of_user_reach(self):
        assert "subscription_events" not in _strip_comments(
            SUBSCRIPTIONS_MIGRATION.read_text())


# ==========================================================================
# 8.3 ordering-migration contract
# ==========================================================================

class TestOrderingMigrationContract:
    def test_ordering_migration_exists_and_leaves_earlier_files_untouched(self):
        assert ORDERING_MIGRATION.exists()
        assert "20261002000000" not in MIGRATION.read_text()
        assert "provider_occurred_at" not in SUBSCRIPTIONS_MIGRATION.read_text()

    def test_rpc_extension_is_additive_with_defaults(self):
        names, _types = _rpc_signature(ORDERING_MIGRATION)
        original, _ = _rpc_signature(MIGRATION)
        assert names[: len(original)] == original
        assert names[len(original):] == [
            "p_provider_occurred_at", "p_provider_sequence"]
        sql = ORDERING_MIGRATION.read_text()
        assert "p_provider_occurred_at     TIMESTAMPTZ DEFAULT NULL" in sql
        assert "p_provider_sequence        TEXT DEFAULT NULL" in sql

    def test_extended_grants_use_the_declared_types(self):
        sql = ORDERING_MIGRATION.read_text()
        _names, types = _rpc_signature(ORDERING_MIGRATION)
        assert types == ["TEXT", "TEXT", "TEXT", "JSONB", "TEXT", "TEXT",
                         "BIGINT", "BOOLEAN", "TEXT", "TEXT", "TEXT",
                         "TIMESTAMPTZ", "TIMESTAMPTZ", "TIMESTAMPTZ", "TEXT"]
        revoke = re.search(
            r"REVOKE ALL ON FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
            r"FROM PUBLIC, anon, authenticated", sql, re.S)
        grant = re.search(
            r"GRANT EXECUTE ON FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
            r"TO service_role", sql, re.S)
        assert revoke and grant, "missing EXECUTE hardening on the RPC"
        for text in (revoke.group(1), grant.group(1)):
            declared = [t.strip().upper() for t in text.replace("\n", " ").split(",")]
            assert declared == types

    def test_stale_guard_is_inside_the_function(self):
        body = ORDERING_MIGRATION.read_text().split("AS $$", 1)[1]
        assert "last_applied_occurred_at" in body
        assert "stale_event" in body

    def test_ordering_columns_are_nullable_additions(self):
        body = _strip_comments(ORDERING_MIGRATION.read_text())
        assert "ADD COLUMN IF NOT EXISTS provider_occurred_at TIMESTAMPTZ NULL" in body
        assert "ADD COLUMN IF NOT EXISTS provider_sequence TEXT NULL" in body
        assert "ADD COLUMN IF NOT EXISTS last_applied_occurred_at TIMESTAMPTZ NULL" in body

    def test_audit_indexes_exist(self):
        body = _strip_comments(ORDERING_MIGRATION.read_text())
        assert "subscription_events_subscription_created_idx" in body
        assert "subscription_events_provider_type_created_idx" in body
        assert "subscription_events_occurred_idx" in body

    def test_ordering_migration_is_additive(self):
        ddl = _strip_comments(ORDERING_MIGRATION.read_text()).split(
            "CREATE OR REPLACE FUNCTION", 1)[0].lower()
        for destructive in ("drop table", "drop column", "drop policy",
                            "truncate", "delete from",
                            "alter table public.subscriptions drop",
                            "insert into"):
            assert destructive not in ddl, destructive


# ==========================================================================
# 8.3 transition + ordering behavior
# ==========================================================================

def _occurred(days_offset):
    return (NOW + timedelta(days=days_offset)).isoformat()


class TestCanceledNoResurrect:
    def test_paid_invoice_after_canceled_is_ignored(self):
        decision = decide_transition("canceled", "invoice.update",
                                     {"status": "success"}, now=NOW)
        assert decision.status is None and decision.outcome == "ignored"

    def test_paid_invoice_after_expired_is_ignored(self):
        decision = decide_transition("expired", "invoice.update",
                                     {"status": "paid"}, now=NOW)
        assert decision.status is None and decision.outcome == "ignored"

    def test_paid_invoice_after_paused_is_ignored(self):
        decision = decide_transition("paused", "invoice.update",
                                     {"status": "success"}, now=NOW)
        assert decision.status is None and decision.outcome == "ignored"

    def test_paid_invoice_after_past_due_still_restores(self):
        decision = decide_transition("past_due", "invoice.update",
                                     {"status": "success"}, now=NOW)
        assert decision.status == "active"

    def test_create_reactivates_canceled_end_to_end(self):
        # Returning customer (customer code already bound): the fresh
        # subscription code is adopted and the row reactivates.
        store = FakeStore([sub_row(id=1, status="canceled",
                                   provider_subscription_id="SUB_old",
                                   provider_customer_id="CUS_x")])
        raw = delivery(create_event(subscription_code="SUB_new",
                                    customer_code="CUS_x"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "processed"
        assert store.status_of(1) == "active"
        assert store.rows[0]["provider_subscription_id"] == "SUB_new"

    def test_canceled_row_never_resurrects_via_orchestration(self):
        store = FakeStore([sub_row(id=1, status="canceled",
                                   provider_subscription_id="SUB_x")])
        raw = delivery(invoice_event("invoice.update", status="success"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.status_of(1) == "canceled"
        assert store.applies[0]["update"] is None


class TestCreateOverActive:
    def test_same_subscription_rebinds_and_stays_active(self):
        store = FakeStore([sub_row(id=1, status="active",
                                   provider_subscription_id="SUB_x",
                                   provider_customer_id="CUS_old")])
        raw = delivery(create_event(next_payment_date="2026-12-01T00:00:00Z"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "processed"
        assert store.status_of(1) == "active"
        assert store.rows[0]["provider_customer_id"] == "CUS_x"
        assert len(store.rows) == 1  # never a second row

    def test_different_subscription_adopts_new_binding(self):
        store = FakeStore([sub_row(id=1, status="active",
                                   provider_subscription_id="SUB_old")])
        raw = delivery(create_event(subscription_code="SUB_old",
                                    customer_code="CUS_x"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.subscription_id == 1
        assert store.status_of(1) == "active"


class TestOrderingAndStaleness:
    def test_provider_time_extraction_priority(self):
        from subscription_service import extract_provider_time
        assert extract_provider_time(
            {"paid_at": "2026-10-02T00:00:00Z",
             "created_at": "2026-10-01T00:00:00Z"}
        ).isoformat() == "2026-10-01T00:00:00+00:00"
        assert extract_provider_time({}) is None
        assert extract_provider_time({"created_at": "not-a-date"}) is None

    def test_older_event_cannot_overwrite_newer_state(self):
        store = FakeStore([sub_row(
            id=1, status="active", provider_subscription_id="SUB_x",
            last_applied_occurred_at=_occurred(0))])
        stale = {"event": "invoice.payment_failed",
                 "data": {"status": "failed",
                          "created_at": _occurred(-5),
                          "subscription": {"subscription_code": "SUB_x"}}}
        result = process_paystack_event(store, raw_body=delivery(stale),
                                        now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.status_of(1) == "active"
        assert list(store.events.values())[0]["error_code"] == "stale_event"

    def test_newer_event_applies_and_advances_marker(self):
        store = FakeStore([sub_row(
            id=1, status="active", provider_subscription_id="SUB_x",
            last_applied_occurred_at=_occurred(-5))])
        fresh = {"event": "invoice.payment_failed",
                 "data": {"status": "failed",
                          "created_at": _occurred(0),
                          "subscription": {"subscription_code": "SUB_x"}}}
        result = process_paystack_event(store, raw_body=delivery(fresh),
                                        now=lambda: NOW)
        assert result.status == "past_due"
        assert store.status_of(1) == "past_due"

    def test_missing_ordering_metadata_arrival_wins(self):
        store = FakeStore([sub_row(
            id=1, status="active", provider_subscription_id="SUB_x",
            last_applied_occurred_at=_occurred(0))])
        result = process_paystack_event(
            store, raw_body=delivery(invoice_event("invoice.payment_failed")),
            now=lambda: NOW)
        assert result.status == "past_due"

    def test_ordering_metadata_reaches_the_store(self):
        store = FakeStore([sub_row(id=1, status="active",
                                   provider_subscription_id="SUB_x")])
        payload = {"event": "invoice.payment_failed",
                   "data": {"status": "failed",
                            "created_at": _occurred(0),
                            "subscription": {"subscription_code": "SUB_x"}}}
        process_paystack_event(store, raw_body=delivery(payload),
                               now=lambda: NOW)
        assert store.applies[0]["provider_occurred_at"] == _occurred(0)


class TestNonAuthoritativeEvents:
    @pytest.mark.parametrize("event", ["subscription.not_renew",
                                       "subscription.expiring_cards",
                                       "charge.success",
                                       "invoice.create"])
    def test_recorded_but_never_mutates(self, event):
        store = FakeStore([sub_row(id=1, status="active",
                                   provider_subscription_id="SUB_x")])
        raw = delivery({"event": event,
                        "data": {"subscription": {"subscription_code": "SUB_x"}}})
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome in ("processed", "ignored")
        assert store.status_of(1) == "active"
        assert store.applies[0]["update"] is None


class TestPeriodStart:
    def test_create_never_infers_period_start(self):
        # 8.3.1 §B: data.created_at is a record timestamp, not a
        # billing-period semantic. No supported payload field is
        # authoritative for the period start, so it stays unset (NULL).
        for data in ({"subscription_code": "SUB_x",
                      "created_at": "2026-09-15T00:00:00Z"},
                     {"subscription_code": "SUB_x",
                      "paid_at": "2026-09-15T00:00:00Z"},
                     {"subscription_code": "SUB_x",
                      "transaction_date": "2026-09-15T00:00:00Z"},
                     {"subscription_code": "SUB_x"}):
            decision = decide_transition("expired", "subscription.create",
                                         dict(data), now=NOW)
            assert decision.status == "active"
            assert "current_period_start" not in decision.fields

    def test_period_start_preserved_end_to_end_as_null(self):
        store = FakeStore([sub_row(id=1, status="expired",
                                   provider_subscription_id="SUB_x")])
        raw = delivery(create_event(next_payment_date="2026-11-01T00:00:00Z"))
        process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert store.rows[0]["current_period_end"] == \
            "2026-11-01T00:00:00+00:00"
        assert store.rows[0]["current_period_start"] is None


class TestProvisionalAdoption:
    def test_create_adopts_provisional_row_by_customer_code(self):
        # Provisional rows (status expired, NULL provider ids except the
        # customer code bound at checkout/verify time) are adopted only
        # by subscription.create, never by invoice/charge events.
        store = FakeStore([dict(sub_row(id=1, status="expired",
                                        provider="paystack",
                                        provider_customer_id="CUS_new",
                                        provider_subscription_id=None),
                                plan="growth")])
        raw = delivery(create_event(subscription_code="SUB_new",
                                    customer_code="CUS_new"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "processed"
        assert result.subscription_id == 1
        assert store.status_of(1) == "active"
        assert store.rows[0]["provider_subscription_id"] == "SUB_new"

    def test_invoice_never_adopts_a_provisional_row(self):
        store = FakeStore([sub_row(id=1, status="expired",
                                   provider_customer_id="CUS_x")])
        raw = delivery({"event": "invoice.payment_failed",
                        "data": {"status": "failed",
                                 "customer": {"customer_code": "CUS_x"}}})
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.status_of(1) == "expired"

    def test_uncorrelatable_first_event_creates_nothing(self):
        store = FakeStore([])
        raw = delivery(create_event(subscription_code="SUB_ghost",
                                    customer_code="CUS_ghost"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.rows == []
        assert list(store.events.values())[0]["error_code"] == "uncorrelated"

    def test_reference_alone_never_adopts(self):
        # 8.3.1 §A: a fresh provisional row carries the echoed checkout
        # reference but no bound customer/subscription codes. A
        # subscription.create for a DIFFERENT customer must NOT adopt
        # it: the reference is not a webhook match key and fail-closed
        # behavior is preserved until the verify-based binder binds the
        # customer code.
        store = FakeStore([dict(
            sub_row(id=1, status="expired", provider="paystack"),
            provider_reference="footyedge_abc123")])
        raw = delivery(create_event(subscription_code="SUB_other",
                                    customer_code="CUS_other"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "ignored"
        assert store.status_of(1) == "expired"
        assert store.rows[0]["provider_reference"] == "footyedge_abc123"

    def test_bound_reference_row_adopts_via_customer_code(self):
        # The achievable path: checkout persisted the reference, the
        # (future) verify-based binder bound the customer code to the
        # JWT owner's row, and subscription.create adopts it -> active.
        store = FakeStore([dict(
            sub_row(id=1, status="expired", provider="paystack",
                    provider_customer_id="CUS_bound"),
            provider_reference="footyedge_abc123")])
        raw = delivery(create_event(subscription_code="SUB_new",
                                    customer_code="CUS_bound"))
        result = process_paystack_event(store, raw_body=raw, now=lambda: NOW)
        assert result.outcome == "processed"
        assert store.status_of(1) == "active"
        assert store.rows[0]["provider_subscription_id"] == "SUB_new"
        assert store.rows[0]["provider_reference"] == "footyedge_abc123"

# ==========================================================================
# 8.3.1 Issue 3: single authoritative RPC signature
# ==========================================================================

def _declared_creates(sql: str):
    """Signatures from CREATE OR REPLACE FUNCTION statements."""
    return re.findall(
        r"CREATE OR REPLACE FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
        r"RETURNS TABLE", sql, re.S)


def _declared_drops(sql: str):
    """Signatures from DROP FUNCTION statements."""
    return re.findall(
        r"DROP FUNCTION IF EXISTS public\.apply_paystack_event\((.*?)\)\s*;",
        sql, re.S)


def _normalize_args(arglist: str):
    """Bare upper-cased argument types from a CREATE or DROP arg list.

    CREATE form carries "name TYPE [DEFAULT ...]" per parameter; DROP
    form carries bare types. Both normalize to the type tuple, which is
    what PostgreSQL uses (with the function name) as the identity.
    """
    out = []
    for part in arglist.replace("\n", " ").split(","):
        part = part.strip()
        if not part:
            continue
        if " " in part:
            bare = part.split("DEFAULT")[0].strip().upper().split()
            out.append(bare[-1])
        else:
            out.append(part.strip().upper())
    return tuple(out)


class TestSingleRpcSignature:
    def test_overload_problem_is_real_before_the_fix(self):
        # The 8E file declares 13 args; the 8.3 ordering file declares 15.
        # PostgreSQL identifies functions by (name, arg types), so CREATE
        # OR REPLACE with 15 args creates an OVERLOAD, not a replacement.
        _, types_8e = _rpc_signature(MIGRATION)
        _, types_83 = _rpc_signature(ORDERING_MIGRATION)
        assert len(types_8e) == 13
        assert len(types_83) == 15
        assert types_83[:13] == types_8e

    def test_final_inventory_is_exactly_one_guarded_signature(self):
        # Simulate applying migrations in filename order: CREATE adds an
        # overload, DROP removes one. The 8.3.1 fix must leave exactly
        # the 15-argument guarded signature.
        inventory = set()
        for path in (MIGRATION, ORDERING_MIGRATION, SINGLE_SIG_MIGRATION):
            sql = path.read_text()
            for args in _declared_creates(sql):
                inventory.add(_normalize_args(args))
            for args in _declared_drops(sql):
                inventory.discard(_normalize_args(args))
        assert len(inventory) == 1
        surviving = next(iter(inventory))
        assert surviving == tuple(_rpc_signature(ORDERING_MIGRATION)[1])
        assert len(surviving) == 15

    def test_fix_drops_exactly_the_8e_signature(self):
        drops = _declared_drops(SINGLE_SIG_MIGRATION.read_text())
        assert len(drops) == 1
        assert _normalize_args(drops[0]) == tuple(_rpc_signature(MIGRATION)[1])

    def test_fix_grants_target_only_the_surviving_signature(self):
        sql = SINGLE_SIG_MIGRATION.read_text()
        _names, types = _rpc_signature(ORDERING_MIGRATION)
        revoke = re.search(
            r"REVOKE ALL ON FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
            r"FROM PUBLIC, anon, authenticated", sql, re.S)
        grant = re.search(
            r"GRANT EXECUTE ON FUNCTION public\.apply_paystack_event\((.*?)\)\s*"
            r"TO service_role", sql, re.S)
        assert revoke and grant
        expected = ", ".join(types)
        for text in (revoke.group(1), grant.group(1)):
            declared = [t.strip().upper()
                        for t in text.replace("\n", " ").split(",")]
            assert declared == types
        assert "TO anon" not in sql and "TO authenticated" not in sql
        assert "TO PUBLIC" not in sql

    def test_call_site_matches_the_surviving_signature(self):
        source = (ROOT / "billing_api.py").read_text()
        # Exactly one live RPC invocation (docstring prose + error text
        # excluded): a single authoritative mutation path.
        assert source.count('rpc("apply_paystack_event"') == 1
        assert '"p_provider_occurred_at": provider_occurred_at' in source
        assert '"p_provider_sequence": provider_sequence' in source

    def test_reference_migration_adds_only_a_nullable_column(self):
        body = _strip_comments(REFERENCE_MIGRATION.read_text())
        assert "ADD COLUMN IF NOT EXISTS provider_reference TEXT NULL" in body
        lowered = body.lower()
        for forbidden in ("drop ", "delete from", "truncate",
                          "create policy", "grant ", "revoke "):
            assert forbidden not in lowered, forbidden


# ==========================================================================
# Route shape and secret hygiene
# ==========================================================================

class TestRouteAndHygiene:
    def test_signature_is_checked_before_any_store_use(self):
        source = (ROOT / "billing_api.py").read_text()
        verify = source.index("verify_paystack_signature(raw, signature, secret)")
        store = source.index("SupabaseSubscriptionStore(get_supabase_client())")
        assert verify < store

    def test_raw_body_is_used_for_verification(self):
        source = (ROOT / "billing_api.py").read_text()
        assert "await request.body()" in source
        assert "verify_paystack_signature(raw," in source

    def test_no_secret_values_in_committed_sources(self):
        pattern = re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}")
        for name in ("billing.py", "billing_api.py", "subscription_service.py",
                     "tests/test_billing_paystack.py",
                     "tests/test_billing_webhooks.py",
                     "docs/billing-paystack.md"):
            text = (ROOT / name).read_text()
            assert not pattern.search(text), name

    def test_secret_is_only_read_from_the_environment(self):
        source = (ROOT / "billing_api.py").read_text()
        assert 'os.environ.get("PAYSTACK_SECRET_KEY"' in source
        assert "PAYSTACK_SECRET_KEY = " not in source

    def test_date_parsing_is_timezone_aware(self):
        parsed = parse_dt("2026-11-01T00:00:00Z")
        assert parsed is not None and parsed.tzinfo is not None
        assert parse_dt("2026-11-01T00:00:00").tzinfo is timezone.utc
        assert parse_dt(None) is None
        assert parse_dt(12345) is None
