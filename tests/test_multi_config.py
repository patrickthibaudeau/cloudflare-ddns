import pytest
from ddns.config import load_all_settings


def _clear(monkeypatch):
    for k in [
        "CLOUDFLARE_ZONE_NAME",
        "CLOUDFLARE_ZONE_NAMES",
        "CLOUDFLARE_RECORD_NAME",
        "CLOUDFLARE_RECORD_NAMES",
    ]:
        monkeypatch.delenv(k, raising=False)


def test_load_all_settings_multi_defaults(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAMES", "example.com, example.net")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    settings_list = load_all_settings()
    assert len(settings_list) == 2
    zones = [s.zone_name for s in settings_list]
    records = [s.record_name for s in settings_list]
    assert zones == ["example.com", "example.net"]
    # Without record overrides each record defaults to its zone
    assert records == zones
    assert all(s.record_type == "A" for s in settings_list)


def test_load_all_settings_multi_with_global_record(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAMES", "alpha.com,beta.org")
    monkeypatch.setenv("CLOUDFLARE_RECORD_NAME", "dyn.example")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    settings_list = load_all_settings()
    assert [s.record_name for s in settings_list] == ["dyn.example", "dyn.example"]


def test_load_all_settings_multi_with_record_names_list(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAMES", "z1.com,z2.com")
    monkeypatch.setenv("CLOUDFLARE_RECORD_NAMES", "host1.z1.com,host2.z2.com")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    settings_list = load_all_settings()
    assert [s.record_name for s in settings_list] == ["host1.z1.com", "host2.z2.com"]


def test_load_all_settings_record_names_mismatch(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAMES", "a.com,b.com")
    monkeypatch.setenv("CLOUDFLARE_RECORD_NAMES", "one.a.com")  # mismatch length
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    with pytest.raises(ValueError):
        load_all_settings()


def test_single_zone_multi_record_names(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("CLOUDFLARE_ZONE_NAME", "solo.com")
    monkeypatch.setenv("CLOUDFLARE_RECORD_NAMES", "solo.com,host1.solo.com,host2.solo.com")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    settings_list = load_all_settings()
    assert len(settings_list) == 3
    # All zones should replicate the single zone name
    assert all(s.zone_name == "solo.com" for s in settings_list)
    assert [s.record_name for s in settings_list] == ["solo.com", "host1.solo.com", "host2.solo.com"]
