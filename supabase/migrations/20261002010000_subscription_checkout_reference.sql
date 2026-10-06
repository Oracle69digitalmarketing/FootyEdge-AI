-- ============================================
-- FootyEdge AI checkout reference (Objective 8.3.1, Issue 1)
-- LOCAL migration only. NOT applied to production.
-- Backward-compatible: only ADDs one nullable column; never drops,
-- rewrites, constrains, or backfills. Never edits earlier migrations.
-- ============================================
--
-- SCOPE
-- 1. Paystack `transaction/initialize` returns exactly two usable
--    fields: `authorization_url` and `reference` (the latter is OUR
--    `footyedge_<uuid4hex>` reference, minted server-side and echoed
--    by the provider). No customer code, no subscription code.
-- 2. The reference is therefore the ONLY authoritative
--    checkout<->provider correlation token available at checkout time.
--    Persisting it on the provisional row enables the future
--    server-side verify-based binder: an authenticated confirm step
--    calls `transaction/verify/{reference}`, checks status/amount/plan
--    against the server's plan map, and binds the verified customer
--    code to the JWT owner's row. That binder is a separate
--    specification (new write path + route); this migration only
--    stores the join key.
-- 3. The webhook NEVER matches on this column (adoption stays
--    subscription-code, then customer-code for subscription.create
--    only). Email/amount/name/timestamps remain non-keys. Fail-closed
--    behavior is unchanged: an unbound provisional row cannot be
--    adopted by any event.
--
-- ROLLBACK STANCE: forward-fix only.

ALTER TABLE public.subscriptions
    ADD COLUMN IF NOT EXISTS provider_reference TEXT NULL;

-- No index: the future binder looks rows up by user_id (already UNIQUE)
-- and verifies the reference against the provider; the column is an
-- audit/anti-replay token, not a lookup key. No uniqueness constraint:
-- references are uuid-based unique by construction, and the one-row-
-- per-user invariant is already enforced by subscriptions_user_id_key.

-- Verification queries (read-only; run after apply in a non-prod context):
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns
--   WHERE table_name = 'subscriptions' AND column_name = 'provider_reference';
--   -- expected: one row, text, YES
