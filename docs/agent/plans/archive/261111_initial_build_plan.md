# Plan: `dbschemer init` command

Source spec: [`docs/agent/specs/261111_initial_build.md`](../specs/261111_initial_build.md)

## Goal

`dbschemer init [--file <path>] [--force]` writes a sample `.dbschemer.toml` (the README sample
config) to the current directory, or to `--file`.

## Behavior

| Situation | Result |
|---|---|
| Target does not exist, parent dir exists | Write template, print `Created <path>`, exit 0 |
| Target exists, no `--force` | Print error `<path> already exists; use --force to overwrite`, exit 1, file unchanged |
| Target exists, `--force` | Overwrite, print `Created <path>`, exit 0 |
| Parent directory of target missing | Print error `Directory <parent> does not exist`, exit 1, nothing created |

## Steps

0. **Settings never read from the cwd** (spec decision 5) – `locallib/settings.py`,
   `locallib/appsettings.py`
   - Replace `SETTINGS_FILE = "./settings.toml"` / `default_settings_file()` with
     `default_settings_dir() -> Path`. It returns `PACKAGED_SETTINGS_FILE.parent` when
     `locallib/settings.toml` exists, and otherwise the repo root (`Path(__file__).resolve().parent.parent`).
   - `AppSettings.load(env, settings_dir: Path | None = None)`: if `settings_dir` is `None`, use
     `default_settings_dir()`. Load `settings.toml`, `secrets.toml` and `settings.local.toml`
     from that directory. Pass the paths as `str` to `from_toml`. A missing `secrets.toml` or
     `settings.local.toml` is fine (already true today).
   - Tests (`tests/conftest.py`): the autouse `isolated_cwd` fixture must also monkeypatch
     `locallib.settings.default_settings_dir`. Patch it where it is looked up: if
     `appsettings.py` imports the function by name, patch `locallib.appsettings.default_settings_dir`.
     Point it at `tmp_path`, so the repo's real `settings.toml` is never read. The existing
     `settings_file` / `secrets.toml` fixtures that write into `tmp_path` then keep working
     unchanged.
   - Update `tests/unit/test_settings.py` tests for `default_settings_file` to cover
     `default_settings_dir` instead (packaged dir present -> package dir; absent -> repo root).
   - Add a test: a `settings.toml` in the cwd with a distinctive `appname` is **not** loaded
     when `default_settings_dir` points elsewhere.
   - Update `tests/README.md` and the comment on `[tool.hatch.build.targets.wheel.force-include]`
     in `pyproject.toml` to describe the new behavior.

1. **Template** – `locallib/services/config_template.py`
   - `CONFIG_TEMPLATE: str` that matches the README sample exactly (comments included):
     two databases `sample` and `sample2`, each with
     `connection_string="mssql+mssql-python://Server=<server>;Database=<database>;UID=<user>;TrustServerCertificate=yes;Encrypt=yes;"`,
     `password_env_var="DBSCHEMER_PWD_<name>"`, `output="./docs/db/<name>"`.
   - The README sample has no trailing whitespace (cleaned in review), so the template can be
     a byte-for-byte copy of the README block.

2. **Service** – `locallib/services/init_service.py`
   ```python
   class InitService:
       def __init__(self, template: str): ...
       def run(self, path: Path, force: bool = False) -> Path:
           # parent missing -> FileNotFoundError (explicit check, clear message)
           # write with open(path, "x" if not force else "w", encoding="utf-8")
           #   -> "x" raises FileExistsError atomically (no exists()/write race)
           # return path
   ```
   - Log the action with `logger.info`. Do not construct other classes.

3. **Factory** – `locallib/dependencies.py`
   - Add `create_init_service(self) -> InitService` that returns
     `InitService(template=CONFIG_TEMPLATE)`.

4. **Command** – `locallib/commands/init.py`
   ```python
   @click.command("init")
   @click.option("--file", "file", type=click.Path(dir_okay=False, path_type=Path),
                 default=Path(".dbschemer.toml"), show_default=True)
   @click.option("--force", is_flag=True, default=False, help="Overwrite an existing file.")
   @pass_factory
   def init(factory, file, force): ...
   ```
   - Catch `FileExistsError` and `FileNotFoundError`, then raise `click.ClickException(msg)`
     (exit code 1). Also catch any other `OSError` (e.g. `PermissionError`) and convert it to
     a `ClickException` with the OS message, so `main()` does not log a full traceback.
   - On success, `click.echo(f"Created {path}")`.
   - Name the function `init` (or `init_command` with `@click.command("init")` to avoid
     shadowing). Either way the command name is `init`.

5. **Register** – `locallib/cli.py`: `cli.add_command(init)`.

6. **Tests**
   - `tests/unit/test_init_service.py` (`@pytest.mark.unit`, uses `tmp_path`):
     - writes the file, and the content equals `CONFIG_TEMPLATE`
     - the output parses with `tomllib`; `databases.sample` and `databases.sample2` each have
       `connection_string`, `password_env_var`, `output`; the env vars are `DBSCHEMER_PWD_sample`
       and `DBSCHEMER_PWD_sample2`
     - existing file + `force=False` raises `FileExistsError` and the content is unchanged
     - existing file + `force=True` overwrites it
     - missing parent dir raises `FileNotFoundError` and creates no directory
   - `tests/unit/test_main.py` (CLI via `CliRunner`, uses the `settings_file` fixture so the
     factory can load settings):
     - `init` creates `.dbschemer.toml` in `isolated_cwd`, exit 0, `Created` in the output
     - second `init` exits 1 with "already exists"
     - `init --force` exits 0
     - `init --file sub/x.toml` exits 1 when `sub/` is missing; succeeds once `sub/` exists
     - `--help` lists `init`
   - Factory test in `tests/unit/test_dependencies.py`: `create_init_service()` returns an
     `InitService`.
   - Optional: a test that the template matches the README sample block, to keep them in sync.
     Locate README via `Path(__file__).resolve().parents[2] / "README.md"` (tests run with
     cwd changed to `tmp_path` by the autouse `isolated_cwd` fixture).

7. **Verify**: `uvx ruff format`, `uvx ruff check --fix`, `uv run mypy`,
   `uv run pytest tests/unit/`.

8. **Wrap up**: add an implementation summary to this plan and to the spec.

## Out of scope

- The `export` command and its config model, including building engines from `.dbschemer.toml`
  (the README already documents `.dbschemer.toml` as the database config source).
- Removing the `example` command/service/tests (kept by decision).

## Code review (2026-11-13, `main...HEAD`)

- Branch contains only docs/config changes (commit `5a8367c`); steps 0–8 above are **not yet
  implemented** (no `init` command, `InitService`, `config_template.py`, or settings-dir change).
- Reviewed diff: README/pyproject/`dbschemer.py`/MEMORY.md `main.py` -> `dbschemer.py` rename is
  correct; `uv run mypy` passes; `uv run pytest tests/unit` passes (72). Ruff errors exist only in
  pre-existing `docs/extract_schema.py` and `docs/generate_docs.py` (not part of this branch).
- No code changes made during review.
- Note: README now documents `dbschemer init` and cwd-independent settings ahead of the
  implementation; MEMORY.md still describes the current `./settings.toml` fallback, which
  step 0 will change and should be updated then.

## Implementation summary (2026-11-13)

All steps 0–8 implemented on `add-init-command`.

- **Settings (step 0):** `locallib/settings.py` drops `SETTINGS_FILE`/`default_settings_file()`
  for `default_settings_dir(packaged=None, repo_root=None) -> Path` (packaged `locallib/` dir
  if `locallib/settings.toml` exists, else `REPO_ROOT`). `AppSettings.load(env, settings_dir=None)`
  reads `settings.toml`, `secrets.toml`, `settings.local.toml` from that dir only.
  `tests/conftest.py` `isolated_cwd` patches `locallib.appsettings.default_settings_dir` to
  `tmp_path`. New tests cover packaged/repo-root selection, loading from `settings_dir`, and
  ignoring a cwd `settings.toml`/`secrets.toml`.
- **Template:** `locallib/services/config_template.py` builds `CONFIG_TEMPLATE` from a per-database
  block (keeps lines under ruff's 88-char limit); a test asserts it equals the README `toml`
  block byte-for-byte.
- **Service:** `locallib/services/init_service.py` `InitService(template).run(path, force)` — explicit
  parent-dir check (`FileNotFoundError("Directory <parent> does not exist")`), atomic `"x"` open
  re-raised as `FileExistsError("<path> already exists; use --force to overwrite")`, LF newlines.
- **Factory/command:** `ServiceFactory.create_init_service()`; `locallib/commands/init.py`
  `init_command` (`@click.command("init")`, `--file`, `--force`) converts any `OSError` to
  `click.ClickException` (exit 1); registered in `locallib/cli.py`.
- **Tests:** `tests/unit/test_init_service.py` (6), init CLI tests in `test_main.py` (6, incl.
  `PermissionError`), factory test in `test_dependencies.py`.
- **Docs:** `pyproject.toml` force-include comment, `tests/README.md`, `MEMORY.md`, README project
  layout (`appsettings.py` vs `settings.py`).
- **Verify:** ruff format/check clean on `locallib`, `tests`, `dbschemer.py`; mypy clean;
  `pytest tests/unit` 87 passed. Manual run from a temp dir containing an invalid `settings.toml`:
  `init` creates the file, rerun exits 1 with "already exists", `--file nope/x.toml` exits 1.
