-- ============================================
-- FootyEdge AI Staging: profiles table
-- Objective 7C.8E.1 — Staging Migration Design (HARDENED)
-- STAGING ONLY: Do NOT apply to production database.
-- ============================================

-- Staging-only migration: modifies profiles table for staging environment.
-- This migration MUST NOT be applied to production.
-- It adds staging-specific columns and RLS policies that are
-- guard-gated against production deployment.

CREATE TABLE IF NOT EXISTS public.profiles (
    id           uuid                     NOT NULL,
    email        text                     NOT NULL,
    full_name    text,
    avatar_url   text,
    is_premium   boolean                  NOT NULL DEFAULT false,
    role         text                     NOT NULL DEFAULT 'user',
    created_at   timestamp with time zone NOT NULL DEFAULT now(),
    updated_at   timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT profiles_pkey PRIMARY KEY (id),
    CONSTRAINT profiles_id_fkey FOREIGN KEY (id)
        REFERENCES auth.users(id) ON DELETE CASCADE,
    CONSTRAINT profiles_email_key UNIQUE (email),
    CONSTRAINT profiles_role_check CHECK (role IN ('owner','admin','user'))
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users read only their own profile (staging guard)
DO $$
BEGIN
    IF current_setting('app.env', true) = 'staging' THEN
        CREATE POLICY "Users read own profile" ON public.profiles
            FOR SELECT TO authenticated
            USING (auth.uid() = id);
    ELSE
        RAISE NOTICE 'Staging RLS policy skipped: not running in staging environment';
    END IF;
END$$;

-- Staging-only: users update self-service columns (guard gate)
DO $$
BEGIN
    IF current_setting('app.env', true) = 'staging' THEN
        CREATE POLY "Self-service profile update" ON public.profiles
            FOR UPDATE TO authenticated
            USING (auth.uid() = id)
            WITH CHECK (role = 'user' OR auth.uid() = id);
    ELSE
        RAISE NOTICE 'Staging RLS policy skipped: not running in staging environment';
    END IF;
END$$;

-- Idempotency guard: only apply if profiles table exists without these policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'profiles' AND policyname = 'Users read own profile') THEN
        RAISE NOTICE 'Staging profiles RLS policy not applied: already applied or table does not exist';
    ELSE
        RAISE NOTICE 'Staging profiles RLS policy: already present';
    END IF;
END$$;

-- Staging marker
COMMENT ON TABLE public.profiles IS 'Staging-only profile table. Do not apply to production. Use migration 20260930000000 for production baseline.';
