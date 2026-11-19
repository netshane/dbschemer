The following error occured when attempting to connect to a database that is not accessible.
This should not dump out a full traceback to the user.  It should display an error and attempt to translate it.
If the db server is not reachable, the user should be informed with a clear error message rather than a full traceback.
For other errors that can't be decoded, provide enough information to troubleshoot.



❯ op run --env-file=XXXXX -- uv run dbschemer.py export contactmanager_work
11:47:10 :: Environment: development
11:47:11 :: Extracting schema for 'ContactManager'...
11:47:26 :: Uncaught exception: [Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9
Traceback (most recent call last):

  File "/Users/smayer/source/dbschemer/dbschemer.py", line 12, in <module>
    main()
    └ <function main at 0x10315cd50>

> File "/Users/smayer/source/dbschemer/locallib/cli.py", line 59, in main
    cli()
    └ <Group cli>

  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1462, in __call__
    return self.main(*args, **kwargs)
           │    │     │       └ {}
           │    │     └ ()
           │    └ <function Command.main at 0x1035d85c0>
           └ <Group cli>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1383, in main
    rv = self.invoke(ctx)
         │    │      └ <click.core.Context object at 0x109f8acf0>
         │    └ <function Group.invoke at 0x1035da2a0>
         └ <Group cli>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1850, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
           │               │       │       │      └ <click.core.Context object at 0x10a0e5f90>
           │               │       │       └ <function Command.invoke at 0x1035d8040>
           │               │       └ <Command export>
           │               └ <click.core.Context object at 0x10a0e5f90>
           └ <function Group.invoke.<locals>._process_result at 0x10a114e00>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 1246, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           │   │      │    │           │   └ {'database_name': 'contactmanager_work', 'file': PosixPath('.dbschemer.toml'), 'row_count': False}
           │   │      │    │           └ <click.core.Context object at 0x10a0e5f90>
           │   │      │    └ <function export_command at 0x10a115380>
           │   │      └ <Command export>
           │   └ <function Context.invoke at 0x1035d2140>
           └ <click.core.Context object at 0x10a0e5f90>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 814, in invoke
    return callback(*args, **kwargs)
           │         │       └ {'database_name': 'contactmanager_work', 'file': PosixPath('.dbschemer.toml'), 'row_count': False}
           │         └ ()
           └ <function export_command at 0x10a115380>

  File "/Users/smayer/source/dbschemer/locallib/commands/__init__.py", line 59, in new_func
    return ctx.invoke(f, get_factory(ctx), *args, **kwargs)
           │   │      │  │           │      │       └ {'database_name': 'contactmanager_work', 'file': PosixPath('.dbschemer.toml'), 'row_count': False}
           │   │      │  │           │      └ ()
           │   │      │  │           └ <click.core.Context object at 0x10a0e5f90>
           │   │      │  └ <function get_factory at 0x10396b1c0>
           │   │      └ <function export_command at 0x10a115220>
           │   └ <function Context.invoke at 0x1035d2140>
           └ <click.core.Context object at 0x10a0e5f90>

  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/click/core.py", line 814, in invoke
    return callback(*args, **kwargs)
           │         │       └ {'database_name': 'contactmanager_work', 'file': PosixPath('.dbschemer.toml'), 'row_count': False}
           │         └ (<locallib.dependencies.ServiceFactory object at 0x10388af90>,)
           └ <function export_command at 0x10a115220>

  File "/Users/smayer/source/dbschemer/locallib/commands/export.py", line 44, in export_command
    result = service.run(database)
             │       │   └ 'ContactManager'
             │       └ <function ExportService.run at 0x10a04d430>
             └ <locallib.services.export_service.ExportService object at 0x10a1763c0>

  File "/Users/smayer/source/dbschemer/locallib/services/export_service.py", line 32, in run
    schema = self.extractor.extract(database)
             │    │         │       └ 'ContactManager'
             │    │         └ <function SchemaExtractor.extract at 0x10a04c460>
             │    └ <locallib.services.schema_extractor.SchemaExtractor object at 0x10a176120>
             └ <locallib.services.export_service.ExportService object at 0x10a1763c0>

  File "/Users/smayer/source/dbschemer/locallib/services/schema_extractor.py", line 28, in extract
    with self.engine.connect() as conn:
         │    │      └ <function Engine.connect at 0x109e6a980>
         │    └ Engine(mssql://)
         └ <locallib.services.schema_extractor.SchemaExtractor object at 0x10a176120>

  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py", line 3279, in connect
    return self._connection_cls(self)
           │    │               └ Engine(mssql://)
           │    └ <class 'sqlalchemy.engine.base.Connection'>
           └ Engine(mssql://)
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py", line 154, in __init__
    self._dbapi_connection = engine.raw_connection()
    │                        │      └ <function Engine.raw_connection at 0x109e6aae0>
    │                        └ Engine(mssql://)
    └ <sqlalchemy.engine.base.Connection object at 0x10a176510>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/engine/base.py", line 3303, in raw_connection
    return self.pool.connect()
           │    │    └ <function Pool.connect at 0x1097d5b10>
           │    └ <sqlalchemy.pool.impl.QueuePool object at 0x10a0e60d0>
           └ Engine(mssql://)
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 445, in connect
    return _ConnectionFairy._checkout(self)
           │                │         └ <sqlalchemy.pool.impl.QueuePool object at 0x10a175d30>
           │                └ <classmethod(<function _ConnectionFairy._checkout at 0x1097d9c70>)>
           └ <class 'sqlalchemy.pool.base._ConnectionFairy'>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 1340, in _checkout
    fairy = _ConnectionRecord.checkout(pool)
            │                 │        └ <sqlalchemy.pool.impl.QueuePool object at 0x10a175d30>
            │                 └ <classmethod(<function _ConnectionRecord.checkout at 0x1097d7320>)>
            └ <class 'sqlalchemy.pool.base._ConnectionRecord'>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 713, in checkout
    rec = pool._do_get()
          │    └ <function QueuePool._do_get at 0x1097e3b60>
          └ <sqlalchemy.pool.impl.QueuePool object at 0x10a175d30>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/impl.py", line 176, in _do_get
    with util.safe_reraise():
         │    └ <class 'sqlalchemy.util.langhelpers.safe_reraise'>
         └ <module 'sqlalchemy.util' from '/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/util/__init__.py'>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py", line 166, in __exit__
    raise exc_value.with_traceback(exc_tb)
          │         │              └ <traceback object at 0x10a46ee00>
          │         └ <method 'with_traceback' of 'BaseException' objects>
          └ RuntimeError('[Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9')
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/impl.py", line 174, in _do_get
    return self._create_connection()
           │    └ <function Pool._create_connection at 0x1097d5590>
           └ <sqlalchemy.pool.impl.QueuePool object at 0x10a175d30>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 386, in _create_connection
    return _ConnectionRecord(self)
           │                 └ <sqlalchemy.pool.impl.QueuePool object at 0x10a175d30>
           └ <class 'sqlalchemy.pool.base._ConnectionRecord'>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 675, in __init__
    self.__connect()
    └ <sqlalchemy.pool.base._ConnectionRecord object at 0x10a0853d0>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 932, in __connect
    with util.safe_reraise():
         │    └ <class 'sqlalchemy.util.langhelpers.safe_reraise'>
         └ <module 'sqlalchemy.util' from '/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/util/__init__.py'>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/util/langhelpers.py", line 166, in __exit__
    raise exc_value.with_traceback(exc_tb)
          │         │              └ <traceback object at 0x10a46ecc0>
          │         └ <method 'with_traceback' of 'BaseException' objects>
          └ RuntimeError('[Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9')
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 928, in __connect
    self.dbapi_connection = connection = pool._invoke_creator(self)
    │    │                               │    │               └ <sqlalchemy.pool.base._ConnectionRecord object at 0x10a0853d0>
    │    │                               │    └ <function Pool._should_wrap_creator.<locals>.<lambda> at 0x10a45f270>
    │    │                               └ <sqlalchemy.pool.impl.QueuePool object at 0x10a175d30>
    │    └ <member 'dbapi_connection' of '_ConnectionRecord' objects>
    └ <sqlalchemy.pool.base._ConnectionRecord object at 0x10a0853d0>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/sqlalchemy/pool/base.py", line 358, in <lambda>
    return lambda rec: creator_fn()
                  │    └ <function create_db_engine.<locals>.mssql_creator at 0x10a149850>
                  └ <sqlalchemy.pool.base._ConnectionRecord object at 0x10a0853d0>

  File "/Users/smayer/source/dbschemer/locallib/db.py", line 110, in mssql_creator
    return mssql_python.connect(odbc_str)
           │            └ <function connect at 0x10a0b4d50>
           └ <module 'mssql_python' from '/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/mssql_python/__init__.py'>

  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/mssql_python/db_connection.py", line 46, in connect
    conn = Connection(
           └ <class 'mssql_python.connection.Connection'>
  File "/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/mssql_python/connection.py", line 319, in __init__
    self._conn = ddbc_bindings.Connection(
    │            │             └ <class 'ddbc_bindings.Connection'>
    │            └ <module 'mssql_python.ddbc_bindings' from '/Users/smayer/source/dbschemer/.venv/lib/python3.14/site-packages/mssql_python/ddb...
    └ <mssql_python.connection.Connection object at 0x10a176660>

RuntimeError: [Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9

---

## Review (2026-11-14)

### Root cause
- `mssql_python.connect()` raises a bare **`RuntimeError`** from the C++ binding
  (`ddbc_bindings.Connection`) when the connection fails at the TCP/ODBC layer. It is
  not an `mssql_python.Error` and SQLAlchemy does not wrap it in `DBAPIError`
  (the engine uses a `creator`), so none of the handlers in
  `locallib/commands/export.py` catch it. It falls through to the catch-all in
  `locallib/cli.py:main()`, which calls `logger.exception(...)`.
- `logger.exception` with loguru's default `diagnose=True` prints **local variable
  values** in every frame. The trace above shows `odbc_str` (server, database, UID).
  `PWD=` is appended at the end of that string and was only hidden here because loguru
  truncated the value. A shorter connection string could print the password. **This is
  a security issue as well as a usability one.**
- `0x2AF9` = 11001 = `WSAHOST_NOT_FOUND`: the server name could not be resolved
  (DNS lookup failed, VPN probably down). The error took about 15 seconds to appear
  because of the driver's login timeout.

### Requirements (refined)
1. A failure to connect during `export` prints a single-line error (no traceback) and
   exits with code 1 (the `click.ClickException` behavior).
2. The message names the config entry and the server (from `describe_server`), and
   never includes the connection string, UID or password.
3. Known causes get a plain-language explanation and a hint, followed by the raw
   driver message on a second line (`Driver error: ...`) for troubleshooting.
4. Errors that can't be decoded print the exception type, the driver message
   (SQLSTATE/native error code when present) and a hint on how to get the full
   traceback (see Q2).
5. Tracebacks are never logged with `diagnose=True` (no local variable values).

### Known errors to translate
| Match (driver message) | Meaning shown to the user |
|---|---|
| `TCP Provider: Error code 0x2AF9` (11001) / `0x2AFC` (11004) | Server name could not be resolved (DNS). Check `Server=` and your network/VPN. |
| `0x274C` (10060) / `Login timeout expired` / SQLSTATE `HYT00` | Server did not respond (timeout). Check the host, port, firewall and VPN. |
| `0x274D` (10061) | Connection refused. SQL Server is not listening on that host/port. |
| `0x2751` (10065) | Host unreachable (no network route). |
| `0x2746` (10054) | Connection reset by the server (often TLS/encryption settings). |
| native error `18456` / SQLSTATE `28000` | Login failed. Check UID and the password env var. |
| native error `4060` | Cannot open the database (wrong name or no permission). |
| `SSL Provider` / `certificate` | TLS/certificate failure. Check `Encrypt` / `TrustServerCertificate`. |
| `Data source name not found` / `Can't open lib` (IM002/01000) | ODBC driver missing. Install ODBC Driver 18 for SQL Server. |

### Proposed implementation
- New `locallib/db_errors.py`: a `DbErrorTranslator` class (built by `ServiceFactory`)
  with `translate(exc, database_name, server) -> str`. It uses a table-driven list of
  `(pattern, explanation, hint)` rules so new rules are cheap to add. Pure logic, so
  it is fully unit-testable without a database.
- A `is_db_error(exc)` helper that recognizes `DBAPIError`, `mssql_python.Error`, and
  `RuntimeError` whose message starts with an ODBC driver prefix (`[Microsoft]`,
  `[unixODBC]`). Other `RuntimeError`s, which are probably real bugs, are not
  swallowed.
- `export.py`: replace the `DBAPIError` / `mssql_python.Error` branches with one
  branch that calls the translator. Log the traceback at DEBUG with `diagnose=False`.
- `cli.py:main()`: catch-all changes per Q1.
- Tests: translator rules (each row above, plus an unknown message), export CLI
  test with a fake engine that raises `RuntimeError('[Microsoft][ODBC Driver 18 for
  SQL Server]TCP Provider: Error code 0x2AF9')` (assert no `Traceback`, server shown,
  UID/PWD not shown, exit code 1), and a non-ODBC `RuntimeError` that still reaches the
  catch-all.

### Decisions (2026-11-14)
- **D1. Generic catch-all:** `main()` no longer prints tracebacks by default. It prints
  `Unexpected error: <Type>: <message>` plus a hint to rerun with `--traceback`, and
  exits with code 1.
- **D2. `--traceback` global flag:** shows the full traceback for both translated
  database errors and unexpected errors. Tracebacks are printed with the standard
  `traceback` module (to stderr), **not** `logger.exception`, so local variable values
  are never shown regardless of how the loguru sinks are configured.
- **D3. `connect_timeout`:** an optional per-database setting in `.dbschemer.toml`
  (integer seconds, > 0). When it is unset, the driver default applies.
  - `mssql+mssql-python://`: passed as `attrs_before={SQL_ATTR_LOGIN_TIMEOUT: n}`
    to `mssql_python.connect` (the documented way to do it; the `timeout=` kwarg is
    the query timeout).
  - `mssql+pyodbc` URLs: `connect_args={"timeout": n}`.
  - Any other URL with `connect_timeout` set: `ValueError` ("connect_timeout is not
    supported for driver X"), which is reported as a normal export error.
  - The sample config (`config_template.py`) and README get a commented-out
    `# connect_timeout=15` line (they must stay identical).
  - Caveat: the login timeout may not bound OS-level DNS resolution time. Verify
    manually against an unreachable host.
- **D4. Scope:** only `export` connects today. The translator is reusable for later
  commands.

### Review changes
- Added this Review section (root cause, refined requirements, error table,
  implementation outline, questions). The original request text is unchanged.
- Flagged the `diagnose=True` local-variable leak (possible password exposure) as part
  of this fix (requirement 5).
- Recorded the user decisions D1-D4 (replacing the open questions) and wrote the plan:
  `docs/agent/plans/261114_db_not_connected_plan.md`.

## Implementation summary (2026-11-14)
Implemented per `docs/agent/plans/261114_db_not_connected_plan.md`. A failed connection during
`export` now prints:
```
Error: Cannot connect to 'bad' (server 'nohost.invalid'): the server name could not be resolved (DNS lookup failed). Check Server= in the connection string and your network/VPN.
Driver error: [Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9
```
and exits with code 1. Errors that can't be decoded print the type, the raw driver message and a
`--traceback` hint. Unexpected errors print `Unexpected error: <Type>: <msg>`. `--traceback`
prints stdlib tracebacks (no local variables). `logger.exception` has been removed from all error
paths. The optional `connect_timeout` setting is supported for mssql-python and pyodbc.

## Code review fixes (2026-11-14)
- `db_errors.py`: moved the "cannot open the database" rule (4060) ahead of "login failed".
  SQL Server's 4060 message contains "The login failed." and is usually followed by an
  18456/28000 record, so it was being reported as a login failure. Added
  `test_cannot_open_database_wins_over_login_failed`. 186 passed; ruff and mypy clean.
- `.dbschemer.toml` (a personal config with internal server names, UID and local output paths)
  had been committed; it was removed from the branch commit (amended) and added to `.gitignore`.
