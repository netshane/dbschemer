import pytest

from locallib.dependencies import ServiceFactory
from locallib.services.config_template import CONFIG_TEMPLATE
from locallib.services.init_service import InitService


@pytest.mark.unit
def test_get_engine_is_cached_per_name(fake_factory):
    first = fake_factory.get_engine("main")
    assert fake_factory.get_engine("main") is first
    assert len(fake_factory.engine_calls) == 1


@pytest.mark.unit
def test_get_engine_passes_database_settings(make_settings):
    calls = []

    def builder(conn_str, **kwargs):
        calls.append((conn_str, kwargs))
        return object()

    settings = make_settings(
        databases={
            "a": {
                "connection_string": "sqlite://",
                "isolation_level": "READ COMMITTED",
                "password": "pw",
            }
        }
    )
    ServiceFactory(settings, engine_builder=builder).get_engine("a")
    assert calls == [
        ("sqlite://", {"isolation_level": "READ COMMITTED", "password": "pw"})
    ]


@pytest.mark.unit
def test_new_database_needs_only_settings(make_settings):
    settings = make_settings(databases={"newdb": {"connection_string": "sqlite://"}})
    factory = ServiceFactory(settings)
    with factory.get_engine("newdb").connect() as conn:
        assert conn.exec_driver_sql("select 1").scalar() == 1
    factory.dispose()


@pytest.mark.unit
def test_unknown_database_raises(fake_factory):
    with pytest.raises(KeyError, match="'missing' is not configured"):
        fake_factory.get_engine("missing")


@pytest.mark.unit
def test_dispose_clears_engines(fake_factory):
    fake_factory.get_engine("main")
    fake_factory.dispose()
    fake_factory.get_engine("main")
    assert len(fake_factory.engine_calls) == 2


@pytest.mark.unit
def test_password_passed_to_builder_as_plain_string(make_settings):
    calls = []

    def builder(conn_str, **kwargs):
        calls.append(kwargs["password"])
        return object()

    settings = make_settings(
        databases={"a": {"connection_string": "sqlite://", "password": "pw"}}
    )
    ServiceFactory(settings, engine_builder=builder).get_engine("a")
    assert calls == ["pw"]


@pytest.mark.unit
def test_database_without_connection_string_raises(make_settings):
    settings = make_settings(databases={"old": {"password": "pw"}})
    with pytest.raises(ValueError, match="'old' has no connection_string"):
        ServiceFactory(settings).get_engine("old")


class _Engine:
    def __init__(self, fail: bool):
        self.fail = fail
        self.disposed = False

    def dispose(self):
        self.disposed = True
        if self.fail:
            raise RuntimeError("boom")


@pytest.mark.unit
def test_dispose_continues_after_failure(make_settings):
    engines = {"a": _Engine(fail=True), "b": _Engine(fail=False)}
    settings = make_settings(
        databases={name: {"connection_string": name} for name in engines}
    )
    factory = ServiceFactory(
        settings,
        engine_builder=lambda c, **_: engines[c],  # type: ignore[arg-type]
    )
    factory.get_engine("a")
    factory.get_engine("b")
    factory.dispose()
    assert engines["a"].disposed and engines["b"].disposed
    # cache cleared: next call rebuilds
    engines["a"] = _Engine(fail=False)
    assert factory.get_engine("a") is engines["a"]


@pytest.mark.unit
def test_from_environment_loads_settings(settings_file):
    factory = ServiceFactory.from_environment("development")
    assert factory.settings.environment == "development"
    assert factory.settings.logging["marker"] == "dev"


@pytest.mark.unit
def test_log_level_overrides_settings(settings_file, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        "locallib.dependencies.nslog.init_logging",
        lambda **kw: captured.update(kw),
    )
    ServiceFactory.from_environment("development", log_level="WARNING")
    assert captured["level"] == "WARNING"


@pytest.mark.unit
def test_log_level_overrides_settings_for_file_logging(settings_file, monkeypatch):
    console: dict = {}
    files: dict = {}
    monkeypatch.setattr(
        "locallib.dependencies.nslog.init_logging", lambda **kw: console.update(kw)
    )
    monkeypatch.setattr(
        "locallib.dependencies.nslog.init_file_logging",
        lambda **kw: files.update(kw),
    )
    factory = ServiceFactory.from_environment("development", log_level="CRITICAL")
    factory.configure_logging(file_logging=True)
    assert console["level"] == "CRITICAL"
    assert files["level"] == "CRITICAL"


@pytest.mark.unit
def test_create_init_service_injects_template(make_settings):
    service = ServiceFactory(make_settings()).create_init_service()
    assert isinstance(service, InitService)
    assert service.template == CONFIG_TEMPLATE


def _export_config(tmp_path, password_env_var="DBSCHEMER_TEST_PW", extra=""):
    from locallib.dbschemer_config import DbschemerConfig

    pw_line = f'password_env_var = "{password_env_var}"\n' if password_env_var else ""
    pw_line += extra
    path = tmp_path / ".dbschemer.toml"
    path.write_text(
        "[databases.db]\n"
        'connection_string = "mssql+mssql-python://Server=sql01;Database=Sales"\n'
        f"{pw_line}"
        'output = "docs/db"\n'
    )
    return DbschemerConfig.load(path)


@pytest.mark.unit
def test_create_export_service_passes_password_and_caches(fake_factory, tmp_path):
    config = _export_config(tmp_path)
    environ = {"DBSCHEMER_TEST_PW": "s3cret"}
    service = fake_factory.create_export_service(config, "db", False, environ)
    fake_factory.create_export_service(config, "db", True, environ)
    assert fake_factory.engine_calls == [
        (
            "mssql+mssql-python://Server=sql01;Database=Sales",
            {
                "isolation_level": "AUTOCOMMIT",
                "password": "s3cret",
                "connect_timeout": None,
            },
        )
    ]
    assert service.output_dir == tmp_path.resolve() / "docs/db"
    assert service.extractor.server == "sql01"
    assert "export:db" in fake_factory._engines


@pytest.mark.unit
def test_create_export_service_without_password(fake_factory, tmp_path):
    config = _export_config(tmp_path, password_env_var=None)
    fake_factory.create_export_service(config, "db", False, {})
    assert fake_factory.engine_calls[0][1]["password"] is None


@pytest.mark.unit
@pytest.mark.parametrize("environ", [{}, {"DBSCHEMER_TEST_PW": ""}])
def test_create_export_service_missing_password(fake_factory, tmp_path, environ):
    config = _export_config(tmp_path)
    with pytest.raises(ValueError, match="DBSCHEMER_TEST_PW .password for 'db'"):
        fake_factory.create_export_service(config, "db", False, environ)
    assert fake_factory.engine_calls == []


@pytest.mark.unit
def test_create_export_service_passes_connect_timeout(fake_factory, tmp_path):
    config = _export_config(tmp_path, None, extra="connect_timeout = 12\n")
    fake_factory.create_export_service(config, "db", False, {})
    assert fake_factory.engine_calls[0][1]["connect_timeout"] == 12


@pytest.mark.unit
def test_create_db_error_translator_and_reporter(fake_factory):
    from locallib.db_errors import DbErrorTranslator
    from locallib.error_reporter import ErrorReporter

    assert isinstance(fake_factory.create_db_error_translator(), DbErrorTranslator)
    assert isinstance(fake_factory.create_error_reporter(), ErrorReporter)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("db_type", "module"),
    [("postgres", "postgres"), ("mysql", "mysql"), ("sqlserver", "sqlserver")],
)
def test_export_service_selects_queries_by_type(
    fake_factory, tmp_path, db_type, module
):
    from locallib.dbschemer_config import DbschemerConfig

    path = tmp_path / ".dbschemer.toml"
    path.write_text(
        f'[databases.db]\ntype="{db_type}"\nserver="h"\ndatabase="d"\noutput="o"\n'
    )
    service = fake_factory.create_export_service(
        DbschemerConfig.load(path), "db", False
    )
    assert service.extractor.queries.__name__.endswith(f".{module}")


def _typed_config(tmp_path, db_type, extra):
    from locallib.dbschemer_config import DbschemerConfig

    path = tmp_path / ".dbschemer.toml"
    path.write_text(
        f'[databases.db]\ntype="{db_type}"\nserver="h"\ndatabase="d"\n'
        f'output="o"\n{extra}'
    )
    return DbschemerConfig.load(path)


@pytest.mark.unit
def test_user_from_env_var_sqlserver(fake_factory, tmp_path):
    config = _typed_config(tmp_path, "sqlserver", 'user_env_var="DBU"\n')
    fake_factory.create_export_service(config, "db", False, {"DBU": "envuser"})
    url = fake_factory.engine_calls[0][0]
    assert "UID=envuser;" in url
    assert "Trusted_Connection" not in url


@pytest.mark.unit
@pytest.mark.parametrize("db_type", ["postgres", "mysql"])
def test_user_from_env_var_url_types(fake_factory, tmp_path, db_type):
    config = _typed_config(tmp_path, db_type, 'user_env_var="DBU"\n')
    fake_factory.create_export_service(config, "db", False, {"DBU": "envuser"})
    assert "//envuser@" in fake_factory.engine_calls[0][0]


@pytest.mark.unit
def test_user_wins_over_user_env_var(fake_factory, tmp_path):
    config = _typed_config(tmp_path, "sqlserver", 'user="direct"\nuser_env_var="DBU"\n')

    class Strict(dict):
        def get(self, key, default=None):
            raise AssertionError("environment must not be read")

    fake_factory.create_export_service(config, "db", False, Strict())
    assert "UID=direct;" in fake_factory.engine_calls[0][0]


@pytest.mark.unit
@pytest.mark.parametrize("environ", [{}, {"DBU": ""}])
def test_missing_user_env_var(fake_factory, tmp_path, environ):
    config = _typed_config(tmp_path, "sqlserver", 'user_env_var="DBU"\n')
    with pytest.raises(ValueError, match="DBU .user for 'db'"):
        fake_factory.create_export_service(config, "db", False, environ)
    assert fake_factory.engine_calls == []


@pytest.mark.unit
def test_no_user_uses_integrated(fake_factory, tmp_path):
    config = _typed_config(tmp_path, "sqlserver", "")
    fake_factory.create_export_service(config, "db", False, {})
    assert "Trusted_Connection=yes" in fake_factory.engine_calls[0][0]
