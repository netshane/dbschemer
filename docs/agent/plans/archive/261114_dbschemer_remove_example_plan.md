# Plan: remove example service and command

Spec: `docs/agent/specs/261114_dbschemer_remove_example.md`

1. Delete `locallib/commands/example.py`, `locallib/services/example_service.py`, `tests/unit/test_example_service.py`.
2. `locallib/cli.py`: remove import and `cli.add_command(example)`.
3. `locallib/dependencies.py`: remove `ExampleService` import and `create_example_service`.
4. `tests/unit/test_dependencies.py`: remove the `ExampleService` import and `test_create_example_service_injects_dependencies`.
5. `tests/unit/test_main.py`: re-point global-option/error-path tests to `init` (see spec); remove example-only tests; fix `test_help`.
6. README.md and tests/README.md: remove example references.
7. Remove `--simulate` (decided): `cli.py` option/param, `CliOptions.simulate`, `get_factory` call, `ServiceFactory.simulate` and `from_environment` param; delete `test_simulate_flag`; grep tests/conftest for `simulate`.
8. `grep -rni example` to confirm; run `uvx ruff format`, `uvx ruff check --fix`, `uv run mypy`, `uv run pytest tests/unit/`.
9. Append implementation summary to the spec and this plan.

## Implementation summary
- Deleted `commands/example.py`, `services/example_service.py`, `tests/unit/test_example_service.py`.
- Removed `example` registration from `cli.py`; removed `create_example_service` from `ServiceFactory`.
- Removed `--simulate` end to end (`cli.py`, `CliOptions`, `get_factory`, `ServiceFactory.__init__`/`from_environment`, `tests/conftest.py` FakeServiceFactory).
- `tests/unit/test_main.py`: global-option/error-path tests re-pointed to `init` (log level observed via the `Environment:` debug line or a monkeypatched `InitService.run`); example-only tests deleted; usage-error case now uses `export`.
- README.md and tests/README.md references reworded.
- Verified: ruff format/check clean, 230 unit tests pass, mypy shows only 4 pre-existing test-file errors (same on main), no remaining references outside docs/agent specs/plans.

## Code review (main...HEAD)
- No defects found. Corrected the verification line (mypy has 4 pre-existing errors in tests, identical on main).
