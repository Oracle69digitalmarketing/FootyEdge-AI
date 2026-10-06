-- ============================================
-- FootyEdge AI webhook event history (Objective 8E)
-- LOCAL migration only. NOT applied to production.
-- Backward-compatible: only ADDs one table/indexes; never drops,
-- rewrites, backfills, or touches existing tables.
-- ============================================
--
-- SCOPE
-- 1. public.subscription_events: durable, append-only history of
--    provider webhook deliveries for 8E subscription synchronization.
-- 2. Provider event identity is UNIQUE(provider, provider_event_id) and
--    is the concurrency boundary for idempotent redelivery. Paystack
--    sends no stable top-level event ID, so the application records
--    provider_event_id as the SHA-256 hex of the exact raw delivery
--    bytes (see subscription_service.event_identity); identical
--    redeliveries therefore collide, distinct events never do.
-- 3. RLS: enabled with NO policies for anon/authenticated, so ordinary
--    users (and anonymous callers) can neither read provider payloads
--    nor write events. Service-role / trusted backend only.
-- 4. No seed inserts. No payment-provider assumptions beyond the
--    provider TEXT label. No 8C object is altered.
-- 5. public.apply_paystack_event(): the transaction boundary. The
--    service-role backend CANNOT make three writes atomic over PostgREST
--    HTTP, so the event claim, the subscription update and the event
--    completion all happen inside this single function (and therefore a
--    single transaction). See the long comment above it.

CREATE TABLE IF NOT EXISTS public.subscription_events (
    id                BIGSERIAL PRIMARY KEY,
    subscription_id   BIGINT NULL REFERENCES public.subscriptions(id) ON DELETE SET NULL,
    provider          TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    payload           JSONB NOT NULL,
    processing_status TEXT NOT NULL,
    error_code        TEXT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at      TIMESTAMPTZ NULL,

    CONSTRAINT subscription_events_provider_event_uidx UNIQUE (provider, provider_event_id),
    CONSTRAINT subscription_events_status_check CHECK (processing_status IN ('received', 'processed', 'ignored', 'failed'))
);

ALTER TABLE public.subscription_events ENABLE ROW LEVEL SECURITY;

-- Deny by default: strip default-privilege grants and grant nothing to
-- anon/authenticated. service_role keeps its default full rights for
-- trusted server-side webhook processing (no RLS policy is needed for
-- the table-owner path, and none is created for any other role).
REVOKE ALL ON TABLE public.subscription_events FROM anon, authenticated;

-- -----------------------------------------------------------------------
-- public.apply_paystack_event(): the single atomic webhook write boundary
-- -----------------------------------------------------------------------
-- WHY THIS EXISTS
-- An 8E delivery needs three writes: (a) claim the event id, (b) apply the
-- subscription transition, (c) mark the event processed/ignored/failed.
-- Over PostgREST each of those is a separate HTTP request and therefore a
-- separate implicit transaction, so doing them from Python is NOT atomic:
-- a crash between (a) and (b) would leave a 'received' event that can never
-- be re-applied (its unique id is already spent), i.e. a silently lost
-- subscription update. This function is that transaction, in the database.
--
-- GUARANTEES
-- * INSERT ... ON CONFLICT (provider, provider_event_id) DO NOTHING is the
--   concurrency arbiter: exactly one concurrent delivery inserts, updates
--   the subscription and completes the event. Losers return inserted=false
--   and change nothing. A plain 23505 is never surfaced to the caller.
-- * Any failure raises, so the whole transaction (event row + subscription
--   update) rolls back. There is no half-applied state, and a retryable
--   redelivery is processed from scratch.
-- * Only the columns listed in the signature can be written. Callers cannot
--   smuggle arbitrary keys into the subscription row.
-- * The update is guarded by s.provider = p_provider, so a provider event
--   can never mutate a row that is not bound to that provider.
--
-- SECURITY
-- SECURITY DEFINER (it must write tables that have RLS enabled with no
-- user policy), so EXECUTE is the entire security boundary: revoked from
-- PUBLIC/anon/authenticated and granted only to service_role. Without the
-- REVOKE, Postgres' default "EXECUTE to PUBLIC" would let any API caller
-- mutate arbitrary subscription rows through this function.
CREATE OR REPLACE FUNCTION public.apply_paystack_event(
    p_provider                 TEXT,
    p_provider_event_id        TEXT,
    p_event_type               TEXT,
    p_payload                  JSONB,
    p_processing_status        TEXT,
    p_error_code               TEXT,
    p_subscription_id          BIGINT,
    p_apply_subscription       BOOLEAN,
    p_new_status               TEXT,
    p_provider_customer_id     TEXT,
    p_provider_subscription_id TEXT,
    p_current_period_start     TIMESTAMPTZ,
    p_current_period_end       TIMESTAMPTZ
)
RETURNS TABLE (event_id BIGINT, inserted BOOLEAN)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_event_id BIGINT;
BEGIN
    INSERT INTO public.subscription_events (
        subscription_id, provider, provider_event_id, event_type, payload,
        processing_status, error_code
    )
    VALUES (
        p_subscription_id, p_provider, p_provider_event_id, p_event_type,
        COALESCE(p_payload, '{}'::jsonb), p_processing_status, p_error_code
    )
    ON CONFLICT (provider, provider_event_id) DO NOTHING
    RETURNING id INTO v_event_id;

    IF v_event_id IS NULL THEN
        -- Already recorded: a duplicate delivery. No mutation of anything.
        RETURN QUERY SELECT NULL::BIGINT, false;
        RETURN;
    END IF;

    IF COALESCE(p_apply_subscription, false)
       AND p_subscription_id IS NOT NULL
       AND p_new_status IS NOT NULL THEN
        UPDATE public.subscriptions AS s
           SET status                   = p_new_status,
               provider                 = COALESCE(p_provider, s.provider),
               provider_customer_id     = COALESCE(p_provider_customer_id, s.provider_customer_id),
               provider_subscription_id = COALESCE(p_provider_subscription_id, s.provider_subscription_id),
               current_period_start     = COALESCE(p_current_period_start, s.current_period_start),
               current_period_end       = COALESCE(p_current_period_end, s.current_period_end)
         WHERE s.id = p_subscription_id
           AND s.provider = p_provider;
    END IF;

    IF p_processing_status IN ('processed', 'ignored', 'failed') THEN
        UPDATE public.subscription_events
           SET processed_at = now()
         WHERE id = v_event_id;
    END IF;

    RETURN QUERY SELECT v_event_id, true;
END;
$$;

REVOKE ALL ON FUNCTION public.apply_paystack_event(
    TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, BIGINT, BOOLEAN, TEXT, TEXT, TEXT,
    TIMESTAMPTZ, TIMESTAMPTZ
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.apply_paystack_event(
    TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, BIGINT, BOOLEAN, TEXT, TEXT, TEXT,
    TIMESTAMPTZ, TIMESTAMPTZ
) TO service_role;

-- Verification queries (read-only; run after apply in a non-prod context):
-- SELECT tablename, rowsecurity FROM pg_tables WHERE tablename = 'subscription_events';
-- SELECT policyname FROM pg_policies WHERE tablename = 'subscription_events';
-- SELECT conname FROM pg_constraint WHERE conrelid = 'public.subscription_events'::regclass;
-- SELECT has_function_privilege('anon', 'public.apply_paystack_event(text,text,text,jsonb,text,text,bigint,boolean,text,text,text,timestamptz,timestamptz)', 'EXECUTE') AS anon_may_call;
--   -- expected: false
-- SELECT has_function_privilege('service_role', 'public.apply_paystack_event(text,text,text,jsonb,text,text,bigint,boolean,text,text,text,timestamptz,timestamptz)', 'EXECUTE') AS service_may_call;
--   -- expected: true

