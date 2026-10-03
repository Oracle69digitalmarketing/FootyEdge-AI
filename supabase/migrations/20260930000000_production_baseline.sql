-- ============================================
-- FootyEdge AI production baseline (Objective 6D-F)
-- ============================================
-- 1. This is a PRODUCTION BASELINE migration.
-- 2. Generated from the verified FootyEdge production schema
--    (project ref xnmuretszqqvqcqasihc, "FootyEdge AI") captured via
--    `supabase db pull --declarative --schema public` (pg-delta)
--    during Objective 6D-E into an isolated workspace; assembled here
--    in the CLI-generated dependency/load order (see manifest).
-- 3. Production already contained the historical 001-equivalent schema
--    (competitions, seasons, team_competition_season,
--    team_identity_sources, team_aliases, player identity tables,
--    value_bets/predictions/user_bets links, assert_canonical_team_id()
--    WITHOUT its trigger) BEFORE migration-history adoption. Remote
--    migration history was EMPTY at capture time.
-- 4. The historical e722407 canonical team-ID data transformation
--    (legacy IDs 101-106, 10001-10004 -> six SHA-256/12-hex IDs) is
--    intentionally NOT replayed here. Production data is authoritative
--    for that transformation; this baseline carries SCHEMA ONLY.
-- 5. Existing production DATA (competitions/seasons rows, teams,
--    matches, predictions) is intentionally NOT seeded by this baseline.
-- 6. This baseline is intended to be recorded as applied WITHOUT
--    executing it (`migration repair --status applied <version>`).
-- 7. Future managed migrations begin with 002 (match provider identity).
-- NO executable historical DML below. Schema state only.
-- ============================================
-- ---- source: public/schema.sql ----
COMMENT ON SCHEMA "public" IS 'standard public schema';

REVOKE ALL ON SCHEMA "public" FROM PUBLIC;

GRANT USAGE ON SCHEMA "public" TO PUBLIC;

REVOKE ALL ON SCHEMA "public" FROM "anon";

GRANT USAGE ON SCHEMA "public" TO "anon";

REVOKE ALL ON SCHEMA "public" FROM "authenticated";

GRANT USAGE ON SCHEMA "public" TO "authenticated";

REVOKE ALL ON SCHEMA "public" FROM "pg_database_owner";

GRANT CREATE, USAGE ON SCHEMA "public" TO "pg_database_owner";

REVOKE ALL ON SCHEMA "public" FROM "postgres";

GRANT USAGE ON SCHEMA "public" TO "postgres";

REVOKE ALL ON SCHEMA "public" FROM "service_role";

GRANT USAGE ON SCHEMA "public" TO "service_role";
-- ---- source: public/adp_wipes.sql ----
-- Clears assumed destination defaults before creating objects.
-- Safe to load on a project that does not have those defaults.

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON SEQUENCES FROM "anon";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON SEQUENCES FROM "authenticated";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON SEQUENCES FROM "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON FUNCTIONS FROM "anon";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON FUNCTIONS FROM "authenticated";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON FUNCTIONS FROM "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON TABLES FROM "anon";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON TABLES FROM "authenticated";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON TABLES FROM "service_role";
-- ---- source: _cluster/extensions/pgcrypto.sql ----
CREATE EXTENSION "pgcrypto" SCHEMA "extensions";

COMMENT ON EXTENSION "pgcrypto" IS 'cryptographic functions';
-- ---- source: _cluster/extensions/uuid-ossp.sql ----
CREATE EXTENSION "uuid-ossp" SCHEMA "extensions";

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';
-- ---- source: public/sequences/accas_id_seq.sql ----
CREATE SEQUENCE "public"."accas_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."accas_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."accas_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."accas_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."accas_id_seq" TO "postgres";
-- ---- source: public/sequences/activity_log_id_seq.sql ----
CREATE SEQUENCE "public"."activity_log_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."activity_log_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."activity_log_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."activity_log_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."activity_log_id_seq" TO "postgres";
-- ---- source: public/sequences/competitions_id_seq.sql ----
CREATE SEQUENCE "public"."competitions_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."competitions_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."competitions_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."competitions_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."competitions_id_seq" TO "postgres";
-- ---- source: public/sequences/matches_id_seq.sql ----
CREATE SEQUENCE "public"."matches_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."matches_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."matches_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."matches_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."matches_id_seq" TO "postgres";
-- ---- source: public/sequences/player_identity_sources_id_seq.sql ----
CREATE SEQUENCE "public"."player_identity_sources_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."player_identity_sources_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."player_identity_sources_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."player_identity_sources_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."player_identity_sources_id_seq" TO "postgres";
-- ---- source: public/sequences/player_team_history_id_seq.sql ----
CREATE SEQUENCE "public"."player_team_history_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."player_team_history_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."player_team_history_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."player_team_history_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."player_team_history_id_seq" TO "postgres";
-- ---- source: public/sequences/players_id_seq.sql ----
CREATE SEQUENCE "public"."players_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."players_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."players_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."players_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."players_id_seq" TO "postgres";
-- ---- source: public/sequences/predictions_id_seq.sql ----
CREATE SEQUENCE "public"."predictions_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."predictions_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."predictions_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."predictions_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."predictions_id_seq" TO "postgres";
-- ---- source: public/sequences/seasons_id_seq.sql ----
CREATE SEQUENCE "public"."seasons_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."seasons_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."seasons_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."seasons_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."seasons_id_seq" TO "postgres";
-- ---- source: public/sequences/team_aliases_id_seq.sql ----
CREATE SEQUENCE "public"."team_aliases_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_aliases_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_aliases_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."team_aliases_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_aliases_id_seq" TO "postgres";
-- ---- source: public/sequences/team_identity_sources_id_seq.sql ----
CREATE SEQUENCE "public"."team_identity_sources_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_identity_sources_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_identity_sources_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."team_identity_sources_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_identity_sources_id_seq" TO "postgres";
-- ---- source: public/sequences/team_ratings_history_id_seq.sql ----
CREATE SEQUENCE "public"."team_ratings_history_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_ratings_history_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_ratings_history_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."team_ratings_history_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."team_ratings_history_id_seq" TO "postgres";
-- ---- source: public/sequences/user_bets_id_seq.sql ----
CREATE SEQUENCE "public"."user_bets_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."user_bets_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."user_bets_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."user_bets_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."user_bets_id_seq" TO "postgres";
-- ---- source: public/sequences/value_bets_id_seq.sql ----
CREATE SEQUENCE "public"."value_bets_id_seq" AS bigint INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1 NO CYCLE;

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."value_bets_id_seq" TO "anon", "authenticated";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."value_bets_id_seq" TO "service_role";

REVOKE ALL ON SEQUENCE "public"."value_bets_id_seq" FROM "postgres";

GRANT SELECT, UPDATE, USAGE ON SEQUENCE "public"."value_bets_id_seq" TO "postgres";
-- ---- source: auth/tables/users.sql ----
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();
-- ---- source: public/tables/accas.sql ----
CREATE TABLE "public"."accas" (
  "id"               bigint                   NOT NULL DEFAULT nextval('public.accas_id_seq'::regclass),
  "user_id"          uuid,
  "selections_json"  jsonb,
  "total_odds"       double precision,
  "stake"            double precision,
  "potential_return" double precision,
  "bookmaker"        text,
  "status"           character varying(20)    DEFAULT 'pending'::character varying,
  "created_at"       timestamp with time zone DEFAULT now(),
  CONSTRAINT "accas_pkey" PRIMARY KEY (id),
  CONSTRAINT "accas_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

ALTER TABLE "public"."accas"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."accas_id_seq" OWNED BY "public"."accas"."id";

CREATE POLICY "Users can insert own accas" ON "public"."accas"
  FOR INSERT
  TO PUBLIC
  WITH CHECK ((auth.uid() = user_id));

CREATE POLICY "Users can view own accas" ON "public"."accas"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = user_id));

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."accas" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."accas" TO "service_role";

REVOKE ALL ON TABLE "public"."accas" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."accas" TO "postgres";
-- ---- source: public/tables/activity_log.sql ----
CREATE TABLE "public"."activity_log" (
  "id"         bigint                   NOT NULL DEFAULT nextval('public.activity_log_id_seq'::regclass),
  "user_id"    uuid,
  "action"     character varying(100),
  "details"    jsonb,
  "created_at" timestamp with time zone DEFAULT now(),
  CONSTRAINT "activity_log_pkey" PRIMARY KEY (id),
  CONSTRAINT "activity_log_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

ALTER TABLE "public"."activity_log"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."activity_log_id_seq" OWNED BY "public"."activity_log"."id";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."activity_log" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."activity_log" TO "service_role";

REVOKE ALL ON TABLE "public"."activity_log" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."activity_log" TO "postgres";
-- ---- source: public/tables/competitions.sql ----
CREATE TABLE "public"."competitions" (
  "id"         bigint                   NOT NULL DEFAULT nextval('public.competitions_id_seq'::regclass),
  "code"       text                     NOT NULL,
  "name"       text                     NOT NULL,
  "comp_type"  text                     NOT NULL DEFAULT 'domestic_league'::text,
  "country"    text,
  "gender"     text                     NOT NULL DEFAULT 'men'::text,
  "created_at" timestamp with time zone DEFAULT now(),
  CONSTRAINT "competitions_code_key" UNIQUE (code),
  CONSTRAINT "competitions_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."competitions"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."competitions_id_seq" OWNED BY "public"."competitions"."id";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."competitions" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."competitions" TO "service_role";

REVOKE ALL ON TABLE "public"."competitions" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."competitions" TO "postgres";
-- ---- source: public/tables/matches.sql ----
CREATE TABLE "public"."matches" (
  "id"           bigint                      NOT NULL DEFAULT nextval('public.matches_id_seq'::regclass),
  "home_team_id" bigint,
  "away_team_id" bigint,
  "match_date"   timestamp without time zone NOT NULL,
  "league"       character varying(100),
  "home_goals"   integer,
  "away_goals"   integer,
  "home_xg"      double precision,
  "away_xg"      double precision,
  "created_at"   timestamp without time zone DEFAULT now(),
  CONSTRAINT "matches_pkey" PRIMARY KEY (id),
  CONSTRAINT "matches_away_team_id_fkey" FOREIGN KEY (away_team_id) REFERENCES public.teams(id) ON DELETE CASCADE,
  CONSTRAINT "matches_home_team_id_fkey" FOREIGN KEY (home_team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."matches"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."matches_id_seq" OWNED BY "public"."matches"."id";

CREATE INDEX idx_matches_date ON public.matches USING btree (match_date);

CREATE POLICY "Public read matches" ON "public"."matches"
  FOR SELECT
  TO PUBLIC
  USING (true);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."matches" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."matches" TO "service_role";

REVOKE ALL ON TABLE "public"."matches" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."matches" TO "postgres";
-- ---- source: public/tables/player_identity_sources.sql ----
CREATE TABLE "public"."player_identity_sources" (
  "id"                 bigint                   NOT NULL DEFAULT nextval('public.player_identity_sources_id_seq'::regclass),
  "player_id"          bigint,
  "source"             text                     NOT NULL,
  "external_player_id" text,
  "external_name"      text,
  "created_at"         timestamp with time zone DEFAULT now(),
  CONSTRAINT "player_identity_sources_pkey" PRIMARY KEY (id),
  CONSTRAINT "player_identity_sources_source_external_player_id_key" UNIQUE (source, external_player_id),
  CONSTRAINT "player_identity_sources_player_id_fkey" FOREIGN KEY (player_id) REFERENCES public.players(id) ON DELETE CASCADE
);

ALTER TABLE "public"."player_identity_sources"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."player_identity_sources_id_seq" OWNED BY "public"."player_identity_sources"."id";

CREATE INDEX idx_player_sources_player ON public.player_identity_sources USING btree (player_id);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."player_identity_sources" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."player_identity_sources" TO "service_role";

REVOKE ALL ON TABLE "public"."player_identity_sources" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."player_identity_sources" TO "postgres";
-- ---- source: public/tables/player_team_history.sql ----
CREATE TABLE "public"."player_team_history" (
  "id"             bigint                   NOT NULL DEFAULT nextval('public.player_team_history_id_seq'::regclass),
  "player_id"      bigint                   NOT NULL,
  "team_id"        bigint                   NOT NULL,
  "competition_id" bigint,
  "season_id"      bigint,
  "valid_from"     date,
  "valid_to"       date,
  "created_at"     timestamp with time zone DEFAULT now(),
  CONSTRAINT "player_team_history_competition_id_fkey" FOREIGN KEY (competition_id) REFERENCES public.competitions(id),
  CONSTRAINT "player_team_history_pkey" PRIMARY KEY (id),
  CONSTRAINT "player_team_history_player_id_fkey" FOREIGN KEY (player_id) REFERENCES public.players(id) ON DELETE CASCADE,
  CONSTRAINT "player_team_history_season_id_fkey" FOREIGN KEY (season_id) REFERENCES public.seasons(id),
  CONSTRAINT "player_team_history_team_id_fkey" FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."player_team_history"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."player_team_history_id_seq" OWNED BY "public"."player_team_history"."id";

CREATE INDEX idx_player_history_player ON public.player_team_history USING btree (player_id);

CREATE INDEX idx_player_history_team ON public.player_team_history USING btree (team_id);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."player_team_history" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."player_team_history" TO "service_role";

REVOKE ALL ON TABLE "public"."player_team_history" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."player_team_history" TO "postgres";
-- ---- source: public/tables/players.sql ----
CREATE TABLE "public"."players" (
  "id"           bigint                   NOT NULL DEFAULT nextval('public.players_id_seq'::regclass),
  "external_id"  bigint,
  "team_id"      bigint,
  "name"         text                     NOT NULL,
  "position"     text,
  "nationality"  text,
  "age"          integer,
  "photo_url"    text,
  "number"       integer,
  "is_injured"   boolean                  DEFAULT false,
  "is_suspended" boolean                  DEFAULT false,
  "created_at"   timestamp with time zone DEFAULT now(),
  "updated_at"   timestamp with time zone DEFAULT now(),
  CONSTRAINT "players_name_team_id_key" UNIQUE (name, team_id),
  CONSTRAINT "players_pkey" PRIMARY KEY (id),
  CONSTRAINT "players_team_id_fkey" FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."players"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."players_id_seq" OWNED BY "public"."players"."id";

CREATE POLICY "Public read players" ON "public"."players"
  FOR SELECT
  TO PUBLIC
  USING (true);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."players" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."players" TO "service_role";

REVOKE ALL ON TABLE "public"."players" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."players" TO "postgres";
-- ---- source: public/tables/predictions.sql ----
CREATE TABLE "public"."predictions" (
  "id"                 bigint                      NOT NULL DEFAULT nextval('public.predictions_id_seq'::regclass),
  "match_id"           bigint,
  "home_team"          character varying(100),
  "away_team"          character varying(100),
  "home_prob"          double precision,
  "draw_prob"          double precision,
  "away_prob"          double precision,
  "home_xg"            double precision,
  "away_xg"            double precision,
  "confidence"         double precision,
  "best_bet_market"    character varying(50),
  "best_bet_selection" character varying(100),
  "best_bet_odds"      double precision,
  "best_bet_ev"        double precision,
  "created_at"         timestamp without time zone DEFAULT now(),
  "actual_result"      character varying(10),
  CONSTRAINT "predictions_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."predictions"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."predictions_id_seq" OWNED BY "public"."predictions"."id";

ALTER TABLE "public"."predictions"
  ADD CONSTRAINT "predictions_match_id_fkey" FOREIGN KEY (match_id) REFERENCES public.matches(id) ON DELETE SET NULL NOT VALID;

CREATE INDEX idx_predictions_created ON public.predictions USING btree (created_at DESC);

CREATE INDEX idx_predictions_market_confidence ON public.predictions USING btree (best_bet_market, confidence DESC);

CREATE POLICY "Public read predictions" ON "public"."predictions"
  FOR SELECT
  TO PUBLIC
  USING (true);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."predictions" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."predictions" TO "service_role";

COMMENT ON COLUMN "public"."predictions"."actual_result" IS 'The actual match result (e.g., Home, Draw, Away) for accuracy tracking.';

REVOKE ALL ON TABLE "public"."predictions" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."predictions" TO "postgres";
-- ---- source: public/tables/profiles.sql ----
CREATE TABLE "public"."profiles" (
  "id"         uuid                     NOT NULL,
  "email"      text                     NOT NULL,
  "full_name"  text,
  "avatar_url" text,
  "is_premium" boolean                  DEFAULT false,
  "role"       text                     DEFAULT 'user'::text,
  "created_at" timestamp with time zone DEFAULT now(),
  "updated_at" timestamp with time zone DEFAULT now(),
  CONSTRAINT "profiles_email_key" UNIQUE (email),
  CONSTRAINT "profiles_id_fkey" FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE,
  CONSTRAINT "profiles_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."profiles"
  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read profiles" ON "public"."profiles"
  FOR SELECT
  TO PUBLIC
  USING (true);

CREATE POLICY "Users can update own profile" ON "public"."profiles"
  FOR UPDATE
  TO PUBLIC
  USING ((auth.uid() = id));

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."profiles" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."profiles" TO "service_role";

REVOKE ALL ON TABLE "public"."profiles" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."profiles" TO "postgres";
-- ---- source: public/tables/seasons.sql ----
CREATE TABLE "public"."seasons" (
  "id"         bigint                   NOT NULL DEFAULT nextval('public.seasons_id_seq'::regclass),
  "label"      text                     NOT NULL,
  "start_year" integer,
  "end_year"   integer,
  "created_at" timestamp with time zone DEFAULT now(),
  CONSTRAINT "seasons_label_key" UNIQUE (label),
  CONSTRAINT "seasons_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."seasons"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."seasons_id_seq" OWNED BY "public"."seasons"."id";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."seasons" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."seasons" TO "service_role";

REVOKE ALL ON TABLE "public"."seasons" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."seasons" TO "postgres";
-- ---- source: public/tables/team_aliases.sql ----
CREATE TABLE "public"."team_aliases" (
  "id"         bigint                   NOT NULL DEFAULT nextval('public.team_aliases_id_seq'::regclass),
  "team_id"    bigint                   NOT NULL,
  "alias"      text                     NOT NULL,
  "source"     text,
  "valid_from" date,
  "valid_to"   date,
  "created_at" timestamp with time zone DEFAULT now(),
  CONSTRAINT "team_aliases_alias_source_key" UNIQUE (alias, source),
  CONSTRAINT "team_aliases_pkey" PRIMARY KEY (id),
  CONSTRAINT "team_aliases_team_id_fkey" FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."team_aliases"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."team_aliases_id_seq" OWNED BY "public"."team_aliases"."id";

CREATE INDEX idx_team_aliases_alias ON public.team_aliases USING btree (alias);

CREATE INDEX idx_team_aliases_team ON public.team_aliases USING btree (team_id);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_aliases" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_aliases" TO "service_role";

REVOKE ALL ON TABLE "public"."team_aliases" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_aliases" TO "postgres";
-- ---- source: public/tables/team_competition_season.sql ----
CREATE TABLE "public"."team_competition_season" (
  "team_id"        bigint                   NOT NULL,
  "competition_id" bigint                   NOT NULL,
  "season_id"      bigint                   NOT NULL,
  "created_at"     timestamp with time zone DEFAULT now(),
  CONSTRAINT "team_competition_season_competition_id_fkey" FOREIGN KEY (competition_id) REFERENCES public.competitions(id) ON DELETE CASCADE,
  CONSTRAINT "team_competition_season_pkey" PRIMARY KEY (team_id, competition_id, season_id),
  CONSTRAINT "team_competition_season_season_id_fkey" FOREIGN KEY (season_id) REFERENCES public.seasons(id) ON DELETE CASCADE,
  CONSTRAINT "team_competition_season_team_id_fkey" FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."team_competition_season"
  ENABLE ROW LEVEL SECURITY;

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_competition_season" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_competition_season" TO "service_role";

REVOKE ALL ON TABLE "public"."team_competition_season" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_competition_season" TO "postgres";
-- ---- source: public/tables/team_identity_sources.sql ----
CREATE TABLE "public"."team_identity_sources" (
  "id"               bigint                   NOT NULL DEFAULT nextval('public.team_identity_sources_id_seq'::regclass),
  "team_id"          bigint                   NOT NULL,
  "source"           text                     NOT NULL,
  "external_team_id" text,
  "external_name"    text,
  "created_at"       timestamp with time zone DEFAULT now(),
  "updated_at"       timestamp with time zone DEFAULT now(),
  CONSTRAINT "team_identity_sources_pkey" PRIMARY KEY (id),
  CONSTRAINT "team_identity_sources_source_external_team_id_key" UNIQUE (source, external_team_id),
  CONSTRAINT "team_identity_sources_team_id_fkey" FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."team_identity_sources"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."team_identity_sources_id_seq" OWNED BY "public"."team_identity_sources"."id";

CREATE INDEX idx_team_identity_sources_name ON public.team_identity_sources USING btree (external_name);

CREATE INDEX idx_team_identity_sources_team ON public.team_identity_sources USING btree (team_id);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_identity_sources" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_identity_sources" TO "service_role";

REVOKE ALL ON TABLE "public"."team_identity_sources" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_identity_sources" TO "postgres";
-- ---- source: public/tables/team_ratings_history.sql ----
CREATE TABLE "public"."team_ratings_history" (
  "id"               bigint                      NOT NULL DEFAULT nextval('public.team_ratings_history_id_seq'::regclass),
  "team_id"          bigint,
  "rating_date"      date                        NOT NULL,
  "elo_rating"       double precision,
  "attack_strength"  double precision,
  "defense_strength" double precision,
  "created_at"       timestamp without time zone DEFAULT now(),
  CONSTRAINT "team_ratings_history_pkey" PRIMARY KEY (id),
  CONSTRAINT "team_ratings_history_team_id_fkey" FOREIGN KEY (team_id) REFERENCES public.teams(id) ON DELETE CASCADE
);

ALTER TABLE "public"."team_ratings_history"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."team_ratings_history_id_seq" OWNED BY "public"."team_ratings_history"."id";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_ratings_history" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_ratings_history" TO "service_role";

REVOKE ALL ON TABLE "public"."team_ratings_history" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."team_ratings_history" TO "postgres";
-- ---- source: public/tables/teams.sql ----
CREATE TABLE "public"."teams" (
  "id"               bigint                   NOT NULL,
  "name"             text                     NOT NULL,
  "country"          text,
  "logo_url"         text,
  "league_name"      text,
  "elo_rating"       double precision         DEFAULT 1500,
  "attack_strength"  double precision         DEFAULT 1.0,
  "defense_strength" double precision         DEFAULT 1.0,
  "home_advantage"   double precision         DEFAULT 50,
  "form_rating"      double precision         DEFAULT 0.5,
  "total_matches"    integer                  DEFAULT 0,
  "wins"             integer                  DEFAULT 0,
  "draws"            integer                  DEFAULT 0,
  "losses"           integer                  DEFAULT 0,
  "goals_scored"     integer                  DEFAULT 0,
  "goals_conceded"   integer                  DEFAULT 0,
  "created_at"       timestamp with time zone DEFAULT now(),
  "updated_at"       timestamp with time zone DEFAULT now(),
  CONSTRAINT "teams_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."teams"
  ENABLE ROW LEVEL SECURITY;

CREATE INDEX idx_teams_name ON public.teams USING btree (name);

CREATE POLICY "Admin full access" ON "public"."teams"
  FOR ALL
  TO PUBLIC
  USING (((auth.jwt() ->> 'email'::text) = 'sophiemabel69@gmail.com'::text));

CREATE POLICY "Public read access" ON "public"."teams"
  FOR SELECT
  TO PUBLIC
  USING (true);

CREATE POLICY "Public read teams" ON "public"."teams"
  FOR SELECT
  TO PUBLIC
  USING (true);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."teams" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."teams" TO "service_role";

REVOKE ALL ON TABLE "public"."teams" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."teams" TO "postgres";
-- ---- source: public/tables/user_bets.sql ----
CREATE TABLE "public"."user_bets" (
  "id"            bigint                   NOT NULL DEFAULT nextval('public.user_bets_id_seq'::regclass),
  "user_id"       uuid,
  "match_id"      bigint,
  "market"        text,
  "selection"     text,
  "odds"          double precision,
  "stake"         double precision,
  "potential_win" double precision,
  "profit_loss"   double precision,
  "status"        text                     DEFAULT 'pending'::text,
  "created_at"    timestamp with time zone DEFAULT now(),
  CONSTRAINT "user_bets_pkey" PRIMARY KEY (id),
  CONSTRAINT "user_bets_user_id_fkey" FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

ALTER TABLE "public"."user_bets"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."user_bets_id_seq" OWNED BY "public"."user_bets"."id";

ALTER TABLE "public"."user_bets"
  ADD CONSTRAINT "user_bets_match_id_fkey" FOREIGN KEY (match_id) REFERENCES public.matches(id) ON DELETE SET NULL NOT VALID;

CREATE POLICY "Users can insert own bets" ON "public"."user_bets"
  FOR INSERT
  TO PUBLIC
  WITH CHECK ((auth.uid() = user_id));

CREATE POLICY "Users can view own bets" ON "public"."user_bets"
  FOR SELECT
  TO PUBLIC
  USING ((auth.uid() = user_id));

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_bets" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_bets" TO "service_role";

REVOKE ALL ON TABLE "public"."user_bets" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."user_bets" TO "postgres";
-- ---- source: public/tables/value_bets.sql ----
CREATE TABLE "public"."value_bets" (
  "id"              bigint                   NOT NULL DEFAULT nextval('public.value_bets_id_seq'::regclass),
  "home_team"       character varying(100),
  "away_team"       character varying(100),
  "market"          character varying(50),
  "selection"       character varying(100),
  "odds"            double precision,
  "our_probability" double precision,
  "ev"              double precision,
  "status"          character varying(20)    DEFAULT 'active'::character varying,
  "match_timestamp" timestamp with time zone,
  "created_at"      timestamp with time zone DEFAULT now(),
  "opening_odds"    double precision,
  "line_movement"   character varying(10)    DEFAULT 'stable'::character varying,
  "match_id"        bigint,
  "prediction_id"   bigint,
  CONSTRAINT "value_bets_pkey" PRIMARY KEY (id)
);

ALTER TABLE "public"."value_bets"
  ENABLE ROW LEVEL SECURITY;

ALTER SEQUENCE "public"."value_bets_id_seq" OWNED BY "public"."value_bets"."id";

ALTER TABLE "public"."value_bets"
  ADD CONSTRAINT "value_bets_match_id_fkey" FOREIGN KEY (match_id) REFERENCES public.matches(id) ON DELETE SET NULL NOT VALID;

ALTER TABLE "public"."value_bets"
  ADD CONSTRAINT "value_bets_prediction_id_fkey" FOREIGN KEY (prediction_id) REFERENCES public.predictions(id) ON DELETE CASCADE NOT VALID;

CREATE INDEX idx_value_bets_status_ev ON public.value_bets USING btree (status, ev DESC);

CREATE POLICY "Public read value_bets" ON "public"."value_bets"
  FOR SELECT
  TO PUBLIC
  USING (true);

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."value_bets" TO "anon", "authenticated";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."value_bets" TO "service_role";

REVOKE ALL ON TABLE "public"."value_bets" FROM "postgres";

GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLE "public"."value_bets" TO "postgres";
-- ---- source: public/functions/assert_canonical_team_id.sql ----
CREATE OR REPLACE FUNCTION public.assert_canonical_team_id()
  RETURNS TRIGGER
  LANGUAGE plpgsql
  AS $function$
DECLARE
    expected BIGINT;
BEGIN

    expected := (
        'x' ||
        substring(
            encode(
                digest(
                    trim(
                        regexp_replace(
                            NEW.name,
                            '\s+',
                            ' ',
                            'g'
                        )
                    ),
                    'sha256'
                ),
                'hex'
            )
            FOR 12
        )
    )::bit(48)::bigint;


    IF NEW.id <> expected THEN

        RAISE EXCEPTION
            'teams.id % does not equal canonical SHA-256/12-hex % for name %',
            NEW.id,
            expected,
            NEW.name;

    END IF;


    RETURN NEW;

END;
$function$;

GRANT EXECUTE ON FUNCTION "public"."assert_canonical_team_id"() TO PUBLIC, "anon", "authenticated";

GRANT EXECUTE ON FUNCTION "public"."assert_canonical_team_id"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."assert_canonical_team_id"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."assert_canonical_team_id"() TO "postgres";
-- ---- source: public/functions/handle_new_user.sql ----
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

REVOKE ALL ON FUNCTION "public"."handle_new_user"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."handle_new_user"() TO "postgres";
-- ---- source: public/functions/rls_auto_enable.sql ----
CREATE OR REPLACE FUNCTION public.rls_auto_enable()
  RETURNS event_trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'pg_catalog'
  AS $function$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%' AND cmd.schema_name NOT LIKE 'pg_temp%' THEN
      BEGIN
        EXECUTE format('alter table if exists %s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip % (either system schema or not in enforced list: %.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$function$;

GRANT EXECUTE ON FUNCTION "public"."rls_auto_enable"() TO PUBLIC, "anon", "authenticated";

GRANT EXECUTE ON FUNCTION "public"."rls_auto_enable"() TO "service_role";

REVOKE ALL ON FUNCTION "public"."rls_auto_enable"() FROM "postgres";

GRANT EXECUTE ON FUNCTION "public"."rls_auto_enable"() TO "postgres";
-- ---- source: _cluster/event_triggers.sql ----
CREATE EVENT TRIGGER "ensure_rls"
  ON ddl_command_end
  WHEN TAG IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
  EXECUTE FUNCTION "public"."rls_auto_enable"();
-- ---- source: public/default_privileges.sql ----
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT SELECT, UPDATE, USAGE ON SEQUENCES TO "anon";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT SELECT, UPDATE, USAGE ON SEQUENCES TO "authenticated";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT SELECT, UPDATE, USAGE ON SEQUENCES TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON FUNCTIONS FROM PUBLIC;

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT EXECUTE ON FUNCTIONS TO "anon";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT EXECUTE ON FUNCTIONS TO "authenticated";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT EXECUTE ON FUNCTIONS TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLES TO "anon";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLES TO "authenticated";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT DELETE, INSERT, MAINTAIN, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE ON TABLES TO "service_role";
