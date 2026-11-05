"""Native children receive visualization-independent runtime variables, never service secrets."""

import os

from earthmind_worker.settings import Settings


def native_environment() -> dict[str, str]:
    allowed = {"PATH", "SUMO_HOME", "LANG", "LC_ALL", "TZ"}
    return {name: value for name, value in os.environ.items() if name in allowed}


def runner_environment(settings: Settings) -> dict[str, str]:
    environment = native_environment()
    if os.environ.get("PYTHONPATH"):
        environment["PYTHONPATH"] = os.environ["PYTHONPATH"]
    environment.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "SIMULATION_INPUTS_ROOT": settings.simulation_inputs_root,
            "SIMULATION_ARTIFACTS_ROOT": settings.simulation_artifacts_root,
            "SIMULATION_TIMEOUT_SECONDS": str(settings.simulation_timeout_seconds),
        }
    )
    return environment
