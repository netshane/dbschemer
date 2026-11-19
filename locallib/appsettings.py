from pathlib import Path

from nscomponents import SettingsBase
from pydantic import Field

from locallib.settings import (
    DatabaseSettings,
    default_settings_dir,
    project_name,
    redact_database_passwords,
    resolve_environment,
)


class AppSettings(SettingsBase):
    # Defaults to the project name in pyproject.toml; settings.toml may override.
    appname: str = Field(default_factory=project_name)
    logging: dict = {}
    databases: dict[str, DatabaseSettings] = {}

    @classmethod
    def load(
        cls, env: str | None = None, settings_dir: Path | None = None
    ) -> "AppSettings":
        """Load settings.toml, secrets.toml and settings.local.toml from
        ``settings_dir`` (default: the tool's own settings directory, never the
        current directory). Missing secrets/local files are ignored."""
        environment = resolve_environment(env)
        if settings_dir is None:
            settings_dir = default_settings_dir()
        # nscomponents is untyped, so from_toml returns Any.
        settings: AppSettings = cls.from_toml(
            toml_file=str(settings_dir / "settings.toml"),
            secrets_file=str(settings_dir / "secrets.toml"),
            local_file=str(settings_dir / "settings.local.toml"),
            force_env=environment,
        )
        settings.environment = environment
        # SettingsBase keeps every raw value in ``settings``; mask the passwords
        # there too so they cannot leak via repr or logging.
        settings.settings = redact_database_passwords(settings.settings)
        return settings
