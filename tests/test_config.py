import os
import importlib
from ddns.config import load_settings


def test_load_settings_with_api_key(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_EMAIL", "user@example.com")
    monkeypatch.setenv("CLOUDFLARE_API_KEY", "abc123")
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAME", "example.com")
    settings = load_settings()
    assert settings.email == "user@example.com"
    assert settings.api_key == "abc123"
    assert settings.api_token is None
    headers = settings.auth_headers
    assert "X-Auth-Email" in headers and headers["X-Auth-Email"] == "user@example.com"
    assert headers["X-Auth-Key"] == "abc123"


def test_load_settings_with_api_token(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok123")
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAME", "example.com")
    # Clear other vars
    for k in ["CLOUDFLARE_EMAIL", "CLOUDFLARE_API_KEY"]:
        monkeypatch.delenv(k, raising=False)
    settings = load_settings()
    assert settings.api_token == "tok123"
    assert settings.api_key is None
    assert settings.email is None
    headers = settings.auth_headers
    assert headers["Authorization"].startswith("Bearer ")


def test_missing_zone_raises(monkeypatch):
    # Ensure missing
    for k in ["CLOUDFLARE_ZONE_NAME", "CLOUDFLARE_EMAIL", "CLOUDFLARE_API_KEY", "CLOUDFLARE_API_TOKEN"]:
        monkeypatch.delenv(k, raising=False)
    try:
        load_settings()
    except Exception as e:
        assert "CLOUDFLARE_ZONE_NAME" in str(e)
    else:  # pragma: no cover
        raise AssertionError("Expected exception not raised")

