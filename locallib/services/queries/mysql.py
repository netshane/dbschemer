"""MySQL catalog queries used by ``SchemaExtractor``.

Covers the connected database only (``DATABASE()``); MySQL's "schema" is the
database, so ``schema_name`` is the database name. Every query has an
``ORDER BY`` so the export is deterministic. Comments map to the description
fields; ``row_count`` is ``TABLES.TABLE_ROWS`` (an estimate for InnoDB).
"""

TABLES_QUERY = """
SELECT
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS table_name,
    'USER_TABLE' AS table_type,
    TABLE_ROWS AS row_count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_SCHEMA, TABLE_NAME
"""

# data_type is COLUMN_TYPE (e.g. ``varchar(50)``, ``decimal(10,2)``), so the
# separate length/precision/scale fields are informational only.
COLUMNS_QUERY = """
SELECT
    c.TABLE_SCHEMA AS schema_name,
    c.TABLE_NAME AS table_name,
    c.COLUMN_NAME AS column_name,
    c.ORDINAL_POSITION AS ordinal_position,
    c.COLUMN_TYPE AS data_type,
    c.CHARACTER_MAXIMUM_LENGTH AS max_length,
    c.NUMERIC_PRECISION AS `precision`,
    c.NUMERIC_SCALE AS scale,
    CASE WHEN c.IS_NULLABLE = 'YES' THEN 1 ELSE 0 END AS is_nullable,
    CASE WHEN LOCATE('auto_increment', c.EXTRA) > 0 THEN 1 ELSE 0 END
        AS is_identity,
    c.COLUMN_DEFAULT AS default_value,
    NULLIF(c.COLUMN_COMMENT, '') AS column_description
FROM information_schema.COLUMNS c
INNER JOIN information_schema.TABLES t
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
WHERE c.TABLE_SCHEMA = DATABASE() AND t.TABLE_TYPE = 'BASE TABLE'
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION
"""

PK_QUERY = """
SELECT
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS table_name,
    CONSTRAINT_NAME AS pk_name,
    COLUMN_NAME AS column_name,
    ORDINAL_POSITION AS key_ordinal
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE() AND CONSTRAINT_NAME = 'PRIMARY'
ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
"""

FK_QUERY = """
SELECT
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS table_name,
    CONSTRAINT_NAME AS fk_name,
    COLUMN_NAME AS column_name,
    REFERENCED_TABLE_SCHEMA AS referenced_schema,
    REFERENCED_TABLE_NAME AS referenced_table,
    REFERENCED_COLUMN_NAME AS referenced_column
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
"""

# MySQL has no INCLUDE columns.
INDEX_QUERY = """
SELECT
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS table_name,
    INDEX_NAME AS index_name,
    INDEX_TYPE AS index_type,
    CASE WHEN NON_UNIQUE = 0 THEN 1 ELSE 0 END AS is_unique,
    COLUMN_NAME AS column_name,
    SEQ_IN_INDEX AS key_ordinal,
    CASE WHEN COLLATION = 'D' THEN 1 ELSE 0 END AS is_descending_key,
    0 AS is_included_column
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME <> 'PRIMARY'
ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
"""

VIEWS_QUERY = """
SELECT
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS view_name,
    VIEW_DEFINITION AS view_definition
FROM information_schema.VIEWS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_SCHEMA, TABLE_NAME
"""

PROCEDURES_QUERY = """
SELECT
    ROUTINE_SCHEMA AS schema_name,
    ROUTINE_NAME AS procedure_name,
    CREATED AS create_date,
    LAST_ALTERED AS modify_date,
    ROUTINE_DEFINITION AS procedure_definition,
    NULLIF(ROUTINE_COMMENT, '') AS procedure_description
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE'
ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
"""

# ORDINAL_POSITION 0 is a function's return value, not a parameter.
PROCEDURE_PARAMS_QUERY = """
SELECT
    p.SPECIFIC_SCHEMA AS schema_name,
    p.SPECIFIC_NAME AS procedure_name,
    p.PARAMETER_NAME AS parameter_name,
    p.ORDINAL_POSITION AS parameter_id,
    p.DTD_IDENTIFIER AS data_type,
    p.CHARACTER_MAXIMUM_LENGTH AS max_length,
    p.NUMERIC_PRECISION AS `precision`,
    p.NUMERIC_SCALE AS scale,
    CASE WHEN p.PARAMETER_MODE IN ('OUT', 'INOUT') THEN 1 ELSE 0 END AS is_output,
    0 AS has_default_value,
    NULL AS default_value
FROM information_schema.PARAMETERS p
WHERE p.SPECIFIC_SCHEMA = DATABASE() AND p.ROUTINE_TYPE = 'PROCEDURE'
    AND p.ORDINAL_POSITION > 0
ORDER BY p.SPECIFIC_SCHEMA, p.SPECIFIC_NAME, p.ORDINAL_POSITION
"""

FUNCTIONS_QUERY = """
SELECT
    ROUTINE_SCHEMA AS schema_name,
    ROUTINE_NAME AS function_name,
    'FN' AS function_type_code,
    'SCALAR_FUNCTION' AS function_type,
    CREATED AS create_date,
    LAST_ALTERED AS modify_date,
    ROUTINE_DEFINITION AS function_definition,
    NULLIF(ROUTINE_COMMENT, '') AS function_description
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'FUNCTION'
ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
"""

FUNCTION_PARAMS_QUERY = PROCEDURE_PARAMS_QUERY.replace(
    "p.ROUTINE_TYPE = 'PROCEDURE'", "p.ROUTINE_TYPE = 'FUNCTION'"
).replace("AS procedure_name", "AS function_name")

# Table comments. Column and routine comments are already in the description
# fields, and MySQL has no database-level properties.
TABLE_EXTENDED_PROPERTIES_QUERY = """
SELECT
    TABLE_SCHEMA AS schema_name,
    TABLE_NAME AS table_name,
    'Comment' AS property_name,
    TABLE_COMMENT AS property_value
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
    AND TABLE_COMMENT <> ''
ORDER BY TABLE_SCHEMA, TABLE_NAME
"""

DB_EXTENDED_PROPERTIES_QUERY: str | None = None
PROCEDURE_EXTENDED_PROPERTIES_QUERY: str | None = None
FUNCTION_EXTENDED_PROPERTIES_QUERY: str | None = None
COLUMN_EXTENDED_PROPERTIES_QUERY: str | None = None
VIEW_DEFINITION_PERMISSION_QUERY: str | None = None
VIEW_DEFINITION_GRANT: str | None = None
