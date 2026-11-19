Build the `export` command.

Using the files `docs/extract_schema.py` and `docs/generate_docs.py` build the functionality.  It should use the database name passed as an argument.  It should look for `.dbschemer.toml` in the current directory or use the file provided as an argument.

## Requirements (added during review)

- Command: `dbschemer export <database_name> [--file <config_file>] [--row-count]`
  (matches the README Usage section).
  - `<database_name>` is required. It selects the `[databases.<database_name>]` table in the
    config file.
  - `--file` defaults to `./.dbschemer.toml`. A missing or unreadable file, or invalid TOML,
    prints a clear error and exits 1.
  - An unknown database name prints an error that lists the configured names, and exits 1.
- Config model (`.dbschemer.toml`), one entry per `[databases.<name>]`:
  - `connection_string` (required): `mssql+mssql-python://<ODBC string>` or any SQLAlchemy URL.
    Engines are built with the existing `locallib.db.create_db_engine`.
  - `password_env_var` (optional): the name of the environment variable that holds the
    password. If it is set and that variable is missing or empty, fail with a clear error.
    The password is passed as `password=` to `create_db_engine` and never formatted into a
    string or logged.
  - `output` (required): the output directory. A relative path is resolved against the
    **directory that holds the config file**, not the cwd. (This is the same thing when the
    default `./.dbschemer.toml` is used.)
  - Unknown keys are an error (`extra="forbid"`), so typos are caught.
  - The `init` template (`CONFIG_TEMPLATE`) must load with this model (test-enforced).
- Export pipeline: extract the schema into a dict (`extract_schema.py` logic). Write
  `<output>/schema.json`. Then generate markdown from that dict (`generate_docs.py` logic), all
  in one command. The generator takes the dict directly; it does not re-read the JSON.
- Output layout: written directly into `<output>` (no extra `<database>/schema/` level).
  ```
  <output>/schema.json
  <output>/README.md               # index
  <output>/views.md
  <output>/schemas/<schema>.md
  <output>/tables/<schema>.<table>.md
  <output>/stored_procedures.md    # only if any
  <output>/procedures/<schema>.<proc>.md
  <output>/functions.md            # only if any
  <output>/functions/<schema>.<func>.md
  ```
  `<output>` and its parent directories are created if they are missing.
- Deterministic output: running it twice against an unchanged schema gives identical files.
  - Row counts (from `sys.partitions`) are left out **everywhere** (the JSON, the README
    "Total Rows" column, the schema files' "Rows" column and the table files) unless
    `--row-count` is given. This finishes the TODO in `generate_docs.py`.
  - `schema.json` is written with `indent=2`, `sort_keys=False` (insertion order is already
    deterministic, because every query has an `ORDER BY`), `default=str`, UTF-8, with a
    trailing newline.
  - All markdown files are written as UTF-8 with `\n` newlines.
- `server` in the output comes from the connection string: the ODBC `Server=` key (via
  `parse_odbc_keys`) or the URL host. It is never the password or the full connection string.
- Scope: SQL Server only (the queries use `sys.*` catalog views).
- Console output: progress messages go through `logger` (debug/info). On success the command
  prints a short summary with `click.echo`: the output path and the counts of tables, views,
  procedures and functions. The large per-table summary that `generate_docs.py` prints to the
  console is dropped.
- Errors: connection or query failures (`sqlalchemy.exc.DBAPIError` / `OperationalError`)
  become a `click.ClickException` with a clean message, and the message has no password in it.
  `OSError` while writing also becomes a `ClickException`.
- `export` does not read databases from the tool's `settings.toml` (spec 261111, decision 6).

## Bugs in the source scripts to fix while porting (decided during review)

1. **Broken links in schema files.** `schemas/<schema>.md` links to `tables/<schema>.<table>.md`,
   but that path is relative to `schemas/`. The link must be `../tables/...`.
2. **Duplicate rows for partitioned tables.** `tables_query` joins `sys.partitions` with
   `index_id IN (0,1)`, so it returns one row per partition. As a result `row_count` ends up
   holding only the last partition's count. Fix: get the counts in a subquery with
   `SUM(p.rows)`, grouped by `object_id`.
3. **Unescaped markdown table cells.** Column descriptions, defaults, parameter defaults,
   index and FK names, and view/table names in table rows are not escaped. Apply the existing
   `|` / newline escaping (`_format_extended_properties` already does this) to every value
   written into a markdown table cell.
4. **Fragile keys.** `".".join(fk_key.split(".")[:2])` breaks when a schema or table name
   contains a `.`. Use tuple keys `(schema, table)` instead of joined strings.
5. **Duplicated type formatting.** The column type formatting in the table loop repeats
   `_format_param_type`. Use one helper for both.
6. **`print()` calls and hard-coded paths.** These are replaced by injected config and logger
   output (see Requirements).

## Proposed implementation

1. `locallib/dbschemer_config.py`: pydantic `DbschemerDatabase` (`connection_string: str`,
   `password_env_var: str | None`, `output: Path`, `extra="forbid"`) and `DbschemerConfig`
   (`databases: dict[str, DbschemerDatabase]`, `base_dir: Path`). `DbschemerConfig.load(path)`
   uses `tomllib` and raises `ConfigError` (a new exception) for a missing file, bad TOML or a
   validation error. It also has `resolve_output(name) -> Path`.
2. `locallib/services/schema_extractor.py`: `SchemaExtractor(engine: Engine, server: str,
   include_row_count: bool)` with `extract(database: str) -> dict`. The SQL lives in module
   constants (or `locallib/services/schema_queries.py`).
3. `locallib/services/docs_generator.py`: `DocsGenerator(include_row_count: bool)` with
   `generate(schema: dict, output_dir: Path) -> list[Path]`. These are pure functions over the
   dict, plus the file writes.
4. `locallib/services/export_service.py`: `ExportService(extractor, generator, output_dir)`
   with `run(database) -> ExportResult` (counts and output path). It writes `schema.json`, then
   calls the generator.
5. `ServiceFactory.create_export_service(config: DbschemerConfig, name: str, include_row_count:
   bool)`. It reads the password from `os.environ`, builds the engine with the injected
   `engine_builder` (and caches it in `self._engines`, so `dispose()` cleans it up), derives
   `server`, and builds the extractor, generator and service.
6. `locallib/commands/export.py`: a thin click command with `@pass_factory`. It converts
   `ConfigError`, `KeyError` (unknown database), `ValueError`, `DBAPIError` and `OSError`
   into `ClickException`. Register it in `locallib/cli.py`.
7. Tests (`@pytest.mark.unit`, no database):
   - config: load the init template; check relative output resolution against the config
     dir; check errors for a missing file, bad TOML, an unknown key and an unknown database;
     check password env var missing vs set.
   - extractor: a fake `Connection` / `Engine` returns canned rows per query, and the test
     checks the dict shape (FK/index grouping, included columns, extended properties, and
     that row counts are omitted without `--row-count`).
   - generator: feed a small schema dict into `tmp_path`. Check the file set, the link
     targets (they exist relative to the linking file), that cells with `|` and newlines are
     escaped, the row-count on/off behavior, and that a second run gives byte-identical files.
   - CLI: `export` with a pre-seeded factory and a fake engine builder; check exit codes for
     each error path.
   - Optional `integration`-marked test against a real SQL Server.
8. README: document `--row-count`, the output layout, and that `output` is relative to the
   config file.
9. `uvx ruff format`, `uvx ruff check --fix`, `uv run mypy`, `uv run pytest tests/unit/`.

## Decisions (resolved 2026-11-13)

1. **Stale files on re-export.** Before writing, delete only what the export generates:
   `schema.json`, `README.md`, `views.md`, `stored_procedures.md` and `functions.md`, plus the
   `schemas/`, `tables/`, `procedures/` and `functions/` directories. Any other file in
   `<output>` is left alone. There is no `--clean` flag.
2. **Output layout.** Files are written directly into `<output>` (layout above).
3. **`schema.json`** is kept.
4. **Password env var configured but missing or empty:** fail with a clear error (exit 1).
5. **Legacy `settings.toml` database support** (`AppSettings.databases`, `DatabaseSettings`,
   `ServiceFactory.get_engine`, `redact_database_passwords`, the `[default.databases.*]`
   examples) is removed in a separate cleanup, not in this change.
6. **Legacy scripts.** Delete `docs/extract_schema.py` and `docs/generate_docs.py` once they
   are ported.
7. **Procedure and function `created` / `modified` dates** are kept.

## Review notes (2026-11-13)

Changes made during review:
- Fixed the typo `docs/extract_schmema.py` -> `docs/extract_schema.py`.
- Added the Requirements, "Bugs in the source scripts", Proposed implementation and Open
  questions sections.
- Decided (low risk / high confidence): the CLI signature matches the README; config errors
  and unknown database names exit 1 with clear messages; `output` is resolved relative to the
  config file; extraction and generation run in one pass with no JSON round-trip; output is
  deterministic, and row counts are opt-in via `--row-count` everywhere (this finishes the
  script's TODO); `server` is derived from the connection string; scope is SQL Server only;
  `print` is replaced by logger output plus a short summary.
- Found 6 issues in the source scripts that the port must fix (listed above).
- The requester answered the open questions (now Decisions 1-7 above).
- Plan details added on top of Decisions 1-7 (low risk):
  - Extract the schema **before** cleaning, so a connection or query failure leaves the
    previous docs in place.
  - `clean` never follows symlinked directories.
  - The `database` value in the output comes from the connection string's
    `Database=` key or the URL database, and falls back to the config name.
- Implementation plan: `docs/agent/plans/261113_dbschemer_export_plan.md`.

## Implementation summary (2026-11-13)

Implemented on branch `add-export-command` (not committed).

New modules:
- `locallib/dbschemer_config.py`: `ConfigError`, `DbschemerDatabase`, `DbschemerConfig`
  (`load`, `get`, `resolve_output`). Besides `base_dir`, the model also keeps `path` (the
  config file) so the unknown-database message can name it. Both are set by `load()`; a
  `path` / `base_dir` key in the file is rejected.
- `locallib/db.py`: `describe_server`, `describe_database`.
- `locallib/services/schema_queries.py`, `schema_extractor.py`, `docs_generator.py`,
  `export_service.py`.
- `ServiceFactory.create_export_service` (engine cached as `export:<name>`).
- `locallib/commands/export.py`, registered in `locallib/cli.py`.
- Tests: `tests/fakes.py` (fake engine + canned rows), `tests/unit/test_dbschemer_config.py`,
  `test_schema_extractor.py`, `test_docs_generator.py`, `test_export_service.py`, additions to
  `test_db.py`, `test_dependencies.py`, `test_main.py`; optional
  `tests/integration/test_export_integration.py` (skipped unless
  `DBSCHEMER_IT_CONNECTION_STRING` is set).
- README Usage updated; `docs/extract_schema.py` and `docs/generate_docs.py` deleted.

Deviations / additions beyond the plan (all for determinism or clean errors):
- Queries changed beyond `TABLES_QUERY`:
  - `FK_QUERY` also orders by `fkc.constraint_column_id` and `INDEX_QUERY` by
    `ic.index_column_id`. Without this, the column order inside composite FKs and the order of
    included columns was undefined.
  - The procedure and function extended-property queries now filter `ep.minor_id = 0`. Before,
    parameter-level properties were mixed in and could overwrite the object's own properties
    with the same name.
- `sqlalchemy.exc.ArgumentError` (an unparsable `connection_string`) becomes
  `Invalid connection_string for '<name>' in <file>`. The parser's own message is not shown,
  because it echoes the whole string.
- `_cell` also replaces a lone `\r`.
- The `database` passed to `ExportService.run` is computed in the command
  (`describe_database(...) or database_name`).

Known limitations (same as the scripts): ~~markdown link targets are not URL-encoded~~
(fixed in the code review below).

Verification: `uvx ruff format`, `uvx ruff check` and `uv run mypy` are clean;
`uv run pytest tests/` gives 138 passed, 1 skipped (the integration test). No export has been
run against a real SQL Server.

## Code review fixes (2026-11-13)

A code review of `main...HEAD` was run, and these high-confidence findings were fixed:
- **Extended-property joins** (`COLUMNS_QUERY`, `PROCEDURES_QUERY`, `FUNCTIONS_QUERY`) now
  filter `ep.class = 1`. Before, an `MS_Description` on an index (class 7, where `minor_id` is
  the index_id) could attach to the column with the same id, or duplicate its row.
- **`FUNCTION_PARAMS_QUERY`** now skips `parameter_id = 0`, the return value of a scalar
  function. It had been listed as an unnamed INPUT parameter.
- **File names / links** (`docs_generator.py`): the new `_file_name()` replaces `/` and `\`
  in schema and object names, so a name like `../x` cannot write outside `<output>`. The new
  `_href()` URL-encodes every markdown link, so names with spaces or parentheses link correctly.
- **`export` errors**: the `KeyError` handler now covers only `config.get()`, so a `KeyError`
  from a bug inside the extractor or generator is no longer shown as a user error. The
  command also catches `mssql_python.Error`: `mssql+mssql-python` engines use the pyodbc
  dialect, so SQLAlchemy does not wrap those errors in `DBAPIError`.
- Tests added: unsafe names and encoded links, the mssql_python error path, an internal
  KeyError that is no longer masked, and the query filters. Results: `uv run pytest tests/`
  gives 142 passed, 1 skipped; ruff and mypy (`locallib`) are clean.

Follow-up (decided by the requester, 2026-11-13):
- **Cleanup refactor done.** The new `DocsGenerator._write_routines()` writes both the
  procedure pages and the function pages and their indexes. Tables are grouped by schema
  once (`_group_by_schema`), and the result is passed to `_index()`. The generated output is
  byte-identical to the output before the refactor (diffed on the sample schema).
- **Accepted, not changed:**
  - `clean()` removes the generated directories even if the user made them. The
    application owns the output directory.
  - Objects whose names differ only by case can collide on case-insensitive filesystems.
  - `describe_server` / `describe_database` do not recognize the ODBC synonyms
    (`Data Source`, `Address`, `Initial Catalog`).
