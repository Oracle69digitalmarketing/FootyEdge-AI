-- ============================================
-- FootyEdge AI subscriptions foundation (Objective 8C)
-- LOCAL migration only. NOT applied to production.
-- Backward-compatible: only ADDs one table/function/trigger/indexes,
-- narrows one privilege grant; never drops, rewrites, or backfills data.
-- ============================================
--
-- SCOPE
-- 1. public.subscriptions: one row per user, plan/status CHECKs,
--    nullable provider + billing-period fields (no provider selected yet).
-- 2. RLS: authenticated users may SELECT only their own row; all writes
--    are service-role / trusted server-side only (no user INSERT/UPDATE/
--    DELETE policies exist, so RLS denies them by default).
-- 3. profiles.role hardening: the baseline grants UPDATE on profiles to
--    anon/authenticated with only a row-scoped policy, so any signed-in
--    user could previously set their own role/is_premium. This migration
--    narrows the UPDATE privilege to self-service columns only
--    (full_name, avatar_url). No policy text is changed.
-- 4. No subscription_events table: webhook/event history belongs to 8E
--    once a payment provider (and its event vocabulary) exists.
-- 5. No backfill: absence of a subscriptions row means Starter at the
--    application layer until 8C+ adoption defines otherwise.
-- 6. No owner/admin write policies: the frontend bootstrap owner email
--    must never become a database RLS rule. Trusted writes use the
--    service role until durable server-side authorization exists.

-- ---------- 1. subscriptions table ----------
CREATE TABLE IF NOT EXISTS public.subscriptions (
    id                     BIGSERIAL PRIMARY KEY,
    user_id                UUID                     NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan                   TEXT                     NOT NULL,
    status                 TEXT                     NOT NULL,
    provider               TEXT,
    provider_customer_id   TEXT,
    provider_subscription_id TEXT,
    current_period_start   TIMESTAMPTZ,
    current_period_end     TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT subscriptions_user_id_key UNIQUE (user_id),
    CONSTRAINT subscriptions_plan_check CHECK (plan IN ('starter', 'growth', 'business', 'enterprise')),
    CONSTRAINT subscriptions_status_check CHECK (status IN ('trialing', 'active', 'past_due', 'paused', 'canceled', 'expired'))
);

-- Provider subscription identity: unique where a provider subscription
-- actually exists; NULLs never collide (partial index, not a constraint).
CREATE UNIQUE INDEX IF NOT EXISTS subscriptions_provider_subscription_uidx
    ON public.subscriptions (provider, provider_subscription_id)
    WHERE provider_subscription_id IS NOT NULL;

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- ---------- 2. subscriptions privileges (deny by default) ----------
-- NOTE: database default privileges grant broad rights on future tables
-- to anon/authenticated/service_role, so access is explicitly revoked
-- here and then granted narrowly. service_role keeps its default full
-- rights for trusted server-side management; no RLS policy is needed
-- for it (table owner path bypasses RLS).
REVOKE ALL ON TABLE public.subscriptions FROM anon, authenticated;
GRANT SELECT ON TABLE public.subscriptions TO authenticated;
GRANT SELECT ON TABLE public.subscriptions TO service_role;

-- Users read only their own row. No INSERT/UPDATE/DELETE policy exists
-- for anon/authenticated, so RLS denies all such writes by default.
CREATE POLICY "Users read own subscription" ON public.subscriptions
    FOR SELECT
    TO authenticated
    USING ((auth.uid() = user_id));

-- ---------- 3. subscriptions updated_at (narrowly scoped) ----------
CREATE OR REPLACE FUNCTION public.handle_subscription_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_subscriptions_updated_at ON public.subscriptions;
CREATE TRIGGER trg_subscriptions_updated_at
    BEFORE UPDATE ON public.subscriptions
    FOR EACH ROW EXECUTE FUNCTION public.handle_subscription_updated_at();

-- ---------- 4. profiles.role hardening ----------
-- Baseline state: GRANT UPDATE ON profiles TO anon/authenticated plus a
-- row-scoped ("Users can update own profile") policy with no column
-- restriction, so a signed-in user could UPDATE role/is_premium/email.
-- Narrow the privilege to genuine self-service columns. Legitimate
-- full_name/avatar_url edits keep working; role, is_premium, email, id
-- and timestamps can no longer be written via the anon/authenticated
-- roles. service_role and postgres grants are untouched, so trusted
-- server-side management (and future owner tooling) still works.
REVOKE UPDATE ON TABLE public.profiles FROM anon, authenticated;
GRANT UPDATE (full_name, avatar_url) ON TABLE public.profiles TO authenticated;

-- Verification queries (read-only; run after apply in a non-prod context):
-- SELECT tablename, rowsecurity FROM pg_tables WHERE tablename IN ('subscriptions', 'profiles');
-- SELECT policyname, cmd, roles FROM pg_policies WHERE tablename = 'subscriptions';
-- SELECT grantee, privilege_type FROM information_schema.role_table_grants
--   WHERE table_name = 'profiles' AND privilege_type = 'UPDATE';
-- SELECT conname FROM pg_constraint WHERE conrelid = 'public.subscriptions'::regclass;
