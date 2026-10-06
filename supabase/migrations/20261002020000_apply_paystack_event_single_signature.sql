-- ============================================
-- FootyEdge AI single RPC signature (Objective 8.3.1, Issue 3)
-- LOCAL migration only. NOT applied to production.
-- Never edits earlier migrations.
-- ============================================
--
-- PROBLEM
-- PostgreSQL identifies a function by (name, argument types); argument
-- DEFAULTs are not part of the identity. The 8.3 ordering migration's
-- `CREATE OR REPLACE FUNCTION public.apply_paystack_event(... 15 args)`
-- therefore did NOT replace the 8E 13-argument version: after both
-- migrations apply, TWO overloads coexist:
--   apply_paystack_event(TEXT x13)  -- 8E, no stale-event guard
--   apply_paystack_event(TEXT x13, TIMESTAMPTZ, TEXT) -- 8.3, guarded
-- The 8.3 REVOKE/GRANT statements targeted only the 15-argument form,
-- so the 13-argument overload kept its 8E grants (service_role
-- EXECUTE): an accidental alternate mutation boundary without the
-- stale-event guard.
--
-- FIX (this migration, applied AFTER 20261002000000_*)
-- 1. Drop the superseded 13-argument overload. This removes dead code
--    only: the application call site already sends all 15 parameters,
--    and no other caller exists. No table data is touched.
-- 2. Re-assert REVOKE/GRANT on the single surviving 15-argument
--    signature (idempotent): EXECUTE service_role-only.
--
-- RESULT: exactly one authoritative apply_paystack_event mutation path.
--
-- ROLLBACK STANCE: forward-fix only.

DROP FUNCTION IF EXISTS public.apply_paystack_event(
    TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, BIGINT, BOOLEAN, TEXT, TEXT, TEXT,
    TIMESTAMPTZ, TIMESTAMPTZ
);

REVOKE ALL ON FUNCTION public.apply_paystack_event(
    TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, BIGINT, BOOLEAN, TEXT, TEXT, TEXT,
    TIMESTAMPTZ, TIMESTAMPTZ, TIMESTAMPTZ, TEXT
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.apply_paystack_event(
    TEXT, TEXT, TEXT, JSONB, TEXT, TEXT, BIGINT, BOOLEAN, TEXT, TEXT, TEXT,
    TIMESTAMPTZ, TIMESTAMPTZ, TIMESTAMPTZ, TEXT
) TO service_role;

-- Verification queries (read-only; run after apply in a non-prod context):
-- SELECT oid::regprocedure FROM pg_proc WHERE proname = 'apply_paystack_event';
--   -- expected: exactly ONE row, the 15-argument form
-- SELECT has_function_privilege('anon', 'public.apply_paystack_event(text,text,text,jsonb,text,text,bigint,boolean,text,text,text,timestamptz,timestamptz,timestamptz,text)', 'EXECUTE') AS anon_may_call;
--   -- expected: false
-- SELECT has_function_privilege('service_role', 'public.apply_paystack_event(text,text,text,jsonb,text,text,bigint,boolean,text,text,text,timestamptz,timestamptz,timestamptz,text)', 'EXECUTE') AS service_may_call;
--   -- expected: true
