-- ============================================
-- FootyEdge AI STAGING-ONLY Migration
-- Owner Provisioning + Account Activity + Admin Action Audit
-- ============================================
--
-- WARNING: STAGING ONLY. This migration MUST NOT be applied to production.
-- It encodes the founder owner email and performs a one-shot privilege
-- promotion that is authorized specifically for the staging release.
--
-- What this migration does (every step idempotent / re-run safe):
--   1. public.account_events   per-user account activity (append-only).
--   2. public.admin_actions    admin action audit trail (append-only).
--   3. Re-creates public.handle_new_user() HARDENED:
--        - every signup gets role='user' and is_premium=false
--        - the hard-coded email bootstrap is REMOVED
--        - records an account.registered activity event
--   4. ONE-SHOT owner provisioning: promotes EXACTLY ONE existing staging
--      profile (the confirmed founder email) to role='owner'. The block
--      aborts the whole migration (transaction fails) unless exactly one
--      matching profile exists. No subscription row is created;
--      is_premium is never used to simulate ownership.
--
-- SECURITY POSTURE
--   - Deny by default: REVOKE ALL from PUBLIC/anon/authenticated on both
--     new tables; only the service role (server-side key) is granted
--     SELECT + INSERT. The migrations run as the table owner, which keeps
--     full rights for manual staging review.
--   - RLS is ENABLED on both tables with NO policies, so browser-key
--     (anon/authenticated) access is denied even if grants were widened
--     by mistake. service_role bypasses RLS by platform design; that is
--     the intended server-side access path.
--   - No role-assignment surface is created: nothing in the repository
--     UI or API writes profiles.role. Owner status exists only via this
--     one-shot block (and any future separately-authorized migration).
--   - is_premium is retired for new signups (always false). Existing rows
--     are NOT rewritten: the column simply has no entitlement effect
--     anywhere in the application.
--   - audit rows carry actor identity (migration label or authenticated
--     admin user id) but never credentials, tokens, or raw payloads.
--
-- MANUAL APPLICATION (staging Supabase Dashboard / psql as postgres):
--   Precondition: the founder has already registered through the normal
--   sign-up flow with the confirmed email, so a profiles row exists.
--   Verify before applying (read-only):
--       SELECT count(*) FROM public.profiles
--        WHERE lower(email) = 'adewaleadewumi78@gmail.com';
--   Expected: 1. If 0, the founder must sign up first; if >1, resolve the
--   duplicate (email is UNIQUE in the hardened staging profiles table, so
--   >1 cannot occur there) before applying.
--   Apply this file, then verify:
--       SELECT id, email, role, is_premium FROM public.profiles
--        WHERE lower(email) = 'adewaleadewumi78@gmail.com';
--       SELECT count(*) FROM public.profiles WHERE role = 'owner';
--   Expected: exactly one owner row, the founder's, with is_premium false.
--   Re-running this file is a safe no-op (tables IF NOT EXISTS, function
--   CREATE OR REPLACE, promotion guarded to non-owner profiles only).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Account activity events (real, per-user, append-only)
-- ---------------------------------------------------------------------------
-- event_type values written by the application and this migration:
--   account.registered              recorded by the signup trigger
--   session.authenticated_observed  recorded when the API verifies a JWT
--   usage.predict_requested         recorded on a real /api/predict call
--   usage.bet_recorded              recorded on a real /api/bets/record call
--   usage.strategy_analyzed         recorded on a real /api/analyze-strategy
--   usage.acca_generated            recorded on a real /api/acca-builder call
-- source values: 'db_trigger' | 'api'
-- dedupe_key: NULL for once-per-life events (registration); otherwise a
-- stable key (e.g. user:date or a UTC-day-prefixed per-event key) so a
-- repeated observation collapses via ON CONFLICT DO NOTHING.
CREATE TABLE IF NOT EXISTS public.account_events (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type   text NOT NULL,
    source       text NOT NULL,
    dedupe_key   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT account_events_dedupe_key UNIQUE (user_id, event_type, dedupe_key)
);

CREATE INDEX IF NOT EXISTS account_events_user_created_idx
    ON public.account_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS account_events_created_idx
    ON public.account_events (created_at DESC);

ALTER TABLE public.account_events ENABLE ROW LEVEL SECURITY;
-- No policies: anon/authenticated have no direct access (deny by default).
REVOKE ALL ON TABLE public.account_events FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON TABLE public.account_events TO service_role;

-- ---------------------------------------------------------------------------
-- 2. Admin action audit trail (append-only)
-- ---------------------------------------------------------------------------
-- Recorded server-side for sensitive admin reads (admin authorization
-- probes) and any future state-changing admin action. actor_id is the
-- authenticated admin's user id when the actor is a user; actor_label
-- identifies non-user actors (e.g. this migration). action is a stable
-- vocabulary value; target is a bounded, non-credential descriptor.
-- event_types / actions currently used:
--   admin.auth_probe              logged when an owner/admin session calls
--                                 the admin authorization probe endpoint
--   owner_provisioning.one_shot   logged by this migration for the
--                                 founder promotion
CREATE TABLE IF NOT EXISTS public.admin_actions (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id     uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_label  text,
    action       text NOT NULL,
    target       text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS admin_actions_created_idx
    ON public.admin_actions (created_at DESC);
CREATE INDEX IF NOT EXISTS admin_actions_actor_idx
    ON public.admin_actions (actor_id, created_at DESC);

ALTER TABLE public.admin_actions ENABLE ROW LEVEL SECURITY;
-- No policies: anon/authenticated have no direct access (deny by default).
REVOKE ALL ON TABLE public.admin_actions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON TABLE public.admin_actions TO service_role;

-- ---------------------------------------------------------------------------
-- 3. Hardened signup trigger: no email bootstrap, role always 'user'
-- ---------------------------------------------------------------------------
-- Supersedes both the production-baseline version (hard-coded owner email
-- bootstrap) and the 20261007000000 ensure version. Identical semantics to
-- the hardened staging profiles migration plus registration recording.
-- The activity insert is isolated: if it ever fails, the signup itself
-- still succeeds (activity is observability, never a sign-up dependency).
CREATE OR REPLACE FUNCTION public.handle_new_user()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    AS $function$
BEGIN
    INSERT INTO public.profiles (id, email, role, is_premium)
    VALUES (new.id, new.email, 'user', false);

    BEGIN
        INSERT INTO public.account_events (user_id, event_type, source)
        VALUES (new.id, 'account.registered', 'db_trigger');
    EXCEPTION WHEN OTHERS THEN
        NULL;  -- never block sign-up on activity recording
    END;

    RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.handle_new_user() TO service_role;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ---------------------------------------------------------------------------
-- 4. ONE-SHOT owner provisioning (strict single-account promotion)
-- ---------------------------------------------------------------------------
-- Confirmed founder owner email (authorization for this staging release):
--   adewaleadewumi78@gmail.com
--
-- Guarantees:
--   - only EXACTLY ONE matching existing profile is ever promoted
--   - 0 matches  -> EXCEPTION (migration aborts, nothing changes)
--   - >1 matches -> EXCEPTION (migration aborts, nothing changes)
--   - already    -> no-op (idempotent; no double-promotion, no re-log)
--   - no subscription row is created; is_premium is left as stored
--     (false for all profiles created by this migration's trigger)
DO $do$
DECLARE
    v_count integer;
BEGIN
    PERFORM 1
    FROM public.profiles
    WHERE lower(email) = 'adewaleadewumi78@gmail.com'
    LIMIT 1;

    SELECT count(*) INTO v_count
    FROM public.profiles
    WHERE lower(email) = 'adewaleadewumi78@gmail.com';

    IF v_count IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION
            'Owner provisioning failed: expected exactly one profile for the confirmed founder email, found %. The founder must register through the normal sign-up flow before this migration is applied (or duplicates must be resolved). No rows were modified.',
            v_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.profiles
        WHERE lower(email) = 'adewaleadewumi78@gmail.com'
          AND role = 'owner'
    ) THEN
        UPDATE public.profiles
        SET role = 'owner', updated_at = now()
        WHERE lower(email) = 'adewaleadewumi78@gmail.com';

        INSERT INTO public.admin_actions (actor_id, actor_label, action, target)
        VALUES (
            (SELECT id FROM public.profiles
              WHERE lower(email) = 'adewaleadewumi78@gmail.com'),
            'migration:20261114000000_staging_owner_account_admin',
            'owner_provisioning.one_shot',
            'profile:adewaleadewumi78@gmail.com'
        );
    END IF;
END;
$do$;

COMMIT;