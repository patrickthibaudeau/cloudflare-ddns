from __future__ import annotations
import time
from typing import Callable, Any, Optional

from .config import Settings
from . import cloudflare

Result = dict[str, Any]


def run_once(settings: Settings, last_ip: str | None = None, ip_getter: Callable[[str], str] | None = None) -> Result:
    """Run a single update cycle.

    Returns a result dict with keys: action (created|updated|noop), ip, record_id (if known).
    ip_getter is optional to simplify testing; if None it's resolved at call time so monkeypatching works.
    """
    if ip_getter is None:
        from .ip import get_public_ip as _get_public_ip  # local import so tests can patch ddns.ip.get_public_ip
        ip_getter = _get_public_ip

    current_ip = ip_getter(settings.record_type)

    # Short-circuit if IP unchanged (when last_ip provided)
    if last_ip and last_ip == current_ip:
        return {"action": "noop", "ip": current_ip, "reason": "unchanged-cached"}

    zone_id = cloudflare.get_zone_id(settings.auth_headers, settings.zone_name)
    record = cloudflare.find_dns_record(settings.auth_headers, zone_id, settings.record_type, settings.record_name)

    if record:
        if record.get("content") == current_ip:
            return {"action": "noop", "ip": current_ip, "record_id": record.get("id"), "reason": "unchanged-remote"}
        if settings.dry_run:
            return {"action": "update-skip-dry-run", "ip": current_ip, "record_id": record.get("id")}
        updated = cloudflare.update_dns_record(
            settings.auth_headers,
            zone_id,
            record["id"],
            settings.record_type,
            settings.record_name,
            current_ip,
            settings.ttl,
            settings.proxied,
        )
        return {"action": "updated", "ip": current_ip, "record_id": updated.get("id")}
    else:
        if settings.dry_run:
            return {"action": "create-skip-dry-run", "ip": current_ip}
        created = cloudflare.create_dns_record(
            settings.auth_headers,
            zone_id,
            settings.record_type,
            settings.record_name,
            current_ip,
            settings.ttl,
            settings.proxied,
        )
        return {"action": "created", "ip": current_ip, "record_id": created.get("id")}


def run_loop(settings: Settings, sleep_fn: Callable[[int], None] = time.sleep, ip_getter: Callable[[str], str] | None = None) -> None:
    if not settings.interval:
        run_once(settings, ip_getter=ip_getter)
        return
    last_ip: Optional[str] = None
    while True:  # pragma: no cover - loop control tested indirectly
        try:
            result = run_once(settings, last_ip=last_ip, ip_getter=ip_getter)
            last_ip = result.get("ip")
        except Exception:  # log & continue; simplistic handling
            pass
        sleep_fn(settings.interval)
