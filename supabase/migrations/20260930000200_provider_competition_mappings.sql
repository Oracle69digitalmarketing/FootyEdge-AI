-- ============================================
-- FootyEdge AI 003: Provider competition/season mappings (Objective 6B)
-- Run in Supabase SQL Editor AFTER 001_global_football_identity.sql.
-- Backward-compatible: only ADDs two mapping tables/indexes plus
-- idempotent seed rows; never alters existing tables, canonical IDs,
-- or identity data. No competition-season membership here (6C scope).
-- ============================================

-- Safety: the canonical FK targets must exist (see 001). This migration
-- does NOT alter competitions or seasons in any way.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'competitions' AND column_name = 'id'
    ) THEN
        RAISE EXCEPTION '003 requires competitions(id) to exist; aborting.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'seasons' AND column_name = 'id'
    ) THEN
        RAISE EXCEPTION '003 requires seasons(id) to exist; aborting.';
    END IF;
END $$;

-- 1. Provider competition identity -> canonical competitions.id.
-- Answers: "Which canonical competition does this provider competition
-- ID represent?" External IDs are TEXT identifiers stored verbatim
-- (never cast, hashed, or inferred from names). The unique grain is
-- (source, external_competition_id): the same raw provider string under
-- two sources stays independently representable, and one provider
-- identity can never point at two canonical records.
CREATE TABLE IF NOT EXISTS provider_competition_mapping (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_competition_id TEXT NOT NULL,
    competition_id BIGINT NOT NULL
        REFERENCES competitions(id)
        ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT provider_competition_mapping_source_external_key
        UNIQUE (source, external_competition_id)
);
CREATE INDEX IF NOT EXISTS idx_provider_competition_mapping_competition
    ON provider_competition_mapping(competition_id);

-- 2. Provider season identity -> canonical seasons.id.
-- Answers: "Which canonical season does this provider season ID
-- represent?" Kept separate from competition mapping: competition and
-- season are distinct canonical entities and their relationship is 6C
-- scope, not enforced here.
CREATE TABLE IF NOT EXISTS provider_season_mapping (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_season_id TEXT NOT NULL,
    season_id BIGINT NOT NULL
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT provider_season_mapping_source_external_key
        UNIQUE (source, external_season_id)
);
CREATE INDEX IF NOT EXISTS idx_provider_season_mapping_season
    ON provider_season_mapping(season_id);

-- 3. Seed rows with authoritative in-repository evidence ONLY.
-- Provenance: prediction_pipeline.py ODDS_API_LEAGUE_MAP explicitly maps
-- each internal league label to its The-Odds-API sport key, and
-- football_api_client.py FootballAPIClient fetches those sport keys live
-- (sports_to_fetch includes soccer_epl). Each seeded canonical code
-- exists in the 001 competitions seed. Targets resolve by code (never by
-- hardcoded BIGSERIAL id); ON CONFLICT DO NOTHING keeps seeding
-- idempotent and never overwrites an existing mapping.
INSERT INTO provider_competition_mapping (source, external_competition_id, competition_id)
SELECT 'odds-api', 'soccer_epl', id FROM competitions WHERE code = 'ENG-Premier League'
ON CONFLICT (source, external_competition_id) DO NOTHING;
INSERT INTO provider_competition_mapping (source, external_competition_id, competition_id)
SELECT 'odds-api', 'soccer_spain_la_liga', id FROM competitions WHERE code = 'ESP-La Liga'
ON CONFLICT (source, external_competition_id) DO NOTHING;
INSERT INTO provider_competition_mapping (source, external_competition_id, competition_id)
SELECT 'odds-api', 'soccer_germany_bundesliga', id FROM competitions WHERE code = 'GER-Bundesliga'
ON CONFLICT (source, external_competition_id) DO NOTHING;
INSERT INTO provider_competition_mapping (source, external_competition_id, competition_id)
SELECT 'odds-api', 'soccer_italy_serie_a', id FROM competitions WHERE code = 'ITA-Serie A'
ON CONFLICT (source, external_competition_id) DO NOTHING;
INSERT INTO provider_competition_mapping (source, external_competition_id, competition_id)
SELECT 'odds-api', 'soccer_france_ligue_one', id FROM competitions WHERE code = 'FRA-Ligue 1'
ON CONFLICT (source, external_competition_id) DO NOTHING;
-- Deliberately NOT seeded: ODDS_API_LEAGUE_MAP key 'INT-World Cup'
-- (-> soccer_fifa_world_cup) matches no seeded competitions.code
-- (001 seeds 'FIFA-World Cup'), so no authoritative link exists.
-- provider_season_mapping is deliberately left unseeded: the repository
-- holds no provider season IDs (pipeline CURRENT_SEASON '2425' is an
-- FBref season format, not a provider season identifier).

-- Verification queries (read-only):
-- SELECT source, external_competition_id, competition_id FROM provider_competition_mapping ORDER BY id;
-- SELECT source, external_season_id, season_id FROM provider_season_mapping ORDER BY id;
-- SELECT source, external_competition_id, COUNT(*) FROM provider_competition_mapping
--   GROUP BY source, external_competition_id HAVING COUNT(*) > 1;
-- SELECT source, external_season_id, COUNT(*) FROM provider_season_mapping
--   GROUP BY source, external_season_id HAVING COUNT(*) > 1;
-- SELECT m.source, m.external_competition_id FROM provider_competition_mapping m
--   LEFT JOIN competitions c ON c.id = m.competition_id WHERE c.id IS NULL;
-- SELECT m.source, m.external_season_id FROM provider_season_mapping m
--   LEFT JOIN seasons s ON s.id = m.season_id WHERE s.id IS NULL;
