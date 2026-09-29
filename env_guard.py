"""Minimal Environment-Safety Boundary (Environment Guard v1).

Stdlib-only. Validates that destructive operations (cleanup / restore)
and the admin full-sync endpoint only ever target the expected Supabase
database for the declared environment. Never exposes SUPABASE_SERVICE_KEY.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

ALLOWED_ENVIRONMENTS = frozenset({"production", "staging", "development"})
DESTRUCTIVE_OPERATIONS = frozenset({"cleanup", "restore"})

ENV_VAR = "FOOTYEDGE_ENV"
URL_VAR = "SUPABASE_URL"
KEY_VAR = "SUPABASE_SERVICE_KEY"
HOST_VAR = "FOOTYEDGE_SUPABASE_HOST"
CONFIRM_VAR = "FOOTYEDGE_CONFIRM_PRODUCTION"


class EnvGuardError(Exception):
    """Raised when environment-safety validation refuses an operation."""


def _read(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def get_environment() -> str:
    """Read and validate FOOTYEDGE_ENV. Returns the validated environment string."""
    environment = _read(ENV_VAR)
    if environment is None:
        raise EnvGuardError(f"Missing required environment variable: {ENV_VAR}.")
    if environment not in ALLOWED_ENVIRONMENTS:
        raise EnvGuardError(
            f"Invalid {ENV_VAR}={environment!r}. "
            "Expected one of: development, production, staging."
        )
    return environment


def validate_database_target() -> str:
    """Validate the database target for the current environment.

    Returns the validated environment string. Never returns the service key.
    """
    environment = get_environment()

    url = _read(URL_VAR)
    if url is None:
        raise EnvGuardError(f"Missing required environment variable: {URL_VAR}.")

    if _read(KEY_VAR) is None:
        raise EnvGuardError(f"Missing required environment variable: {KEY_VAR}.")

    expected_host = _read(HOST_VAR)
    if expected_host is None:
        raise EnvGuardError(f"Missing required environment variable: {HOST_VAR}.")

    try:
        parsed = urlsplit(url)
    except Exception:
        raise EnvGuardError(f"Malformed {URL_VAR}: URL is not parseable.")

    hostname = parsed.hostname
    if not hostname:
        raise EnvGuardError(f"Malformed {URL_VAR}: URL has no hostname.")

    if hostname.lower() != expected_host.lower():
        raise EnvGuardError(
            f"{URL_VAR} hostname {hostname!r} does not match "
            f"{HOST_VAR} {expected_host!r}."
        )

    return environment


def require_destructive_approval(operation: str) -> str:
    """Validate target, then enforce production confirmation scoping.

    Returns the validated environment string.
    """
    if operation not in DESTRUCTIVE_OPERATIONS:
        raise EnvGuardError(f"Unknown destructive operation: {operation!r}.")

    environment = validate_database_target()

    if environment == "production":
        confirmation = _read(CONFIRM_VAR)
        if confirmation != operation:
            raise EnvGuardError(
                f"Production {operation!r} requires "
                f"{CONFIRM_VAR}={operation!r}."
            )

    return environment


__all__ = [
    "ALLOWED_ENVIRONMENTS",
    "DESTRUCTIVE_OPERATIONS",
    "EnvGuardError",
    "get_environment",
    "require_destructive_approval",
    "validate_database_target",
]
