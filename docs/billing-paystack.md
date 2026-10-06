# FootyEdge billing — Paystack integration (8D + 8E, hardened 8.3)

Provider: **Paystack** (initial; abstraction in `billing.py` allows another
provider later). Mode is declared by `PAYSTACK_MODE=test|live`; **no live
billing is activated by Objective 8** (test mode only until a launch
objective authorizes live).

## Overall flow

FootyEdge plan → Paystack plan → `POST /api/billing/checkout`
→ customer authorization → Paystack subscription → webhook (8E)
→ `public.subscriptions`. The frontend callback must only ever show
"processing / confirmation pending"; it never marks plans active.

## 8D: Checkout initialization (this module)

### Environment (placeholders only — never commit real values)

```bash
PAYSTACK_MODE=test                       # test|live, explicit, no default
PAYSTACK_SECRET_KEY=<test secret>        # server-side only, never VITE_
PAYSTACK_GROWTH_PLAN_CODE=<test plan>    # e.g. PLN_xxxxxxxx for ₦5,000/mo
PAYSTACK_BUSINESS_PLAN_CODE=<test plan>  # e.g. PLN_xxxxxxxx for ₦15,000/mo
```

Startup validation (`billing.validate_paystack_config`, enforced by
`build_provider`): the secret prefix must match the declared mode
(`test`→`sk_test_…`, `live`→`sk_live_…`); both plan codes must be
present, non-empty and non-placeholder. Missing/invalid → fail closed
with `Payment initialization failed`; secret values never appear in
errors or logs. No live→test fallback, no client-supplied secrets.

Server-authoritative pricing: growth = 500_000 kobo, business = 1_500_000
kobo (Paystack amounts are minor units), NGN, monthly. Starter is free
(checkout rejected); Enterprise is manual (checkout rejected). Amounts come
from `billing.PAID_PLANS`, never from the browser.

### Identity

Checkout requires a Supabase JWT (`Authorization: Bearer`). The backend
derives `auth.users.id` + email via the Auth API; browser-supplied user
identity is never trusted.

### Provisional rows (8.3, reference binding 8.3.1)

A successful checkout initialization records a provisional
`subscriptions` row (`billing.build_provisional_row`, persisted by the
checkout route via the service-role client): `{user_id (server-derived),
plan, status='expired' (non-entitling: 8F maps expired → starter),
provider='paystack', NULL provider identifiers, provider_reference,
NULL periods}`. Insert-only (`upsert … ignore_duplicates` on `user_id`):
an existing row is never modified here, so an active subscriber
re-entering checkout cannot be downgraded. A persistence failure is
logged and does NOT fail the checkout; the webhook then falls back to
ignored/uncorrelated.

`transaction/initialize` returns exactly `authorization_url` + the
echoed `reference` (our minted `footyedge_<uuid4hex>`; see
`PaystackProvider.initialize_subscription_checkout`): no customer code,
no subscription code. The echoed reference is therefore the ONLY
authoritative checkout↔provider token and is persisted in
`subscriptions.provider_reference` (nullable, 8.3.1 migration
`20261002010000`) as an audit/anti-replay token. The webhook NEVER
matches on it; email, amount, name and timestamps are never keys.

Only `subscription.create` may adopt a provisional row, via the
authoritative subscription/customer identifiers (subscription code
first, customer code fallback). Invoice/charge events never adopt.
Uncorrelatable first events are recorded `ignored/uncorrelated`
(HTTP 200) and stay visible in the admin audit view.

**Unresolved integration prerequisite (8.3.1):** end-to-end
auto-adoption still requires one future binding step — a server-side,
authenticated confirm operation that calls
`transaction/verify/{reference}` for the JWT owner's provisional row,
checks status/amount/plan against the server plan map, and binds the
verified customer code to that row (separate specification: new write
path + route; deliberately not improvised here). Until it exists, a
fresh provisional row with NULL provider ids correctly stays
`ignored` rather than guessed. Fail-closed behavior is preserved
throughout.

### Idempotency

Each initialization mints a unique `footyedge_<uuid4hex>` reference, so
retries cannot collide on references. True duplicate-subscription
prevention (one active subscription per user) requires the 8C table plus
8E synchronization and is explicitly deferred — no locking here.

## 8E: Webhook synchronization (this module)

### HTTP boundary

`POST /api/webhooks/paystack` — **service-role only, no auth header required.**

1. Raw body is read via `await request.body()`.
2. `x-paystack-signature` header is verified with HMAC-SHA512 over the
   **exact raw bytes** using `PAYSTACK_SECRET_KEY`. Fail-closed: any
   anomaly → 401, no further processing.
3. JSON is parsed; malformed/non-object/missing `event` field → durable
   `failed` event recorded, 400 returned (non-retryable for garbage).
4. Event identity = `evt_` + SHA-256 hex of the raw bytes. Byte-identical
   redeliveries collide (duplicate); distinct deliveries never do.
   Paystack sends no stable top-level event ID, so this is the documented
   fallback. The algorithm is frozen (no canonicalization).
5. Ordering metadata (8.3, NULL-tolerant): `data.created_at`, then
   `data.paid_at`, then `data.transaction_date` is forwarded as
   `provider_occurred_at` and compared against the subscription's
   `last_applied_occurred_at` marker (Python fast-path + atomic guard in
   `public.apply_paystack_event`, extended 15-arg form in migration
   `20261002000000_webhook_ordering_guard.sql`). A provably older event
   is recorded `ignored/stale_event` and never overwrites newer state.
   NULL on either side → arrival-wins. Indexes added for
   `(subscription_id, created_at)`, `(provider, event_type, created_at)`
   and `(provider, provider_occurred_at)` audit reads.
5. Correlation (read-only): by `provider_subscription_id` first; for
   `subscription.create` only, fallback to `provider_customer_id`. Email
   is **never** used as a correlation key.
6. State transition (pure, tested, conservative):
   - `subscription.create` → active, binds provider ids, records
     `current_period_end` from `next_payment_date` if present.
     `current_period_start` is intentionally left NULL: no field in the
     supported webhook payloads is authoritative for the billing-period
     start (`data.created_at` is a record timestamp, `paid_at` /
     `transaction_date` are payment timestamps — 8.3.1 §B). The
     entitlement resolver never depends on that column. Over `active`: idempotent
     rebind (same or new code, still one row per user). Over `canceled`:
     valid reactivation. Adopts provisional rows via customer fallback.
   - `invoice.payment_failed` → `past_due` **only** from `active`/`trialing`;
     never escalates `canceled`/`expired`; never revokes on transient failure.
     No grace period, no timer, no auto-expiry.
   - `invoice.update` with paid status (`success`/`paid`) → restores `active`
     from `past_due`/`trialing`; no-op `processed` from `active`;
     **`ignored` from `canceled`/`expired`/`paused`** — invoices never
     resurrect; only a fresh `subscription.create` reactivates.
   - `subscription.not_renew` → records event, **no state change**; paid
     period preserved.
   - `subscription.disable` → preserves future paid period
     (`current_period_end` > now); otherwise `canceled`.
   - `subscription.expiring_cards` / `charge.success` → record only.
   - Unknown / uncorrelated events → recorded as `ignored`, no mutation.
7. **Single atomic write** via `public.apply_paystack_event()`:
   - INSERT event ON CONFLICT DO NOTHING (idempotency claim)
   - Conditional subscription UPDATE (whitelisted columns only)
   - UPDATE event `processed_at` (terminal status)
   - All in one transaction; duplicate returns `inserted=false` and touches
     nothing. Transient failure rolls back cleanly → no stranded event id,
     redelivery retries from scratch.

### Event history table

`public.subscription_events` — append-only, RLS enabled, **no policies for
anon/authenticated**. Ordinary users cannot read provider payloads or write
events. Service-role bypasses RLS and calls the atomic RPC.

Columns:
- `id` BIGSERIAL PK
- `subscription_id` BIGINT FK → subscriptions(id) SET NULL
- `provider` TEXT NOT NULL
- `provider_event_id` TEXT NOT NULL
- `event_type` TEXT NOT NULL
- `payload` JSONB NOT NULL
- `processing_status` TEXT NOT NULL CHECK IN ('received','processed','ignored','failed')
- `error_code` TEXT NULL (truncated to 64 chars)
- `created_at` TIMESTAMPTZ DEFAULT now()
- `processed_at` TIMESTAMPTZ NULL

Unique constraint: `(provider, provider_event_id)` — the idempotency boundary.

### Atomic RPC: `public.apply_paystack_event(...)`

SECURITY DEFINER, SET search_path = public. The entire three-write sequence
(event claim + subscription update + event completion) runs in one database
transaction. Callable **only by `service_role`** (EXECUTE revoked from
PUBLIC/anon/authenticated, granted to service_role). This is the only
correctness boundary: splitting into multiple PostgREST calls would leave
events stranded in `received` after a partial crash and silently lose
subscription updates.

Signature history (8.3.1 §C): the 8E migration declared a 13-argument
form; the 8.3 ordering migration declared a 15-argument form
(`p_provider_occurred_at`, `p_provider_sequence`, both DEFAULT NULL).
Because PostgreSQL identifies functions by (name, argument types), both
overloads coexisted until migration `20261002020000` dropped the
superseded 13-argument overload and re-asserted service_role-only grants
on the surviving 15-argument form. Exactly one authoritative mutation
path exists.

Parameters map 1:1 to whitelisted subscription columns (`status`,
`provider`, `provider_customer_id`, `provider_subscription_id`,
`current_period_start`, `current_period_end`). Callers cannot smuggle
arbitrary keys.

### HTTP responses

- `200 {"status":"processed"}` — state applied (or no-op recorded).
- `200 {"status":"ignored"}` — event persisted, no subscription found or
  unknown type; not a provider retry signal.
- `200 {"status":"duplicate"}` — already recorded, idempotent redelivery.
- `502` — retryable processing failure (DB transient, lookup failure,
  internal error). Provider will redeliver.
- `401` — invalid HMAC signature.
- `400` — malformed JSON / missing event field (deterministic rejection,
  no retry).

### Production prerequisites (not satisfied by 8E)

- Baseline migration `20260930000000_production_baseline.sql` applied.
- 8C `public.subscriptions` table with RLS (allows user SELECT, denies
  user UPDATE of `role`/`subscription_*`).
- 8.3 `20261002000000_webhook_ordering_guard.sql` applied after the 8E
  migration (ordering columns, stale-event guard, audit indexes).
- Paystack dashboard: webhook URL configured to `/api/webhooks/paystack`
  with the secret matching `PAYSTACK_MODE`; events enabled per `SUPPORTED_EVENTS`.
- `PAYSTACK_MODE`, `PAYSTACK_SECRET_KEY`, `PAYSTACK_GROWTH_PLAN_CODE`,
  `PAYSTACK_BUSINESS_PLAN_CODE` in production environment (validated at
  startup; live values only under a launch objective).

### Safety rules (expanded from 8D)

- `PAYSTACK_SECRET_KEY` never leaves the server (no `VITE_`, no logs,
  no error payloads, no snapshots, no commits). `WebhookError.public`
  is the only string that crosses the HTTP boundary.
- Safe client errors only: `Invalid plan`, `Authentication required`,
  `Payment initialization failed`, `Payment provider unavailable`,
  `Invalid webhook signature`, `Webhook processing failed`.
- Tests (`tests/test_billing_paystack.py`, `tests/test_billing_webhooks.py`)
  use fake transports; no live Paystack calls in unit tests.
- No email-based subscription lookup. No creation of unknown subscriptions.
- No unwhitelisted columns reachable from webhook payloads.