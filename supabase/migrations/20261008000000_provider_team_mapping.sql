-- ============================================
-- FootyEdge AI API-Football team mapping (Objective 10.2C.2).
--
-- Mirrors provider_competition_mapping for teams: answers "which
-- canonical teams.id does this API-Football team ID represent?"
-- External IDs are TEXT identifiers stored verbatim (never cast,
-- hashed, or inferred from names). Unique grain is
-- (source, external_team_id). No RLS/policies/grants are declared here,
-- matching the competition-mapping tables: only the table owner and
-- service_role can touch mapping rows; player sync writes use the
-- service-role server client.
-- Deliberately unseeded: the repository holds no verified API-Football
-- team IDs (see 10.2C.1 precedent: seed only with in-repository
-- evidence). Mapping rows are inserted only after live API verification
-- of each canonical team's provider ID. ON CONFLICT DO NOTHING keeps any
-- future seeding idempotent and never overwrites an existing mapping.
-- ============================================

CREATE TABLE IF NOT EXISTS provider_team_mapping (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_team_id TEXT NOT NULL,
    team_id BIGINT NOT NULL
        REFERENCES teams(id)
        ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT provider_team_mapping_source_external_key
        UNIQUE (source, external_team_id)
);
CREATE INDEX IF NOT EXISTS idx_provider_team_mapping_team
    ON provider_team_mapping(team_id);

-- Verification queries (read-only):
-- SELECT source, external_team_id, team_id FROM provider_team_mapping ORDER BY id;
-- SELECT source, external_team_id, COUNT(*) FROM provider_team_mapping
--   GROUP BY source, external_team_id HAVING COUNT(*) > 1;
-- SELECT m.source, m.external_team_id FROM provider_team_mapping m
--   LEFT JOIN teams t ON t.id = m.team_id WHERE t.id IS NULL;
