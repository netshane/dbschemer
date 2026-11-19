"""The per-project ``.dbschemer.toml`` config file."""

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
    model_validator,
)

DbType = Literal["sqlserver", "postgres", "mysql"]


class ConfigError(Exception):
    """The config file is missing, unreadable or invalid."""


class DbschemerDatabase(BaseModel):
    """One ``[databases.<name>]`` table.

    Either ``type`` + ``server`` + ``database`` (+ optional ``user``/``port``)
    or a raw ``connection_string`` override, never both.
    """

    model_config = ConfigDict(extra="forbid")

    type: DbType | None = None
    server: str | None = None
    database: str | None = None
    user: str | None = None
    # name of an environment variable holding the user; ignored if user is set
    user_env_var: str | None = None
    port: PositiveInt | None = None
    connection_string: str | None = None
    password_env_var: str | None = None
    output: Path
    # connection/login timeout in seconds; None = driver default
    connect_timeout: PositiveInt | None = None

    @model_validator(mode="after")
    def _check_connection_fields(self) -> Self:
        discrete = {
            "type": self.type,
            "server": self.server,
            "database": self.database,
            "user": self.user,
            "user_env_var": self.user_env_var,
            "port": self.port,
        }
        given = [k for k, v in discrete.items() if v is not None]
        if self.connection_string is not None:
            if given:
                raise ValueError(
                    "connection_string cannot be combined with "
                    f"{', '.join(given)}; use one or the other"
                )
            return self
        missing = [k for k in ("type", "server", "database") if discrete[k] is None]
        if missing:
            raise ValueError(
                "set either connection_string or type, server and database "
                f"(missing: {', '.join(missing)})"
            )
        return self


class DbschemerConfig(BaseModel):
    """All databases in a config file.

    ``path`` (the config file) and ``base_dir`` (its directory) are set by
    ``load()`` and never read from the file.
    """

    model_config = ConfigDict(extra="forbid")

    databases: dict[str, DbschemerDatabase] = {}
    path: Path = Path(".dbschemer.toml")
    base_dir: Path = Path(".")

    @classmethod
    def load(cls, path: Path) -> "DbschemerConfig":
        """Read and validate ``path``. Raises ``ConfigError`` on any failure."""
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except FileNotFoundError:
            raise ConfigError(f"Config file {path} not found") from None
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Config file {path} is not valid TOML: {e}") from None
        except OSError as e:
            raise ConfigError(f"Cannot read config file {path}: {e}") from None
        # path / base_dir are not file settings: reject them like unknown keys.
        for key in ("path", "base_dir"):
            if key in data:
                raise ConfigError(f"Config file {path} is invalid: unknown key '{key}'")
        try:
            config = cls.model_validate(data)
        except ValidationError as e:
            raise ConfigError(f"Config file {path} is invalid: {e}") from None
        return config.model_copy(
            update={"path": path, "base_dir": path.resolve().parent}
        )

    def get(self, name: str) -> DbschemerDatabase:
        """Return ``[databases.<name>]``; ``KeyError`` lists the configured names."""
        db = self.databases.get(name)
        if db is None:
            configured = ", ".join(sorted(self.databases)) or "none"
            raise KeyError(
                f"Database '{name}' is not configured in {self.path} "
                f"(configured: {configured})"
            )
        return db

    def resolve_output(self, name: str) -> Path:
        """The output directory, relative paths resolved against ``base_dir``."""
        output = self.get(name).output
        return output if output.is_absolute() else self.base_dir / output
