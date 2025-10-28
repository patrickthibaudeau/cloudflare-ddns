from __future__ import annotations
import argparse
import sys
import time
from typing import List, Tuple, Dict
from .config import load_settings, load_all_settings, Settings
from .updater import run_once, run_loop


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cloudflare DDNS Updater")
    p.add_argument("--env", dest="env_path", help="Path to .env file", default=None)
    # Single zone overrides (backwards compatible)
    p.add_argument("--zone", dest="zone_name", help="Override zone name")
    p.add_argument("--record", dest="record_name", help="Override record name (defaults to zone)")
    # Multi-zone CSV overrides
    p.add_argument("--zones", dest="zones_csv", help="Comma-separated list of zones (overrides env zones)")
    p.add_argument("--records", dest="records_csv", help="Comma-separated list of record names (match zones order)")
    p.add_argument("--type", dest="record_type", help="Record type A or AAAA")
    p.add_argument("--ttl", dest="ttl", type=int, help="TTL (default from env or 300)")
    p.add_argument("--proxied", dest="proxied", action="store_true", help="Enable Cloudflare proxy")
    p.add_argument("--no-proxied", dest="proxied", action="store_false", help="Disable Cloudflare proxy")
    p.set_defaults(proxied=None)
    p.add_argument("--interval", dest="interval", type=int, help="Loop interval seconds (omit to run once)")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="Do not apply changes")
    p.add_argument("--once", dest="force_once", action="store_true", help="Force single run even if interval env set")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    return p


def _apply_single_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    return Settings(
        api_token=settings.api_token,
        api_key=settings.api_key,
        email=settings.email,
        zone_name=args.zone_name or settings.zone_name,
        record_name=(args.record_name or settings.record_name or args.zone_name or settings.zone_name),
        record_type=(args.record_type or settings.record_type).upper(),
        ttl=args.ttl if args.ttl is not None else settings.ttl,
        proxied=settings.proxied if args.proxied is None else args.proxied,
        interval=(settings.interval if args.interval is None else args.interval),
        dry_run=settings.dry_run or args.dry_run,
    )


def _parse_csv(csv: str | None) -> List[str]:
    if not csv:
        return []
    return [part.strip() for part in csv.split(',') if part.strip()]


def _apply_multi_overrides(settings_list: List[Settings], args: argparse.Namespace) -> List[Settings]:
    # Determine base auth + common attributes from first settings (env already validated)
    if not settings_list:
        return settings_list
    base = settings_list[0]

    zones = _parse_csv(args.zones_csv) if args.zones_csv else None
    records_csv = _parse_csv(args.records_csv) if args.records_csv else []

    # If no zones override provided, keep existing list (maybe env multi or single); still apply global overrides
    if zones is not None and len(zones) > 0:
        # Build new settings list from zones override
        if records_csv:
            if len(records_csv) != len(zones):
                raise ValueError("--records count must match --zones count")
            record_names = records_csv
        elif args.record_name:
            record_names = [args.record_name for _ in zones]
        else:
            # default each zone's record name to itself
            record_names = zones[:]
        settings_list = [
            Settings(
                api_token=base.api_token,
                api_key=base.api_key,
                email=base.email,
                zone_name=z,
                record_name=r,
                record_type=base.record_type,
                ttl=base.ttl,
                proxied=base.proxied,
                interval=base.interval,
                dry_run=base.dry_run,
            )
            for z, r in zip(zones, record_names)
        ]

    # Apply global overrides (record_type, ttl, proxied, interval, dry_run)
    updated: List[Settings] = []
    for s in settings_list:
        updated.append(
            Settings(
                api_token=s.api_token,
                api_key=s.api_key,
                email=s.email,
                zone_name=s.zone_name,
                record_name=s.record_name,
                record_type=(args.record_type or s.record_type).upper(),
                ttl=args.ttl if args.ttl is not None else s.ttl,
                proxied=s.proxied if args.proxied is None else args.proxied,
                interval=(s.interval if args.interval is None else args.interval),
                dry_run=s.dry_run or args.dry_run,
            )
        )

    return updated


def _run_multi_once(settings_list: List[Settings], verbose: bool) -> int:
    # Cache IP per record type to reduce outbound queries
    from .ip import get_public_ip as _get_public_ip
    ip_cache: Dict[str, str] = {}

    def ip_getter(rt: str) -> str:
        if rt not in ip_cache:
            ip_cache[rt] = _get_public_ip(rt)
        return ip_cache[rt]

    exit_code = 0
    for s in settings_list:
        try:
            result = run_once(s, ip_getter=ip_getter)
            if verbose:
                print(f"{s.zone_name} {s.record_name} {s.record_type} -> {result['action']} ip={result.get('ip')} id={result.get('record_id')}")
        except Exception as e:  # continue others
            exit_code = 1
            print(f"Error updating {s.zone_name}/{s.record_name}: {e}", file=sys.stderr)
    return exit_code


def _run_multi_loop(settings_list: List[Settings], interval: int, verbose: bool, force_once: bool, ip_getter=None) -> int:
    if force_once or not interval:
        return _run_multi_once(settings_list, verbose)
    # Ensure all intervals match the provided interval
    for s in settings_list:
        if s.interval and s.interval != interval:
            print("All intervals must match when running multi-zone loop", file=sys.stderr)
            return 2
    last_ips: Dict[Tuple[str, str], str] = {}
    from .ip import get_public_ip as _get_public_ip

    while True:  # pragma: no cover
        # Clear IP cache for each iteration to fetch fresh IP
        ip_cache: Dict[str, str] = {}

        def cached_get(rt: str) -> str:
            if rt not in ip_cache:
                ip_cache[rt] = _get_public_ip(rt)
            return ip_cache[rt]

        for s in settings_list:
            key = (s.zone_name, s.record_name)
            try:
                result = run_once(s, last_ip=last_ips.get(key), ip_getter=cached_get)
                last_ips[key] = result.get("ip", last_ips.get(key))
                if verbose:
                    print(f"{s.zone_name} {s.record_name} {s.record_type} -> {result['action']} ip={result.get('ip')} id={result.get('record_id')}")
            except Exception as e:
                print(f"Error updating {s.zone_name}/{s.record_name}: {e}", file=sys.stderr)
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load settings (possibly multiple)
    try:
        settings_list = load_all_settings(args.env_path)
    except Exception as e:  # configuration error
        print(f"Config error: {e}", file=sys.stderr)
        return 2

    # Determine if multi or single mode after overrides
    if args.zones_csv or (len(settings_list) > 1):
        try:
            settings_list = _apply_multi_overrides(settings_list, args)
        except Exception as e:
            print(f"Argument error: {e}", file=sys.stderr)
            return 2
        # Basic validation
        for s in settings_list:
            if s.record_type not in {"A", "AAAA"}:
                print("Record type must be A or AAAA", file=sys.stderr)
                return 2
        if args.verbose:
            zones_desc = ", ".join(f"{s.zone_name}:{s.record_name}" for s in settings_list)
            print(f"Starting DDNS updater (multi): zones={zones_desc} type={settings_list[0].record_type} dry_run={settings_list[0].dry_run} interval={settings_list[0].interval}")
        # Decide loop
        interval = settings_list[0].interval if settings_list else None
        try:
            if interval and not args.force_once:
                return _run_multi_loop(settings_list, interval, args.verbose, args.force_once)
            else:
                return _run_multi_once(settings_list, args.verbose)
        except KeyboardInterrupt:
            if args.verbose:
                print("Interrupted")
            return 130
    else:
        # Single mode legacy path
        settings = settings_list[0]
        settings = _apply_single_overrides(settings, args)

        if settings.record_type not in {"A", "AAAA"}:
            print("Record type must be A or AAAA", file=sys.stderr)
            return 2

        if args.verbose:
            print(f"Starting DDNS updater: zone={settings.zone_name} record={settings.record_name} type={settings.record_type} dry_run={settings.dry_run} interval={settings.interval}")

        try:
            if settings.interval and not args.force_once:
                run_loop(settings)
            else:
                result = run_once(settings)
                if args.verbose:
                    print(result)
        except KeyboardInterrupt:
            if args.verbose:
                print("Interrupted")
            return 130
        except Exception as e:  # top-level runtime error
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
