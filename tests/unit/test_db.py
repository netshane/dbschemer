import pytest

from locallib.db import (
    add_odbc_password,
    create_db_engine,
    parse_odbc_keys,
    quote_odbc_value,
)


@pytest.mark.unit
def test_quote_odbc_value_escapes_braces():
    assert quote_odbc_value("a;b{c}d") == "{a;b{c}}d}"


@pytest.mark.unit
@pytest.mark.parametrize("base", ["Server=x;UID=u", "Server=x;UID=u;"])
def test_add_odbc_password(base):
    assert add_odbc_password(base, "p}w") == "Server=x;UID=u;PWD={p}}w};"


@pytest.mark.unit
def test_url_engine_uses_isolation_level():
    engine = create_db_engine("sqlite://", isolation_level="SERIALIZABLE")
    with engine.connect() as conn:
        assert conn.get_isolation_level() == "SERIALIZABLE"


@pytest.mark.unit
def test_url_engine_password_injected_not_formatted():
    engine = create_db_engine(
        "mssql+pyodbc://user@host/db?driver=x",
        password="p@ss{w}rd;",
        isolation_level="AUTOCOMMIT",
    )
    assert engine.url.password == "p@ss{w}rd;"
    assert engine.url.username == "user"


@pytest.mark.unit
def test_mssql_python_engine_passes_password_to_driver(monkeypatch):
    import sys
    import types

    captured: list[str] = []

    class Stop(Exception):
        pass

    def fake_connect(conn_str: str):
        captured.append(conn_str)
        raise Stop

    monkeypatch.setitem(
        sys.modules, "mssql_python", types.SimpleNamespace(connect=fake_connect)
    )
    engine = create_db_engine(
        "mssql+mssql-python://Server=x;UID=u",
        password="a;b}",
        isolation_level="AUTOCOMMIT",
    )
    assert engine.dialect.name == "mssql"
    with pytest.raises(Stop):
        engine.connect()
    assert captured == ["Server=x;UID=u;PWD={a;b}}};"]


@pytest.mark.unit
def test_parse_odbc_keys_handles_braces():
    keys = parse_odbc_keys("Server=x; UID = u ;PWD={a;b}}c};Trusted_Connection=Yes")
    assert keys == {
        "server": "x",
        "uid": "u",
        "pwd": "a;b}c",
        "trusted_connection": "Yes",
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    "conn_str",
    [
        "Server=x;UID=u;PWD=old",
        "Server=x;UID=u;Password={old}",
        "Server=x;Trusted_Connection=yes",
    ],
)
def test_add_odbc_password_rejects_conflicting_credentials(conn_str):
    with pytest.raises(ValueError):
        add_odbc_password(conn_str, "new")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("conn_str", "server", "database"),
    [
        (
            "mssql+mssql-python://Server=sql01,1433;Database=Sales;UID=u;PWD=secret",
            "sql01,1433",
            "Sales",
        ),
        ("mssql+mssql-python://UID=u;PWD=secret", "", ""),
        ("mssql+pyodbc://u:secret@sqlhost/Sales?driver=x", "sqlhost", "Sales"),
        ("sqlite://", "", ""),
    ],
)
def test_describe_server_and_database(conn_str, server, database):
    from locallib.db import describe_database, describe_server

    assert describe_server(conn_str) == server
    assert describe_database(conn_str) == database
    assert "secret" not in describe_server(conn_str)
    assert "secret" not in describe_database(conn_str)


def _fake_mssql_python(monkeypatch, captured: list):
    import sys
    import types

    class Stop(Exception):
        pass

    def fake_connect(conn_str: str, **kwargs):
        captured.append((conn_str, kwargs))
        raise Stop

    monkeypatch.setitem(
        sys.modules,
        "mssql_python",
        types.SimpleNamespace(connect=fake_connect, SQL_ATTR_LOGIN_TIMEOUT=103),
    )
    return Stop


@pytest.mark.unit
@pytest.mark.parametrize(
    ("timeout", "expected"), [(7, {"attrs_before": {103: 7}}), (None, {})]
)
def test_mssql_python_connect_timeout(monkeypatch, timeout, expected):
    captured: list = []
    stop = _fake_mssql_python(monkeypatch, captured)
    engine = create_db_engine("mssql+mssql-python://Server=x", connect_timeout=timeout)
    with pytest.raises(stop):
        engine.connect()
    assert captured == [("Server=x", expected)]


@pytest.mark.unit
def test_pyodbc_connect_timeout(monkeypatch):
    import sqlalchemy

    import locallib.db as db_module

    seen: dict = {}

    def fake_create_engine(url, **kwargs):
        seen.update(kwargs)
        return sqlalchemy.create_engine("sqlite://")

    monkeypatch.setattr(db_module, "create_engine", fake_create_engine)
    create_db_engine("mssql+pyodbc://u@h/db?driver=x", connect_timeout=9)
    assert seen["connect_args"] == {"timeout": 9}


@pytest.mark.unit
def test_connect_timeout_unsupported_driver():
    with pytest.raises(ValueError, match="not supported for driver 'sqlite'"):
        create_db_engine("sqlite://", connect_timeout=5)
