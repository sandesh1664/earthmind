"""Exercise the migrated host database and SQLAlchemy session integration tests."""

import os
import subprocess
import sys
from urllib.parse import quote

import psycopg
from dotenv import dotenv_values
from smoke import port


def database_url() -> str:
    settings = dotenv_values(".env")

    def setting(name: str, default: str = "") -> str:
        return os.environ.get(name) or settings.get(name) or default

    password = setting("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError("POSTGRES_PASSWORD must be configured in the ignored environment file")
    user = quote(setting("POSTGRES_USER", "earthmind"), safe="")
    database = quote(setting("POSTGRES_DB", "earthmind"), safe="")
    host_port = port("DB_PORT", "5434")
    return f"postgresql://{user}:{quote(password, safe='')}@127.0.0.1:{host_port}/{database}"


def main() -> int:
    url = database_url()
    with psycopg.connect(url, connect_timeout=3) as connection:
        version, postgis = (
            connection.execute("SELECT version(), PostGIS_Version()").fetchone() or ()
        )
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        metadata = connection.execute(
            "SELECT application_name, schema_version, created_at, updated_at "
            "FROM system_metadata WHERE application_name = 'EARTHMIND'"
        ).fetchone()
        if revision != ("0004_run_state_integrity",) or metadata is None or metadata[1] != 1:
            raise RuntimeError("Database migration or application metadata is not current")
        print(f"PostgreSQL: {version}")
        print(f"PostGIS: {postgis}")
        print(f"Migration: {revision[0]}; metadata: {metadata[0]}, schema {metadata[1]}")
    environment = {**os.environ, "EARTHMIND_TEST_DATABASE_URL": url}
    return subprocess.call(
        [
            "uv",
            "run",
            "--locked",
            "pytest",
            "-m",
            "integration",
            "apps/api/tests",
        ],
        env=environment,
    )


if __name__ == "__main__":
    sys.exit(main())
