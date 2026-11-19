import pytest

from locallib.services.docs_generator import DocsGenerator
from locallib.services.export_service import ExportResult, ExportService
from locallib.services.schema_extractor import SchemaExtractor
from tests.fakes import FakeEngine, sample_rows


class RecordingGenerator(DocsGenerator):
    def __init__(self, calls):
        super().__init__(include_row_count=False)
        self.calls = calls

    def clean(self, output_dir):
        self.calls.append("clean")
        super().clean(output_dir)

    def write_json(self, schema, output_dir):
        self.calls.append("write_json")
        return super().write_json(schema, output_dir)

    def generate(self, schema, output_dir):
        self.calls.append("generate")
        return super().generate(schema, output_dir)


class RecordingExtractor(SchemaExtractor):
    def __init__(self, calls, engine):
        super().__init__(engine, "sql01", include_row_count=False)
        self.calls = calls

    def extract(self, database):
        self.calls.append(f"extract:{database}")
        return super().extract(database)


@pytest.mark.unit
def test_run_order_and_result(tmp_path):
    calls: list[str] = []
    service = ExportService(
        RecordingExtractor(calls, FakeEngine(sample_rows())),
        RecordingGenerator(calls),
        tmp_path,
    )
    result = service.run("Sales")
    assert calls == ["extract:Sales", "clean", "write_json", "generate"]
    assert result == ExportResult(
        tmp_path, tables=3, views=1, procedures=1, functions=1
    )
    assert (tmp_path / "schema.json").is_file()


@pytest.mark.unit
def test_extract_failure_leaves_output_untouched(tmp_path):
    (tmp_path / "README.md").write_text("old")
    calls: list[str] = []
    service = ExportService(
        RecordingExtractor(calls, FakeEngine({}, error=RuntimeError("db down"))),
        RecordingGenerator(calls),
        tmp_path,
    )
    with pytest.raises(RuntimeError, match="db down"):
        service.run("Sales")
    assert calls == ["extract:Sales"]
    assert (tmp_path / "README.md").read_text() == "old"
