import os
from collections.abc import Mapping
from typing import Protocol

from loguru import logger
from nscomponents import nslogging as nslog
from sqlalchemy.engine import Engine

from locallib.appsettings import AppSettings
from locallib.db import build_connection, create_db_engine, describe_server, dialect_for
from locallib.db_errors import DbErrorTranslator
from locallib.dbschemer_config import DbschemerConfig
from locallib.error_reporter import ErrorReporter
from locallib.services.config_template import CONFIG_TEMPLATE
from locallib.services.docs_generator import DocsGenerator
from locallib.services.export_service import ExportService
from locallib.services.init_service import InitService
from locallib.services.queries import get_queries
from locallib.services.schema_extractor import SchemaExtractor


class EngineBuilder(Protocol):
    def __call__(
        self,
        conn_str: str,
        *,
        isolation_level: str,
        password: str | None,
        connect_timeout: int | None = None,
    ) -> Engine: ...


class ServiceFactory:
    """The single place where application services are constructed.

    Receives settings once; creates each database engine at most once (one
    connection pool per database) and injects dependencies into services.
    """

    def __init__(
        self,
        settings: AppSettings,
        log_level: str | None = None,
        engine_builder: EngineBuilder = create_db_engine,
    ):
        self.settings = settings
        self.log_level = log_level
        self._engine_builder = engine_builder
        self._engines: dict[str, Engine] = {}

    @classmethod
    def from_environment(
        cls,
        env: str | None = None,
        log_level: str | None = None,
    ) -> "ServiceFactory":
        """Load settings for ``env``, build the factory and configure logging.

        ``log_level`` (a loguru level name) overrides the level in settings.
        """
        settings = AppSettings.load(env)
        factory = cls(settings, log_level=log_level)
        factory.configure_logging()
        logger.debug(f"Environment: {settings.environment}")
        return factory

    def configure_logging(self, file_logging: bool = False) -> None:
        log_settings = dict(self.settings.logging)
        if self.log_level:
            log_settings["level"] = self.log_level
        nslog.init_logging(application=self.settings.appname, **log_settings)
        if file_logging:
            nslog.init_file_logging(application=self.settings.appname, **log_settings)

    def get_engine(self, name: str) -> Engine:
        """Return the cached engine for ``[databases.<name>]`` in settings.toml."""
        if name not in self._engines:
            db = self.settings.databases.get(name)
            if db is None:
                configured = ", ".join(sorted(self.settings.databases)) or "none"
                raise KeyError(
                    f"Database '{name}' is not configured (configured: {configured})"
                )
            if not db.connection_string:
                raise ValueError(
                    f"Database '{name}' has no connection_string; add it under "
                    f"[default.databases.{name}] in settings.toml"
                )
            self._engines[name] = self._engine_builder(
                db.connection_string,
                isolation_level=db.isolation_level,
                password=db.password.get_secret_value() if db.password else None,
            )
        return self._engines[name]

    def dispose(self) -> None:
        """Dispose every engine; one failure does not stop the others."""
        try:
            for name, engine in self._engines.items():
                try:
                    engine.dispose()
                except Exception as e:
                    # No logger.exception: diagnose=True would print locals.
                    logger.error(
                        f"Failed to dispose engine '{name}': {type(e).__name__}: {e}"
                    )
        finally:
            self._engines.clear()

    # --- services -------------------------------------------------------------

    def create_db_error_translator(self) -> DbErrorTranslator:
        return DbErrorTranslator()

    def create_error_reporter(self) -> ErrorReporter:
        return ErrorReporter()

    def create_init_service(self) -> InitService:
        return InitService(template=CONFIG_TEMPLATE)

    def create_export_service(
        self,
        config: DbschemerConfig,
        name: str,
        include_row_count: bool,
        environ: Mapping[str, str] = os.environ,
    ) -> ExportService:
        """Build the export pipeline for ``[databases.<name>]`` in ``config``.

        Raises ``KeyError`` for an unknown database and ``ValueError`` if the
        configured password or user environment variable is missing or empty.
        The user is taken from ``user``, else ``user_env_var``, else the
        connection uses integrated credentials.
        """
        db = config.get(name)
        password: str | None = None
        if db.password_env_var:
            password = environ.get(db.password_env_var) or None
            if password is None:
                raise ValueError(
                    f"Environment variable {db.password_env_var} "
                    f"(password for '{name}') is not set"
                )
        if not db.user and db.user_env_var:
            user = environ.get(db.user_env_var) or None
            if user is None:
                raise ValueError(
                    f"Environment variable {db.user_env_var} "
                    f"(user for '{name}') is not set"
                )
            db = db.model_copy(update={"user": user})
        connection = build_connection(db)
        key = f"export:{name}"
        if key not in self._engines:
            self._engines[key] = self._engine_builder(
                connection,
                isolation_level="AUTOCOMMIT",
                password=password,
                connect_timeout=db.connect_timeout,
            )
        extractor = SchemaExtractor(
            self._engines[key],
            server=describe_server(connection),
            include_row_count=include_row_count,
            queries=get_queries(db.type or dialect_for(connection)),
        )
        return ExportService(
            extractor,
            DocsGenerator(include_row_count=include_row_count),
            output_dir=config.resolve_output(name),
        )
