"""Reviewed staging migrations for Phase 15J.

These migrations are explicitly staging-only and must NOT be applied to production.
They modify the staging database only and include strict guards.

Migration files:
  20261102000000_staging_profiles.sql
  20261102000100_staging_subscriptions.sql
  20261102000200_staging_teams.sql
