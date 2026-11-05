"""Read-only Linux /proc ownership checks; never expose command lines or environments."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

MAX_PROCESS_SCAN = 8192
MAX_CMDLINE_BYTES = 65536


def _stat(path: Path) -> tuple[str, int, int, int]:
    # comm may contain spaces/parentheses; fields after its final ')' are stable.
    payload = path.read_text()
    closing = payload.rfind(")")
    if closing < 0:
        raise ValueError("Malformed process stat record")
    fields = payload[closing + 2 :].split()
    if len(fields) < 20:
        raise ValueError("Truncated process stat record")
    return fields[0], int(fields[1]), int(fields[2]), int(fields[19])


def _known_process(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"[1-9]\d{0,9}:[1-9]\d{0,19}", value):
        raise argparse.ArgumentTypeError("Expected PID:START_TICKS from an earlier inspection")
    pid, started = value.split(":")
    return int(pid), int(started)


def inspect(run_id: UUID, known_processes: list[tuple[int, int]] | None = None) -> dict[str, Any]:
    root = Path("/proc")
    if not root.is_dir():
        return {
            "status": "NOT RUN",
            "run_id": str(run_id),
            "reason": "Linux /proc is required; run this inspector inside the worker container",
        }
    identifier = str(run_id)
    pattern = re.compile(r"(?<![0-9a-f])" + re.escape(identifier) + r"(?![0-9a-f])", re.I)
    known = dict(known_processes or [])
    if len(known) > 64:
        raise ValueError("Known-process correlation exceeds its bounded budget")
    inspector_pid = os.getpid()
    entries = [path for path in root.iterdir() if path.name.isdecimal()]
    if len(entries) > MAX_PROCESS_SCAN:
        raise ValueError("Process inventory exceeds the bounded inspection budget")
    owned: list[dict[str, Any]] = []
    unattributed_zombies: list[dict[str, Any]] = []
    skipped = 0
    for process in entries:
        pid = int(process.name)
        if pid == inspector_pid:
            continue
        try:
            state, parent, group, started = _stat(process / "stat")
            with (process / "cmdline").open("rb") as source:
                command = source.read(MAX_CMDLINE_BYTES + 1)
            if len(command) > MAX_CMDLINE_BYTES:
                skipped += 1
                continue
            arguments = [item.decode(errors="replace") for item in command.split(b"\0") if item]
            try:
                cwd = os.readlink(process / "cwd")
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                cwd = ""
            comm = (process / "comm").read_text().strip()
            if _stat(process / "stat")[3] != started:
                skipped += 1
                continue
            executable = Path(arguments[0]).name if arguments else comm
            runner = "earthmind_worker.simulation_runner" in arguments or (
                len(arguments) > 1 and Path(arguments[1]).name == "simulation_runner.py"
            )
            native = executable in {"sumo", "sumo-gui"} or comm in {"sumo", "sumo-gui"}
            correlated = known.get(pid) == started
            if not (runner or native or correlated):
                continue
            matched_cwd = bool(pattern.search(cwd))
            matched_argument = any(pattern.search(argument) for argument in arguments)
            matched = matched_cwd or matched_argument or correlated
            record = {
                "pid": pid,
                "parent_pid": parent,
                "pgid": group,
                "start_time_ticks": started,
                "state": state,
                "kind": "sumo" if native else "python_runner" if runner else "known_process",
                "is_zombie": state == "Z",
            }
            if matched:
                record["ownership_evidence"] = (
                    "prior_pid_and_start_ticks"
                    if correlated
                    else "run_uuid_in_cwd"
                    if matched_cwd
                    else "run_uuid_in_runner_arguments"
                )
                owned.append(record)
            elif native and state == "Z":
                # A zombie loses cmdline/cwd. Never silently claim it belongs to
                # no run; correlate its prior PID+start time when available.
                unattributed_zombies.append(record)
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, OSError):
            skipped += 1
    owned.sort(key=lambda item: item["pid"])
    groups = sorted({item["pgid"] for item in owned})
    live = [item for item in owned if item["state"] not in {"Z", "X", "x"}]
    return {
        "status": "observed",
        "run_id": identifier,
        "scope": "Actual Linux process cmdline/cwd ownership, values never retained",
        "inspector_pid_excluded": inspector_pid,
        "owned_process_count": len(owned),
        "owned_live_process_count": len(live),
        "owned_zombie_process_count": sum(item["is_zombie"] for item in owned),
        "owned_process_group_count": len(groups),
        "owned_pgids": groups,
        "processes": owned,
        "unattributed_native_zombies": unattributed_zombies,
        "unattributed_native_zombie_count": len(unattributed_zombies),
        "processes_skipped_due_to_exit_or_permissions": skipped,
        "limitations": [
            "No process is signaled or modified",
            "No environment, credentials, full command line or cwd is emitted",
            "Vanished processes are normal races; restricted unreadable records are counted",
            "A zombie without cmdline/cwd requires prior PID+start-time "
            "correlation for run ownership",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=UUID, required=True)
    parser.add_argument("--known-process", type=_known_process, action="append", default=[])
    parser.add_argument("--expect-none", action="store_true")
    options = parser.parse_args()
    result = inspect(options.run_id, options.known_process)
    print(json.dumps(result, indent=2, allow_nan=False))
    if result["status"] == "NOT RUN":
        return 2
    if options.expect_none:
        return (
            0
            if (
                result["owned_process_count"] == 0
                and result["unattributed_native_zombie_count"] == 0
            )
            else 1
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
