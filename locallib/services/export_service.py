from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from locallib.services.docs_generator import DocsGenerator
from locallib.services.schema_extractor import SchemaExtractor


@dataclass(frozen=True)
class ExportResult:
    output_dir: Path
    tables: int
    views: int
    procedures: int
    functions: int


class ExportService:
    """Extracts a database schema and writes ``schema.json`` plus markdown docs."""

    def __init__(
        self, extractor: SchemaExtractor, generator: DocsGenerator, output_dir: Path
    ):
        self.extractor = extractor
        self.generator = generator
        self.output_dir = output_dir

    def run(self, database: str) -> ExportResult:
        logger.info(f"Extracting schema for '{database}'...")
        # Extract first: a connection or query failure leaves the old docs intact.
        schema = self.extractor.extract(database)
        self.generator.clean(self.output_dir)
        self.generator.write_json(schema, self.output_dir)
        self.generator.generate(schema, self.output_dir)
        logger.info(f"Wrote docs to {self.output_dir}")
        return ExportResult(
            output_dir=self.output_dir,
            tables=len(schema["tables"]),
            views=len(schema["views"]),
            procedures=len(schema["stored_procedures"]),
            functions=len(schema["functions"]),
        )
