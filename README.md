# JFStack Downloader

An **independent, self-hosted Docker project** combining JDownloader 2 with an authenticated URL intake panel, a conservative ad-shortener resolver, persistent job history and a private Click'n'Load integration. No qBittorrent, Jellyfin, other downloads, or cross-stack mounts.

[Leer en español](docs/README.es.md)

> **Release 0.1.0 (MVP).** Automatic support covers HTTP redirects, HTML meta refresh, and simple static JavaScript navigation patterns. Complex JavaScript shorteners, advertisements with timed buttons, CAPTCHAs and anti-bot challenges are **not** automatically bypassed. Those items are left for manual review or JDownloader's own plugins. `sent` means delivered to LinkGrabber, not downloaded.

## Architecture

```text
Browser / curl
    | Basic auth, localhost-only port 8080
    v
JFStack intake (FastAPI + URL resolver + SQLite history)
    | 127.0.0.1:9666 (Click'n'Load; never host-published)
    v
JDownloader 2 (LinkGrabber + downloader + HTTPS GUI on port 5800)
    | own volumes ONLY
    +-- ./data/config      (JD state)
    +-- ./data/downloads   (downloaded files)

FastAPI owns only ./data/app (SQLite)
```

The app uses `network_mode: service:jdownloader` to reach JDownloader's default localhost-only Click'n'Load listener; the two containers do **not** share filesystem mounts. No MyJDownloader account is needed.

## Requirements

- Linux server running Docker Engine with Docker Compose v2, network access for the images and target URLs.
- Python 3 for the one-time local initializer (not required for ongoing runtime).
- Approximately 1 GB RAM free or more depending on JDownloader workload, plus space for downloads.
- A private access path, preferably SSH port forwarding or a VPN/TLS reverse proxy.

## Install

```bash
git clone https://github.com/YOUR-ORG/docker-jdownloader.git
cd docker-jdownloader
python3 scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Replace the placeholder Git remote with your own repository; alternatively extract the project ZIP and run the commands from the extracted folder. `init_env.py` creates `.env`, fills two independent randomly generated passwords, sets host UID/GID for a non-root invoker, creates local data directories and restricts `.env` to mode 600. Re-running it preserves existing passwords.

**Local access:**

- Intake panel: <http://127.0.0.1:8080> (HTTP Basic; credentials `APP_USERNAME` and `APP_PASSWORD` from `.env`).
- JDownloader GUI: <https://127.0.0.1:5800> (HTTPS + built-in login; credentials `JD_WEB_USERNAME` and `JD_WEB_PASSWORD`). Its initial self-signed certificate may prompt a browser warning. Configure a trusted certificate/reverse proxy as appropriate.

JDownloader's GUI is maintained by a community Docker image, not an official JDownloader container. The first launch can take longer while the application initializes and updates.

### Access from your computer over SSH

Ports are bound to host loopback by default. On your workstation:

```bash
ssh -N -L 8080:127.0.0.1:8080 -L 5800:127.0.0.1:5800 user@your-server
```

Then open the two localhost URLs above. You may publish **only the intended frontends** through your own WireGuard/private reverse proxy with HTTPS and correct access restrictions, but do not expose the Click'n'Load listener (9666). For a reverse proxy in Docker, route internally to the `jdownloader` container on port `8000` for FastAPI; the JDownloader UI runs HTTPS on `5800` and will need a TLS-capable upstream configuration. Do not simply change `BIND_ADDRESS` to `0.0.0.0` on an untrusted network.


### If Click'n'Load is disconnected

In the JDownloader GUI, open **Settings → Advanced Settings**, search for `RemoteAPI: Extern Interface` (or `cnl`) and ensure it is enabled. Keep **Extern Interface Localhost Only** enabled: both containers share the network namespace, so publishing 9666 is unnecessary. JDownloader may ask you to authorize links sent from an external application; approve your own panel's request in the JD GUI. Restart JD if the changed settings require it.

```bash
docker compose restart jdownloader app
docker compose logs --tail=80 app
```

The *JDownloader connected* status only confirms that the listener responds; it does not prove a pending authorization prompt has been approved.

## Using the project

1. Open the panel and paste one public HTTP(S) URL per line (up to `APP_MAX_BATCH`, default 20).
2. Click **Resolve & send**. Jobs are queued and processed by two workers by default.
3. View each job's original URL, resulting URL, resolution method and result.
4. `sent`: open the **JDownloader GUI** and look in **LinkGrabber**. You can confirm or start downloads there according to JDownloader settings.
5. `ready`: JDownloader's CNL endpoint is unavailable; start/verify JD and use **Send URL to JDownloader** or **Retry resolution**.
6. `manual`: the site needs interaction, CAPTCHA, or an unsupported redirect; you can open the URL in your own browser or submit it directly to JDownloader for its own plugins to analyze.
7. `error`: the URL failed validation or processing. Review the cause before retrying.

The intake panel is **not** a replacement for the JDownloader download progress and CAPTCHA UI. URL history includes any query-string tokens and is kept only on your host; protect the SQLite backup accordingly.

### API

The API uses HTTP Basic auth and requires `Content-Type: application/json` plus `X-JFStack-Request: 1` for writes. Example (the password prompt avoids putting a password in the shell command):

```bash
curl -u admin -H 'X-JFStack-Request: 1' -H 'Content-Type: application/json' \
  -d '{"links":"https://example.com/file.zip\nhttps://example.org/short"}' \
  http://127.0.0.1:8080/api/jobs
```

Endpoints: `GET /healthz`, `GET /api/status`, `GET /api/jobs`, `POST /api/jobs`, `POST /api/jobs/{id}/retry`, `POST /api/jobs/{id}/send`. `send` submits the best available URL after public-target validation. There is no remote JDownloader credential or MyJDownloader account in the app.

## Configuration

All options are set in the **single** `.env` file:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BIND_ADDRESS` | `127.0.0.1` | Host binding for the two UIs; retain loopback by default |
| `APP_PORT`, `JD_WEB_PORT` | `8080`, `5800` | Published intake / JD HTTPS GUI ports |
| `APP_USERNAME`, `APP_PASSWORD` | `admin`, generated | Intake panel Basic credentials |
| `JD_WEB_USERNAME`, `JD_WEB_PASSWORD` | `admin`, generated | JD's own HTTPS login credentials |
| `PUID`, `PGID` | `1000`, `1000` | Host file ownership; initializer detects your IDs |
| `TZ` | `Europe/Madrid` | Container timezone |
| `JD_CONFIG_PATH` | `./data/config` | Exclusive JD persistent config |
| `JD_DOWNLOADS_PATH` | `./data/downloads` | Exclusive JD output |
| `APP_DATA_PATH` | `./data/app` | Exclusive app SQLite files |
| `APP_MAX_BATCH` | `20` | Maximum URLs per submission; valid range 1–100 |
| `APP_WORKERS` | `2` | Parallel background workers; valid range 1–4 |
| `APP_REQUEST_TIMEOUT` | `12` | Per-link resolution timeout; range 2–30 sec |
| `APP_MAX_HOPS` | `8` | Maximum redirect/HTML navigation steps; range 1–12 |
| `JDOWNLOADER_IMAGE_TAG` | `latest` | Community image tag; pin a tested tag for managed deployments |

If using absolute disk paths, edit only the corresponding variables in `.env`, then ensure the `PUID:PGID` user has write access. **No reference to another stack is needed.**

## Operations and backups

```bash
# Status and logs
docker compose ps
docker compose logs -f --tail=100

# Stop and restart (persistent data is retained)
docker compose down
docker compose up -d --build

# Update images (review and back up first)
docker compose pull
docker compose up -d --build

# Offline backup for consistent SQLite and JD state
docker compose down
tar -czf jfstack-jdownloader-backup.tar.gz .env data/

# Restore: unpack .env and data/ into the project folder, then
# docker compose up -d --build
```

A pending job is recovered after app restart. If a crash happens between JDownloader accepting a link and the app recording the acknowledgement, retrying can insert a duplicate; inspect LinkGrabber before manually retrying ambiguous cases. Do not use `docker compose down -v` to wipe data.

## Security and limitations

- Both user-facing ports are bound to host `127.0.0.1`; use SSH or a **trusted private HTTPS** ingress for remote access. The intake UI uses Basic authentication, so unencrypted remote HTTP would disclose credentials.
- CNL is localhost-only within the dedicated project network namespace; JD's own web GUI uses HTTPS with authentication and VNC is disabled.
- URL validation enforces HTTP(S), public DNS/IPs, standard web ports, redirect checks and HTML inspection size/hop limits. Browser-side ad scripts are **not** executed in this release. Never submit targets you do not trust: JDownloader's own hoster plugins operate independently and can follow further redirects.
- Outbound HTTP requests are made on the server, which can reveal its public IP to the target service. There is no built-in VPN/proxy requirement or bypass service.
- Full HTML/JS ad-gate automation and native download-state polling are future work. See [architecture notes](docs/ARCHITECTURE.md).

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt pytest pytest-asyncio httpx
APP_PASSWORD=local-development-password-long-enough APP_DB_PATH=/tmp/jfstack-dev.sqlite3 \
  PYTHONPATH=backend uvicorn app.main:app --reload --app-dir backend
PYTHONPATH=backend pytest -q tests
```

The service needs a running JDownloader Click'n'Load listener to submit links in the real deployment. Tests use local fixtures and do **not** prove the external JD integration, Docker networking, DNS availability, or download completion. Run a real smoke test on the target Docker host before relying on it.

## License and attribution

JFStack Downloader's original application code is licensed under MIT (see [LICENSE](LICENSE)). JDownloader and the `jlesage/jdownloader-2` image are separate upstream projects with their own licenses and maintenance policies; this repository does not redistribute those third-party binaries.
