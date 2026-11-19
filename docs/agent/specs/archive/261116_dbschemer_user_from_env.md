Update the `.dbschemer.toml` file to allow the `user_env_var` setting to specify that the username to use to connect to the database should be read from the specified environment variable.
If a `user` value is provided that should take precedence over the `user_env_var` setting.
If neither value is provided the current behavior of using integrated credentials should remain unchanged.

## Clarified requirements (added in review)
- `user_env_var` is a new optional string field on `[databases.<name>]` (`DbschemerDatabase`): the *name* of the environment variable holding the username. It mirrors the existing `password_env_var`.
- Precedence: `user` > `user_env_var` > integrated credentials. When `user` is set, `user_env_var` is ignored and the environment variable is not read.
- `user_env_var` cannot be combined with `connection_string` (same rule as `user`); config validation fails with a clear message. Put `UID=` in the connection string instead.
- The variable is resolved when the export service is created (`create_export_service` in `locallib/dependencies.py`, using the injected `environ`), where `password_env_var` is already resolved. The resolved name is passed to `build_connection` through a copy of the config (`model_copy(update={"user": ...})`); `build_connection` itself stays pure.
- Applies to all types: sqlserver emits `UID=` instead of `Trusted_Connection=yes`; postgres and mysql set the URL username.
- If `user_env_var` is set (and `user` is not) but the variable is unset or empty, fail with a `ValueError` like `Environment variable X (user for 'name') is not set`. It must NOT silently fall back to integrated credentials.
- Neither `user` nor `user_env_var` set: behavior unchanged.
- The username is never logged or echoed; only the variable name appears in messages.
- Docs and tests: update README (config reference and precedence), the `init` template if it lists optional fields, and add unit tests in `test_dbschemer_config.py` (field accepted, rejected with `connection_string`), `test_dependencies.py` (env used, `user` wins, missing/empty errors, neither -> integrated), and `test_build_connection.py` if needed.

## Review notes
Changes made: added the "Clarified requirements" section above.

Resolved: a missing or empty `user_env_var` variable is a hard error (confirmed by requester). No fallback to integrated credentials.

The implementation plan is in `docs/agent/plans/261116_dbschemer_user_from_env_plan.md`.

## Implementation summary
- `DbschemerDatabase.user_env_var` added and rejected alongside `connection_string`.
- `create_export_service` resolves `user_env_var` (only when `user` is unset) from the injected `environ`, raising `ValueError` if missing/empty, and passes it via `model_copy`; `build_connection` unchanged.
- `init` template and README (sample + reference) document the option and precedence.
- Tests added in `test_dbschemer_config.py` and `test_dependencies.py` (sqlserver, postgres, mysql, precedence, missing/empty, integrated fallback).
- ruff clean; pytest passes; mypy shows only 4 pre-existing test-file errors.
