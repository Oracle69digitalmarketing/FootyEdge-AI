-- ============================================
-- FootyEdge AI profile signup trigger ensure (Objective 9.3D.3).
--
-- Idempotent and additive: recreates public.handle_new_user() EXACTLY as
-- defined in the production baseline (including the documented owner
-- bootstrap expression) and re-attaches on_auth_user_created
-- AFTER INSERT ON auth.users. A healthy install is a no-op recreate; a
-- missing or disabled trigger is repaired. No backfill here: profiles
-- for pre-existing auth users are a separate, explicitly authorized step.
-- Never drops tables, rewrites data, or touches unrelated structures.
-- Application is manual/gated via the repository migration workflow;
-- this file MUST NOT be auto-applied.
-- ============================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  SECURITY DEFINER
  AS $function$
BEGIN
    INSERT INTO public.profiles (id, email, role, is_premium)
    VALUES (new.id, new.email, 'user', (new.email = 'sophiemabel69@gmail.com'));
    RETURN NEW;
END;
$function$;

GRANT EXECUTE ON FUNCTION "public"."handle_new_user"() TO PUBLIC, "anon", "authenticated";
GRANT EXECUTE ON FUNCTION "public"."handle_new_user"() TO "service_role";
GRANT EXECUTE ON FUNCTION "public"."handle_new_user"() TO "postgres";

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
