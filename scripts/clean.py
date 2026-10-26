"""Remove only known disposable EARTHMIND build caches, preserving data and config."""

import shutil
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (".pytest_cache", ".mypy_cache", ".ruff_cache", "apps/web/.next"):
        path = root / relative
        if path.is_symlink():
            raise RuntimeError(f"Refusing to follow cache symlink: {relative}")
        if path.is_dir():
            shutil.rmtree(path)
            print(f"Removed disposable cache: {relative}")
    print("Persistent volumes, datasets, credentials, source, and dependencies preserved")


if __name__ == "__main__":
    main()
