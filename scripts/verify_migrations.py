"""Verify fresh/repeated migrations using only a disposable, isolated project."""

import os
import subprocess

from dotenv import dotenv_values

PROJECT = "earthmind-m01-verification"
ENVIRONMENT = {**os.environ, "DB_PORT": "55434", "API_PORT": "58000", "WEB_PORT": "53000"}
COMMAND = ["docker", "compose", "--project-name", PROJECT, "--env-file", ".env"]


def compose(*arguments: str) -> str:
    print(f"$ {' '.join([*COMMAND, *arguments])}", flush=True)
    result = subprocess.run(
        [*COMMAND, *arguments], env=ENVIRONMENT, check=False, text=True, capture_output=True
    )
    print(result.stdout + result.stderr, end="", flush=True)
    result.check_returncode()
    return result.stdout


def sql(statement: str) -> str:
    # This database is an empty fixture created by this script, never the main project.
    settings = dotenv_values(".env")
    user = os.environ.get("POSTGRES_USER") or settings.get("POSTGRES_USER") or "earthmind"
    database = os.environ.get("POSTGRES_DB") or settings.get("POSTGRES_DB") or "earthmind"
    return compose("exec", "-T", "db", "psql", "-U", user, "-d", database, "-tAc", statement)


def main() -> None:
    if compose("ps", "--all", "--quiet").strip():
        raise RuntimeError(f"Refusing to overwrite existing disposable project {PROJECT}")
    volumes = subprocess.check_output(
        [
            "docker",
            "volume",
            "ls",
            "--quiet",
            "--filter",
            f"label=com.docker.compose.project={PROJECT}",
        ],
        text=True,
    )
    if volumes.strip():
        raise RuntimeError(f"Refusing to overwrite existing volumes for {PROJECT}")
    try:
        compose("up", "--detach", "--wait", "--wait-timeout", "120", "db")
        sql("DROP EXTENSION IF EXISTS postgis")
        if sql("SELECT count(*) FROM pg_extension WHERE extname='postgis'").strip() != "0":
            raise RuntimeError("The isolated fixture must begin without PostGIS")
        compose("run", "--rm", "migrate")
        revision = sql("SELECT version_num FROM alembic_version").strip()
        if revision != "0002_system_metadata":
            raise RuntimeError(f"Unexpected fresh migration revision: {revision}")
        sql("SELECT PostGIS_Version(); SELECT application_name,schema_version FROM system_metadata")
        compose("run", "--rm", "migrate")
        compose(
            "run",
            "--rm",
            "migrate",
            "alembic",
            "-c",
            "apps/api/alembic.ini",
            "downgrade",
            "0001_postgis",
        )
        if sql("SELECT to_regclass('public.system_metadata') IS NULL").strip() != "t":
            raise RuntimeError("Metadata downgrade did not remove its own table")
        compose("run", "--rm", "migrate")
        if (
            sql("SELECT count(*) FROM system_metadata WHERE application_name='EARTHMIND'").strip()
            != "1"
        ):
            raise RuntimeError("Metadata upgrade did not restore exactly one application seed")
    finally:
        compose("down", "--volumes", "--remove-orphans")
    print(
        "PASS: fresh database, missing-extension recovery, repeated upgrade "
        "and metadata downgrade/upgrade"
    )


if __name__ == "__main__":
    main()
