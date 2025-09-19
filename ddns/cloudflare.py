from __future__ import annotations
import requests
from typing import Any, Optional

API_BASE = "https://api.cloudflare.com/client/v4"

class CloudflareAPIError(RuntimeError):
    pass


def _handle(resp: requests.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
        raise
    if not data.get("success"):
        raise CloudflareAPIError(str(data.get("errors")))
    return data


def get_zone_id(headers: dict[str, str], zone_name: str) -> str:
    params = {"name": zone_name, "status": "active"}
    resp = requests.get(f"{API_BASE}/zones", headers=headers, params=params, timeout=15)
    data = _handle(resp)
    result = data.get("result", [])
    if not result:
        raise CloudflareAPIError(f"Zone not found: {zone_name}")
    return result[0]["id"]


def find_dns_record(headers: dict[str, str], zone_id: str, record_type: str, name: str) -> Optional[dict[str, Any]]:
    params = {"type": record_type.upper(), "name": name}
    resp = requests.get(f"{API_BASE}/zones/{zone_id}/dns_records", headers=headers, params=params, timeout=15)
    data = _handle(resp)
    result = data.get("result", [])
    if result:
        return result[0]
    return None


def create_dns_record(headers: dict[str, str], zone_id: str, record_type: str, name: str, content: str, ttl: int, proxied: bool) -> dict[str, Any]:
    payload = {
        "type": record_type.upper(),
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    resp = requests.post(f"{API_BASE}/zones/{zone_id}/dns_records", headers=headers, json=payload, timeout=15)
    data = _handle(resp)
    return data["result"]


def update_dns_record(headers: dict[str, str], zone_id: str, record_id: str, record_type: str, name: str, content: str, ttl: int, proxied: bool) -> dict[str, Any]:
    payload = {
        "type": record_type.upper(),
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    resp = requests.put(f"{API_BASE}/zones/{zone_id}/dns_records/{record_id}", headers=headers, json=payload, timeout=15)
    data = _handle(resp)
    return data["result"]

