import os
import tomllib
from importlib import metadata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr

# Environment variables that select the settings section when --env is not given.
# Checked in order; the first one that is set (non-empty) wins.
ENV_VAR_NAMES = ("APP_ENV", "ASPNETCORE_ENVIRONMENT", "DOTNET_ENVIRONMENT")
ENV_DEVELOPMENT = "development"
ENV_PRODUCTION = "production"
ENVIRONMENTS = (ENV_DEVELOPMENT, ENV_PRODUCTION)

# Used when neither --env nor the environment variable is set. An end user running
# the tool is assumed, so default to production.
DEFAULT_ENVIRONMENT = ENV_PRODUCTION

REDACTED = "**********"


class DatabaseSettings(BaseModel):
    """One entry of the ``[databases.<name>]`` table in settings.toml."""

    # Optional at load time so a stray secrets.toml entry for a database that is
    # not in settings.toml does not stop the app starting. ServiceFactory raises
    # a clear error if such a database is actually requested.
    connection_string: str | None = None
    isolation_level: str = "AUTOCOMMIT"
    # Keep the password out of settings.toml: set it under the same table in
    # secrets.toml (``[default.databases.<name>] password = "..."``).
    # SecretStr keeps it out of repr/str and log output.
    password: SecretStr | None = None


PACKAGE_NAME = "locallib"
PYPROJECT_FILE = Path(__file__).resolve().parent.parent / "pyproject.toml"
# The wheel ships settings.toml inside the package (see pyproject.toml); a source
# checkout has no copy here and uses the repo-root settings.toml.
PACKAGED_SETTINGS_FILE = Path(__file__).resolve().parent / "settings.toml"
REPO_ROOT = Path(__file__).resolve().parent.parent


def default_settings_dir(
    packaged: Path | None = None, repo_root: Path | None = None
) -> Path:
    """Return the directory holding the tool's own settings.toml.

    Never the current directory: a project's own settings.toml must not be read.
    The packaged copy (installed wheel) wins; otherwise the source checkout root.
    """
    packaged = packaged or PACKAGED_SETTINGS_FILE
    if packaged.is_file():
        return packaged.parent
    return repo_root or REPO_ROOT


def project_name(pyproject_file: Path = PYPROJECT_FILE) -> str:
    """Return ``[project] name`` from pyproject.toml.

    pyproject.toml is the single place the project is named. In a source
    checkout it is read directly; in an installed wheel (no pyproject.toml) the
    name comes from the package metadata.
    """
    if pyproject_file.is_file():
        with pyproject_file.open("rb") as f:
            return str(tomllib.load(f)["project"]["name"])
    distributions = metadata.packages_distributions().get(PACKAGE_NAME)
    if distributions:
        return distributions[0]
    raise RuntimeError(f"Cannot determine project name: {pyproject_file} not found")


def resolve_environment(env: str | None = None) -> str:
    """Return the settings section name to load.

    Section names in settings.toml are lowercase and the lookup is
    case-sensitive, so the name is normalised here.
    """
    if env:
        return env.strip().lower()
    for name in ENV_VAR_NAMES:
        env_value = (os.getenv(name) or "").strip().lower()
        if env_value:
            return env_value
    return DEFAULT_ENVIRONMENT


def redact_database_passwords(raw: dict[str, Any]) -> dict[str, Any]:
    databases = raw.get("databases")
    if not isinstance(databases, dict):
        return raw
    redacted = {
        name: (
            {**db, "password": REDACTED}
            if isinstance(db, dict) and "password" in db
            else db
        )
        for name, db in databases.items()
    }
    return {**raw, "databases": redacted}
