-- ============================================
-- FootyEdge AI 005: Canonical player identity (Objective 7)
-- Run in Supabase SQL Editor AFTER 001_global_football_identity.sql.
-- Backward-compatible: only ADDs one alias table and tightens two
-- columns on EMPTY tables with fail-closed preconditions; never alters
-- existing tables, canonical IDs, 6A-6D identity data, or RLS posture.
-- Zero seeds, zero synthetic rows, zero fabricated provider IDs.
-- player_team_history is untouched (relationship table, not identity).
-- players.external_id is untouched and remains unused.
-- ============================================

-- Safety: the canonical FK target must exist. players.id is the
-- internally generated BIGSERIAL primary key (see supabase_schema.sql);
-- this migration does NOT alter players in any way and never assigns IDs.
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'players' AND column_name = 'id'
    ) THEN
        RAISE EXCEPTION '005 requires players(id) to exist; aborting.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'player_identity_sources' AND column_name = 'player_id'
    ) THEN
        RAISE EXCEPTION '005 requires player_identity_sources(player_id) to exist; aborting.';
    END IF;
END $$;

-- 1. Tighten player_identity_sources to the approved mapping contract:
-- player_id NOT NULL (no orphan mappings), external_player_id TEXT
-- NOT NULL (a mapping without an external ID is not a mapping).
-- Fail-closed preconditions: if the tables are unexpectedly populated
-- with violating rows, abort loudly instead of reinterpreting data.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM player_identity_sources WHERE player_id IS NULL) THEN
        RAISE EXCEPTION '005 refuses: player_identity_sources contains NULL player_id rows; manual review required.';
    END IF;
    IF EXISTS (SELECT 1 FROM player_identity_sources WHERE external_player_id IS NULL) THEN
        RAISE EXCEPTION '005 refuses: player_identity_sources contains NULL external_player_id rows; manual review required.';
    END IF;
END $$;
ALTER TABLE player_identity_sources ALTER COLUMN player_id SET NOT NULL;
ALTER TABLE player_identity_sources ALTER COLUMN external_player_id SET NOT NULL;

-- 2. Player aliases: evidence pointers to canonical players(id), never
-- identities. source is NOT NULL (no legacy alias data exists, so the
-- PostgreSQL NULL-uniqueness hole is closed for free): the UNIQUE grain
-- is exactly (alias, source). Validity windows are recorded evidence
-- only; no resolver may infer identity from dates.
CREATE TABLE IF NOT EXISTS player_aliases (
    id BIGSERIAL PRIMARY KEY,
    player_id BIGINT NOT NULL
        REFERENCES players(id)
        ON DELETE CASCADE,
    alias TEXT NOT NULL,
    source TEXT NOT NULL,
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT player_aliases_alias_source_key
        UNIQUE (alias, source)
);
CREATE INDEX IF NOT EXISTS idx_player_aliases_player
    ON player_aliases(player_id);
CREATE INDEX IF NOT EXISTS idx_player_aliases_alias
    ON player_aliases(alias);

-- RLS posture matches every 6A-6D identity table: enabled, zero policies
-- (service_role-only). Deliberately no public read policy here.
ALTER TABLE player_aliases ENABLE ROW LEVEL SECURITY;

-- 3. Seed policy: NO rows seeded. Production holds zero players, zero
-- mappings, zero aliases, zero history rows, and the repository holds no
-- provider player IDs; any seed would be fabricated identity (forbidden).

-- Verification queries (read-only):
-- SELECT id, name FROM players ORDER BY id;
-- SELECT player_id, source, external_player_id FROM player_identity_sources ORDER BY id;
-- SELECT player_id, alias, source FROM player_aliases ORDER BY id;
-- SELECT player_id, source, external_player_id, COUNT(*) FROM player_identity_sources
--   GROUP BY player_id, source, external_player_id HAVING COUNT(*) > 1;
-- SELECT alias, source, COUNT(*) FROM player_aliases
--   GROUP BY alias, source HAVING COUNT(*) > 1;
-- SELECT m.player_id FROM player_identity_sources m
--   LEFT JOIN players p ON p.id = m.player_id WHERE p.id IS NULL;
-- SELECT a.player_id FROM player_aliases a
--   LEFT JOIN players p ON p.id = a.player_id WHERE p.id IS NULL;
-- SELECT conname, contype FROM pg_constraint WHERE conrelid = 'player_aliases'::regclass;
