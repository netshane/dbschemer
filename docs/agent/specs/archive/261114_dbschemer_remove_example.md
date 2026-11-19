Remove the example service and command from the application.

## Scope (added by review)

Remove:
- `locallib/commands/example.py` and its registration/import in `locallib/cli.py`
- `locallib/services/example_service.py`, plus `ServiceFactory.create_example_service` and the import in `locallib/dependencies.py`
- `tests/unit/test_example_service.py` and `test_create_example_service_injects_dependencies` in `tests/unit/test_dependencies.py`
- README.md "To add a feature, copy the example slice" paragraph: reword to describe the pattern using `init`/`export` as references.
- `tests/README.md` example `-k "test_example_command"` lines: replace with an existing test (e.g. `test_init_creates_config`).

Rewrite, don't delete: `tests/unit/test_main.py` uses `example` as the vehicle for global-option and error-path tests (`--env`, `--log-level`, settings-load failures, `--traceback`, early failure visibility). Those behaviours still exist and must stay covered. Re-point them at `init` (it uses `@pass_factory` and so loads settings). Tests that asserted example-specific output ("Processing workorderid", "Starting run") need another way to observe the log level, e.g. the `Environment: <env>` debug line emitted by `ServiceFactory.from_environment`, or a monkeypatched `InitService.run` that logs messages.
- `test_help`: drop the `"example" in result.output` assertion (`init`/`export` are covered elsewhere).
- Delete `test_example_command` and `test_service_error_is_nonzero_exit` (no equivalent behaviour); `test_simulate_flag` depends on the open question below.
- `test_help_and_usage_errors_do_not_load_settings`: re-point to `["init", "--help"]` and assert `--force`; drop the `["example"]` usage-error case (init has no required args), or use `["export"]` (missing DATABASE argument, exit 2).

Acceptance: no remaining references to `example`/`ExampleService`/`workorderid` outside `docs/agent/*/archive`; ruff, mypy and `uv run pytest tests/unit/` pass.

## Decision
- Remove the `--simulate` flag as well (CLI option in `locallib/cli.py`, `CliOptions.simulate` and its use in `get_factory` in `locallib/commands/__init__.py`, and `simulate` on `ServiceFactory.__init__`/`from_environment` in `locallib/dependencies.py`). Delete `test_simulate_flag` and fix any test/fixture (`tests/conftest.py`) that passes `simulate=`. Remove any README mention.

## Review notes
- Spec expanded with explicit scope, test-rewrite requirements and acceptance criteria. Added open question on `--simulate`.
- Open question on `--simulate` resolved by requester: remove it.

## Implementation summary
- Deleted `commands/example.py`, `services/example_service.py`, `tests/unit/test_example_service.py`.
- Removed `example` registration from `cli.py`; removed `create_example_service` from `ServiceFactory`.
- Removed `--simulate` end to end (`cli.py`, `CliOptions`, `get_factory`, `ServiceFactory.__init__`/`from_environment`, `tests/conftest.py` FakeServiceFactory).
- `tests/unit/test_main.py`: global-option/error-path tests re-pointed to `init` (log level observed via the `Environment:` debug line or a monkeypatched `InitService.run`); example-only tests deleted; usage-error case now uses `export`.
- README.md and tests/README.md references reworded.
- Verified: ruff format/check clean, 230 unit tests pass, mypy shows only 4 pre-existing test-file errors (same on main), no remaining references outside docs/agent specs/plans.
