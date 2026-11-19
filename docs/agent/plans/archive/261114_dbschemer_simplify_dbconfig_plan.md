# Plan: simplify dbconfig + multi-db support

Source spec: `docs/agent/specs/261114_dbschemer_simplify_dbconfig.md` (see its Decisions section).

## Steps

1. **Dependencies**: `uv add psycopg pymysql`.
2. **Config model** (`locallib/dbschemer_config.py`): add `type` (Literal `sqlserver|postgres|mysql`), `server`, `database`, `user`, `port`; make `connection_string` optional; model validator: exactly one of `connection_string` or (`type`+`server`+`database`); reject mixing; `port` must be positive.
3. **Connection building** (`locallib/db.py`, pure functions): `build_connection(db)`.
   - sqlserver: ODBC string `Server=<server[,port]>;Database=;[UID=;|Trusted_Connection=yes;]TrustServerCertificate=yes;Encrypt=yes;` with `mssql+mssql-python://` prefix.
   - postgres/mysql: `URL.create(...)`; password injected via existing `password` path.
   - Extend `create_db_engine` `connect_timeout` support: psycopg `connect_timeout`, pymysql `connect_timeout` in `connect_args`.
   - `describe_server` / `describe_database` work for built values.
4. **Wiring** (`dependencies.py`, `commands/export.py`): use the built connection instead of `db.connection_string`; keep password env var behavior; sanitize errors.
5. **Extraction**: split `schema_queries.py` into per-dialect modules (`sqlserver`, `postgres`, `mysql`) exposing the same named queries and column aliases, so `SchemaExtractor` stays unchanged where possible. Select by `type` in the factory (`dependencies.py`); infer type from the connection string / dialect name for `connection_string` configs. Postgres: `pg_catalog`/`information_schema`, `pg_description`, `pg_proc` (kind `p` vs `f`), `pg_class.reltuples`/count for rows. MySQL: `information_schema` (`TABLES`, `COLUMNS`, `STATISTICS`, `KEY_COLUMN_USAGE`, `ROUTINES`, `PARAMETERS`, `VIEWS`), column/table comments. Every query keeps a deterministic `ORDER BY`. Adjust `SchemaExtractor` for type differences (e.g. `max_length`, `is_identity` -> auto increment/serial).
6. **Init/README**: update `config_template.py` and the README sample (byte-identical) to the simple fields; update `test_init_service.py`.
7. **Tests**: unit tests for validator, connection building per type, describe_*, dialect selection, and each query module's shape (aliases present, ORDER BY). Integration tests marked `integration` for postgres/mysql, skipped when no instance is configured.
8. **Finish**: `uvx ruff format`, `uvx ruff check --fix`, `mypy`, `pytest`; add a short note to `docs/agent/memory/MEMORY.md`; write an implementation summary in the spec and this plan.

## Risks
- Postgres/MySQL catalog queries cannot be tested against a live server here; review SQL carefully.
- Largest step is 5; implement and commit per dialect.

## Implementation summary (2026-11-14)

All steps done; see the summary in the spec. Deviations: extraction was not committed per dialect (no commits were requested); the integration test is dialect-aware rather than separate per-database tests. ruff, mypy and pytest (217 passed, 1 skipped) are clean.

## Code review (main...HEAD, 2026-11-14)
- Reviewed config model, `build_connection`/`dialect_for`, factory wiring, extractor changes and the Postgres/MySQL query modules.
- No high-confidence issues found, so no code changes. pytest (217 passed, 1 skipped), ruff and mypy are clean.
- Not verifiable here: the Postgres/MySQL SQL has not been run against live servers (see Risks). Run the integration tests against real instances before relying on it.
