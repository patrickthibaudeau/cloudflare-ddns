from ddns.updater import run_once
from ddns.config import Settings


class DummySettings(Settings):
    pass


def make_settings(**overrides):
    base = dict(
        api_token=None,
        api_key="k",
        email="e@example.com",
        zone_name="example.com",
        record_name="home.example.com",
        record_type="A",
        ttl=120,
        proxied=False,
        interval=None,
        dry_run=False,
    )
    base.update(overrides)
    return DummySettings(**base)


def test_run_once_create(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr("ddns.cloudflare.get_zone_id", lambda headers, zone: "zone123")
    monkeypatch.setattr("ddns.cloudflare.find_dns_record", lambda *a, **k: None)
    created = {}

    def fake_create(headers, zone_id, rt, name, content, ttl, proxied):
        created.update({"content": content, "id": "rec123"})
        return created

    monkeypatch.setattr("ddns.cloudflare.create_dns_record", fake_create)
    monkeypatch.setattr("ddns.ip.get_public_ip", lambda rt: "1.2.3.4")

    result = run_once(settings)
    assert result["action"] == "created"
    assert result["ip"] == "1.2.3.4"
    assert result["record_id"] == "rec123"


def test_run_once_update(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr("ddns.cloudflare.get_zone_id", lambda *a, **k: "zone123")
    monkeypatch.setattr("ddns.cloudflare.find_dns_record", lambda *a, **k: {"id": "rec1", "content": "1.1.1.1"})
    updated = {}

    def fake_update(headers, zone_id, rec_id, rt, name, content, ttl, proxied):
        updated.update({"id": rec_id, "content": content})
        return updated

    monkeypatch.setattr("ddns.cloudflare.update_dns_record", fake_update)
    monkeypatch.setattr("ddns.ip.get_public_ip", lambda rt: "2.2.2.2")

    result = run_once(settings)
    assert result["action"] == "updated"
    assert result["ip"] == "2.2.2.2"
    assert result["record_id"] == "rec1"


def test_run_once_noop_remote(monkeypatch):
    settings = make_settings()
    monkeypatch.setattr("ddns.cloudflare.get_zone_id", lambda *a, **k: "zone123")
    monkeypatch.setattr("ddns.cloudflare.find_dns_record", lambda *a, **k: {"id": "rec1", "content": "3.3.3.3"})
    monkeypatch.setattr("ddns.ip.get_public_ip", lambda rt: "3.3.3.3")
    result = run_once(settings)
    assert result["action"] == "noop"
    assert result["reason"] == "unchanged-remote"


def test_run_once_noop_cached(monkeypatch):
    settings = make_settings()
    # Should not call Cloudflare find if cached IP matches; but we allow calls; behavior returns noop with reason
    monkeypatch.setattr("ddns.ip.get_public_ip", lambda rt: "4.4.4.4")
    # Provide stubs anyway
    monkeypatch.setattr("ddns.cloudflare.get_zone_id", lambda *a, **k: "zone123")
    monkeypatch.setattr("ddns.cloudflare.find_dns_record", lambda *a, **k: {"id": "rec4", "content": "4.4.4.4"})
    result = run_once(settings, last_ip="4.4.4.4")
    assert result["action"] == "noop"
    assert result["reason"] == "unchanged-cached"


def test_run_once_dry_run_create(monkeypatch):
    settings = make_settings(dry_run=True)
    monkeypatch.setattr("ddns.cloudflare.get_zone_id", lambda *a, **k: "zone123")
    monkeypatch.setattr("ddns.cloudflare.find_dns_record", lambda *a, **k: None)
    monkeypatch.setattr("ddns.ip.get_public_ip", lambda rt: "5.5.5.5")
    result = run_once(settings)
    assert result["action"] == "create-skip-dry-run"


def test_run_once_dry_run_update(monkeypatch):
    settings = make_settings(dry_run=True)
    monkeypatch.setattr("ddns.cloudflare.get_zone_id", lambda *a, **k: "zone123")
    monkeypatch.setattr("ddns.cloudflare.find_dns_record", lambda *a, **k: {"id": "rec5", "content": "6.6.6.6"})
    monkeypatch.setattr("ddns.ip.get_public_ip", lambda rt: "7.7.7.7")
    result = run_once(settings)
    assert result["action"] == "update-skip-dry-run"

