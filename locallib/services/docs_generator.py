"""Writes ``schema.json`` and the markdown docs for an extracted schema dict."""

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote

from loguru import logger

SIZED_TYPES = ("varchar", "nvarchar", "char", "nchar", "binary", "varbinary")


def _cell(value: Any) -> str:
    """Make ``value`` safe for one markdown table cell."""
    return (
        str(value)
        .replace("|", "\\|")
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _format_type(item: dict[str, Any]) -> str:
    """A column's or parameter's data type with its length/precision."""
    dtype: str = item["data_type"]
    if dtype in SIZED_TYPES and item["max_length"] is not None:
        length = item["max_length"]
        if dtype.startswith("n") and length > 0:
            length = length // 2  # n-types store 2 bytes per character
        dtype = f"{dtype}(MAX)" if length == -1 else f"{dtype}({length})"
    elif dtype in ("decimal", "numeric") and item["precision"] is not None:
        dtype = f"{dtype}({item['precision']},{item['scale']})"
    elif dtype == "datetime2" and item["scale"] is not None:
        dtype = f"{dtype}({item['scale']})"
    return dtype


def _property_table(props: dict[str, Any]) -> str:
    content = "| Property | Value |\n|----------|-------|\n"
    for name, value in sorted(props.items()):
        content += f"| {_cell(name)} | {_cell(value)} |\n"
    return content


def _format_extended_properties(props: dict[str, Any], heading_level: int = 2) -> str:
    if not props:
        return ""
    heading = "#" * heading_level
    return f"\n{heading} Extended Properties\n\n" + _property_table(props)


def _file_name(*parts: str) -> str:
    """``<part>.<part>.md`` with path separators replaced, so a database name
    such as ``a/b`` or ``../x`` can never leave its output folder."""
    safe = (p.replace("/", "_").replace("\\", "_") for p in parts)
    return ".".join(safe) + ".md"


def _href(folder: str, *parts: str) -> str:
    """A URL-encoded relative markdown link to ``folder/<_file_name(parts)>``."""
    return quote(f"{folder}/{_file_name(*parts)}")


def _group_by_schema(
    tables: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table in tables:
        grouped[table["schema"]].append(table)
    return grouped


def _by_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda i: (i["schema"], i["name"]))


class DocsGenerator:
    """Renders the schema dict produced by ``SchemaExtractor`` to files."""

    GENERATED_FILES = (
        "schema.json",
        "README.md",
        "views.md",
        "stored_procedures.md",
        "functions.md",
    )
    GENERATED_DIRS = ("schemas", "tables", "procedures", "functions")

    def __init__(self, include_row_count: bool):
        self.include_row_count = include_row_count

    # --- files -----------------------------------------------------------------

    def clean(self, output_dir: Path) -> None:
        """Delete only what an export generates; leave every other file alone."""
        for name in self.GENERATED_FILES:
            (output_dir / name).unlink(missing_ok=True)
        for name in self.GENERATED_DIRS:
            path = output_dir / name
            if path.is_symlink():
                path.unlink()  # never follow a symlinked directory
            elif path.is_dir():
                shutil.rmtree(path)

    @staticmethod
    def _write(path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        logger.debug(f"Wrote {path}")
        return path

    def write_json(self, schema: dict[str, Any], output_dir: Path) -> Path:
        content = json.dumps(schema, indent=2, default=str) + "\n"
        return self._write(output_dir / "schema.json", content)

    def generate(self, schema: dict[str, Any], output_dir: Path) -> list[Path]:
        """Write the markdown docs and return the paths written."""
        output_dir.mkdir(parents=True, exist_ok=True)
        tables_by_schema = _group_by_schema(schema["tables"])
        written = [
            self._write(output_dir / "README.md", self._index(schema, tables_by_schema))
        ]
        for schema_name in sorted(tables_by_schema):
            written.append(
                self._write(
                    output_dir / "schemas" / _file_name(schema_name),
                    self._schema_file(schema_name, tables_by_schema[schema_name]),
                )
            )
        for table in schema["tables"]:
            written.append(
                self._write(
                    output_dir / "tables" / _file_name(table["schema"], table["name"]),
                    self._table_file(table),
                )
            )
        written.append(
            self._write(output_dir / "views.md", self._views_file(schema["views"]))
        )

        written += self._write_routines(
            schema.get("stored_procedures", []),
            output_dir,
            folder="procedures",
            index_name="stored_procedures.md",
            title="Stored Procedures",
            is_function=False,
        )
        written += self._write_routines(
            schema.get("functions", []),
            output_dir,
            folder="functions",
            index_name="functions.md",
            title="Functions",
            is_function=True,
        )
        return written

    def _write_routines(
        self,
        routines: list[dict[str, Any]],
        output_dir: Path,
        folder: str,
        index_name: str,
        title: str,
        is_function: bool,
    ) -> list[Path]:
        """Write one page per routine plus an index; nothing if there are none."""
        if not routines:
            return []
        written: list[Path] = []
        index = f"# {title}\n\n"
        for routine in _by_name(routines):
            full_name = f"{routine['schema']}.{routine['name']}"
            count = len(routine.get("parameters", []))
            link = _href(folder, routine["schema"], routine["name"])
            detail = f"{routine.get('type', '')}, " if is_function else ""
            index += f"- [{full_name}]({link}) ({detail}{count} parameters)\n"
            written.append(
                self._write(
                    output_dir
                    / folder
                    / _file_name(routine["schema"], routine["name"]),
                    self._routine_file(routine, is_function=is_function),
                )
            )
        written.append(self._write(output_dir / index_name, index))
        return written

    # --- content ---------------------------------------------------------------

    def _index(
        self,
        schema: dict[str, Any],
        tables_by_schema: dict[str, list[dict[str, Any]]],
    ) -> str:
        procedures = schema.get("stored_procedures", [])
        functions = schema.get("functions", [])
        content = (
            f"# {schema['database']} Database Schema\n\n"
            f"**Server:** {schema['server']}\n"
            f"**Database:** {schema['database']}\n"
            f"**Tables:** {len(schema['tables'])}\n"
            f"**Views:** {len(schema['views'])}\n"
            f"**Stored Procedures:** {len(procedures)}\n"
            f"**Functions:** {len(functions)}\n"
        )
        content += _format_extended_properties(schema.get("extended_properties", {}))

        content += "\n## Schemas\n\n"
        if self.include_row_count:
            content += "| Schema | Tables | Total Rows |\n"
            content += "|--------|--------|------------|\n"
        else:
            content += "| Schema | Tables |\n|--------|--------|\n"
        for schema_name in sorted(tables_by_schema):
            tables = tables_by_schema[schema_name]
            row = (
                f"| [{_cell(schema_name)}]({_href('schemas', schema_name)}) "
                f"| {len(tables)} |"
            )
            if self.include_row_count:
                total = sum(t.get("row_count") or 0 for t in tables)
                row += f" {total:,} |"
            content += row + "\n"

        content += "\n## Views\n\n| Schema | View Name |\n|--------|-----------|\n"
        for view in schema["views"]:
            content += f"| {_cell(view['schema'])} | {_cell(view['name'])} |\n"

        if procedures:
            content += (
                "\n## Stored Procedures\n\n"
                "| Schema | Procedure | Parameters |\n"
                "|--------|-----------|------------|\n"
            )
            for proc in _by_name(procedures):
                link = _href("procedures", proc["schema"], proc["name"])
                content += (
                    f"| {_cell(proc['schema'])} "
                    f"| [{_cell(proc['name'])}]({link}) "
                    f"| {len(proc.get('parameters', []))} |\n"
                )

        if functions:
            content += (
                "\n## Functions\n\n"
                "| Schema | Function | Type | Parameters |\n"
                "|--------|----------|------|------------|\n"
            )
            for func in _by_name(functions):
                link = _href("functions", func["schema"], func["name"])
                content += (
                    f"| {_cell(func['schema'])} "
                    f"| [{_cell(func['name'])}]({link}) "
                    f"| {_cell(func.get('type', ''))} "
                    f"| {len(func.get('parameters', []))} |\n"
                )
        return content

    def _schema_file(self, schema_name: str, tables: list[dict[str, Any]]) -> str:
        content = f"# {schema_name} Schema\n\n## Tables\n\n"
        if self.include_row_count:
            content += "| Table | Columns | Rows | Primary Key |\n"
            content += "|-------|---------|------|-------------|\n"
        else:
            content += "| Table | Columns | Primary Key |\n"
            content += "|-------|---------|-------------|\n"
        for table in sorted(tables, key=lambda t: t["name"]):
            link = _href("../tables", schema_name, table["name"])
            pk = ", ".join(table.get("primary_key", [])) or "-"
            col_count = len(table.get("columns", []))
            row = f"| [{_cell(table['name'])}]({link}) | {col_count} |"
            if self.include_row_count:
                row += f" {table.get('row_count') or 0:,} |"
            content += f"{row} {_cell(pk)} |\n"
        return content

    def _table_file(self, table: dict[str, Any]) -> str:
        full_name = f"{table['schema']}.{table['name']}"
        content = f"# {full_name}\n\n**Schema:** {table['schema']}\n"
        if self.include_row_count:
            content += f"**Rows:** {table.get('row_count') or 0:,}\n"
        content += _format_extended_properties(table.get("extended_properties", {}))

        content += (
            "\n## Columns\n\n"
            "| # | Column | Type | Nullable | Default | Description |\n"
            "|---|--------|------|----------|---------|-------------|\n"
        )
        for col in table.get("columns", []):
            nullable = "YES" if col["nullable"] else "NO"
            default = col.get("default")
            default_str = f"`{_cell(default)}`" if default else "-"
            desc = _cell(col.get("description") or "-")
            content += (
                f"| {col['position']} | {_cell(col['name'])} "
                f"| {_cell(_format_type(col))} | {nullable} | {default_str} "
                f"| {desc} |\n"
            )

        cols_with_props = [
            c for c in table.get("columns", []) if c.get("extended_properties")
        ]
        if cols_with_props:
            content += "\n## Column Extended Properties\n\n"
            for col in cols_with_props:
                content += f"### {col['name']}\n\n"
                content += _property_table(col["extended_properties"]) + "\n"

        if table.get("primary_key"):
            content += "\n## Primary Key\n\n"
            content += f"**Columns:** {', '.join(table['primary_key'])}\n"

        if table.get("foreign_keys"):
            content += (
                "\n## Foreign Keys\n\n"
                "| Name | Columns | References |\n"
                "|------|---------|------------|\n"
            )
            for fk in table["foreign_keys"]:
                cols = ", ".join(fk["columns"])
                ref = (
                    f"{fk['referenced_schema']}.{fk['referenced_table']} "
                    f"({', '.join(fk['referenced_columns'])})"
                )
                content += f"| {_cell(fk['name'])} | {_cell(cols)} | {_cell(ref)} |\n"

        if table.get("indexes"):
            content += (
                "\n## Indexes\n\n"
                "| Name | Type | Unique | Columns | Included |\n"
                "|------|------|--------|---------|----------|\n"
            )
            for idx in table["indexes"]:
                cols = ", ".join(c["name"] for c in idx["columns"])
                included = ", ".join(idx.get("included_columns", [])) or "-"
                unique = "YES" if idx["is_unique"] else "NO"
                content += (
                    f"| {_cell(idx['name'])} | {_cell(idx['type'])} | {unique} "
                    f"| {_cell(cols)} | {_cell(included)} |\n"
                )
        return content

    @staticmethod
    def _views_file(views: list[dict[str, Any]]) -> str:
        content = "# Views\n\n"
        for view in views:
            content += f"## {view['schema']}.{view['name']}\n\n"
            if view.get("definition"):
                content += f"```sql\n{view['definition']}\n```\n\n"
            else:
                content += "*Definition not available*\n\n"
        return content

    @staticmethod
    def _routine_file(routine: dict[str, Any], is_function: bool) -> str:
        full_name = f"{routine['schema']}.{routine['name']}"
        content = f"# {full_name}\n\n**Schema:** {routine['schema']}\n"
        if is_function:
            content += f"**Type:** {routine.get('type', '-')}\n"
        content += (
            f"**Created:** {routine.get('created', '-')}\n"
            f"**Modified:** {routine.get('modified', '-')}\n"
        )
        if routine.get("description"):
            content += f"\n**Description:** {routine['description']}\n"
        content += _format_extended_properties(routine.get("extended_properties", {}))

        if routine.get("parameters"):
            content += (
                "\n## Parameters\n\n"
                "| # | Name | Type | Direction | Has Default | Default |\n"
                "|---|------|------|-----------|-------------|---------|\n"
            )
            for param in routine["parameters"]:
                direction = "OUTPUT" if param.get("is_output") else "INPUT"
                has_default = "YES" if param.get("has_default") else "NO"
                default = _cell(param.get("default") or "-")
                content += (
                    f"| {param['position']} | {_cell(param['name'])} "
                    f"| {_cell(_format_type(param))} | {direction} "
                    f"| {has_default} | {default} |\n"
                )

        content += "\n## Definition\n\n"
        if routine.get("definition"):
            content += f"```sql\n{routine['definition']}\n```\n"
        else:
            content += "*Definition not available*\n"
        return content
