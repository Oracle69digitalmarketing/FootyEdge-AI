-- ============================================
-- FootyEdge AI Staging: subscriptions table
-- Objective 7C.8E.1 — Staging Migration Design (HARDENED)
-- STAGING ONLY: Do NOT apply to production database.
-- ============================================

-- Staging-only migration: modifies subscriptions table for staging environment.
-- This migration MUST NOT be applied to production.
-- It adds staging-specific subscription RLS policies and guards.

CREATE TABLE IF NOT EXISTS public.subscriptions (
    id                   uuid                     NOT NULL,
    user_id              uuid                     NOT NULL,
    plan                 text                     NOT NULL DEFAULT 'free',
    status               text                     NOT NULL DEFAULT 'active',
    provider             text,
    provider_subscription_id text,
    current_period_start timestamp with time zone NOT NULL DEFAULT now(),
    current_period_end   timestamp with time zone NOT NULL DEFAULT now() + interval '1 month',
    created_at           timestamp with time zone NOT NULL DEFAULT now(),
    updated_at           timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT subscriptions_pkey PRIMARY KEY (id),
    CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT subscriptions_plan_check CHECK (plan IN ('free','pro','premium')),
    CONSTRAINT subscriptions_status_check CHECK (status IN ('active','canceled','past_due','trialing'))
);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- Staging-only RLS policy (guard-gated)
DO $$
BEGIN
    IF current_setting('app.env', true) = 'staging' THEN
        CREATE POLICY "Users read own subscription" ON public.subscriptions
            FOR SELECT TO authenticated
            USING (auth.uid() = user_id);
    ELSE
        RAISE NOTICE 'Staging subscriptions RLS policy skipped: not running in staging environment';
    END IF;
END$$;

-- Staging-only: service-role can manage subscriptions
DO $$
BEGIN
    IF current_setting('app.env', true) = 'staging' THEN
        CREATE POLICY "Service-role manage subscriptions" ON public.subscriptions
            FOR ALL TO service_role
            USING (true)
            WITH CHECK (true);
    ELSE
        RAISE NOTICE 'Staging subscriptions service-role policy skipped: not running in staging environment';
    END IF;
END$$;

-- Idempotency guard
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'subscriptions' AND policyname = 'Users read own subscription') THEN
        RAISE NOTICE 'Staging subscriptions RLS policy not applied: already applied or table does not exist';
    ELSE
        RAISE NOTICE 'Staging subscriptions RLS policy: already present';
    END IF;
END$$;

-- Staging marker
COMMENT ON TABLE public.subscriptions IS 'Staging-only subscription table. Do not apply to production. Use migration 20261001000000 for production baseline.';
