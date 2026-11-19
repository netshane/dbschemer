# Plan: `dbschemer export` command

Source spec: [`docs/agent/specs/261113_dbschemer_export.md`](../specs/261113_dbschemer_export.md)
(the Requirements, "Bugs in the source scripts" and Decisions sections are authoritative).

Source scripts being ported: `docs/extract_schema.py`, `docs/generate_docs.py` (deleted at the end).

## Goal

`dbschemer export <database_name> [--file <config>] [--row-count]` reads `[databases.<name>]`
from `.dbschemer.toml` (or `--file`), connects to SQL Server, extracts the schema and writes
`schema.json` plus markdown docs into the configured `output` directory. Running it twice
against an unchanged schema produces identical files.

## Behavior

| Situation | Result |
|---|---|
| Success | Clean generated items, write files, print `Exported <db> to <output>: N tables, N views, N procedures, N functions`, exit 0 |
| Config file missing / unreadable / invalid TOML / validation error (incl. unknown key) | `ClickException` with path + reason, exit 1 |
| Database name not in config | `Database '<name>' is not configured in <path> (configured: a, b)`, exit 1 |
| `password_env_var` set but env var missing or empty | `Environment variable <VAR> (password for '<name>') is not set`, exit 1 |
| Connection / query error (`sqlalchemy.exc.DBAPIError`) | `Failed to export '<name>': <driver message>`, exit 1, no password in message |
| `OSError` while cleaning/writing | `ClickException(str(e))`, exit 1 |

## Steps

1. **Config model**: `locallib/dbschemer_config.py`
   ```python
   class ConfigError(Exception): ...

   class DbschemerDatabase(BaseModel):
       model_config = ConfigDict(extra="forbid")
       connection_string: str
       password_env_var: str | None = None
       output: Path

   class DbschemerConfig(BaseModel):
       model_config = ConfigDict(extra="forbid")
       databases: dict[str, DbschemerDatabase] = {}
       base_dir: Path = Path(".")          # set by load(), not from the file

       @classmethod
       def load(cls, path: Path) -> "DbschemerConfig": ...
       def get(self, name: str) -> DbschemerDatabase: ...   # KeyError w/ configured list
       def resolve_output(self, name: str) -> Path: ...     # base_dir / output if relative
   ```
   - `load`: `tomllib.load` in binary mode. Wrap `FileNotFoundError`, `OSError`,
     `tomllib.TOMLDecodeError` and `pydantic.ValidationError` in `ConfigError` with the path.
     Set `base_dir = path.resolve().parent`.
   - Keep `base_dir` out of the TOML validation: pop it from the input or set it after
     validation with `model_copy(update=...)`.

2. **Server name helper**: `locallib/db.py`
   - `describe_server(conn_str: str) -> str`. For `mssql+mssql-python://`, use
     `parse_odbc_keys(...)` and return `server` (or `""`). Otherwise use
     `make_url(conn_str).host or ""`. It must never return credentials.

3. **Queries**: `locallib/services/schema_queries.py`
   - Copy the SQL constants from `extract_schema.py` unchanged, **except** `TABLES_QUERY`.
     That one gets row counts from a subquery
     `SELECT object_id, SUM(rows) AS row_count FROM sys.partitions WHERE index_id IN (0,1) GROUP BY object_id`,
     LEFT JOINed on `t.object_id` (bug fix 2).

4. **Extractor**: `locallib/services/schema_extractor.py`
   ```python
   class SchemaExtractor:
       def __init__(self, engine: Engine, server: str, include_row_count: bool): ...
       def extract(self, database: str) -> dict[str, Any]: ...
   ```
   - Port `extract_schema()` and split it into private methods per object type. Use tuple keys
     `(schema, name)` / `(schema, table, fk_name)` everywhere instead of `".".join` and
     `split(".")` (bug fix 4).
   - Leave out the `row_count` key from tables when `include_row_count` is false.
   - Strip `function_type_code` as the script does. Convert extended property values with
     `str()`.
   - Replace `print` with `logger.debug`. The output dict structure is otherwise the same as
     the script's.

5. **Generator**: `locallib/services/docs_generator.py`
   ```python
   class DocsGenerator:
       GENERATED_FILES = ("schema.json", "README.md", "views.md",
                          "stored_procedures.md", "functions.md")
       GENERATED_DIRS = ("schemas", "tables", "procedures", "functions")
       def __init__(self, include_row_count: bool): ...
       def clean(self, output_dir: Path) -> None: ...      # Decision 1
       def write_json(self, schema: dict, output_dir: Path) -> Path: ...
       def generate(self, schema: dict, output_dir: Path) -> list[Path]: ...
   ```
   - `clean`: for each name in `GENERATED_FILES`, `unlink(missing_ok=True)`. For each name in
     `GENERATED_DIRS`, `shutil.rmtree` only if it is a real directory (not a symlink; if it is
     a symlink, unlink it). Touch nothing else.
   - `write_json`: `json.dumps(schema, indent=2, default=str) + "\n"`, UTF-8.
   - `generate`: port `generate_docs()` and drop its console summary. Write everything with
     `Path.write_text(..., encoding="utf-8", newline="\n")`. `mkdir(parents=True,
     exist_ok=True)` the output and sub dirs.
   - Bug fixes:
     - (1) links in `schemas/<schema>.md` use `../tables/<schema>.<table>.md`.
     - (3) `_cell(value) -> str` escapes `|` and replaces `\r\n` / `\n` with a space. Apply it
       to every value interpolated into a markdown table row (names, types, defaults,
       descriptions, FK/index columns, extended properties).
     - (5) a single `_format_type(item)` is used for columns and parameters.
   - Row counts when `include_row_count` is false: drop the "Total Rows" column in the
     README schemas table and the "Rows" column in schema files, and leave out `**Rows:**` in
     table files. When it is true, keep the script's output.
   - Keep the per-object ordering the script uses (sorted by schema and name). Iterate
     `tables_by_schema` in sorted order when writing schema files.
   - Return the list of files written (useful for tests and the summary).

6. **Export service**: `locallib/services/export_service.py`
   ```python
   @dataclass(frozen=True)
   class ExportResult:
       output_dir: Path; tables: int; views: int; procedures: int; functions: int

   class ExportService:
       def __init__(self, extractor: SchemaExtractor, generator: DocsGenerator,
                    output_dir: Path): ...
       def run(self, database: str) -> ExportResult:
           schema = self.extractor.extract(database)   # extract first: a DB failure
           self.generator.clean(self.output_dir)       # leaves the old docs intact
           self.generator.write_json(schema, self.output_dir)
           self.generator.generate(schema, self.output_dir)
           return ExportResult(...)
   ```
   - `database` passed to `extract` is the database name from the `Database=` key of the
     connection string, or the URL database, falling back to the config name. Add
     `describe_database(conn_str)` next to `describe_server` in `db.py`.

7. **Factory**: `locallib/dependencies.py`
   ```python
   def create_export_service(self, config: DbschemerConfig, name: str,
                             include_row_count: bool,
                             environ: Mapping[str, str] = os.environ) -> ExportService:
   ```
   - `db = config.get(name)`. If `db.password_env_var` is set, `environ.get(var)` must be a
     non-empty string, otherwise raise `ValueError` (Decision 4).
   - Build the engine with `self._engine_builder(db.connection_string,
     isolation_level="AUTOCOMMIT", password=pwd)`, cache it in `self._engines[f"export:{name}"]`
     so `dispose()` cleans it up, and build the extractor, generator and service.
   - Do not touch `get_engine` or `AppSettings.databases` (Decision 5: separate cleanup).

8. **Command**: `locallib/commands/export.py`
   ```python
   @click.command("export")
   @click.argument("database_name")
   @click.option("--file", "file", type=click.Path(dir_okay=False, path_type=Path),
                 default=Path(".dbschemer.toml"), show_default=True,
                 help="Config file to read.")
   @click.option("--row-count", is_flag=True, default=False,
                 help="Include table row counts in the output.")
   @pass_factory
   def export_command(factory, database_name, file, row_count): ...
   ```
   - Load the config, create the service and run it. Map `ConfigError`, `KeyError`
     (`e.args[0]`), `ValueError`, `sqlalchemy.exc.DBAPIError` (use `str(e.orig)` when present)
     and `OSError` to `click.ClickException`.
   - Echo the summary line. Register it in `locallib/cli.py`.

9. **Tests** (`@pytest.mark.unit`, no database, in `tests/unit/`):
   - `test_dbschemer_config.py`:
     - `CONFIG_TEMPLATE` loads and has `sample` / `sample2`.
     - Relative `output` resolves against the config dir (config in a subdir of `tmp_path`);
       an absolute `output` is kept as is.
     - Errors: missing file, bad TOML, unknown key, missing `output`, unknown database name
       (the message lists the configured names).
   - `test_db.py` additions: `describe_server` / `describe_database` for both connection
     string forms. They never include `PWD`.
   - `test_schema_extractor.py`:
     - A fake engine/connection maps each query constant to a list of
       `SimpleNamespace` rows.
     - Check the composite FK grouping, index key vs included columns, every
       extended-properties level, parameters attached to the right object, and a schema or
       table name containing `.`.
     - `row_count` is absent unless enabled.
   - `test_docs_generator.py` (on `tmp_path`):
     - The expected file set is written.
     - Every relative markdown link resolves to an existing file.
     - `|` and newlines in a description stay in one table cell.
     - Row-count off: no "Rows" text; on: counts present.
     - Two runs give byte-identical output.
     - `clean` removes the generated items but keeps `notes.md` and an unrelated `extra/`
       directory.
     - A stale `tables/x.y.md` is gone after an export without that table.
   - `test_export_service.py`: the order of operations; if extraction fails, the existing
     output is untouched.
   - `test_main.py` / CLI:
     - `export` with a pre-seeded factory (`ctx.meta`) and a fake `engine_builder`; the
       success path prints the summary.
     - Exit 1 for: a missing config, an unknown database, a missing password env var
       (`monkeypatch.delenv`) and a `DBAPIError` raised by the fake engine.
     - `--help` works without a config.
   - Optional `@pytest.mark.integration` test that runs a real export against a server named
     by an env var; skipped by default.

10. **Docs and cleanup**
    - README Usage: add `--row-count`, the output layout, and that `output` is relative to the
      config file and that generated files are replaced on each export.
    - Delete `docs/extract_schema.py` and `docs/generate_docs.py` (Decision 6).
    - Add any non-obvious lessons to `docs/agent/memory/MEMORY.md`.

11. **Verify**: `uvx ruff format`, `uvx ruff check --fix`, `uv run mypy`,
    `uv run pytest tests/unit/`.

12. **Finish**: write an implementation summary at the end of this plan and of the spec.

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
