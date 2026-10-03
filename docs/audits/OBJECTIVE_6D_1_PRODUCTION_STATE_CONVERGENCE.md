# FootyEdge AI — Objective 6D.1
## Production State-Convergence Audit

Date: 2026-10-03 (UTC)
Environment: production (`FOOTYEDGE_ENV=production`, validated via `env_guard.validate_database_target()`)
Database: production Supabase project (hostname verified to match `FOOTYEDGE_SUPABASE_HOST` via the existing production environment guard; secret values withheld from this record)

This is a documentation/audit record only. No application code, production data,
database schema, migrations, tests, dependencies, or numerical behavior were
changed in order to produce it.

### Scope

Record that the Competition/Season Identity architecture represented by
migrations 003 (Objective 6B, provider competition/season mappings) and 004
(Objective 6C, competition-season membership) was independently verified
against production using read-only access. Distinguish throughout:

- Migration SQL exists and was reviewed, **from**
- Migration SQL was executed against production.

### Migration 003

Repository status: reviewed. Authoritative file
`supabase_migrations/003_provider_competition_mappings.sql`, byte-identical to
CLI mirror `supabase/migrations/20260930000200_provider_competition_mappings.sql`
(`diff` clean). Defines `provider_competition_mapping` (PK id,
FK→`competitions(id)` ON DELETE CASCADE, UNIQUE(source,
external_competition_id), index on competition_id) and
`provider_season_mapping` (PK id, FK→`seasons(id)` ON DELETE CASCADE,
UNIQUE(source, external_season_id), index on season_id), plus five idempotent
`odds-api` seed rows resolving targets by `WHERE code =` (never hardcoded IDs).
No season seeds. Additive only; no destructive statements.

Production execution status: NOT PERFORMED DURING OBJECTIVE 6D (see Migration
Execution Limitation below).

Production state: VERIFIED STATE-CONVERGED — production already satisfies the
intended schema/data contract of 003 (table presence, column shape, and the
exact five seed rows confirmed via read-only REST reads).

Verification: offline migration-contract tests (`tests/test_provider_mappings.py`,
17 passed) assert the SQL definitions statically; live reads confirmed the five
seed rows exactly, zero duplicate grains, zero orphan references.

### Migration 004

Repository status: reviewed. Authoritative file
`supabase_migrations/004_competition_season_membership.sql`, byte-identical to
CLI mirror `supabase/migrations/20260930000300_competition_season_membership.sql`
(`diff` clean). Defines `competition_season` (composite PRIMARY KEY
(competition_id, season_id), FKs→`competitions(id)`/`seasons(id)` ON DELETE
CASCADE). Zero seed rows by documented policy. Additive only; no provider,
team, or destructive logic.

Production execution status: NOT PERFORMED DURING OBJECTIVE 6D (see Migration
Execution Limitation below).

Production state: VERIFIED STATE-CONVERGED — production already satisfies the
intended schema/data contract of 004 (table present with composite-key shape;
zero rows, as the migration specifies).

Verification: offline migration-contract tests
(`tests/test_competition_season_membership.py`, 18 passed) assert the SQL
definitions statically; live reads confirmed table presence and zero rows.

### Production Counts

competitions: 7 — exactly ENG-Premier League (1), ESP-La Liga (2),
GER-Bundesliga (3), ITA-Serie A (4), FRA-Ligue 1 (5), UEFA-Champions League
(6), FIFA-World Cup (7). No competitions added.

seasons: 2 — exactly 2025/26 (1), 2024/25 (2).

provider_competition_mapping: 5 — exactly:
odds-api / soccer_epl → 1;
odds-api / soccer_spain_la_liga → 2;
odds-api / soccer_germany_bundesliga → 3;
odds-api / soccer_italy_serie_a → 4;
odds-api / soccer_france_ligue_one → 5.
Note: the fifth external ID is `soccer_france_ligue_one` in both production
and the repository SQL seed. It is recorded here verbatim as observed, not
corrected to any alternative spelling.

provider_season_mapping: 0 (no provider season IDs fabricated).

competition_season: 0 (absence is intentional; no membership invented).

team_competition_season: 0 (no memberships seeded to make tests pass).

match_provider_identity: 0 rows (table present; untouched by this objective).

teams: 6 rows, all canonical identity values.

legacy_team_ids: 0 (no regression of the completed team identity migration).

orphan mappings: 0. duplicate provider mappings: 0.

### Application Contract

Verified against live production data using the unchanged resolver
(`competition_provenance.py`); production rows were only read, never written
(row counts before/after: 5/0/0, unchanged):

canonical resolution: OK — `ENG-Premier League` → (1, `ENG-Premier League`).

provider resolution: OK — `odds-api` / `soccer_epl` → (1, `ENG-Premier League`).

unknown provider: fails closed — `soccer_unknown_xyz` raised
`UnknownCompetitionIdentityError`.

unknown season: fails closed — label `1999/00` raised
`UnknownCompetitionIdentityError`.

missing membership: fails closed — valid canonical pair with empty live
membership raised `UnknownCompetitionIdentityError`.

conflict handling: OK — synthetic divergent in-memory rows (production
untouched; nothing inserted) raised `CompetitionIdentityConflictError`.

fuzzy matching: none — `ENG-PremierLeague` raised
`UnknownCompetitionIdentityError`.

automatic creation: none — the resolver is read-only (covered by the 6A
read-only/determinism tests; no writes observed).

silent fallback: none — every unknown path raised rather than guessing.

### Test Evidence

6A: 21 passed (`tests/test_competition_provenance.py`).

6B: 17 passed (`tests/test_provider_mappings.py`).

6C: 18 passed (`tests/test_competition_season_membership.py`).

Combined: 56 passed.

Broader runnable suite: 327 passed (`pytest -q
--ignore=tests/test_goal_distribution.py`).

Full-suite limitation: `pytest -q` cannot complete collection because
`tests/test_goal_distribution.py` fails at import with
`ModuleNotFoundError: No module named 'scipy'` (from `from scipy.stats import
poisson` in `agents/goal_distribution_agent.py`). This is an
environment/dependency collection limitation, not a test failure. No
dependencies were installed or altered during 6D.1.

### Constraint Verification

Verified: table existence; expected columns (via successful column-scoped
selects); expected nullability where observable through returned row shapes;
expected row grain (single-row-per-(source, external id) confirmed, zero
duplicate grains in live data); FK target integrity through live references
(zero orphans against live `competitions`/`seasons` IDs); provider mapping
uniqueness through live data; static SQL contract through the offline 6B/6C
migration tests.

Not directly verified: PostgreSQL `pg_catalog` constraint metadata (not
exposable through the read-only PostgREST interface); live CASCADE execution
(deliberately not test-fired; destructive testing is forbidden). The migration
SQL and its offline tests establish the intended FK/CASCADE definitions, while
live PostgREST verification establishes the observable production state.

### Numerical Invariance

`calculate_stake(0.6, 2.0) == 5.0` confirmed (`agents/kelly_agent.py`,
`test_kelly_agent.py` 4 passed). Objective 6D.1 touched no Poisson, Elo, ML,
hybrid probability, EV, Kelly, staking, value-bet selection, or LLM
explanation logic; the only file created by 6D.1 is this audit record.

### Migration Execution Limitation

003 migration execution: NOT PERFORMED DURING OBJECTIVE 6D.
004 migration execution: NOT PERFORMED DURING OBJECTIVE 6D.

Reason: no approved DDL execution channel was available. Available production
access was read-only/PostgREST. No psql, Supabase CLI, database password,
access token, project ref, or equivalent approved DDL channel was available in
the execution environment (all verified absent). No workaround was improvised,
per the objective guardrails.

Production was verified to already be equivalent to the intended state of
migrations 003 and 004. No DDL execution was performed during Objective 6D
because the available production interface was read-only/PostgREST.

No fresh database backup was created during 6D/6D.1; backup availability was
established instead (in-repo `backup_manager.py` / `restore_backup.py`, a
previously recorded snapshot artifact verified parseable, and fresh read
readability proven by the verification reads above). No destructive operations
were performed, so no restore was required.

### Final Status

Production is state-converged with migrations 003 and 004 as defined in the
repository. No schema, data, code, migration, test, dependency, or numerical
change was made by this audit. No commit. No push.
