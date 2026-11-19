"""Run the CLI without the console script: ``uv run dbschemer.py ...``."""

# The CLI lives in locallib/cli.py and this file only re-exports it. Keeping all
# code inside the locallib package simplifies the build: the wheel packages
# locallib (plus this shim) and the console script points at locallib.cli:main.

from locallib.cli import cli, main

__all__ = ["cli", "main"]

if __name__ == "__main__":
    main()
