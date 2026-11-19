import re

import pytest

from locallib.services.queries import sqlserver

# mssql_python cannot fetch sql_variant (ODBC type -150); these must be cast in SQL.
VARIANT_COLUMNS = ("ep.value", "par.default_value")

QUERIES = {
    name: value
    for name, value in vars(sqlserver).items()
    if name.endswith("_QUERY") and isinstance(value, str)
}


@pytest.mark.unit
def test_queries_discovered():
    assert "COLUMNS_QUERY" in QUERIES


@pytest.mark.unit
@pytest.mark.parametrize("name", sorted(QUERIES))
def test_sql_variant_columns_are_cast(name):
    sql = QUERIES[name]
    for column in VARIANT_COLUMNS:
        for match in re.finditer(re.escape(column) + r"\b", sql):
            prefix = sql[: match.start()].rstrip()
            assert prefix.upper().endswith("CAST("), f"{name}: raw {column} selected"
