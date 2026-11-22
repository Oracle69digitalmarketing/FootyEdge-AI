-- ============================================
-- FootyEdge AI Staging: teams table
-- Objective 7C.8E.1 — Staging Migration Design (HARDENED)
-- STAGING ONLY: Do NOT apply to production database.
-- ============================================

-- Staging-only migration: modifies teams table for staging environment.
-- This migration MUST NOT be applied to production.
-- It adds staging-specific team RLS policies and governance guards.

CREATE TABLE IF NOT EXISTS public.teams (
    id                   uuid                     NOT NULL,
    name                 text                     NOT NULL,
    competition          text,
    founded_year         integer,
    stadium_capacity     integer,
    is_active            boolean                  NOT NULL DEFAULT true,
    created_at           timestamp with time zone NOT NULL DEFAULT now(),
    updated_at           timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT teams_pkey PRIMARY KEY (id),
    CONSTRAINT teams_name_key UNIQUE (name),
    CONSTRAINT teams_founded_check CHECK (founded_year >= 1800 AND founded_year <= 2025)
);

ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;

-- Staging-only RLS policy (guard-gated)
DO $$
BEGIN
    IF current_setting('app.env', true) = 'staging' THEN
        CREATE POLICY "Users read active teams" ON public.teams
            FOR SELECT TO authenticated
            USING (is_active = true);
    ELSE
        RAISE NOTICE 'Staging teams RLS policy skipped: not running in staging environment';
    END IF;
END$$;

-- Staging-only: admin full access to teams
DO $$
BEGIN
    IF current_setting('app.env', true) = 'staging' THEN
        CREATE POLICY "Admin full team access" ON public.teams
            FOR ALL TO authenticated
            USING (role = 'admin' OR role = 'owner')
            WITH CHECK (role = 'admin' OR role = 'owner');
    ELSE
        RAISE NOTICE 'Staging teams admin policy skipped: not running in staging environment';
    END IF;
END$$;

-- Idempotency guard
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = 'teams' AND policyname = 'Users read active teams') THEN
        RAISE NOTICE 'Staging teams RLS policy not applied: already applied or table does not exist';
    ELSE
        RAISE NOTICE 'Staging teams RLS policy: already present';
    END IF;
END$$;

-- Staging marker
COMMENT ON TABLE public.teams IS 'Staging-only team table. Do not apply to production. Use migration 20261002000000 for production baseline.';
