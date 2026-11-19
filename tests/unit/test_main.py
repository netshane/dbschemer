"""CLI smoke tests using click's CliRunner against a temp settings.toml."""

import pytest
from click.testing import CliRunner

from locallib.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.mark.unit
def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "--env" in result.output
    assert "init" in result.output
    assert "export" in result.output


@pytest.mark.unit
def test_env_production_loads_production_section(runner, settings_file):
    result = runner.invoke(cli, ["--env", "Production", "init"])
    assert result.exit_code == 0, result.output
    # production logs at INFO, so the DEBUG environment line is filtered out
    assert "Environment: production" not in result.output


@pytest.mark.unit
def test_log_level_debug_overrides_production(runner, settings_file):
    result = runner.invoke(cli, ["--env", "Production", "--log-level", "debug", "init"])
    assert result.exit_code == 0, result.output
    assert "Environment: production" in result.output


@pytest.mark.unit
def test_log_level_error_suppresses_info(runner, settings_file, monkeypatch):
    from loguru import logger

    from locallib.services.init_service import InitService

    def noisy_run(self, path, force=False):
        logger.info("info-message")
        logger.error("error-message")
        return path

    monkeypatch.setattr(InitService, "run", noisy_run)
    result = runner.invoke(cli, ["--log-level", "error", "init"])
    assert result.exit_code == 0, result.output
    assert "error-message" in result.output
    assert "info-message" not in result.output


@pytest.mark.unit
@pytest.mark.parametrize(
    "level", ["warning", "WARN", "critical", "trace", "debug", "info", "error"]
)
def test_log_level_accepts_all_levels(runner, settings_file, level):
    result = runner.invoke(cli, ["--log-level", level, "init"])
    assert result.exit_code == 0, result.output


@pytest.mark.unit
def test_env_development_logs_debug(runner, settings_file):
    result = runner.invoke(cli, ["--env", "development", "init"])
    assert result.exit_code == 0, result.output
    assert "Environment: development" in result.output


@pytest.mark.unit
def test_env_rejects_unknown_value(runner, settings_file):
    result = runner.invoke(cli, ["--env", "staging", "init"])
    assert result.exit_code == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    "args,expected", [(["init", "--help"], "--force"), (["export"], "DATABASE")]
)
def test_help_and_usage_errors_do_not_load_settings(
    runner, isolated_cwd, args, expected
):
    """Subcommand --help and usage errors must not need valid settings."""
    (isolated_cwd / "settings.toml").write_text("this is [[[ not toml")
    result = runner.invoke(cli, args)
    assert result.exit_code in (0, 2), result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert expected in result.output


@pytest.mark.unit
def test_invalid_settings_fail_when_command_runs(runner, isolated_cwd):
    (isolated_cwd / "settings.toml").write_text("this is [[[ not toml")
    result = runner.invoke(cli, ["init"])
    assert result.exit_code != 0
    assert not isinstance(result.exception, SystemExit)


@pytest.mark.unit
def test_main_exits_nonzero_on_uncaught_exception(monkeypatch):
    import locallib.cli as cli_module

    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "cli", boom)
    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 1


@pytest.mark.unit
def test_early_failure_is_visible(isolated_cwd, monkeypatch, capfd):
    """Errors raised before logging is configured must not be swallowed."""
    import locallib.cli as cli_module

    (isolated_cwd / "settings.toml").write_text("this is [[[ not toml")
    monkeypatch.setattr("sys.argv", ["cli", "init"])
    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 1
    err = capfd.readouterr().err
    assert "Unexpected error" in err
    assert "Traceback" not in err
    assert "Rerun with --traceback" in err


@pytest.mark.unit
def test_early_failure_traceback_flag(isolated_cwd, monkeypatch, capfd):
    import locallib.cli as cli_module

    (isolated_cwd / "settings.toml").write_text("this is [[[ not toml")
    monkeypatch.setattr("sys.argv", ["cli", "--traceback", "init"])
    with pytest.raises(SystemExit):
        cli_module.main()
    err = capfd.readouterr().err
    assert "Unexpected error" in err
    assert "Traceback (most recent call last)" in err


@pytest.mark.unit
@pytest.mark.parametrize("flag", [False, True])
def test_main_non_db_runtime_error(monkeypatch, capfd, flag):
    import locallib.cli as cli_module

    def boom() -> None:
        secret = "PWD=hunter2"  # noqa: F841 - a local that must never be printed
        raise RuntimeError("boom")

    monkeypatch.setattr(cli_module, "cli", boom)
    monkeypatch.setattr("sys.argv", ["cli"] + (["--traceback"] if flag else []))
    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 1
    err = capfd.readouterr().err
    assert "Unexpected error: RuntimeError: boom" in err
    assert ("Traceback (most recent call last)" in err) is flag
    assert "hunter2" not in err


@pytest.mark.unit
def test_help_lists_init(runner):
    result = runner.invoke(cli, ["--help"])
    assert "init" in result.output


@pytest.mark.unit
def test_init_creates_config(runner, settings_file, isolated_cwd):
    from locallib.services.config_template import CONFIG_TEMPLATE

    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert "Created .dbschemer.toml" in result.output
    assert (isolated_cwd / ".dbschemer.toml").read_text() == CONFIG_TEMPLATE


@pytest.mark.unit
def test_init_refuses_to_overwrite(runner, settings_file, isolated_cwd):
    (isolated_cwd / ".dbschemer.toml").write_text("keep me")
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 1
    assert "already exists" in result.output
    assert (isolated_cwd / ".dbschemer.toml").read_text() == "keep me"


@pytest.mark.unit
def test_init_force_overwrites(runner, settings_file, isolated_cwd):
    (isolated_cwd / ".dbschemer.toml").write_text("old")
    result = runner.invoke(cli, ["init", "--force"])
    assert result.exit_code == 0, result.output
    assert (isolated_cwd / ".dbschemer.toml").read_text() != "old"


@pytest.mark.unit
def test_init_file_option(runner, settings_file, isolated_cwd):
    result = runner.invoke(cli, ["init", "--file", "sub/x.toml"])
    assert result.exit_code == 1
    assert "does not exist" in result.output
    assert not (isolated_cwd / "sub").exists()

    (isolated_cwd / "sub").mkdir()
    result = runner.invoke(cli, ["init", "--file", "sub/x.toml"])
    assert result.exit_code == 0, result.output
    assert (isolated_cwd / "sub" / "x.toml").is_file()


@pytest.mark.unit
def test_init_other_os_error_is_clean(runner, settings_file, monkeypatch):
    from locallib.services.init_service import InitService

    def denied(self, path, force=False):
        raise PermissionError("Permission denied: x")

    monkeypatch.setattr(InitService, "run", denied)
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 1
    assert "Permission denied" in result.output


# --- export -------------------------------------------------------------------

EXPORT_CONFIG = """
[databases.db]
connection_string = "mssql+mssql-python://Server=sql01;Database=Sales;UID=u"
password_env_var = "DBSCHEMER_TEST_PW"
output = "docs/db"
"""


@pytest.fixture
def export_env(isolated_cwd, monkeypatch, make_settings):
    """A pre-seeded factory whose engine builder returns a FakeEngine."""
    from locallib.dependencies import ServiceFactory
    from tests.fakes import FakeEngine, sample_rows

    state: dict = {"rows": sample_rows(), "error": None, "calls": [], "builder": None}

    def builder(conn_str, **kwargs):
        state["calls"].append((conn_str, kwargs))
        if state["builder"] is not None:  # a real builder, e.g. create_db_engine
            return state["builder"](conn_str, **kwargs)
        return FakeEngine(state["rows"], error=state["error"])

    factory = ServiceFactory(make_settings(), engine_builder=builder)
    monkeypatch.setattr(
        ServiceFactory, "from_environment", classmethod(lambda cls, *a, **k: factory)
    )
    monkeypatch.setenv("DBSCHEMER_TEST_PW", "s3cret-pw")
    (isolated_cwd / ".dbschemer.toml").write_text(EXPORT_CONFIG)
    return state


@pytest.mark.unit
def test_export_success(runner, export_env, isolated_cwd):
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 0, result.output
    out = isolated_cwd.resolve() / "docs" / "db"
    assert (
        f"Exported db to {out}: 3 tables, 1 views, 1 procedures, 1 functions"
        in result.output
    )
    assert (out / "schema.json").is_file()
    assert "**Database:** Sales" in (out / "README.md").read_text()
    assert export_env["calls"][0][1]["password"] == "s3cret-pw"


@pytest.mark.unit
def test_export_file_option_and_row_count(runner, export_env, isolated_cwd):
    sub = isolated_cwd / "proj"
    sub.mkdir()
    (sub / "cfg.toml").write_text(EXPORT_CONFIG)
    result = runner.invoke(
        cli, ["export", "db", "--file", "proj/cfg.toml", "--row-count"]
    )
    assert result.exit_code == 0, result.output
    assert '"row_count": 1500' in (sub / "docs" / "db" / "schema.json").read_text()


@pytest.mark.unit
def test_export_missing_config(runner, export_env):
    result = runner.invoke(cli, ["export", "db", "--file", "nope.toml"])
    assert result.exit_code == 1
    assert "nope.toml not found" in result.output


@pytest.mark.unit
def test_export_unknown_database(runner, export_env):
    result = runner.invoke(cli, ["export", "other"])
    assert result.exit_code == 1
    assert "Database 'other' is not configured" in result.output
    assert "(configured: db)" in result.output


@pytest.mark.unit
def test_export_missing_password_env(runner, export_env, monkeypatch):
    monkeypatch.delenv("DBSCHEMER_TEST_PW")
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "Environment variable DBSCHEMER_TEST_PW" in result.output
    assert export_env["calls"] == []


@pytest.mark.unit
def test_export_db_error_is_clean(runner, export_env, isolated_cwd):
    from sqlalchemy.exc import OperationalError

    (isolated_cwd / "docs" / "db").mkdir(parents=True)
    (isolated_cwd / "docs" / "db" / "README.md").write_text("old")
    export_env["error"] = OperationalError(
        "SELECT", {}, Exception("Login failed for user 'u'")
    )
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "Cannot connect to 'db' (server 'sql01'): login failed" in result.output
    assert "Driver error: Login failed for user 'u'" in result.output
    assert "s3cret-pw" not in result.output
    assert (isolated_cwd / "docs" / "db" / "README.md").read_text() == "old"


@pytest.mark.unit
def test_export_invalid_url_is_clean(runner, export_env, isolated_cwd):
    (isolated_cwd / ".dbschemer.toml").write_text(
        '[databases.db]\nconnection_string = "not a url pw=x"\noutput = "o"\n'
    )
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "Invalid connection settings for 'db'" in result.output
    assert "pw=x" not in result.output


@pytest.mark.unit
def test_export_write_error_is_clean(runner, export_env, monkeypatch):
    from locallib.services.docs_generator import DocsGenerator

    def denied(self, schema, output_dir):
        raise PermissionError("Permission denied: schema.json")

    monkeypatch.setattr(DocsGenerator, "write_json", denied)
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "Permission denied" in result.output


@pytest.mark.unit
def test_export_help_needs_no_config(runner, isolated_cwd):
    (isolated_cwd / "settings.toml").write_text("this is [[[ not toml")
    result = runner.invoke(cli, ["export", "--help"])
    assert result.exit_code == 0
    assert "--row-count" in result.output
    assert "export" in runner.invoke(cli, ["--help"]).output


@pytest.mark.unit
def test_export_mssql_python_error_is_clean(runner, export_env):
    import mssql_python

    export_env["error"] = mssql_python.Error("Login failed for user 'u'", "")
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "Cannot connect to 'db' (server 'sql01'): login failed" in result.output
    assert "s3cret-pw" not in result.output


@pytest.mark.unit
def test_export_internal_key_error_is_not_masked(runner, export_env):
    export_env["error"] = KeyError("precision")
    result = runner.invoke(cli, ["export", "db"])
    assert isinstance(result.exception, KeyError)
    assert "Error: precision" not in result.output


DNS_ERROR = "[Microsoft][ODBC Driver 18 for SQL Server]TCP Provider: Error code 0x2AF9"


@pytest.mark.unit
def test_export_unreachable_server_is_clean(runner, export_env):
    export_env["error"] = RuntimeError(DNS_ERROR)
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "could not be resolved" in result.output
    assert "server 'sql01'" in result.output
    assert f"Driver error: {DNS_ERROR}" in result.output
    assert "Traceback" not in result.output
    assert "UID=" not in result.output
    assert "s3cret-pw" not in result.output


@pytest.mark.unit
def test_export_unreachable_server_traceback(runner, export_env):
    export_env["error"] = RuntimeError(DNS_ERROR)
    result = runner.invoke(cli, ["--traceback", "export", "db"])
    assert result.exit_code == 1
    assert "Traceback (most recent call last)" in result.stderr
    assert "could not be resolved" in result.stderr
    assert "s3cret-pw" not in result.stderr + result.output


@pytest.mark.unit
def test_export_unknown_odbc_error(runner, export_env):
    export_env["error"] = RuntimeError("[Microsoft][ODBC Driver 18]Weird (99999)")
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "Database error for 'db' (server 'sql01'): RuntimeError:" in result.output
    assert "Rerun with --traceback" in result.output


@pytest.mark.unit
def test_export_non_db_runtime_error_is_not_masked(runner, export_env):
    export_env["error"] = RuntimeError("boom")
    result = runner.invoke(cli, ["export", "db"])
    assert isinstance(result.exception, RuntimeError)


@pytest.mark.unit
def test_export_unsupported_connect_timeout(runner, export_env, isolated_cwd):
    from locallib.db import create_db_engine

    export_env["builder"] = create_db_engine
    (isolated_cwd / ".dbschemer.toml").write_text(
        '[databases.db]\nconnection_string = "sqlite://"\noutput = "o"\n'
        "connect_timeout = 5\n"
    )
    result = runner.invoke(cli, ["export", "db"])
    assert result.exit_code == 1
    assert "connect_timeout is not supported for driver 'sqlite'" in result.output
