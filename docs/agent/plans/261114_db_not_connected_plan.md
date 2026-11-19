# Plan: clear database connection errors

Spec: [`docs/agent/specs/261114_db_not_connected.md`](../specs/261114_db_not_connected.md).
Read its **Review** and **Decisions (D1-D4)** sections first.

## Background
- A failed connection with `mssql_python` raises a bare `RuntimeError("[Microsoft][ODBC Driver 18 ...]...")`
  from `ddbc_bindings`. None of the `export.py` handlers catch it.
- `main()` uses `logger.exception`, and loguru's `diagnose=True` prints local values
  (the connection string, and possibly `PWD=`). Remove all `logger.exception` use on
  these paths.

## Steps

### 1. `locallib/db_errors.py` (new)
- `is_db_error(exc) -> bool`: true for `sqlalchemy.exc.DBAPIError`, `mssql_python.Error`,
  or a `RuntimeError` whose message starts with `[Microsoft]` or `[unixODBC]`.
- `class DbErrorTranslator` with a table of rules
  (`pattern: re.Pattern`, `summary: str`, `hint: str`). Rules come from the spec's
  "Known errors to translate" table. Match case-insensitively on the driver message
  (for `DBAPIError` use `str(e.orig)`).
- `translate(exc, database_name: str, server: str) -> str` returns:
  - known: `Cannot connect to '<name>' (server '<server>'): <summary>. <hint>\nDriver error: <raw>`
  - unknown: `Database error for '<name>' (server '<server>'): <ExcType>: <raw>\nRerun with --traceback for details.`
  - Omit `(server ...)` when the server is `""`. Never include the connection string.
  - The timeout hint mentions the `connect_timeout` setting.
- Add `create_db_error_translator()` to `ServiceFactory` (no dependencies).

### 2. `--traceback` global flag (`locallib/commands/__init__.py`, `locallib/cli.py`)
- Add `traceback: bool = False` to `CliOptions` and a `--traceback` flag on the `cli`
  group ("Show full Python tracebacks for errors").
- New `locallib/error_reporter.py`: `class ErrorReporter` with
  `report_unexpected(exc, show_traceback) -> None` and `print_traceback(exc)`. It writes
  to stderr with `click.echo(err=True)` and `traceback.format_exception` (no locals).
  `main()` can't use the factory, which may not exist yet, so it builds `ErrorReporter()`
  directly. It has no dependencies, so this is the one allowed direct construction;
  note why in a comment. Commands get it from `ServiceFactory.create_error_reporter()`.
- `main()`:
  ```python
  try:
      cli()
  except Exception as e:
      ErrorReporter().report_unexpected(e, show_traceback="--traceback" in sys.argv[1:])
      sys.exit(1)
  ```
  This prints `Unexpected error: <Type>: <msg>`, then either the traceback or the hint
  `Rerun with --traceback for the full traceback.`. Reading `sys.argv` is acceptable
  here because the click context is gone once `cli()` raises. Document that.

### 3. `export.py`
- Replace the `DBAPIError` and `mssql_python.Error` branches with:
  ```python
  except Exception as e:
      if not is_db_error(e):
          raise
      if options.traceback: reporter.print_traceback(e)
      raise click.ClickException(translator.translate(e, database_name, describe_server(connection_string))) from e
  ```
  Keep the `ArgumentError` branch first and the `(ValueError, OSError)` branch. Get
  `options` with `click.get_current_context().find_object(CliOptions)`.
- `describe_server` can raise `ArgumentError` for a bad URL. It won't reach this point
  in that case, because the engine build fails first, but wrap it defensively and fall
  back to `""`.

### 4. `connect_timeout` (D3)
- `DbschemerDatabase.connect_timeout: PositiveInt | None = None`.
- Add `connect_timeout: int | None = None` to `create_db_engine` and the
  `EngineBuilder` protocol:
  - mssql-python: `mssql_python.connect(odbc_str, attrs_before={mssql_python.SQL_ATTR_LOGIN_TIMEOUT: n})`
    only when it is set.
  - URL whose `drivername` ends with `+pyodbc`: `connect_args={"timeout": n}`.
  - Other URL with it set: `ValueError(f"connect_timeout is not supported for driver '{url.drivername}'")`.
- `ServiceFactory.create_export_service` passes `db.connect_timeout`. Update the fake
  builders in `tests/conftest.py` and `tests/unit/test_main.py` to accept the new kwarg.
- `config_template.py`: add `# connection/login timeout in seconds (optional)` and
  `# connect_timeout=15` lines to `_database_block`. Make the README sample identical
  (`test_init_service.py` checks this). Mention `--traceback` and `connect_timeout` in
  the README.

### 5. Tests (`pytest -m unit`)
- `tests/unit/test_db_errors.py`: each rule in the spec table, an unknown ODBC message,
  a `DBAPIError` wrapping, a non-ODBC `RuntimeError` (`is_db_error` is False), and an
  empty server.
- `test_main.py`:
  - export with a fake engine raising
    `RuntimeError("[Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9")`
    on connect. Assert exit code 1, "could not be resolved" and the server in the output,
    no `Traceback`, and no `UID=` or password.
  - The same with `--traceback`: `Traceback` is in stderr, and the password still isn't.
  - Update `test_early_failure_is_visible`: expect `Unexpected error`, with no traceback
    unless `--traceback` is passed.
  - `main()` with a non-db `RuntimeError`, with and without `--traceback`.
- `test_db.py`: `connect_timeout` for mssql-python (patch `mssql_python.connect`,
  assert `attrs_before`), for pyodbc (`connect_args`), and the unsupported-driver error.
- `test_dbschemer_config.py`: valid `connect_timeout`, plus 0 and negative values rejected.
- `test_dependencies.py`: `connect_timeout` is passed to the builder.

### 6. Finish
- `uvx ruff format`, `uvx ruff check --fix`, `uv run mypy locallib`, `uv run pytest`.
- Manual check, if a network is available: export against an unresolvable host with
  `connect_timeout=5`, and confirm the single-line message and the timing (the DNS
  caveat in D3).
- Add short notes to `docs/agent/memory/MEMORY.md`: the `RuntimeError` from
  `ddbc_bindings`, and never using `logger.exception` because of the locals leak.
- Write an implementation summary in this plan and in the spec.

## Implementation summary (2026-11-14)
- `locallib/db_errors.py`: `is_db_error` plus a table-driven `DbErrorTranslator` (`DEFAULT_RULES`,
  matched case-insensitively, first match wins), covering every row of the spec table.
- `locallib/error_reporter.py`: `ErrorReporter` (stderr, stdlib `traceback`, no locals).
  `main()` builds it directly (documented); commands use `ServiceFactory.create_error_reporter()`.
  `ServiceFactory.create_db_error_translator()` was added as well.
- `--traceback` global flag -> `CliOptions.traceback`; `main()` reads `sys.argv` for it.
- `export.py`: one `except Exception` branch after the `ArgumentError` and `(ValueError, OSError)`
  branches, which re-raises anything that is not a db error. `_safe_server` falls back to `""`.
- `connect_timeout` (`PositiveInt | None`) added to the config, `create_db_engine` and `EngineBuilder`
  (default `None`, so `get_engine` is unchanged). Template and README samples updated, and the
  README documents `connect_timeout` and `--traceback`.
- Also removed `logger.exception` from `ServiceFactory.dispose` (same locals leak).
- Tests: new `test_db_errors.py`, plus new tests in `test_main.py`, `test_db.py`,
  `test_dbschemer_config.py` and `test_dependencies.py`. Two existing export error tests were
  updated to the new message format. The fake builders already accepted `**kwargs`. 185 passed;
  ruff and mypy are clean.
- Manual check (unresolvable host, `connect_timeout=5`): the clean message printed and exit was 1
  after about 5.3s, so on this machine the timeout did bound the DNS failure. The password was not
  in the `--traceback` output.

## Code review fixes (2026-11-14)
- `db_errors.py`: moved the "cannot open the database" rule (4060) ahead of "login failed".
  SQL Server's 4060 message contains "The login failed." and is usually followed by an
  18456/28000 record, so it was being reported as a login failure. Added
  `test_cannot_open_database_wins_over_login_failed`. 186 passed; ruff and mypy clean.
- `.dbschemer.toml` (a personal config with internal server names, UID and local output paths)
  had been committed; it was removed from the branch commit (amended) and added to `.gitignore`.
