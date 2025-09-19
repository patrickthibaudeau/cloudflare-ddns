from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv
from typing import List

ENV_LOADED = False


def load_env(path: str | None = None) -> None:
    global ENV_LOADED
    if ENV_LOADED:
        return
    load_dotenv(dotenv_path=path)  # will silently ignore if not exists
    ENV_LOADED = True


@dataclass
class Settings:
    # Auth: prefer API token over key/email
    api_token: str | None
    api_key: str | None
    email: str | None

    zone_name: str
    record_name: str
    record_type: str = "A"  # A or AAAA
    ttl: int = 300
    proxied: bool = False
    interval: int | None = None  # seconds; if None run once
    dry_run: bool = False

    @property
    def auth_headers(self) -> dict[str, str]:
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        if self.api_key and self.email:
            return {"X-Auth-Email": self.email, "X-Auth-Key": self.api_key}
        raise ValueError("No Cloudflare authentication provided. Set CLOUDFLARE_API_TOKEN or (CLOUDFLARE_EMAIL + CLOUDFLARE_API_KEY)")


def _parse_bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def load_settings(env_path: str | None = None) -> Settings:
    """Load a single Settings object (backwards compatible path).

    This function intentionally ignores CLOUDFLARE_ZONE_NAMES; callers
    that need multi-zone should use load_all_settings.
    """
    load_env(env_path)
    api_token = os.getenv("CLOUDFLARE_API_TOKEN") or None
    api_key = os.getenv("CLOUDFLARE_API_KEY") or None
    email = os.getenv("CLOUDFLARE_EMAIL") or None
    zone = os.getenv("CLOUDFLARE_ZONE_NAME") or ""
    record = os.getenv("CLOUDFLARE_RECORD_NAME") or zone
    record_type = os.getenv("CLOUDFLARE_RECORD_TYPE") or "A"
    ttl = int(os.getenv("CLOUDFLARE_TTL") or 300)
    proxied = _parse_bool(os.getenv("CLOUDFLARE_PROXIED"))
    interval_env = os.getenv("DDNS_INTERVAL") or None
    interval = int(interval_env) if interval_env else None
    dry_run = _parse_bool(os.getenv("DDNS_DRY_RUN"))

    if not zone:
        raise ValueError("CLOUDFLARE_ZONE_NAME is required")

    return Settings(
        api_token=api_token,
        api_key=api_key,
        email=email,
        zone_name=zone,
        record_name=record,
        record_type=record_type.upper(),
        ttl=ttl,
        proxied=proxied,
        interval=interval,
        dry_run=dry_run,
    )


def load_all_settings(env_path: str | None = None) -> list[Settings]:
    """Load potentially multiple Settings entries.

    Supports comma-separated environment variables:
    - CLOUDFLARE_ZONE_NAMES=zone1.com,zone2.net
    - CLOUDFLARE_RECORD_NAMES=host1.zone1.com,host2.zone2.net (optional)

    Fallback to single-zone variables if *_ZONE_NAMES not present.

    Enhancement: if only a single zone is specified (via CLOUDFLARE_ZONE_NAME) but
    multiple CLOUDFLARE_RECORD_NAMES are provided, replicate the zone for each
    record to allow multi-record updates within one zone.
    """
    load_env(env_path)
    api_token = os.getenv("CLOUDFLARE_API_TOKEN") or None
    api_key = os.getenv("CLOUDFLARE_API_KEY") or None
    email = os.getenv("CLOUDFLARE_EMAIL") or None

    zones = _split_csv(os.getenv("CLOUDFLARE_ZONE_NAMES"))
    single_zone = os.getenv("CLOUDFLARE_ZONE_NAME") or ""
    use_multi = len(zones) > 0

    if not use_multi:
        if not single_zone:
            raise ValueError("CLOUDFLARE_ZONE_NAME or CLOUDFLARE_ZONE_NAMES is required")
        zones = [single_zone]

    record_names_multi = _split_csv(os.getenv("CLOUDFLARE_RECORD_NAMES"))
    global_record_name = os.getenv("CLOUDFLARE_RECORD_NAME") or None

    record_type = (os.getenv("CLOUDFLARE_RECORD_TYPE") or "A").upper()
    ttl = int(os.getenv("CLOUDFLARE_TTL") or 300)
    proxied = _parse_bool(os.getenv("CLOUDFLARE_PROXIED"))
    interval_env = os.getenv("DDNS_INTERVAL") or None
    interval = int(interval_env) if interval_env else None
    dry_run = _parse_bool(os.getenv("DDNS_DRY_RUN"))

    if record_names_multi:
        if len(record_names_multi) != len(zones):
            # Allow special case: single zone replicated across multiple record names
            if len(zones) == 1:
                zones = zones * len(record_names_multi)
            else:
                raise ValueError("CLOUDFLARE_RECORD_NAMES length must match CLOUDFLARE_ZONE_NAMES length")
        record_names = record_names_multi
    else:
        # If a single global record name is provided, apply to all, else each zone defaults to itself
        if global_record_name:
            record_names = [global_record_name for _ in zones]
        else:
            record_names = zones[:]

    settings_list: list[Settings] = []
    for zone, record in zip(zones, record_names):
        settings_list.append(
            Settings(
                api_token=api_token,
                api_key=api_key,
                email=email,
                zone_name=zone,
                record_name=record,
                record_type=record_type,
                ttl=ttl,
                proxied=proxied,
                interval=interval,
                dry_run=dry_run,
            )
        )
    return settings_list
