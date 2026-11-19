"""Fake SQLAlchemy engine and canned catalog rows for export tests."""

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from locallib.services.queries import sqlserver as q


def row(**values: Any) -> SimpleNamespace:
    return SimpleNamespace(**values)


class FakeConnection:
    def __init__(self, rows_by_sql: dict[str, list[SimpleNamespace]], error=None):
        self.rows_by_sql = rows_by_sql
        self.error = error
        self.executed: list[str] = []

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def execute(self, statement: Any) -> list[SimpleNamespace]:
        if self.error is not None:
            raise self.error
        sql = statement.text
        self.executed.append(sql)
        return list(self.rows_by_sql.get(sql, []))


class FakeEngine:
    """Maps each query constant to a list of rows; unknown queries return []."""

    def __init__(self, rows_by_sql: dict[str, list[SimpleNamespace]], error=None):
        self.connection = FakeConnection(rows_by_sql, error)
        self.disposed = False

    def connect(self) -> FakeConnection:
        return self.connection

    def dispose(self) -> None:
        self.disposed = True


def column(schema: str, table: str, name: str, position: int, **kw: Any):
    values: dict[str, Any] = dict(
        schema_name=schema,
        table_name=table,
        column_name=name,
        ordinal_position=position,
        data_type="int",
        max_length=4,
        precision=10,
        scale=0,
        is_nullable=False,
        is_identity=False,
        default_value=None,
        column_description=None,
    )
    values.update(kw)
    return row(**values)


def param(schema: str, prefix: str, obj: str, name: str, position: int, **kw: Any):
    values: dict[str, Any] = {
        "schema_name": schema,
        f"{prefix}_name": obj,
        "parameter_name": name,
        "parameter_id": position,
        "data_type": "int",
        "max_length": 4,
        "precision": 10,
        "scale": 0,
        "is_output": False,
        "has_default_value": False,
        "default_value": None,
    }
    values.update(kw)
    return row(**values)


CREATED = datetime(2024, 1, 2, 3, 4, 5)


def sample_rows() -> dict[str, list[SimpleNamespace]]:
    """A small schema: dbo.Customer, dbo.Order, the dotted my.schema.odd.table,
    one view, one procedure and one function."""
    return {
        q.TABLES_QUERY: [
            row(
                schema_name="dbo",
                table_name="Customer",
                table_type="USER_TABLE",
                row_count=1500,
            ),
            row(
                schema_name="dbo",
                table_name="Order",
                table_type="USER_TABLE",
                row_count=20,
            ),
            row(
                schema_name="my.schema",
                table_name="odd.table",
                table_type="USER_TABLE",
                row_count=None,
            ),
        ],
        q.COLUMNS_QUERY: [
            column("dbo", "Customer", "Id", 1, is_identity=True),
            column(
                "dbo",
                "Customer",
                "Name",
                2,
                data_type="nvarchar",
                max_length=200,
                column_description="Full | name\nof customer",
            ),
            column(
                "dbo",
                "Customer",
                "Notes",
                3,
                data_type="varchar",
                max_length=-1,
                is_nullable=True,
                default_value="('a|b')",
            ),
            column("dbo", "Order", "Id", 1),
            column("dbo", "Order", "CustomerId", 2),
            column("dbo", "Order", "Region", 3),
            column(
                "dbo", "Order", "Amount", 4, data_type="decimal", precision=18, scale=2
            ),
            column("my.schema", "odd.table", "Id", 1),
        ],
        q.PK_QUERY: [
            row(
                schema_name="dbo",
                table_name="Customer",
                pk_name="PK_C",
                column_name="Id",
                key_ordinal=1,
            ),
            row(
                schema_name="dbo",
                table_name="Order",
                pk_name="PK_O",
                column_name="Id",
                key_ordinal=1,
            ),
            row(
                schema_name="my.schema",
                table_name="odd.table",
                pk_name="PK_X",
                column_name="Id",
                key_ordinal=1,
            ),
        ],
        q.FK_QUERY: [
            row(
                schema_name="dbo",
                table_name="Order",
                fk_name="FK_Order_Customer",
                column_name="CustomerId",
                referenced_schema="dbo",
                referenced_table="Customer",
                referenced_column="Id",
            ),
            row(
                schema_name="dbo",
                table_name="Order",
                fk_name="FK_Order_Customer",
                column_name="Region",
                referenced_schema="dbo",
                referenced_table="Customer",
                referenced_column="Region",
            ),
            row(
                schema_name="my.schema",
                table_name="odd.table",
                fk_name="FK_odd",
                column_name="Id",
                referenced_schema="dbo",
                referenced_table="Customer",
                referenced_column="Id",
            ),
        ],
        q.INDEX_QUERY: [
            row(
                schema_name="dbo",
                table_name="Order",
                index_name="IX_Order",
                index_type="NONCLUSTERED",
                is_unique=False,
                column_name="Amount",
                key_ordinal=0,
                is_descending_key=False,
                is_included_column=True,
            ),
            row(
                schema_name="dbo",
                table_name="Order",
                index_name="IX_Order",
                index_type="NONCLUSTERED",
                is_unique=False,
                column_name="CustomerId",
                key_ordinal=1,
                is_descending_key=True,
                is_included_column=False,
            ),
        ],
        q.VIEWS_QUERY: [
            row(
                schema_name="dbo",
                view_name="vCustomers",
                view_definition="CREATE VIEW dbo.vCustomers AS SELECT 1",
            ),
        ],
        q.PROCEDURES_QUERY: [
            row(
                schema_name="dbo",
                procedure_name="GetCustomer",
                create_date=CREATED,
                modify_date=CREATED,
                procedure_definition="CREATE PROCEDURE dbo.GetCustomer",
                procedure_description="Gets one",
            ),
        ],
        q.PROCEDURE_PARAMS_QUERY: [
            param("dbo", "procedure", "GetCustomer", "@Id", 1),
            param(
                "dbo",
                "procedure",
                "GetCustomer",
                "@Name",
                2,
                data_type="nvarchar",
                max_length=-1,
                is_output=True,
            ),
        ],
        q.FUNCTIONS_QUERY: [
            row(
                schema_name="dbo",
                function_name="fnTotal",
                function_type_code="FN",
                function_type="SQL_SCALAR_FUNCTION",
                create_date=CREATED,
                modify_date=CREATED,
                function_definition="CREATE FUNCTION dbo.fnTotal",
                function_description=None,
            ),
        ],
        q.FUNCTION_PARAMS_QUERY: [
            param(
                "dbo", "function", "fnTotal", "@x", 1, data_type="datetime2", scale=7
            ),
        ],
        q.DB_EXTENDED_PROPERTIES_QUERY: [
            row(property_name="Owner", property_value="Data team"),
        ],
        q.TABLE_EXTENDED_PROPERTIES_QUERY: [
            row(
                schema_name="dbo",
                table_name="Customer",
                property_name="MS_Description",
                property_value="Customers",
            ),
            row(
                schema_name="my.schema",
                table_name="odd.table",
                property_name="Note",
                property_value=42,
            ),
        ],
        q.COLUMN_EXTENDED_PROPERTIES_QUERY: [
            row(
                schema_name="dbo",
                table_name="Customer",
                column_name="Name",
                property_name="PII",
                property_value="yes|really",
            ),
        ],
        q.PROCEDURE_EXTENDED_PROPERTIES_QUERY: [
            row(
                schema_name="dbo",
                procedure_name="GetCustomer",
                property_name="Owner",
                property_value="api",
            ),
        ],
        q.FUNCTION_EXTENDED_PROPERTIES_QUERY: [
            row(
                schema_name="dbo",
                function_name="fnTotal",
                property_name="Owner",
                property_value="reports",
            ),
        ],
    }
