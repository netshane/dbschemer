"""Real export against SQL Server, PostgreSQL or MySQL (the dialect is taken from
the connection string). Skipped unless DBSCHEMER_IT_CONNECTION_STRING
is set (optionally DBSCHEMER_IT_PASSWORD). Run with ``-m integration``."""

import os

import pytest

from locallib.db import (
    create_db_engine,
    describe_database,
    describe_server,
    dialect_for,
)
from locallib.services.docs_generator import DocsGenerator
from locallib.services.export_service import ExportService
from locallib.services.queries import get_queries
from locallib.services.schema_extractor import SchemaExtractor

CONN = os.environ.get("DBSCHEMER_IT_CONNECTION_STRING")


@pytest.mark.integration
@pytest.mark.skipif(not CONN, reason="DBSCHEMER_IT_CONNECTION_STRING not set")
def test_real_export(tmp_path):
    assert CONN
    engine = create_db_engine(
        CONN, password=os.environ.get("DBSCHEMER_IT_PASSWORD") or None
    )
    try:
        service = ExportService(
            SchemaExtractor(
                engine,
                describe_server(CONN),
                include_row_count=False,
                queries=get_queries(dialect_for(CONN)),
            ),
            DocsGenerator(include_row_count=False),
            tmp_path,
        )
        service.run(describe_database(CONN) or "integration")
        first = (tmp_path / "schema.json").read_bytes()
        service.run(describe_database(CONN) or "integration")
        assert (tmp_path / "schema.json").read_bytes() == first
        assert (tmp_path / "README.md").is_file()
    finally:
        engine.dispose()
