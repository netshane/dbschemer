import pytest

import locallib.settings as settings_module
from locallib.appsettings import AppSettings
from locallib.settings import (
    ENV_VAR_NAMES,
    DatabaseSettings,
    default_settings_dir,
    project_name,
)


@pytest.mark.unit
def test_unset_env_var_defaults_to_production(settings_file):
    settings = AppSettings.load()
    assert settings.environment == "production"
    assert settings.logging["level"] == "INFO"
    assert settings.logging["marker"] == "prd"


@pytest.mark.unit
def test_explicit_development(settings_file):
    settings = AppSettings.load("development")
    assert settings.environment == "development"
    assert settings.logging["marker"] == "dev"


@pytest.mark.unit
def test_explicit_production(settings_file):
    settings = AppSettings.load("production")
    assert settings.logging["level"] == "INFO"
    assert settings.logging["marker"] == "prd"


@pytest.mark.unit
@pytest.mark.parametrize("value", ["Development", "DEVELOPMENT", " development "])
def test_env_var_is_case_insensitive(settings_file, monkeypatch, value):
    monkeypatch.setenv("APP_ENV", value)
    assert AppSettings.load().logging["marker"] == "dev"


@pytest.mark.unit
@pytest.mark.parametrize("name", ENV_VAR_NAMES)
def test_each_env_var_is_supported(settings_file, monkeypatch, name):
    monkeypatch.setenv(name, "development")
    assert AppSettings.load().environment == "development"


@pytest.mark.unit
def test_env_vars_checked_in_order(settings_file, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ASPNETCORE_ENVIRONMENT", "development")
    monkeypatch.setenv("DOTNET_ENVIRONMENT", "development")
    assert AppSettings.load().environment == "production"


@pytest.mark.unit
def test_empty_env_var_falls_through(settings_file, monkeypatch):
    monkeypatch.setenv("APP_ENV", " ")
    monkeypatch.setenv("DOTNET_ENVIRONMENT", "Development")
    assert AppSettings.load().environment == "development"


@pytest.mark.unit
def test_explicit_env_overrides_env_var(settings_file, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    assert AppSettings.load("Production").logging["marker"] == "prd"


@pytest.mark.unit
def test_loads_are_independent(settings_file):
    """No module-level cache: each load reflects its own environment."""
    assert AppSettings.load("production").logging["marker"] == "prd"
    assert AppSettings.load("development").logging["marker"] == "dev"
    assert AppSettings.load().logging["marker"] == "prd"


@pytest.mark.unit
def test_databases_parsed(settings_file):
    db = AppSettings.load().databases["main"]
    assert isinstance(db, DatabaseSettings)
    assert db.connection_string == "sqlite://"
    assert db.isolation_level == "AUTOCOMMIT"
    assert db.password is None


@pytest.mark.unit
def test_secrets_merge_password_into_database(settings_file, isolated_cwd):
    (isolated_cwd / "secrets.toml").write_text(
        '[default.databases.main]\npassword = "s3cr;t{}"\n'
    )
    db = AppSettings.load().databases["main"]
    assert db.connection_string == "sqlite://"
    assert db.password is not None
    assert db.password.get_secret_value() == "s3cr;t{}"


@pytest.mark.unit
def test_make_settings_fixture(make_settings):
    settings = make_settings(databases={"x": {"connection_string": "sqlite://"}})
    assert settings.databases["x"].connection_string == "sqlite://"


@pytest.mark.unit
def test_orphan_secrets_database_does_not_break_load(settings_file, isolated_cwd):
    """A secrets.toml entry for a database missing from settings.toml must not
    stop the app starting (review finding 1)."""
    (isolated_cwd / "secrets.toml").write_text(
        '[default.databases.old]\npassword = "pw"\n'
    )
    settings = AppSettings.load()
    assert settings.databases["old"].connection_string is None
    assert settings.databases["main"].connection_string == "sqlite://"


@pytest.mark.unit
def test_password_is_masked(settings_file, isolated_cwd):
    (isolated_cwd / "secrets.toml").write_text(
        '[default.databases.main]\npassword = "hunter2"\n'
    )
    settings = AppSettings.load()
    db = settings.databases["main"]
    assert db.password is not None
    assert db.password.get_secret_value() == "hunter2"
    assert "hunter2" not in repr(settings)
    assert "hunter2" not in str(settings)
    assert "hunter2" not in repr(settings.settings)


@pytest.mark.unit
def test_appname_defaults_to_pyproject_name(isolated_cwd):
    (isolated_cwd / "settings.toml").write_text("[default.logging]\nlevel = 'INFO'\n")
    assert AppSettings.load().appname == project_name()


@pytest.mark.unit
def test_project_name_reads_pyproject(isolated_cwd):
    pyproject = isolated_cwd / "pyproject.toml"
    pyproject.write_text('[project]\nname = "my-app"\nversion = "0.1.0"\n')
    assert project_name(pyproject) == "my-app"


@pytest.mark.unit
def test_project_name_falls_back_to_metadata(isolated_cwd, monkeypatch):
    monkeypatch.setattr(
        settings_module.metadata,
        "packages_distributions",
        lambda: {"locallib": ["installed-app"]},
    )
    assert project_name(isolated_cwd / "missing.toml") == "installed-app"


@pytest.mark.unit
def test_project_name_errors_when_unknown(isolated_cwd, monkeypatch):
    monkeypatch.setattr(settings_module.metadata, "packages_distributions", dict)
    with pytest.raises(RuntimeError):
        project_name(isolated_cwd / "missing.toml")


@pytest.mark.unit
def test_default_settings_dir_prefers_packaged(isolated_cwd):
    packaged = isolated_cwd / "pkg" / "settings.toml"
    packaged.parent.mkdir()
    packaged.write_text("")
    repo = isolated_cwd / "repo"
    assert default_settings_dir(packaged=packaged, repo_root=repo) == packaged.parent


@pytest.mark.unit
def test_default_settings_dir_falls_back_to_repo_root(isolated_cwd):
    missing = isolated_cwd / "pkg" / "settings.toml"
    repo = isolated_cwd / "repo"
    assert default_settings_dir(packaged=missing, repo_root=repo) == repo


@pytest.mark.unit
def test_default_settings_dir_never_uses_cwd(isolated_cwd):
    (isolated_cwd / "settings.toml").write_text("")
    missing = isolated_cwd / "pkg" / "settings.toml"
    assert default_settings_dir(packaged=missing) == settings_module.REPO_ROOT
    assert isolated_cwd != settings_module.REPO_ROOT


@pytest.mark.unit
def test_default_settings_dir_uses_packaged_module_constant(isolated_cwd, monkeypatch):
    packaged = isolated_cwd / "pkg" / "settings.toml"
    packaged.parent.mkdir()
    packaged.write_text("")
    monkeypatch.setattr(settings_module, "PACKAGED_SETTINGS_FILE", packaged)
    assert default_settings_dir() == packaged.parent


@pytest.mark.unit
def test_load_reads_settings_dir(isolated_cwd):
    settings_dir = isolated_cwd / "pkg"
    settings_dir.mkdir()
    (settings_dir / "settings.toml").write_text(
        "[production.logging]\nmarker = 'packaged'\n"
    )
    (settings_dir / "secrets.toml").write_text(
        '[default.databases.main]\npassword = "pw"\n'
    )
    settings = AppSettings.load(settings_dir=settings_dir)
    assert settings.logging["marker"] == "packaged"
    assert settings.databases["main"].password is not None


@pytest.mark.unit
def test_load_ignores_settings_in_cwd(isolated_cwd):
    """A project's own settings.toml in the cwd must never be loaded."""
    (isolated_cwd / "settings.toml").write_text("[default]\nappname = 'from-cwd'\n")
    (isolated_cwd / "secrets.toml").write_text(
        '[default.databases.main]\npassword = "cwd-pw"\n'
    )
    settings_dir = isolated_cwd / "tool"
    settings_dir.mkdir()
    (settings_dir / "settings.toml").write_text("[default]\nappname = 'tool'\n")
    settings = AppSettings.load(settings_dir=settings_dir)
    assert settings.appname == "tool"
    assert "main" not in settings.databases
