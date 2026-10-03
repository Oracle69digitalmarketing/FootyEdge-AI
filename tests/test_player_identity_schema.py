"""Objective 7: player identity migration contract tests (offline only).

No network, no database, no live provider APIs, no production Supabase.
Validates the 005 migration statically: additive/tightening only, exact
table/column/constraint/index/RLS contract, zero seeds, idempotent guards.
"""
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_MIGRATION = _REPO / "supabase_migrations" / "005_player_identity.sql"
_MIRROR = (_REPO / "supabase" / "migrations"
           / "20261003000000_player_identity.sql")


def _code(sql: str) -> str:
    """Migration code without -- comments (docs may name out-of-scope items)."""
    return "\n".join(
        line for line in sql.splitlines()
        if not line.lstrip().startswith("--")
    )


def test_migration_mirror_is_identical():
    assert _MIRROR.exists()
    assert _MIGRATION.read_text() == _MIRROR.read_text()


def test_player_aliases_table_contract():
    sql = _MIGRATION.read_text()
    assert "CREATE TABLE IF NOT EXISTS player_aliases" in sql
    assert "player_id BIGINT NOT NULL" in sql
    assert "alias TEXT NOT NULL" in sql
    assert "source TEXT NOT NULL" in sql
    assert "valid_from DATE" in sql
    assert "valid_to DATE" in sql
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in sql
    assert "REFERENCES players(id)" in sql
    assert "ON DELETE CASCADE" in sql
    assert "player_aliases_alias_source_key" in sql
    assert "UNIQUE (alias, source)" in sql
    assert "idx_player_aliases_player" in sql
    assert "idx_player_aliases_alias" in sql
    assert "ALTER TABLE player_aliases ENABLE ROW LEVEL SECURITY" in sql


def test_mapping_tightening_contract():
    sql = _MIGRATION.read_text()
    assert ("ALTER TABLE player_identity_sources "
            "ALTER COLUMN player_id SET NOT NULL") in sql
    assert ("ALTER TABLE player_identity_sources "
            "ALTER COLUMN external_player_id SET NOT NULL") in sql
    # Fail-closed preconditions: abort loudly on unexpected violating rows.
    assert "WHERE player_id IS NULL" in sql
    assert "WHERE external_player_id IS NULL" in sql
    assert sql.count("RAISE EXCEPTION") >= 3  # 2 guards + 2 safety checks


def test_migration_is_additive_without_seeds_or_side_effects():
    sql = _MIGRATION.read_text()
    code = _code(sql)
    assert code.count("CREATE TABLE") == 1  # player_aliases only
    assert "INSERT INTO" not in code
    assert "external_id" not in code  # players.external_id untouched/unused
    assert "player_team_history" not in code  # relationship table untouched
    assert "statistics" not in code.lower()
    assert "appearance" not in code.lower()
    assert "lineup" not in code.lower()
    for forbidden in ("DROP TABLE", "DROP COLUMN", "DELETE FROM", "UPDATE "):
        assert forbidden not in code
    for untouched in ("ALTER TABLE players", "ALTER TABLE teams",
                      "ALTER TABLE competitions", "ALTER TABLE seasons",
                      "ALTER TABLE matches", "CREATE TABLE players",
                      "CREATE TABLE player_identity_sources",
                      "CREATE TABLE player_team_history"):
        assert untouched not in code


def test_no_6a_6d_table_definitions():
    sql = _MIGRATION.read_text()
    code = _code(sql)
    for table in ("team_identity_sources", "team_aliases",
                  "match_provider_identity", "provider_competition_mapping",
                  "provider_season_mapping", "competition_season",
                  "team_competition_season"):
        assert f"CREATE TABLE {table}" not in code
        assert f"ALTER TABLE {table}" not in code


def test_no_policies_added_to_identity_tables():
    sql = _MIGRATION.read_text()
    assert "CREATE POLICY" not in sql  # service_role-only posture preserved


def test_safety_preconditions_reference_live_tables():
    sql = _MIGRATION.read_text()
    assert "players" in sql and "player_identity_sources" in sql
    assert "information_schema.columns" in sql
