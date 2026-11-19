Build the `init` command as described in the README.md.

This should generate a configuration file in the current directory named `.dbschemer.toml` with the 
format in the README.md

## Requirements (added during review)

- Command: `dbschemer init [--file <path>] [--force]`
  - `--file` defaults to `./.dbschemer.toml` (mirrors the `--file` option on `export`).
  - If the target file already exists, do **not** overwrite it: print an error and exit non-zero.
    `--force` overwrites.
  - On success, print the path of the file written.
- Generated content is the README.md sample config (two example databases, `sample` and
  `sample2`), with comments, and must parse as valid TOML.
- The generated template must be loadable by the config model that `export` will use
  (`databases.<name>` with `connection_string`, `password_env_var`, `output`).
- `init` must not require a database connection or a `.dbschemer.toml` to exist.

## Proposed implementation

1. `locallib/services/init_service.py` — `InitService(template: str)` with
   `run(path: Path, force: bool) -> Path`. Raises `FileExistsError` when the file exists and
   `force` is false and `FileNotFoundError` when the parent directory does not exist. Writes
   UTF-8 text.
2. Template stored as a module-level constant `CONFIG_TEMPLATE` in
   `locallib/services/config_template.py` (no packaging/resource changes needed).
3. `ServiceFactory.create_init_service()` injects the template.
4. `locallib/commands/init.py` — thin click command using `@pass_factory`; converts
   `FileExistsError` / `FileNotFoundError` into `click.ClickException` (exit code 1, clean message).
5. Register in `locallib/cli.py`.
6. Tests (`@pytest.mark.unit`):
   - service: writes file, refuses to overwrite, overwrites with `force`, errors when the parent
     directory is missing, output parses with
     `tomllib` and contains `databases.sample` / `databases.sample2` with all three keys.
   - CLI: `init` in `isolated_cwd` creates `.dbschemer.toml`; second run exits non-zero;
     `--force` succeeds; `--file` writes to the custom path.
7. `uvx ruff format`, `uvx ruff check --fix`, `uv run mypy`, `uv run pytest tests/unit/`.

## Decisions (resolved 2026-11-13)

1. **Connection string** – the template uses the full example
   `"mssql+mssql-python://Server=<server>;Database=<database>;UID=<user>;TrustServerCertificate=yes;Encrypt=yes;"`.
   README updated to match.
2. **Password env var** – named `DBSCHEMER_PWD_<name>`. README updated to match.
3. **Example scaffolding** – keep the `example` command/service/tests for now.
4. **Parent directories** – if the `--file` parent directory does not exist, fail with a clear
   error (non-zero exit); do not create it.

## Review notes (2026-11-13)

Changes made during review:
- Added Requirements, Proposed implementation and Decisions sections above.
- Decided (low risk): no overwrite without `--force`; `--file` option for symmetry with `export`;
  print the written path; template must be valid TOML.
- Fixed README.md config sample: `uv tools install` -> `uv tool install`; run comments now say
  `dbschemer export <name>` (matching the Usage section instead of `uvx dbschemer <name>`);
  `sample2` output path was a copy-paste duplicate of `sample` -> `./docs/db/sample2`.
- Fixed `uv run mypy` failing with "main.py: Cannot read file": `[tool.mypy] files`, the README
  project layout and the `dbschemer.py` docstring now reference `dbschemer.py` instead of the
  nonexistent `main.py`.
- Applied the answers to the open questions: README sample now uses the full connection string
  example and `DBSCHEMER_PWD_<name>`; `pyproject.toml` hatch comment now references
  `dbschemer.py`.
- Implementation plan: `docs/agent/plans/261111_initial_build_plan.md`.

## Decisions – second review (resolved 2026-11-13)

5. **Settings come only from the tool's own settings file.** `AppSettings.load()` must never read
   `settings.toml`, `secrets.toml` or `settings.local.toml` from the current directory.
   - In an installed wheel it reads the packaged `locallib/settings.toml`.
   - In a source checkout, where that packaged file is absent, it reads the repo-root
     `settings.toml` (located from `__file__`, not the cwd).
   - `secrets.toml` and `settings.local.toml` are read from the same directory as the chosen
     `settings.toml`. In a wheel they do not exist, so nothing extra is loaded.
   - A project's own `settings.toml` is therefore ignored. This change is in scope for this spec.
6. **Databases are configured in `.dbschemer.toml`.** The README "Configuration" section and the
   "To add a database" paragraph now say this (updated in review). Building engines from
   `.dbschemer.toml` is left to the `export` spec.

## Review notes – second pass (2026-11-13)

- README sample: removed the trailing whitespace and reworded the password comment to
  "environment variable that holds the database password (if needed)". The template can now be a
  byte-for-byte copy of the README block, so the optional README-sync test is easy to write.
- Plan: write with `open(path, "x")` (atomic, so no exists-then-write race); convert any other
  `OSError` (such as `PermissionError`) into `click.ClickException`; locate README.md from
  `__file__` in the sync test, because tests `chdir` to `tmp_path`.
- `docs/agent/memory/MEMORY.md`: the stale `main.py` reference now says `dbschemer.py`.
- Raised two open questions (now resolved as decisions 5 and 6 above).
- Second-pass questions resolved by the requester (decisions 5 and 6). README Configuration
  section rewritten. The plan gained a step for settings resolution that does not depend on the cwd.

## Implementation summary (2026-11-13)

Implemented per `docs/agent/plans/261111_initial_build_plan.md` (see its implementation summary).

- `dbschemer init [--file <path>] [--force]` writes `CONFIG_TEMPLATE`
  (`locallib/services/config_template.py`, identical to the README sample, test-enforced) via
  `InitService`; refuses to overwrite without `--force`, fails cleanly (exit 1) when the parent
  directory is missing or on other OS errors; prints `Created <path>`.
- Decision 5: settings are loaded only from `default_settings_dir()` (packaged `locallib/` or the
  repo root), never from the cwd.
- `init` needs no database connection and no existing `.dbschemer.toml`.
- ruff, mypy and 87 unit tests pass.
