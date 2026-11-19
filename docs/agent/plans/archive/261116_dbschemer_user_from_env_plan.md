# Plan: user_env_var

Source spec: `docs/agent/specs/261116_dbschemer_user_from_env.md`

1. `locallib/dbschemer_config.py`: add `user_env_var: str | None = None` to `DbschemerDatabase`; include it in the `discrete` dict in `_check_connection_fields` so it is rejected with `connection_string`.
2. `locallib/dependencies.py` `create_export_service`: after the password handling, if `db.user` is falsy and `db.user_env_var` is set, read `environ.get(db.user_env_var) or None`. If missing, raise `ValueError(f"Environment variable {var} (user for '{name}') is not set")`. Then `db = db.model_copy(update={"user": value})` before `build_connection(db)`. If `db.user` is set, do not read the environment. Update the docstring.
3. Check the CLI error path surfaces this `ValueError` like the password one.
4. `locallib/services/config_template.py` and `README.md`: document `user_env_var` and the precedence (`user` > `user_env_var` > integrated).
5. Tests: `test_dbschemer_config.py` (accepted; rejected with `connection_string`), `test_dependencies.py` (env used; `user` wins and the env var is not read; missing and empty raise; neither -> `Trusted_Connection`), plus postgres or mysql username via env.
6. Run `uvx ruff format`, `uvx ruff check --fix`, `mypy`, `uv run pytest`.
7. Append an implementation summary to the spec and this plan.

## Implementation summary
- `DbschemerDatabase.user_env_var` added and rejected alongside `connection_string`.
- `create_export_service` resolves `user_env_var` (only when `user` is unset) from the injected `environ`, raising `ValueError` if missing/empty, and passes it via `model_copy`; `build_connection` unchanged.
- `init` template and README (sample + reference) document the option and precedence.
- Tests added in `test_dbschemer_config.py` and `test_dependencies.py` (sqlserver, postgres, mysql, precedence, missing/empty, integrated fallback).
- ruff clean; pytest passes; mypy shows only 4 pre-existing test-file errors.
