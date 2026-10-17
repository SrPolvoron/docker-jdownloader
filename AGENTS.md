# Instructions for coding agents

## Purpose and boundaries

Build a portable, independent JFStack Docker stack for JDownloader 2 and URL resolution. Never connect to, mount, or depend on qBittorrent, Jellyfin, or other download stacks. Do not hardcode an actual server's paths, internal DNS names, WireGuard addresses, secrets, or credentials.

## Architecture invariants

- JDownloader remains the download engine. Our application is a resolver, intake API, persistent job history, and local Click'n'Load bridge.
- The application container shares only the JDownloader service's network namespace to reach JDownloader's `127.0.0.1:9666` Click'n'Load listener. Do not publish 9666 or expose the management API remotely by default.
- All paths and bind ports are configured through a single `.env`; no cross-project volumes.
- The JD `/output` and `/config` mounts belong only to the JD service. The application has only its own SQLite volume.
- Do not mistake `sent` for a completed download. JDownloader is authoritative for actual download progress.
- Treat all external URLs as hostile. Revalidate redirect destinations and resolved addresses; prevent SSRF, file schemes, unsafe ports, credentials in URLs, and unbounded resource consumption. Avoid blind ad-button clicking.
- Do not implement CAPTCHA solving or stealth anti-bot bypass. Mark unsupported flows for user review.
- Keep basic authentication; never log user secrets, URL query strings, or credentials.
- SQLite stores job history and recovery state. Keep schemas backward-compatible or provide explicit migrations before shipping schema changes.

## Commands

```sh
python3 scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose logs -f --tail=100
PYTHONPATH=backend pytest -q tests
```

## QA / releases

Run unit and API tests for changes to URL parsing or security. Review redirects, DNS rebinding, response-size limits, and failed JD handoff. Keep external network integration tests separate from deterministic unit tests. Do not create releases, version bumps, or tags without an explicit request.

## Documentation

The root `README.md` must always be English and include `[Leer en español](docs/README.es.md)` near the top. Maintain `docs/README.es.md` as a full Spanish equivalent with `[Read in English](../README.md)` near the top. Keep both synchronized on user-facing changes. Keep `AGENTS.md` in English.
