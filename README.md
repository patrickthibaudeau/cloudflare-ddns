# Cloudflare DDNS Updater

Simple Python dynamic DNS (DDNS) updater for Cloudflare.

## Features
- Supports IPv4 (A) and IPv6 (AAAA) record updates
- Uses Cloudflare API (Global API Key + Email, or API Token)
- Dry‑run mode
- Optional continuous loop with interval
- Smart skip when IP unchanged (cached + remote)
- Multi-zone & multi-record updates in a single run
- Container-friendly (Docker)

## Requirements
- Python 3.11+
- Cloudflare account
- Cloudflare Global API Key + account email (as requested) OR a scoped API Token with DNS edit permission

## Installation (Bare Metal / Virtual Env)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Docker Usage
A `Dockerfile` is included for easy container deployment.

### Build Image
```bash
docker build -t cf-ddns .
```

### Run (Single Shot)
```bash
docker run --rm --env-file .env cf-ddns --once --verbose
```

### Run (Continuous) Using Interval From .env
Ensure `DDNS_INTERVAL` is set in your `.env` file (e.g. `DDNS_INTERVAL=300`).
```bash
docker run -d --name cf-ddns --env-file .env cf-ddns --verbose
```
Stop it:
```bash
docker stop cf-ddns
```

### Override Interval / Options at Runtime
CLI flags override `.env` values:
```bash
docker run --rm --env-file .env cf-ddns --interval 600 --type AAAA --verbose
```

### Use a Token via Docker Secrets (Example Pattern)
If you mount a file containing only the token at `/run/secrets/cf_token`:
```bash
docker run --rm \
  -e CLOUDFLARE_ZONE_NAME=example.com \
  -e CLOUDFLARE_RECORD_NAMES=example.com,home.example.com \
  -e CLOUDFLARE_RECORD_TYPE=A \
  --env CLOUDFLARE_API_TOKEN="$(cat /run/secrets/cf_token)" \
  cf-ddns --verbose
```
(For real Docker Swarm / Compose secrets, map the file then export inside container or add code to read directly.)

### docker-compose.yml Example
```yaml
services:
  ddns:
    build: .
    image: cf-ddns:latest
    restart: unless-stopped
    env_file: .env
    command: ["--verbose"]  # rely on DDNS_INTERVAL in .env for looping
```
Bring it up:
```bash
docker compose up -d --build
```
Logs:
```bash
docker compose logs -f ddns
```

### Minimal Runtime Environment Variables
For single zone + two records:
```
CLOUDFLARE_API_TOKEN=***
CLOUDFLARE_ZONE_NAME=example.com
CLOUDFLARE_RECORD_NAMES=example.com,home.example.com
DDNS_INTERVAL=600
```

### Image Behavior
- ENTRYPOINT: `python -m ddns`
- Default CMD: `--verbose` (remove verbosity by supplying your own CMD)
- Use `--once` to force a single execution even if `DDNS_INTERVAL` set.

### Non-Root User
Container runs as a non-root user (UID 1001) for safer operation. No special volumes required; state is ephemeral.

---

## Configuration (.env)
Copy `.env.example` to `.env` and fill required values.

Mandatory (choose one auth method, this doc shows the requested Global API Key method):
```
CLOUDFLARE_EMAIL=you@example.com
CLOUDFLARE_API_KEY=your_global_api_key
# Or instead:
# CLOUDFLARE_API_TOKEN=your_scoped_token

# Single-zone (legacy) variables:
CLOUDFLARE_ZONE_NAME=example.com
# Optional overrides:
# CLOUDFLARE_RECORD_NAME=home.example.com   # default = zone

# OR Multi-zone (new):
# CLOUDFLARE_ZONE_NAMES=example.com,example.net
# CLOUDFLARE_RECORD_NAMES=home.example.com,office.example.net   # optional; must match zones count
# If CLOUDFLARE_RECORD_NAMES omitted, each zone's record defaults to the zone itself unless CLOUDFLARE_RECORD_NAME is provided (applied to all).

# Single-zone multi-record (new convenience):
# CLOUDFLARE_ZONE_NAME=example.com
# CLOUDFLARE_RECORD_NAMES=example.com,host1.example.com,host2.example.com
# (The single zone is internally replicated for every record name.)

# Common optional settings (apply to all zones/records):
# CLOUDFLARE_RECORD_TYPE=A                  # or AAAA
# CLOUDFLARE_TTL=300
# CLOUDFLARE_PROXIED=false
# DDNS_INTERVAL=300                         # run forever every 300s
# DDNS_DRY_RUN=false
```

### Multi-Zone / Multi-Record Notes
Priority / resolution order when determining zones & records:
1. CLI `--zones` (comma CSV) overrides everything.
2. Environment `CLOUDFLARE_ZONE_NAMES` list.
3. Fallback to single `CLOUDFLARE_ZONE_NAME`.

Record names per zone chosen by:
1. CLI `--records` (comma CSV) if provided (must match zones length OR single zone replicated if only one zone).
2. CLI `--record` single value applied to all zones.
3. Environment `CLOUDFLARE_RECORD_NAMES` list (must match zone list length OR single zone is replicated automatically).
4. Environment `CLOUDFLARE_RECORD_NAME` single value applied to all.
5. Default: each zone name itself.

Single-zone multi-record behavior:
- If you set `CLOUDFLARE_ZONE_NAME` AND a comma list in `CLOUDFLARE_RECORD_NAMES`, the tool creates one update task per record, all within that single zone.
- Example:
  - CLOUDFLARE_ZONE_NAME=example.com
  - CLOUDFLARE_RECORD_NAMES=example.com,home.example.com,office.example.com
  Updates apex + two subdomains in one run.

### Examples
Single zone, two records (apex + subdomain):
```
CLOUDFLARE_ZONE_NAME=example.com
CLOUDFLARE_RECORD_NAMES=example.com,home.example.com
```

Two zones, one record each (defaults):
```
CLOUDFLARE_ZONE_NAMES=example.com,example.net
```

Two zones, explicit record names:
```
CLOUDFLARE_ZONE_NAMES=example.com,example.net
CLOUDFLARE_RECORD_NAMES=home.example.com,office.example.net
```

One record applied to every zone:
```
CLOUDFLARE_ZONE_NAMES=example.com,example.net
CLOUDFLARE_RECORD_NAME=dynamic.example.com
```

## One‑shot Update (single or multi)
```bash
python -m ddns --env .env --verbose
```

## Continuous Update (every N seconds)
Either set `DDNS_INTERVAL` in `.env` or pass `--interval`:
```bash
python -m ddns --env .env --interval 300 --verbose
```

### Continuous Update Behavior
When running in continuous mode with an interval:
- **First iteration**: Fetches current public IP, checks all Cloudflare records, updates only if different
- **Subsequent iterations**: 
  - Fetches fresh public IP each time
  - If IP unchanged from previous check: Returns "noop" immediately (no Cloudflare API call)
  - If IP changed: Queries Cloudflare and updates only records that differ
  
This minimizes API calls and only updates Cloudflare when your public IP actually changes.

**Log output format (with --verbose):**
```
Starting DDNS updater (multi): zones=...
--- Iteration 1: current_ip=70.49.233.249 [initial check] ---
example.com example.com A -> noop ip=70.49.233.249 id=abc123...
example.com home.example.com A -> noop ip=70.49.233.249 id=def456...
--- Iteration 2: cached_ip=70.49.233.249 current_ip=70.49.233.249 [unchanged] ---
example.com example.com A -> noop ip=70.49.233.249 id=None
example.com home.example.com A -> noop ip=70.49.233.249 id=None
--- Iteration 3: cached_ip=70.49.233.249 current_ip=70.49.240.100 [CHANGED] ---
example.com example.com A -> updated ip=70.49.240.100 id=abc123...
example.com home.example.com A -> updated ip=70.49.240.100 id=def456...
```

**Log output meanings:**
- `--- Iteration N: ...` - Shows iteration number, cached IP, current IP, and change status
- `[initial check]` - First run, no cached IP yet
- `[unchanged]` - IP hasn't changed, efficient caching in effect
- `[CHANGED]` - IP has changed, will update Cloudflare records
- `noop ip=X.X.X.X id=<record_id>` - IP checked against Cloudflare, no change needed
- `noop ip=X.X.X.X id=None` - IP unchanged from cache, skipped Cloudflare check (efficient)
- `updated ip=X.X.X.X id=<record_id>` - IP changed, record updated in Cloudflare

## Override Zones / Records via CLI
```bash
# Update two zones with explicit records
python -m ddns --env .env --zones example.com,example.net --records home.example.com,office.example.net --verbose

# Update same record name across multiple zones
python -m ddns --env .env --zones example.com,example.net --record dynamic.example.com --verbose

# Single-zone multi-record (apex + subdomain)
python -m ddns --env .env --verbose  # with CLOUDFLARE_ZONE_NAME & CLOUDFLARE_RECORD_NAMES set
```

## Override Record Type or TTL
```bash
python -m ddns --env .env --type AAAA --ttl 600 --verbose
```

## Dry Run
```bash
python -m ddns --env .env --dry-run --verbose
```

## Exit Codes
- 0 success
- 1 runtime error
- 2 configuration / argument error
- 130 interrupted (Ctrl+C)

## Testing
```bash
pytest -q
```

## How It Works
1. Detect current public IP (IPv4 or IPv6) via multiple endpoints.
2. Fetch Zone ID from Cloudflare.
3. Lookup DNS record; create/update only if content differs.
4. Cache last seen IP in loop to avoid redundant API calls.
5. Multi-mode iterates all configured zones/records with shared IP lookup per record type.
6. Single-zone multi-record simply treats each record name as an independent target in the same zone.

## Security Notes
- Keep your `.env` out of version control (already in `.gitignore`).
- Prefer API Tokens (least privilege). Rotate any exposed Global API Key immediately.

## License
MIT License. See `LICENSE` file.
