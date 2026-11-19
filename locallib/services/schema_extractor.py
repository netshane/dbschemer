"""Reads a database schema into a plain dict (the ``schema.json`` content)."""

from types import ModuleType
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from locallib.services.queries import sqlserver

Key = tuple[str, ...]
Props = dict[str, str]


class SchemaExtractor:
    """Runs the catalog queries of one dialect and assembles the result.

    ``queries`` is a module from ``locallib.services.queries`` (SQL Server by
    default). A query that is ``None`` does not apply to the dialect.

    Objects are keyed by tuples such as ``(schema, name)`` so names that contain
    a ``.`` cannot be confused.
    """

    def __init__(
        self,
        engine: Engine,
        server: str,
        include_row_count: bool,
        queries: ModuleType = sqlserver,
    ):
        self.queries = queries
        self.engine = engine
        self.server = server
        self.include_row_count = include_row_count

    def extract(self, database: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            tables = self._tables(conn)
            procedures = self._routines(
                conn,
                "stored procedures",
                self.queries.PROCEDURES_QUERY,
                self.queries.PROCEDURE_PARAMS_QUERY,
                self.queries.PROCEDURE_EXTENDED_PROPERTIES_QUERY,
                "procedure",
            )
            functions = self._routines(
                conn,
                "functions",
                self.queries.FUNCTIONS_QUERY,
                self.queries.FUNCTION_PARAMS_QUERY,
                self.queries.FUNCTION_EXTENDED_PROPERTIES_QUERY,
                "function",
            )
            views = self._views(conn)
            self._check_view_definition(conn, [*views, *procedures, *functions])
            return {
                "database": database,
                "server": self.server,
                "extended_properties": self._database_properties(conn),
                "tables": tables,
                "views": views,
                "stored_procedures": procedures,
                "functions": functions,
            }

    # --- helpers ---------------------------------------------------------------

    @staticmethod
    def _rows(conn: Connection, sql: str | None) -> list[Any]:
        if sql is None:
            return []
        return list(conn.execute(text(sql)))

    def _grouped_properties(
        self, conn: Connection, sql: str, *key_fields: str
    ) -> dict[Key, Props]:
        result: dict[Key, Props] = {}
        for row in self._rows(conn, sql):
            key = tuple(getattr(row, f) for f in key_fields)
            result.setdefault(key, {})[row.property_name] = str(row.property_value)
        return result

    @staticmethod
    def _quote_identifier(name: str) -> str:
        return "[" + name.replace("]", "]]") + "]"

    def _check_view_definition(
        self, conn: Connection, modules: list[dict[str, Any]]
    ) -> None:
        """Log an error if definitions are missing because the user lacks
        VIEW DEFINITION. Only checked when some definition came back empty, so
        a grant at schema or object level does not cause a false alarm."""
        sql = getattr(self.queries, "VIEW_DEFINITION_PERMISSION_QUERY", None)
        grant = getattr(self.queries, "VIEW_DEFINITION_GRANT", None)
        missing = sum(1 for m in modules if m.get("definition") is None)
        if sql is None or grant is None or missing == 0:
            return
        rows = self._rows(conn, sql)
        if not rows or rows[0].has_permission:
            return
        row = rows[0]
        fix = grant.format(
            database=self._quote_identifier(row.database_name),
            user=self._quote_identifier(row.user_name),
        )
        logger.error(
            f"User '{row.user_name}' does not appear to have VIEW DEFINITION "
            f"permission on '{row.database_name}'; {missing} view, procedure "
            f"and function definition(s) could not be read. Fix with: {fix}"
        )

    # --- object types ----------------------------------------------------------

    def _database_properties(self, conn: Connection) -> Props:
        logger.debug("Extracting database extended properties...")
        return {
            row.property_name: str(row.property_value)
            for row in self._rows(conn, self.queries.DB_EXTENDED_PROPERTIES_QUERY)
        }

    def _tables(self, conn: Connection) -> list[dict[str, Any]]:
        logger.debug("Extracting tables...")
        tables: dict[Key, dict[str, Any]] = {}
        for row in self._rows(conn, self.queries.TABLES_QUERY):
            table: dict[str, Any] = {
                "schema": row.schema_name,
                "name": row.table_name,
                "type": row.table_type,
            }
            if self.include_row_count:
                table["row_count"] = row.row_count
            table.update(columns=[], primary_key=[], foreign_keys=[], indexes=[])
            tables[(row.schema_name, row.table_name)] = table

        logger.debug("Extracting columns...")
        for row in self._rows(conn, self.queries.COLUMNS_QUERY):
            key = (row.schema_name, row.table_name)
            if key in tables:
                tables[key]["columns"].append(
                    {
                        "name": row.column_name,
                        "position": row.ordinal_position,
                        "data_type": row.data_type,
                        "max_length": row.max_length,
                        "precision": row.precision,
                        "scale": row.scale,
                        "nullable": row.is_nullable,
                        "is_identity": row.is_identity,
                        "default": row.default_value,
                        "description": row.column_description,
                    }
                )

        logger.debug("Extracting primary keys...")
        for row in self._rows(conn, self.queries.PK_QUERY):
            key = (row.schema_name, row.table_name)
            if key in tables:
                tables[key]["primary_key"].append(row.column_name)

        logger.debug("Extracting foreign keys...")
        fks: dict[Key, dict[str, Any]] = {}
        for row in self._rows(conn, self.queries.FK_QUERY):
            fk_key = (row.schema_name, row.table_name, row.fk_name)
            fk = fks.setdefault(
                fk_key,
                {
                    "name": row.fk_name,
                    "columns": [],
                    "referenced_schema": row.referenced_schema,
                    "referenced_table": row.referenced_table,
                    "referenced_columns": [],
                },
            )
            fk["columns"].append(row.column_name)
            fk["referenced_columns"].append(row.referenced_column)
        for (schema, table_name, _), fk in fks.items():
            if (schema, table_name) in tables:
                tables[(schema, table_name)]["foreign_keys"].append(fk)

        logger.debug("Extracting indexes...")
        indexes: dict[Key, dict[str, Any]] = {}
        for row in self._rows(conn, self.queries.INDEX_QUERY):
            idx_key = (row.schema_name, row.table_name, row.index_name)
            idx = indexes.setdefault(
                idx_key,
                {
                    "name": row.index_name,
                    "type": row.index_type,
                    "is_unique": row.is_unique,
                    "columns": [],
                    "included_columns": [],
                },
            )
            if row.is_included_column:
                idx["included_columns"].append(row.column_name)
            else:
                idx["columns"].append(
                    {"name": row.column_name, "descending": row.is_descending_key}
                )
        for (schema, table_name, _), idx in indexes.items():
            if (schema, table_name) in tables:
                tables[(schema, table_name)]["indexes"].append(idx)

        logger.debug("Extracting table extended properties...")
        table_props = self._grouped_properties(
            conn,
            self.queries.TABLE_EXTENDED_PROPERTIES_QUERY,
            "schema_name",
            "table_name",
        )
        logger.debug("Extracting column extended properties...")
        column_props = self._grouped_properties(
            conn,
            self.queries.COLUMN_EXTENDED_PROPERTIES_QUERY,
            "schema_name",
            "table_name",
            "column_name",
        )
        for (schema, table_name), table in tables.items():
            table["extended_properties"] = table_props.get((schema, table_name), {})
            for col in table["columns"]:
                col["extended_properties"] = column_props.get(
                    (schema, table_name, col["name"]), {}
                )

        return list(tables.values())

    def _views(self, conn: Connection) -> list[dict[str, Any]]:
        logger.debug("Extracting views...")
        return [
            {
                "schema": row.schema_name,
                "name": row.view_name,
                "definition": row.view_definition,
            }
            for row in self._rows(conn, self.queries.VIEWS_QUERY)
        ]

    def _routines(
        self,
        conn: Connection,
        label: str,
        objects_sql: str,
        params_sql: str,
        props_sql: str,
        prefix: str,
    ) -> list[dict[str, Any]]:
        """Stored procedures or functions; ``prefix`` is the column-name prefix
        used by the queries (``procedure`` or ``function``)."""
        name_field = f"{prefix}_name"
        logger.debug(f"Extracting {label}...")
        routines: dict[Key, dict[str, Any]] = {}
        for row in self._rows(conn, objects_sql):
            routine: dict[str, Any] = {
                "schema": row.schema_name,
                "name": getattr(row, name_field),
            }
            if prefix == "function":
                routine["type_code"] = row.function_type_code.strip()
                routine["type"] = row.function_type
            routine.update(
                created=row.create_date,
                modified=row.modify_date,
                definition=getattr(row, f"{prefix}_definition"),
                description=getattr(row, f"{prefix}_description"),
                parameters=[],
            )
            routines[(row.schema_name, routine["name"])] = routine

        logger.debug(f"Extracting {label} parameters...")
        for row in self._rows(conn, params_sql):
            key: Key = (row.schema_name, getattr(row, name_field))
            if key in routines:
                routines[key]["parameters"].append(
                    {
                        "name": row.parameter_name,
                        "position": row.parameter_id,
                        "data_type": row.data_type,
                        "max_length": row.max_length,
                        "precision": row.precision,
                        "scale": row.scale,
                        "is_output": row.is_output,
                        "has_default": row.has_default_value,
                        "default": row.default_value,
                    }
                )

        logger.debug(f"Extracting {label} extended properties...")
        props = self._grouped_properties(conn, props_sql, "schema_name", name_field)
        for key, routine in routines.items():
            routine["extended_properties"] = props.get(key, {})

        return list(routines.values())
