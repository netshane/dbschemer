"""Per-dialect catalog query sets for ``SchemaExtractor``.

Each module exposes the same constants (``TABLES_QUERY`` ...) whose result
columns use the same aliases, so the extractor is dialect independent. A query
that does not apply to a dialect is ``None``.
"""

from types import ModuleType

from locallib.services.queries import mysql, postgres, sqlserver

QUERY_SETS: dict[str, ModuleType] = {
    "sqlserver": sqlserver,
    "postgres": postgres,
    "mysql": mysql,
}


def get_queries(db_type: str) -> ModuleType:
    """The query module for ``db_type`` (``sqlserver``, ``postgres``, ``mysql``)."""
    try:
        return QUERY_SETS[db_type]
    except KeyError:
        raise ValueError(f"Unsupported database type '{db_type}'") from None
