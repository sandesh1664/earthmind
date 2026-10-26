"""Check Docker's real ignore behavior with synthetic root and nested env files."""

import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    repository = Path(__file__).resolve().parents[2]
    secret_paths = (
        ".env",
        ".env.local",
        "apps/api/.env",
        "apps/web/.env.local",
        "packages/deep/nested/.env.secret",
    )
    with tempfile.TemporaryDirectory(prefix="earthmind-context-") as temporary:
        root = Path(temporary)
        context = root / "input"
        output = root / "output"
        context.mkdir()
        shutil.copyfile(repository / ".dockerignore", context / ".dockerignore")
        (context / "Dockerfile").write_text("FROM scratch\nCOPY . /context\n")
        for name in secret_paths:
            fixture = context / name
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text("EARTHMIND_SYNTHETIC_SECRET=must-not-copy\n")
        (context / ".env.example").write_text("SAFE_EXAMPLE=yes\n")
        (context / "apps/web/package.json").write_text("{}\n")
        subprocess.run(
            [
                "docker",
                "build",
                "--quiet",
                "--platform",
                "linux/arm64",
                "--output",
                f"type=local,dest={output}",
                str(context),
            ],
            check=True,
        )
        exported = output / "context"
        leaked = [name for name in secret_paths if (exported / name).exists()]
        if leaked:
            raise RuntimeError(f"Docker context leaked synthetic environment files: {leaked}")
        for name in (".env.example", "apps/web/package.json"):
            if not (exported / name).is_file():
                raise RuntimeError(f"Docker context incorrectly excluded {name}")
    print("PASS: Docker excludes 5 root/nested env fixtures and includes safe project files")


if __name__ == "__main__":
    main()
