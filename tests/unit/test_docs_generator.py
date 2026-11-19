import re
from pathlib import Path

import pytest

from locallib.services.docs_generator import DocsGenerator, _format_type
from locallib.services.schema_extractor import SchemaExtractor
from tests.fakes import FakeEngine, sample_rows

LINK = re.compile(r"\]\(([^)]+\.md)\)")


def schema(include_row_count=False):
    extractor = SchemaExtractor(FakeEngine(sample_rows()), "sql01", include_row_count)
    return extractor.extract("Sales")


def export(out: Path, include_row_count=False, data=None) -> list[Path]:
    gen = DocsGenerator(include_row_count)
    data = data if data is not None else schema(include_row_count)
    gen.clean(out)
    return [gen.write_json(data, out), *gen.generate(data, out)]


def snapshot(out: Path) -> dict[str, bytes]:
    return {
        p.relative_to(out).as_posix(): p.read_bytes()
        for p in sorted(out.rglob("*"))
        if p.is_file()
    }


@pytest.mark.unit
def test_expected_files(tmp_path):
    out = tmp_path / "a" / "b"  # parents are created
    written = export(out)
    assert sorted(snapshot(out)) == [
        "README.md",
        "functions.md",
        "functions/dbo.fnTotal.md",
        "procedures/dbo.GetCustomer.md",
        "schema.json",
        "schemas/dbo.md",
        "schemas/my.schema.md",
        "stored_procedures.md",
        "tables/dbo.Customer.md",
        "tables/dbo.Order.md",
        "tables/my.schema.odd.table.md",
        "views.md",
    ]
    assert len(written) == len(set(written)) == 12


@pytest.mark.unit
def test_no_procedure_or_function_files_when_none(tmp_path):
    data = schema()
    data["stored_procedures"] = []
    data["functions"] = []
    export(tmp_path, data=data)
    files = snapshot(tmp_path)
    assert "stored_procedures.md" not in files
    assert "functions.md" not in files
    assert not any(f.startswith(("procedures/", "functions/")) for f in files)


@pytest.mark.unit
def test_all_relative_links_resolve(tmp_path):
    export(tmp_path)
    links = 0
    for md in tmp_path.rglob("*.md"):
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            links += 1
            assert (md.parent / target).is_file(), f"{md}: {target}"
    assert links > 0
    schema_file = (tmp_path / "schemas" / "dbo.md").read_text()
    assert "](../tables/dbo.Customer.md)" in schema_file


@pytest.mark.unit
def test_pipes_and_newlines_stay_in_one_cell(tmp_path):
    export(tmp_path)
    text = (tmp_path / "tables" / "dbo.Customer.md").read_text()
    name_row = next(line for line in text.splitlines() if "| Name |" in line)
    assert "Full \\| name of customer" in name_row
    assert name_row.count(" | ") == 5  # 6 cells
    notes_row = next(line for line in text.splitlines() if "| Notes |" in line)
    assert "`('a\\|b')`" in notes_row
    assert "| PII | yes\\|really |" in text


@pytest.mark.unit
def test_row_count_off(tmp_path):
    export(tmp_path)
    for md in tmp_path.rglob("*.md"):
        assert "Rows" not in md.read_text(), md
    assert '"row_count"' not in (tmp_path / "schema.json").read_text()


@pytest.mark.unit
def test_row_count_on(tmp_path):
    export(tmp_path, include_row_count=True)
    assert (
        "| [dbo](schemas/dbo.md) | 2 | 1,520 |" in (tmp_path / "README.md").read_text()
    )
    schema_file = (tmp_path / "schemas" / "dbo.md").read_text()
    assert "| Rows |" in schema_file
    assert "| 1,500 |" in schema_file
    assert "**Rows:** 1,500" in (tmp_path / "tables" / "dbo.Customer.md").read_text()
    assert '"row_count": 1500' in (tmp_path / "schema.json").read_text()


@pytest.mark.unit
def test_output_is_deterministic(tmp_path):
    export(tmp_path)
    first = snapshot(tmp_path)
    export(tmp_path)
    assert snapshot(tmp_path) == first
    assert first["schema.json"].endswith(b"}\n")
    assert all(b"\r\n" not in content for content in first.values())


@pytest.mark.unit
def test_clean_keeps_unrelated_files(tmp_path):
    export(tmp_path)
    (tmp_path / "notes.md").write_text("mine")
    (tmp_path / "extra").mkdir()
    (tmp_path / "extra" / "keep.txt").write_text("keep")
    DocsGenerator(False).clean(tmp_path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == [
        "extra",
        "extra/keep.txt",
        "notes.md",
    ]


@pytest.mark.unit
def test_clean_does_not_follow_symlinked_dir(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    (target / "keep.md").write_text("keep")
    out = tmp_path / "out"
    out.mkdir()
    (out / "tables").symlink_to(target, target_is_directory=True)
    DocsGenerator(False).clean(out)
    assert not (out / "tables").exists()
    assert (target / "keep.md").is_file()


@pytest.mark.unit
def test_stale_table_file_removed(tmp_path):
    export(tmp_path)
    (tmp_path / "tables" / "x.y.md").write_text("stale")
    export(tmp_path)
    assert not (tmp_path / "tables" / "x.y.md").exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ({"data_type": "nvarchar", "max_length": 200}, "nvarchar(100)"),
        ({"data_type": "nvarchar", "max_length": -1}, "nvarchar(MAX)"),
        ({"data_type": "varbinary", "max_length": 16}, "varbinary(16)"),
        ({"data_type": "decimal", "precision": 18, "scale": 2}, "decimal(18,2)"),
        ({"data_type": "datetime2", "scale": 7}, "datetime2(7)"),
        ({"data_type": "int", "max_length": 4}, "int"),
    ],
)
def test_format_type(item, expected):
    assert _format_type(item) == expected


@pytest.mark.unit
def test_unsafe_names_stay_in_output_and_links_are_encoded(tmp_path):
    from urllib.parse import unquote

    data = schema()
    data["tables"][0]["name"] = "../../evil/x"
    data["stored_procedures"][0]["name"] = "Order Details (old)"
    out = tmp_path / "out"
    written = export(out, data=data)
    for path in written:
        assert path.resolve().is_relative_to(out.resolve())
    assert (out / "tables" / "dbo..._.._evil_x.md").is_file()
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "(procedures/dbo.Order%20Details%20%28old%29.md)" in readme
    for md in out.rglob("*.md"):
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            assert (md.parent / unquote(target)).is_file(), (md, target)


@pytest.mark.unit
def test_catalog_queries_filter_object_class_and_return_value():
    from locallib.services.queries import sqlserver as q

    for sql in (q.COLUMNS_QUERY, q.PROCEDURES_QUERY, q.FUNCTIONS_QUERY):
        assert "ep.class = 1" in sql
    assert "par.parameter_id > 0" in q.FUNCTION_PARAMS_QUERY
