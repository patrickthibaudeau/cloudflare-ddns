from __future__ import annotations
import re
import requests
from typing import Iterable

_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
# Basic IPv6 validation (compressed forms included)
_IPV6_RE = re.compile(r"^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$")

_DEFAULT_IPV4_ENDPOINTS = [
    "https://ipv4.icanhazip.com/",
    "https://api.ipify.org/",
    "https://checkip.amazonaws.com/",
]
_DEFAULT_IPV6_ENDPOINTS = [
    "https://ipv6.icanhazip.com/",
    "https://api64.ipify.org/",
]

class IPDetectionError(RuntimeError):
    pass


def _query(endpoints: Iterable[str]) -> str:
    last_err: Exception | None = None
    for url in endpoints:
        try:
            resp = requests.get(url, timeout=5)
            if resp.ok:
                return resp.text.strip()
        except Exception as e:  # pragma: no cover - network errors
            last_err = e
            continue
    raise IPDetectionError(f"Unable to detect IP. Last error: {last_err}")


def get_public_ip(record_type: str) -> str:
    rt = record_type.upper()
    if rt == "A":
        ip = _query(_DEFAULT_IPV4_ENDPOINTS)
        if not _IPV4_RE.match(ip):
            raise IPDetectionError(f"Invalid IPv4 detected: {ip}")
        return ip
    elif rt == "AAAA":
        ip = _query(_DEFAULT_IPV6_ENDPOINTS)
        # IPv6 regex is intentionally loose; additional validation could be added
        if not _IPV6_RE.match(ip):
            raise IPDetectionError(f"Invalid IPv6 detected: {ip}")
        return ip
    else:
        raise ValueError(f"Unsupported record type: {record_type}")

