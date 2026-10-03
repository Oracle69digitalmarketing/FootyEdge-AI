-- ============================================
-- FootyEdge AI 002: Odds API fixture provenance
-- Run in Supabase SQL Editor AFTER 001_global_football_identity.sql.
-- Backward-compatible: only ADDs one table/index, never alters or
-- rebuilds existing tables, rows, or identity data.
-- ============================================

-- Safety: the FK target must exist. matches.id is the internally
-- generated BIGSERIAL primary key (see supabase_schema.sql); this
-- migration does NOT alter matches in any way.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'matches' AND column_name = 'id'
    ) THEN
        RAISE EXCEPTION '002 requires matches(id) to exist; aborting.';
    END IF;
END $$;

-- Separate fixture identity namespace. A provider event (e.g. an Odds
-- API event id) is a FIXTURE identifier and must never be stored as
-- teams.id or team_identity_sources.external_team_id. external_match_id
-- is TEXT and is stored verbatim: never cast to integer, never hashed,
-- never normalized into another identifier. The unique grain is
-- (source, external_match_id) so the same raw event string under two
-- providers remains independently representable.
CREATE TABLE IF NOT EXISTS match_provider_identity (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL
        REFERENCES matches(id)
        ON DELETE CASCADE,
    source TEXT NOT NULL,
    external_match_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT match_provider_identity_source_external_key
        UNIQUE (source, external_match_id)
);

CREATE INDEX IF NOT EXISTS idx_match_provider_identity_match_id
    ON match_provider_identity(match_id);

-- Verification queries (read-only; second query must return zero rows):
-- SELECT source, external_match_id, match_id FROM match_provider_identity ORDER BY id;
-- SELECT source, external_match_id, COUNT(*) FROM match_provider_identity
--   GROUP BY source, external_match_id HAVING COUNT(*) > 1;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'match_provider_identity'::regclass;
