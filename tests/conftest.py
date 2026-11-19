"""Shared fixtures. Unit tests never read the real settings.toml."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from locallib.appsettings import AppSettings
from locallib.dependencies import ServiceFactory
from locallib.settings import ENV_VAR_NAMES

SAMPLE_SETTINGS_TOML = """
[default]
appname = "testapp"

[default.databases.main]
connection_string = "sqlite://"

[default.logging]
level = "DEBUG"
marker = "default"

[development.logging]
level = "DEBUG"
marker = "dev"

[production.logging]
level = "INFO"
marker = "prd"
"""


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run every test in an empty temp dir with no environment variables set, and
    point the tool's settings directory at it, so the real settings.toml /
    secrets.toml can never be picked up."""
    monkeypatch.chdir(tmp_path)
    # appsettings imports default_settings_dir by name, so patch it there.
    monkeypatch.setattr("locallib.appsettings.default_settings_dir", lambda: tmp_path)
    for name in ENV_VAR_NAMES:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


@pytest.fixture
def settings_file(isolated_cwd: Path) -> Path:
    """Write SAMPLE_SETTINGS_TOML to settings.toml in the (patched) settings dir."""
    path = isolated_cwd / "settings.toml"
    path.write_text(SAMPLE_SETTINGS_TOML)
    return path


@pytest.fixture
def make_settings() -> Callable[..., AppSettings]:
    """Build AppSettings directly from keyword values (no files)."""

    def _make(**values: Any) -> AppSettings:
        values.setdefault("appname", "testapp")
        values.setdefault("environment", "development")
        return AppSettings(**values)

    return _make


class FakeServiceFactory(ServiceFactory):
    """ServiceFactory with in-memory SQLite engines and no logging side effects."""

    def __init__(self, settings: AppSettings):
        self.engine_calls: list[tuple[str, dict[str, Any]]] = []
        super().__init__(settings, engine_builder=self._build)

    def _build(self, conn_str: str, **kwargs: Any) -> Engine:
        self.engine_calls.append((conn_str, kwargs))
        return create_engine("sqlite://")

    def configure_logging(self, file_logging: bool = False) -> None:
        pass


@pytest.fixture
def fake_factory(make_settings: Callable[..., AppSettings]) -> FakeServiceFactory:
    settings = make_settings(
        databases={"main": {"connection_string": "mssql+mssql-python://x"}}
    )
    return FakeServiceFactory(settings)
