import pytest
from loguru import logger

from locallib.services.queries import sqlserver as q
from locallib.services.schema_extractor import SchemaExtractor
from tests.fakes import CREATED, FakeEngine, row, sample_rows


def extract(include_row_count=False):
    extractor = SchemaExtractor(FakeEngine(sample_rows()), "sql01", include_row_count)
    return extractor.extract("Sales")


def tables_by_name(schema):
    return {(t["schema"], t["name"]): t for t in schema["tables"]}


@pytest.mark.unit
def test_top_level_shape():
    schema = extract()
    assert list(schema) == [
        "database",
        "server",
        "extended_properties",
        "tables",
        "views",
        "stored_procedures",
        "functions",
    ]
    assert schema["database"] == "Sales"
    assert schema["server"] == "sql01"
    assert schema["extended_properties"] == {"Owner": "Data team"}
    assert [v["name"] for v in schema["views"]] == ["vCustomers"]


@pytest.mark.unit
def test_row_count_only_when_enabled():
    assert all("row_count" not in t for t in extract()["tables"])
    tables = tables_by_name(extract(include_row_count=True))
    assert tables[("dbo", "Customer")]["row_count"] == 1500
    assert tables[("my.schema", "odd.table")]["row_count"] is None


@pytest.mark.unit
def test_composite_foreign_key_grouped():
    order = tables_by_name(extract())[("dbo", "Order")]
    assert order["foreign_keys"] == [
        {
            "name": "FK_Order_Customer",
            "columns": ["CustomerId", "Region"],
            "referenced_schema": "dbo",
            "referenced_table": "Customer",
            "referenced_columns": ["Id", "Region"],
        }
    ]


@pytest.mark.unit
def test_index_key_and_included_columns():
    order = tables_by_name(extract())[("dbo", "Order")]
    assert order["indexes"] == [
        {
            "name": "IX_Order",
            "type": "NONCLUSTERED",
            "is_unique": False,
            "columns": [{"name": "CustomerId", "descending": True}],
            "included_columns": ["Amount"],
        }
    ]


@pytest.mark.unit
def test_dotted_names_keep_their_children():
    odd = tables_by_name(extract())[("my.schema", "odd.table")]
    assert odd["primary_key"] == ["Id"]
    assert [c["name"] for c in odd["columns"]] == ["Id"]
    assert [fk["name"] for fk in odd["foreign_keys"]] == ["FK_odd"]
    assert odd["extended_properties"] == {"Note": "42"}  # converted with str()


@pytest.mark.unit
def test_extended_properties_every_level():
    schema = extract()
    customer = tables_by_name(schema)[("dbo", "Customer")]
    assert customer["extended_properties"] == {"MS_Description": "Customers"}
    cols = {c["name"]: c for c in customer["columns"]}
    assert cols["Name"]["extended_properties"] == {"PII": "yes|really"}
    assert cols["Id"]["extended_properties"] == {}
    assert schema["stored_procedures"][0]["extended_properties"] == {"Owner": "api"}
    assert schema["functions"][0]["extended_properties"] == {"Owner": "reports"}


@pytest.mark.unit
def test_routines_and_parameters():
    schema = extract()
    proc = schema["stored_procedures"][0]
    assert proc["name"] == "GetCustomer"
    assert proc["created"] == CREATED
    assert proc["description"] == "Gets one"
    assert [p["name"] for p in proc["parameters"]] == ["@Id", "@Name"]
    assert proc["parameters"][1]["is_output"] is True

    func = schema["functions"][0]
    assert func["type_code"] == "FN"
    assert func["type"] == "SQL_SCALAR_FUNCTION"
    assert "function_type_code" not in func
    assert [p["name"] for p in func["parameters"]] == ["@x"]


def _hide_definitions(rows):
    for sql, field in (
        (q.VIEWS_QUERY, "view_definition"),
        (q.PROCEDURES_QUERY, "procedure_definition"),
        (q.FUNCTIONS_QUERY, "function_definition"),
    ):
        for r in rows[sql]:
            setattr(r, field, None)
    return rows


def _extract_logging_errors(rows):
    errors: list[str] = []
    sink = logger.add(
        lambda m: errors.append(str(m)), level="ERROR", format="{message}"
    )
    try:
        engine = FakeEngine(rows)
        SchemaExtractor(engine, "sql01", False).extract("Sales")
    finally:
        logger.remove(sink)
    return errors, engine.connection.executed


def _permission_row(has_permission):
    return [
        row(has_permission=has_permission, user_name="ro]user", database_name="Sales")
    ]


@pytest.mark.unit
def test_missing_view_definition_logs_error_with_grant():
    rows = _hide_definitions(sample_rows())
    rows[q.VIEW_DEFINITION_PERMISSION_QUERY] = _permission_row(0)
    errors, _ = _extract_logging_errors(rows)
    assert len(errors) == 1
    assert "VIEW DEFINITION" in errors[0]
    assert "3 view, procedure and function definition(s)" in errors[0]
    assert "USE [Sales]; GRANT VIEW DEFINITION TO [ro]]user];" in errors[0]


@pytest.mark.unit
def test_no_error_when_user_has_view_definition():
    rows = _hide_definitions(sample_rows())
    rows[q.VIEW_DEFINITION_PERMISSION_QUERY] = _permission_row(1)
    errors, _ = _extract_logging_errors(rows)
    assert errors == []


@pytest.mark.unit
def test_permission_not_checked_when_definitions_present():
    rows = sample_rows()
    rows[q.VIEW_DEFINITION_PERMISSION_QUERY] = _permission_row(0)
    errors, executed = _extract_logging_errors(rows)
    assert errors == []
    assert q.VIEW_DEFINITION_PERMISSION_QUERY not in executed
