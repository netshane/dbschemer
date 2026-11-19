import re

import pytest

from locallib.db import (
    build_connection,
    create_db_engine,
    describe_database,
    describe_server,
    dialect_for,
)
from locallib.dbschemer_config import DbschemerDatabase
from locallib.services.queries import QUERY_SETS, get_queries


def make(**kw):
    return DbschemerDatabase(output="o", **kw)


@pytest.mark.unit
def test_sqlserver_trusted_connection():
    conn = build_connection(make(type="sqlserver", server="sql01", database="Sales"))
    assert conn == (
        "mssql+mssql-python://Server=sql01;Database=Sales;Trusted_Connection=yes;"
        "TrustServerCertificate=yes;Encrypt=yes;"
    )


@pytest.mark.unit
def test_sqlserver_user_and_port():
    conn = build_connection(
        make(type="sqlserver", server="sql01", database="Sales", user="u", port=1444)
    )
    assert conn == (
        "mssql+mssql-python://Server=sql01,1444;Database=Sales;UID=u;"
        "TrustServerCertificate=yes;Encrypt=yes;"
    )
    assert describe_server(conn) == "sql01,1444"
    assert describe_database(conn) == "Sales"


@pytest.mark.unit
def test_sqlserver_quotes_special_values():
    conn = build_connection(
        make(type="sqlserver", server="s", database="a;b", user="u{x")
    )
    assert "Database={a;b};" in conn
    assert "UID={u{x};" in conn
    assert describe_database(conn) == "a;b"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("db_type", "prefix"),
    [("postgres", "postgresql+psycopg://"), ("mysql", "mysql+pymysql://")],
)
def test_url_types(db_type, prefix):
    conn = build_connection(
        make(type=db_type, server="h", database="d", user="us@r", port=5433)
    )
    assert conn == f"{prefix}us%40r@h:5433/d"
    assert describe_server(conn) == "h"
    assert describe_database(conn) == "d"
    assert dialect_for(conn) == db_type


@pytest.mark.unit
def test_url_without_user_and_port():
    conn = build_connection(make(type="postgres", server="h", database="d"))
    assert conn == "postgresql+psycopg://h/d"


@pytest.mark.unit
def test_connection_string_override_is_returned_unchanged():
    assert build_connection(make(connection_string="sqlite://")) == "sqlite://"


@pytest.mark.unit
def test_password_is_injected_not_formatted():
    conn = build_connection(make(type="postgres", server="h", database="d", user="u"))
    engine = create_db_engine(conn, password="p@ss:/word")
    assert engine.url.password == "p@ss:/word"
    assert engine.url.drivername == "postgresql+psycopg"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("conn", "arg"),
    [
        ("postgresql+psycopg://h/d", "connect_timeout"),
        ("mysql+pymysql://h/d", "connect_timeout"),
        ("mssql+pyodbc://h/d", "timeout"),
    ],
)
def test_connect_timeout_args(monkeypatch, conn, arg):
    captured = {}
    monkeypatch.setattr(
        "locallib.db.create_engine", lambda url, **kw: captured.update(kw)
    )
    create_db_engine(conn, connect_timeout=7)
    assert captured["connect_args"] == {arg: 7}


@pytest.mark.unit
def test_connect_timeout_unsupported_driver():
    with pytest.raises(ValueError, match="not supported"):
        create_db_engine("sqlite://", connect_timeout=7)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("conn", "expected"),
    [
        ("mssql+mssql-python://Server=x;", "sqlserver"),
        ("mssql+pyodbc://u@h/d", "sqlserver"),
        ("postgresql://h/d", "postgres"),
        ("mysql+pymysql://h/d", "mysql"),
        ("mariadb+pymysql://h/d", "mysql"),
        ("sqlite://", "sqlserver"),
    ],
)
def test_dialect_for(conn, expected):
    assert dialect_for(conn) == expected


@pytest.mark.unit
def test_unknown_query_set():
    with pytest.raises(ValueError, match="Unsupported database type"):
        get_queries("oracle")


NAMES = [
    "TABLES_QUERY",
    "COLUMNS_QUERY",
    "PK_QUERY",
    "FK_QUERY",
    "INDEX_QUERY",
    "VIEWS_QUERY",
    "PROCEDURES_QUERY",
    "PROCEDURE_PARAMS_QUERY",
    "FUNCTIONS_QUERY",
    "FUNCTION_PARAMS_QUERY",
    "DB_EXTENDED_PROPERTIES_QUERY",
    "TABLE_EXTENDED_PROPERTIES_QUERY",
    "PROCEDURE_EXTENDED_PROPERTIES_QUERY",
    "FUNCTION_EXTENDED_PROPERTIES_QUERY",
    "COLUMN_EXTENDED_PROPERTIES_QUERY",
]
ALIASES = {
    "TABLES_QUERY": ["schema_name", "table_name", "table_type", "row_count"],
    "COLUMNS_QUERY": [
        "schema_name",
        "table_name",
        "column_name",
        "ordinal_position",
        "data_type",
        "max_length",
        "precision",
        "scale",
        "is_nullable",
        "is_identity",
        "default_value",
        "column_description",
    ],
    "PK_QUERY": ["pk_name", "column_name", "key_ordinal"],
    "FK_QUERY": [
        "fk_name",
        "referenced_schema",
        "referenced_table",
        "referenced_column",
    ],
    "INDEX_QUERY": [
        "index_name",
        "index_type",
        "is_unique",
        "is_descending_key",
        "is_included_column",
    ],
    "VIEWS_QUERY": ["view_name", "view_definition"],
    "PROCEDURES_QUERY": [
        "procedure_name",
        "create_date",
        "modify_date",
        "procedure_definition",
        "procedure_description",
    ],
    "FUNCTIONS_QUERY": [
        "function_name",
        "function_type_code",
        "function_type",
        "function_definition",
        "function_description",
    ],
    "PROCEDURE_PARAMS_QUERY": [
        "procedure_name",
        "parameter_name",
        "parameter_id",
        "data_type",
        "is_output",
        "has_default_value",
        "default_value",
    ],
    "FUNCTION_PARAMS_QUERY": [
        "function_name",
        "parameter_name",
        "parameter_id",
        "has_default_value",
    ],
}


@pytest.mark.unit
@pytest.mark.parametrize("db_type", sorted(QUERY_SETS))
def test_query_set_shape(db_type):
    module = get_queries(db_type)
    for name in NAMES:
        assert hasattr(module, name), f"{db_type} missing {name}"
        sql = getattr(module, name)
        if sql is None:
            continue
        assert "ORDER BY" in sql, f"{db_type}.{name} has no ORDER BY"
        for alias in ALIASES.get(name, []):
            # an explicit alias, or a column of that name (SQL Server)
            assert re.search(rf"(AS\s+`?|\.){alias}\b", sql), (
                f"{db_type}.{name} lacks alias {alias}"
            )
    # every dialect has the queries the extractor requires
    for name in NAMES[:10] + ["TABLE_EXTENDED_PROPERTIES_QUERY"]:
        assert getattr(module, name) is not None
