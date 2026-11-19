❯ op run --env-file=/Users/smayer/mtz/.ro.env -- uv run dbschemer.py --traceback export contactmanager_work
18:13:07 :: Environment: development
18:13:07 :: Extracting schema for 'ContactManager'...
18:13:08 :: Extracting tables...
18:13:08 :: Extracting columns...
Unexpected error: RuntimeError: Unsupported data type for column - 0x16ae84768, Type - -150, column ID - 12
Traceback (most recent call last):
  File "/Users/smayer/source/dbschemer/locallib/cli.py", line 72, in main
    cli()
    ~~~^^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1462, in __call__
    return self.main(*args, **kwargs)
           ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1383, in main
    rv = self.invoke(ctx)
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1850, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1246, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 814, in invoke
    return callback(*args, **kwargs)
  File "/Users/smayer/source/dbschemer/locallib/commands/__init__.py", line 60, in new_func
    return ctx.invoke(f, get_factory(ctx), *args, **kwargs)
           ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 814, in invoke
    return callback(*args, **kwargs)
  File "/Users/smayer/source/dbschemer/locallib/commands/export.py", line 52, in export_command
    result = service.run(database)
  File "/Users/smayer/source/dbschemer/locallib/services/export_service.py", line 32, in run
    schema = self.extractor.extract(database)
  File "/Users/smayer/source/dbschemer/locallib/services/schema_extractor.py", line 40, in extract
    tables = self._tables(conn)
  File "/Users/smayer/source/dbschemer/locallib/services/schema_extractor.py", line 108, in _tables
    for row in self._rows(conn, self.queries.COLUMNS_QUERY):
               ~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/smayer/source/dbschemer/locallib/services/schema_extractor.py", line 73, in _rows
    return list(conn.execute(text(sql)))
  File "lib/sqlalchemy/engine/_result_cy.py", line 328, in iterrows
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/cursor.py", line 2368, in _fetchiter_impl
    row = fetchone(self, self.cursor)
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/cursor.py", line 1289, in fetchone
    self.handle_exception(result, dbapi_cursor, e)
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/cursor.py", line 1263, in handle_exception
    result.connection._handle_dbapi_exception(
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
        err, None, None, dbapi_cursor, result.context
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py", line 2354, in _handle_dbapi_exception
    raise exc_info[1].with_traceback(exc_info[2])
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/cursor.py", line 1284, in fetchone
    row = dbapi_cursor.fetchone()
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/mssql_python/cursor.py", line 2334, in fetchone
    raise e
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/mssql_python/cursor.py", line 2303, in fetchone
    ret = ddbc_bindings.DDBCSQLFetchOne(
        self.hstmt,
    ...<2 lines>...
        wchar_decoding.get("encoding", "utf-16le"),
    )
RuntimeError: Unsupported data type for column - 0x16ae84768, Type - -150, column ID - 12
---

# Feature Review

## Summary (added by review)
`dbschemer export` fails on SQL Server with `Unsupported data type for column ... Type - -150, column ID - 12`
while running `COLUMNS_QUERY`.

## Root Cause
ODBC type `-150` is `SQL_SS_VARIANT` (`sql_variant`), which `mssql_python` cannot fetch.
Column 12 of `COLUMNS_QUERY` is `ep.value AS column_description`. `sys.extended_properties.value`
is `sql_variant`. The same column is selected in other queries, so they would fail next:

- `sqlserver.py` `COLUMNS_QUERY` (`ep.value AS column_description`)
- `PROCEDURES_QUERY` (`ep.value AS procedure_description`)
- `FUNCTIONS_QUERY` (`ep.value AS function_description`)
- `DB_EXTENDED_PROPERTIES_QUERY`, `TABLE_/PROCEDURE_/FUNCTION_/COLUMN_EXTENDED_PROPERTIES_QUERY` (`ep.value AS property_value`)
- `PROCEDURE_PARAMS_QUERY`, `FUNCTION_PARAMS_QUERY` (`par.default_value` is also `sql_variant`)

## Requirements
1. Every `sql_variant` column in `locallib/services/queries/sqlserver.py` is cast in SQL, e.g.
   `CAST(ep.value AS NVARCHAR(MAX))`, keeping the existing output alias. Unwrapping `sql_variant` is
   not possible client-side because the driver raises during fetch.
2. NULL stays NULL (`CAST(NULL ...)` is NULL). Descriptions remain `None` when absent.
3. `SchemaExtractor` needs no change. `_grouped_properties` already applies `str()` to values.
4. Add a unit test that scans every query string in the `sqlserver` module and fails if a raw
   `ep.value` or `par.default_value` is selected without a `CAST`. A real SQL Server isn't available to unit tests.
5. Other dialects (`mysql.py`, `postgres.py`) are not affected, so they are out of scope.
6. Verify manually by re-running the failing export command against `contactmanager_work`.

## Implementation Plan (draft; not yet written to plans/ since review is not accepted)
1. Edit the queries listed above in `sqlserver.py`.
2. Add the query-scanning test in `tests/unit/` (marker `unit`).
3. `uvx ruff format`, `uvx ruff check --fix`, `mypy`, `uv run pytest`.
4. Re-run the export manually; if another type error appears, apply the same cast approach.
5. Add a short lesson to `docs/agent/memory/MEMORY.md`: `sql_variant` is unsupported by mssql_python, so cast in SQL.
6. Write an implementation summary into this spec.

## Review Notes
- Changed: the spec was only a raw traceback. I added the root cause, scope, requirements and plan above.
- Nothing was implemented.
- Remaining open questions: none. Residual risk: another unsupported type (e.g. `hierarchyid`, `geography`)
  could appear in other databases. `sys.columns` queries only select names/numbers, so this is unlikely here.

## Implementation Summary
- `locallib/services/queries/sqlserver.py`: all `ep.value` and `par.default_value` selects are now
  `CAST(... AS NVARCHAR(MAX))` with the original aliases (10 places).
- Added `tests/unit/test_sqlserver_queries.py`, which fails if a raw `ep.value` / `par.default_value` is not wrapped in `CAST(`.
- Memory note added to `docs/agent/memory/MEMORY.md`.
- ruff and pytest pass (233 passed). mypy reports 3 errors in tests (`FakeEngine` vs `Engine`) that were already there.
- Not done: the manual re-run against `contactmanager_work` needs live DB credentials (1Password).
