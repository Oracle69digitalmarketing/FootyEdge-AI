"""Environment Guard v1 tests (15 tests). Stdlib-only; no network/DB."""

import os

import pytest

from env_guard import (
    EnvGuardError,
    get_environment,
    require_destructive_approval,
    validate_database_target,
)

ENV_VARS = (
    "FOOTYEDGE_ENV",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "FOOTYEDGE_SUPABASE_HOST",
    "FOOTYEDGE_CONFIRM_PRODUCTION",
)

HOST = "xyzcompany.supabase.co"
URL = f"https://{HOST}"
KEY = "test-service-key"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _set_valid(monkeypatch, environment="staging", confirm=False):
    monkeypatch.setenv("FOOTYEDGE_ENV", environment)
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", KEY)
    monkeypatch.setenv("FOOTYEDGE_SUPABASE_HOST", HOST)
    if confirm:
        monkeypatch.setenv("FOOTYEDGE_CONFIRM_PRODUCTION", confirm)


def test_missing_environment(monkeypatch):
    _set_valid(monkeypatch)
    monkeypatch.delenv("FOOTYEDGE_ENV", raising=False)
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_invalid_environment(monkeypatch):
    _set_valid(monkeypatch, environment="qa")
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_missing_url(monkeypatch):
    _set_valid(monkeypatch)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_missing_service_key(monkeypatch):
    _set_valid(monkeypatch)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_missing_expected_host(monkeypatch):
    _set_valid(monkeypatch)
    monkeypatch.delenv("FOOTYEDGE_SUPABASE_HOST", raising=False)
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_malformed_url(monkeypatch):
    _set_valid(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", ":::not a url:::")
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_hostname_mismatch(monkeypatch):
    _set_valid(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://other.supabase.co")
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_matching_host_success(monkeypatch):
    _set_valid(monkeypatch, environment="staging")
    # Case-insensitive match must also succeed.
    monkeypatch.setenv("FOOTYEDGE_SUPABASE_HOST", HOST.upper())
    assert get_environment() == "staging"
    assert validate_database_target() == "staging"
    context = require_destructive_approval("cleanup")
    assert context == "staging"


def test_staging_destructive_approval(monkeypatch):
    _set_valid(monkeypatch, environment="staging")
    context = require_destructive_approval("cleanup")
    assert context == "staging"


def test_development_destructive_approval(monkeypatch):
    _set_valid(monkeypatch, environment="development")
    context = require_destructive_approval("restore")
    assert context == "development"


def test_production_without_confirmation(monkeypatch):
    _set_valid(monkeypatch, environment="production")
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_production_with_wrong_confirmation(monkeypatch):
    _set_valid(monkeypatch, environment="production", confirm="restore")
    with pytest.raises(EnvGuardError):
        require_destructive_approval("cleanup")


def test_production_with_correct_confirmation(monkeypatch):
    _set_valid(monkeypatch, environment="production", confirm="cleanup")
    context = require_destructive_approval("cleanup")
    assert context == "production"


def test_error_message_credential_secrecy(monkeypatch):
    sentinel = "SECRET_SENTINEL_7f3a9c2e"
    _set_valid(monkeypatch, environment="production")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", sentinel)
    with pytest.raises(EnvGuardError) as excinfo:
        require_destructive_approval("cleanup")
    assert sentinel not in str(excinfo.value)
    monkeypatch.setenv("SUPABASE_URL", "https://other.supabase.co")
    with pytest.raises(EnvGuardError) as excinfo2:
        require_destructive_approval("cleanup")
    assert sentinel not in str(excinfo2.value)


def test_cross_operation_confirmation_isolation(monkeypatch):
    _set_valid(monkeypatch, environment="production", confirm="cleanup")
    require_destructive_approval("cleanup")
    with pytest.raises(EnvGuardError):
        require_destructive_approval("restore")
    assert os.environ.get("FOOTYEDGE_CONFIRM_PRODUCTION") == "cleanup"
