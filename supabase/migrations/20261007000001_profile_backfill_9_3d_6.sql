-- ============================================
-- FootyEdge AI missing-profile backfill record (Objective 9.3D.6).
--
-- Context: all four auth.users rows predated the profile signup trigger
-- (created 2026-03/04; trigger lifecycle arrived later), so no profiles
-- existed despite a healthy trigger. Executed 2026-10-07 against
-- production via the admin SQL channel under 9.3D.6 authorization;
-- verified after: auth.users=4, profiles=4, missing=0, orphan=0, with
-- every profile email/role/is_premium matching handle_new_user()
-- semantics. Kept here so the gated workflow has the exact record.
-- Idempotent (missing-only scope plus ON CONFLICT DO NOTHING): a future
-- `db push` applying this file is a safe no-op. Never deletes, never
-- overwrites, never touches auth.users, subscriptions, or Telegram state.
-- ============================================

INSERT INTO public.profiles (id, email, role, is_premium)
SELECT u.id, u.email, 'user', (u.email = 'sophiemabel69@gmail.com')
FROM auth.users u
LEFT JOIN public.profiles p ON p.id = u.id
WHERE p.id IS NULL AND u.email IS NOT NULL
ON CONFLICT DO NOTHING;
