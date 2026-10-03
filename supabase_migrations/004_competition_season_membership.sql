-- ============================================
-- FootyEdge AI 004: Canonical competition-season membership (Objective 6C)
-- Run in Supabase SQL Editor AFTER 001_global_football_identity.sql.
-- Backward-compatible: only ADDs one membership table; never alters
-- existing tables, canonical IDs, provider mappings, or identity data.
-- No provider-specific logic, no team membership logic here.
-- ============================================

-- Safety: the canonical FK targets must exist (see 001). This migration
-- does NOT alter competitions or seasons in any way.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'competitions' AND column_name = 'id'
    ) THEN
        RAISE EXCEPTION '004 requires competitions(id) to exist; aborting.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'seasons' AND column_name = 'id'
    ) THEN
        RAISE EXCEPTION '004 requires seasons(id) to exist; aborting.';
    END IF;
END $$;

-- Canonical competition-season membership: explicit pairing of a canonical
-- competition with a canonical season. This is NOT team_competition_season
-- (which records a team's participation); it records that the pairing
-- itself is a valid canonical identity. Composite primary key follows the
-- team_competition_season precedent and enforces pair uniqueness plus
-- NOT NULL on both columns. Membership references nonexistent canonical
-- records are rejected by the foreign keys.
CREATE TABLE IF NOT EXISTS competition_season (
    competition_id BIGINT NOT NULL
        REFERENCES competitions(id)
        ON DELETE CASCADE,
    season_id BIGINT NOT NULL
        REFERENCES seasons(id)
        ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (competition_id, season_id)
);

-- Seed policy: NO rows seeded. Each candidate pair was inspected and
-- rejected for lack of authoritative repository evidence:
-- - '<pipeline league> x 2024/25': pipeline CURRENT_SEASON '2425' is an
--   FBref season format with no in-repo link to canonical label
--   '2024/25'; mapping it would be season-label inference (forbidden).
-- - '<pipeline league> x 2025/26': no in-repo evidence the pipeline (or
--   any provider feed) operated those leagues in that season.
-- - 'INT-World Cup' / 'INT-Euro' x any season: neither is a seeded
--   competitions.code; mapping would invent canonical identity.
-- - 'UEFA-Champions League' / 'FIFA-World Cup' x any season: seeded as
--   competitions but with no in-repo evidence of operation in a seeded
--   season.
-- - Full Cartesian (7 x 2): guessed coverage (forbidden).
-- - Provider mappings (003) must not create membership implicitly.
-- Membership rows are therefore left for future evidenced registration
-- (6D/production operations), inserted explicitly, never inferred.

-- Verification queries (read-only):
-- SELECT competition_id, season_id FROM competition_season ORDER BY competition_id, season_id;
-- SELECT competition_id, season_id, COUNT(*) FROM competition_season
--   GROUP BY competition_id, season_id HAVING COUNT(*) > 1;
-- SELECT m.competition_id, m.season_id FROM competition_season m
--   LEFT JOIN competitions c ON c.id = m.competition_id
--   LEFT JOIN seasons s ON s.id = m.season_id
--   WHERE c.id IS NULL OR s.id IS NULL;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'competition_season'::regclass;
