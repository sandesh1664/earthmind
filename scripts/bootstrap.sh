#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
sh scripts/verify_environment.sh
uv python install 3.12
uv run --no-project --python 3.12 python - <<'PY'
import re
import secrets
from pathlib import Path

destination = Path('.env')
if not destination.exists():
    template = Path('.env.example').read_text()
    template = re.sub(r'^POSTGRES_PASSWORD=.*$', 'POSTGRES_PASSWORD=' + secrets.token_urlsafe(32), template, flags=re.MULTILINE)
    destination.write_text(template)
    print('Initialized .env with a generated local database password (value hidden)')
else:
    print('Preserved existing .env values')
destination.chmod(0o600)
PY
