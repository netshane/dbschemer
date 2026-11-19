# Unit Tests

Core unit tests for the project. Run them after every change to make sure nothing
unexpected has broken.

Test markers are configured in `pyproject.toml`. `pytest` and `pytest-cov` are in the
`dev` dependency group, which `uv sync` installs by default.

Unit tests never read the real `settings.toml` / `secrets.toml` and need no network:
`tests/conftest.py` runs every test in an empty temp directory and points the tool's
settings directory (`locallib.appsettings.default_settings_dir`) at it. Fixtures:

- `settings_file` - writes a sample `settings.toml` into the temp (settings) directory
- `make_settings(**values)` - builds `AppSettings` directly, without files
- `fake_factory` - a `ServiceFactory` that returns in-memory SQLite engines and skips logging setup

Add additional folders under `tests/` for integration and external tests.

## Running tests

```sh
# run all unit tests
uv run pytest tests/unit/

# with coverage
uv run pytest tests/unit/ --cov=locallib --cov-report=term-missing

# single test
uv run pytest tests/unit/ -k "test_init_creates_config"
uv run pytest tests/unit/test_main.py -k "test_init_creates_config"

# show stdout
uv run pytest -s tests/unit/test_main.py

# run unit tests that are not slow
uv run pytest tests/unit/ -m "unit and not slow"
```
