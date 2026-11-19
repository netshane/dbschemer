from pathlib import Path

import pytest

from locallib.dbschemer_config import ConfigError, DbschemerConfig
from locallib.services.config_template import CONFIG_TEMPLATE

VALID = """
[databases.main]
connection_string = "sqlite://"
output = "out/main"

[databases.abs]
connection_string = "sqlite://"
password_env_var = "PW"
output = "{abs}"
"""


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.mark.unit
def test_init_template_loads(tmp_path):
    config = DbschemerConfig.load(write(tmp_path / ".dbschemer.toml", CONFIG_TEMPLATE))
    assert sorted(config.databases) == ["sample", "sample2"]
    assert config.get("sample").password_env_var == "DBSCHEMER_PWD_sample"


@pytest.mark.unit
def test_relative_output_resolves_against_config_dir(tmp_path):
    abs_out = tmp_path / "elsewhere"
    path = write(tmp_path / "proj" / "cfg.toml", VALID.format(abs=abs_out.as_posix()))
    config = DbschemerConfig.load(path)
    assert config.base_dir == (tmp_path / "proj").resolve()
    assert config.resolve_output("main") == (tmp_path / "proj").resolve() / "out/main"
    assert config.resolve_output("abs") == abs_out


@pytest.mark.unit
def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        DbschemerConfig.load(tmp_path / "nope.toml")


@pytest.mark.unit
def test_bad_toml(tmp_path):
    with pytest.raises(ConfigError, match="not valid TOML"):
        DbschemerConfig.load(write(tmp_path / "c.toml", "this is [[[ not toml"))


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        '[databases.a]\nconnection_string="x"\noutput="o"\ntypo="y"\n',
        'other = 1\n[databases.a]\nconnection_string="x"\noutput="o"\n',
        'base_dir = "/"\n',
    ],
)
def test_unknown_key(tmp_path, content):
    with pytest.raises(ConfigError, match="invalid"):
        DbschemerConfig.load(write(tmp_path / "c.toml", content))


@pytest.mark.unit
def test_missing_output(tmp_path):
    with pytest.raises(ConfigError, match="output"):
        DbschemerConfig.load(
            write(tmp_path / "c.toml", '[databases.a]\nconnection_string="x"\n')
        )


@pytest.mark.unit
def test_unknown_database_lists_configured(tmp_path):
    path = write(tmp_path / "c.toml", VALID.format(abs="/x"))
    config = DbschemerConfig.load(path)
    with pytest.raises(KeyError) as exc:
        config.get("missing")
    message = exc.value.args[0]
    assert "'missing' is not configured" in message
    assert str(path) in message
    assert "(configured: abs, main)" in message


TIMEOUT = '[databases.a]\nconnection_string="x"\noutput="o"\nconnect_timeout={}\n'


@pytest.mark.unit
def test_connect_timeout(tmp_path):
    config = DbschemerConfig.load(write(tmp_path / "c.toml", TIMEOUT.format(15)))
    assert config.get("a").connect_timeout == 15
    assert (
        DbschemerConfig.load(
            write(
                tmp_path / "d.toml",
                '[databases.a]\nconnection_string="x"\noutput="o"\n',
            )
        )
        .get("a")
        .connect_timeout
        is None
    )


@pytest.mark.unit
@pytest.mark.parametrize("value", [0, -1])
def test_connect_timeout_must_be_positive(tmp_path, value):
    with pytest.raises(ConfigError, match="connect_timeout"):
        DbschemerConfig.load(write(tmp_path / "c.toml", TIMEOUT.format(value)))


FIELDS = '[databases.a]\ntype="postgres"\nserver="h"\ndatabase="d"\noutput="o"\n'


@pytest.mark.unit
def test_discrete_fields_are_valid(tmp_path):
    config = DbschemerConfig.load(
        write(tmp_path / "c.toml", FIELDS + 'user="u"\nport=5433\n')
    )
    db = config.get("a")
    assert (db.type, db.server, db.database, db.user, db.port) == (
        "postgres",
        "h",
        "d",
        "u",
        5433,
    )
    assert db.connection_string is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "message"),
    [
        (FIELDS + 'connection_string="x"\n', "cannot be combined with"),
        (
            '[databases.a]\nconnection_string="x"\nuser_env_var="U"\noutput="o"\n',
            "user_env_var",
        ),
        (
            '[databases.a]\nconnection_string="x"\ntype="mysql"\noutput="o"\n',
            "cannot be combined with",
        ),
        (FIELDS.replace("postgres", "oracle"), "type"),
        (FIELDS + "port=0\n", "port"),
    ],
)
def test_invalid_connection_fields(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message):
        DbschemerConfig.load(write(tmp_path / "c.toml", text))


@pytest.mark.unit
def test_missing_connection_info(tmp_path):
    text = '[databases.a]\ntype="mysql"\nserver="h"\noutput="o"\n'
    with pytest.raises(ConfigError, match="missing: database"):
        DbschemerConfig.load(write(tmp_path / "c.toml", text))
    with pytest.raises(ConfigError, match="missing: type, server, database"):
        DbschemerConfig.load(write(tmp_path / "d.toml", '[databases.a]\noutput="o"\n'))


@pytest.mark.unit
def test_user_env_var_accepted(tmp_path):
    config = DbschemerConfig.load(
        write(tmp_path / "c.toml", FIELDS + 'user_env_var="U"\n')
    )
    assert config.get("a").user_env_var == "U"
