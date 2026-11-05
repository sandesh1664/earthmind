"""Verify fresh/repeated migrations using only a disposable, isolated project."""

import os
import subprocess

from dotenv import dotenv_values

PROJECT = "earthmind-m02-verification"
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
        compose(
            "run",
            "--rm",
            "migrate",
            "alembic",
            "-c",
            "apps/api/alembic.ini",
            "upgrade",
            "0002_system_metadata",
        )
        revision = sql("SELECT version_num FROM alembic_version").strip()
        if revision != "0002_system_metadata":
            raise RuntimeError(f"Unexpected fresh M01 migration revision: {revision}")
        sql(
            "INSERT INTO system_metadata(id,application_name,schema_version) "
            "VALUES (gen_random_uuid(),'M01 preservation probe',1)"
        )
        sql("SELECT PostGIS_Version(); SELECT application_name,schema_version FROM system_metadata")
        compose("run", "--rm", "migrate")
        if sql("SELECT version_num FROM alembic_version").strip() != "0005_simulation_execution":
            raise RuntimeError("M01 to M02 migration did not reach the current head")
        if (
            sql(
                "SELECT count(*) FROM system_metadata "
                "WHERE application_name='M01 preservation probe'"
            ).strip()
            != "1"
        ):
            raise RuntimeError("M02 migration did not preserve the M01 row")
        compose("run", "--rm", "migrate")
        compose("run", "--rm", "migrate", "alembic", "-c", "apps/api/alembic.ini", "check")
        # Empty M02 tables can be removed safely; M01 rows must survive either path.
        compose(
            "run",
            "--rm",
            "migrate",
            "alembic",
            "-c",
            "apps/api/alembic.ini",
            "downgrade",
            "0002_system_metadata",
        )
        if sql("SELECT version_num FROM alembic_version").strip() != "0002_system_metadata":
            raise RuntimeError("Empty M02 downgrade did not return to M01")
        if (
            sql(
                "SELECT count(*) FROM system_metadata "
                "WHERE application_name='M01 preservation probe'"
            ).strip()
            != "1"
        ):
            raise RuntimeError("Empty downgrade did not preserve the M01 row")
        compose("run", "--rm", "migrate")
        compose("run", "--rm", "migrate", "alembic", "-c", "apps/api/alembic.ini", "check")
        compose("run", "--rm", "migrate", "python", "-m", "earthmind_api.seed")
        repeated = compose("run", "--rm", "migrate", "python", "-m", "earthmind_api.seed")
        if '"created": false' not in repeated:
            raise RuntimeError("Repeated seed was not idempotent")
        try:
            compose(
                "run",
                "--rm",
                "migrate",
                "alembic",
                "-c",
                "apps/api/alembic.ini",
                "downgrade",
                "0002_system_metadata",
            )
        except subprocess.CalledProcessError as error:
            if "M02 downgrade refused" not in (error.stdout or "") + (error.stderr or ""):
                raise
            print(
                "PASS: populated-research downgrade refused as designed; "
                "expected nonzero child exit"
            )
        else:
            raise RuntimeError("Populated M02 downgrade unexpectedly succeeded")
        if sql("SELECT count(*) FROM road_edges").strip() != "8":
            raise RuntimeError("Protected downgrade failed to preserve the synthetic graph")
        if sql("SELECT version_num FROM alembic_version").strip() != "0005_simulation_execution":
            raise RuntimeError("Protected downgrade did not roll back schema changes atomically")
        compose("run", "--rm", "migrate")
    finally:
        compose("down", "--volumes", "--remove-orphans")
    print(
        "PASS: fresh M01 to M02, preserved legacy data, schema consistency, "
        "idempotent seed and protected research downgrade"
    )


if __name__ == "__main__":
    main()
