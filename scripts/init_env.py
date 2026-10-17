#!/usr/bin/env python3
"""Create local secrets and data directories without uploading any credentials."""
import os
import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / '.env.example'
ENV = ROOT / '.env'


def main():
    if not ENV.exists():
        shutil.copyfile(EXAMPLE, ENV)
    lines = ENV.read_text(encoding='utf-8').splitlines()
    changed = []
    for line in lines:
        if line.startswith('APP_PASSWORD=') and not line.split('=', 1)[1]:
            line = 'APP_PASSWORD=' + secrets.token_urlsafe(32)
        if line.startswith('JD_WEB_PASSWORD=') and not line.split('=', 1)[1]:
            line = 'JD_WEB_PASSWORD=' + secrets.token_urlsafe(32)
        if line.startswith('PUID=') and os.geteuid() != 0:
            line = f'PUID={os.getuid()}'
        if line.startswith('PGID=') and os.geteuid() != 0:
            line = f'PGID={os.getgid()}'
        changed.append(line)
    ENV.write_text('\n'.join(changed) + '\n', encoding='utf-8')
    ENV.chmod(0o600)
    values = dict(s.split('=', 1) for s in changed if '=' in s and not s.startswith('#'))
    for key in ('JD_CONFIG_PATH', 'JD_DOWNLOADS_PATH', 'APP_DATA_PATH'):
        path = Path(values[key])
        if not path.is_absolute():
            path = ROOT / path
        path.mkdir(parents=True, exist_ok=True)
    (ROOT / values['APP_DATA_PATH']).chmod(0o700)
    print('Configured .env (permissions 600) and local data directories.')
    print('Your credentials are only stored in .env. Do not commit this file.')
    print('Start with: docker compose up -d --build')


if __name__ == '__main__':
    main()
