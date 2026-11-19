- **simplify db config**
- low effort
- setup to allow db to be configured with type, server, database, user
- add support for postgres, mysql, and sql server

## Context (from review)

- The config in question is the per-project `.dbschemer.toml` (`locallib/dbschemer_config.py`, `DbschemerDatabase`), written by `dbschemer init` (`locallib/services/config_template.py`, which must match the README sample byte-for-byte). Today each database needs a raw `connection_string` (an ODBC string for SQL Server).
- Export is SQL Server only: `locallib/services/schema_queries.py` uses `sys.*` catalog views, and `SchemaExtractor` assumes their column names. Connecting to Postgres/MySQL is easy; **extracting their schema is not**. Adding them is a medium-to-large change, not low effort.

## Requirements (clarified)

- Each `[databases.<name>]` accepts `type`, `server`, `database`, `user` (plus existing `password_env_var`, `output`, `connect_timeout`) as an alternative to `connection_string`.
- `type` is one of `sqlserver`, `postgres`, `mysql`.
- `connection_string` stays supported as an advanced override. `connection_string` and the discrete fields are mutually exclusive; config validation rejects mixing them and rejects a database with neither.
- Optional `port` field (non-default ports are common for postgres/mysql).
- Connection strings are built from the fields in `locallib/db.py` (pure functions). The password is still injected separately, never formatted into a string.
  - sqlserver: existing `mssql+mssql-python` ODBC path (`Server`, `Database`, `UID`, `Encrypt=yes`, `TrustServerCertificate=yes` as today). No `user` means `Trusted_Connection=yes`.
  - postgres / mysql: SQLAlchemy URL via `URL.create` (e.g. `postgresql+psycopg`, `mysql+pymysql`), so special characters are escaped.
- `describe_server` / `describe_database` and the export command's error reporting must work for configs built from fields.
- Add the driver dependencies with `uv add` (not pip).
- `dbschemer init` template and README sample switch to the simple fields (keep them identical; update the test).
- Existing `.dbschemer.toml` files that use `connection_string` keep working unchanged.
- `settings.toml` (app-level `[default.databases.*]` used by `get_engine`) is out of scope unless the user says otherwise (see Q1).

## Implementation outline (plan, not started)

1. `DbschemerDatabase`: add `type`, `server`, `database`, `user`, `port`; make `connection_string` optional; model validator for the exclusivity rule above.
2. `db.py`: `build_connection_string` / URL builder per type; route `create_db_engine` and `describe_*` through it.
3. `dependencies.py` / `export.py`: use the built value instead of `db.connection_string`.
4. Extraction: introduce a per-dialect query set / extractor selected by `type` (see Q2).
5. Template, README, tests (unit per type; integration markers for live DBs), memory note.

## Decisions (answered by requester)

1. Scope: only `.dbschemer.toml`; `settings.toml` / `DatabaseSettings` are untouched.
2. Postgres and MySQL get full extraction parity with SQL Server (tables, columns, PKs, FKs, indexes, views, procedures, functions, comments, row counts). Where a concept does not exist, the field is empty. Object comments map to the existing description fields; `extended_properties` holds comments only.
3. Drivers: `psycopg` (v3) for Postgres (`postgresql+psycopg`), `pymysql` for MySQL (`mysql+pymysql`).
4. `connection_string` stays as an override.
5. sqlserver: no `user` means `Trusted_Connection=yes`. For postgres/mysql, no `user` means the driver default.
6. No live Postgres/MySQL instances: tests are unit tests only (fake engines, query-set selection, URL/connection-string building). The new catalog queries cannot be verified against a real server in this repo. This is an accepted risk; mark the integration tests `integration` and skipped until an instance exists.
7. `Encrypt=yes` and `TrustServerCertificate=yes` stay hard-coded for sqlserver.

## Review notes

- 2026-11-14: Spec expanded with context, clarified requirements and a plan outline from the existing code. Left the "low effort" label in place but flagged that Postgres/MySQL extraction contradicts it (Q2). No plan file written, because the review is not accepted yet and Q1–Q7 would change it.
- 2026-11-14 (2): Recorded the requester's answers as decisions. Review accepted; plan written to `docs/agent/plans/261114_dbschemer_simplify_dbconfig_plan.md`.

## Implementation summary (2026-11-14)

- `DbschemerDatabase` gained `type/server/database/user/port`; `connection_string` is optional and mutually exclusive with them (model validator).
- `db.build_connection` builds the ODBC string (sqlserver; `Trusted_Connection=yes` without `user`) or a `URL.create` URL (`postgresql+psycopg`, `mysql+pymysql`); `dialect_for` infers the dialect for `connection_string` configs; `connect_timeout` now supports psycopg and pymysql. Added `psycopg[binary]` and `pymysql`.
- `schema_queries.py` moved to `services/queries/sqlserver.py`; new `postgres.py` and `mysql.py`; `get_queries()` selects the set and `SchemaExtractor` takes it as `queries`. Comments map to description fields; table (and Postgres database) comments go to `extended_properties` as `Comment`. Postgres overloaded routines get their argument list appended to the name; row counts are planner estimates (Postgres) / `TABLE_ROWS` (MySQL).
- Template, README and `export` error text (now "Invalid connection settings") updated; `DocsGenerator` tolerates NULL length/precision/scale.
- Tests: validator, connection building, dialect selection, query-set shape, factory selection. The Postgres/MySQL SQL is **not verified against a live server**; the integration test now selects the dialect from `DBSCHEMER_IT_CONNECTION_STRING`.
