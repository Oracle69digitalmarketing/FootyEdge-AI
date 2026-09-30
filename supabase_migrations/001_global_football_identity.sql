-- ============================================
-- FootyEdge AI 001: Global football identity architecture
-- Run in Supabase SQL Editor AFTER the team-ID DML migration.
-- Backward-compatible: only ADDs tables/columns/constraints, never drops.
-- ============================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Provider -> canonical team mapping (external IDs preserved, never PK).
CREATE TABLE IF NOT EXISTS team_identity_sources (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_team_id TEXT,
    external_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, external_team_id)
);
CREATE INDEX IF NOT EXISTS idx_team_identity_sources_team ON team_identity_sources(team_id);
CREATE INDEX IF NOT EXISTS idx_team_identity_sources_name ON team_identity_sources(external_name);

-- 2. Evidence-based aliases (validity window optional).
CREATE TABLE IF NOT EXISTS team_aliases (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    source TEXT,
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (alias, source)
);
CREATE INDEX IF NOT EXISTS idx_team_aliases_team ON team_aliases(team_id);
CREATE INDEX IF NOT EXISTS idx_team_aliases_alias ON team_aliases(alias);

-- 3. Competition / season (competition-agnostic, season-aware).
CREATE TABLE IF NOT EXISTS competitions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    comp_type TEXT NOT NULL DEFAULT 'domestic_league',
    country TEXT,
    gender TEXT NOT NULL DEFAULT 'men',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seasons (
    id BIGSERIAL PRIMARY KEY,
    label TEXT UNIQUE NOT NULL,
    start_year INT,
    end_year INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Team membership per competition+season (never encoded in teams.id).
CREATE TABLE IF NOT EXISTS team_competition_season (
    team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    competition_id BIGINT NOT NULL REFERENCES competitions(id) ON DELETE CASCADE,
    season_id BIGINT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (team_id, competition_id, season_id)
);

-- Seed a minimal competition/season registry (idempotent).
INSERT INTO competitions (code, name, comp_type, country) VALUES
    ('ENG-Premier League','Premier League','domestic_league','England'),
    ('ESP-La Liga','La Liga','domestic_league','Spain'),
    ('GER-Bundesliga','Bundesliga','domestic_league','Germany'),
    ('ITA-Serie A','Serie A','domestic_league','Italy'),
    ('FRA-Ligue 1','Ligue 1','domestic_league','France'),
    ('UEFA-Champions League','Champions League','continental','Europe'),
    ('FIFA-World Cup','World Cup','international','International')
ON CONFLICT (code) DO NOTHING;

INSERT INTO seasons (label, start_year, end_year) VALUES
    ('2025/26', 2025, 2026),
    ('2024/25', 2024, 2025)
ON CONFLICT (label) DO NOTHING;

-- 4. Player identity readiness (minimal evolution; no bulk import here).
CREATE TABLE IF NOT EXISTS player_identity_sources (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT REFERENCES players(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_player_id TEXT,
    external_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, external_player_id)
);
CREATE INDEX IF NOT EXISTS idx_player_sources_player ON player_identity_sources(player_id);

CREATE TABLE IF NOT EXISTS player_team_history (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    team_id BIGINT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    competition_id BIGINT REFERENCES competitions(id),
    season_id BIGINT REFERENCES seasons(id),
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_player_history_player ON player_team_history(player_id);
CREATE INDEX IF NOT EXISTS idx_player_history_team ON player_team_history(team_id);

-- 5. value_bets reconciliation: add nullable match/prediction links.
-- Prod currently has neither column; repo expects prediction_id.
ALTER TABLE value_bets ADD COLUMN IF NOT EXISTS match_id BIGINT;
ALTER TABLE value_bets ADD COLUMN IF NOT EXISTS prediction_id BIGINT;
ALTER TABLE value_bets ADD COLUMN IF NOT EXISTS our_probability FLOAT;
ALTER TABLE value_bets ADD COLUMN IF NOT EXISTS opening_odds FLOAT;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'value_bets_match_id_fkey') THEN
        ALTER TABLE value_bets ADD CONSTRAINT value_bets_match_id_fkey
        FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'value_bets_prediction_id_fkey') THEN
        ALTER TABLE value_bets ADD CONSTRAINT value_bets_prediction_id_fkey
        FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE CASCADE NOT VALID;
    END IF;
END $$;

-- 6. Enforce match linkage where orphans are already clean (NULL allowed).
-- predictions.match_id currently plain BIGINT; validate orphans first:
-- SELECT id FROM predictions WHERE match_id IS NOT NULL AND match_id NOT IN (SELECT id FROM matches);
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'predictions_match_id_fkey') THEN
        ALTER TABLE predictions ADD CONSTRAINT predictions_match_id_fkey
        FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL NOT VALID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_bets_match_id_fkey') THEN
        ALTER TABLE user_bets ADD CONSTRAINT user_bets_match_id_fkey
        FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL NOT VALID;
    END IF;
END $$;

-- 7. Canonical team invariant guard (reject legacy IDs on future writes).
CREATE OR REPLACE FUNCTION public.assert_canonical_team_id()
RETURNS TRIGGER AS $$
DECLARE
    expected BIGINT;
BEGIN
    expected := ('x' || substring(encode(digest(trim(regexp_replace(NEW.name, '\s+', ' ', 'g')), 'sha256'), 'hex') FOR 12))::bit(48)::bigint;
    IF NEW.id <> expected THEN
        RAISE EXCEPTION 'teams.id % does not equal canonical SHA-256/12-hex % for name %', NEW.id, expected, NEW.name;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- NOTE: trigger intentionally NOT enabled yet; enable only after DML migration verified:
-- DROP TRIGGER IF EXISTS trg_canonical_team_id ON teams;
-- CREATE TRIGGER trg_canonical_team_id BEFORE INSERT OR UPDATE ON teams
-- FOR EACH ROW EXECUTE FUNCTION public.assert_canonical_team_id();

-- Verification queries (run read-only after migration):
-- SELECT id, name FROM teams ORDER BY id;
-- SELECT COUNT(*) FROM teams WHERE id IN (101,102,103,104,105,106,10001,10002,10003,10004);
-- SELECT m.id FROM matches m LEFT JOIN teams h ON h.id=m.home_team_id LEFT JOIN teams a ON a.id=m.away_team_id WHERE h.id IS NULL OR a.id IS NULL;
-- SELECT id FROM predictions WHERE match_id IS NOT NULL AND match_id NOT IN (SELECT id FROM matches);
