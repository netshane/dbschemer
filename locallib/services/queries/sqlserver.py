"""SQL Server catalog queries used by ``SchemaExtractor``.

Every query has an ``ORDER BY`` so the export is deterministic.
"""

# Query to get all tables and their schemas. Row counts are summed over
# partitions, so a partitioned table still gives one row.
TABLES_QUERY = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    t.type_desc AS table_type,
    p.row_count
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
LEFT JOIN (
    SELECT object_id, SUM(rows) AS row_count
    FROM sys.partitions
    WHERE index_id IN (0, 1)
    GROUP BY object_id
) p ON t.object_id = p.object_id
ORDER BY s.name, t.name
"""

# Query to get all columns with their details
COLUMNS_QUERY = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS column_name,
    c.column_id AS ordinal_position,
    ty.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity,
    OBJECT_DEFINITION(c.default_object_id) AS default_value,
    CAST(ep.value AS NVARCHAR(MAX)) AS column_description
FROM sys.columns c
INNER JOIN sys.tables t ON c.object_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.extended_properties ep ON ep.class = 1
    AND ep.major_id = c.object_id
    AND ep.minor_id = c.column_id
    AND ep.name = 'MS_Description'
ORDER BY s.name, t.name, c.column_id
"""

# Query to get primary keys
PK_QUERY = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS pk_name,
    c.name AS column_name,
    ic.key_ordinal
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id
    AND i.index_id = ic.index_id
INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
INNER JOIN sys.tables t ON i.object_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE i.is_primary_key = 1
ORDER BY s.name, t.name, ic.key_ordinal
"""

# Query to get foreign keys
FK_QUERY = """
SELECT
    s1.name AS schema_name,
    t1.name AS table_name,
    fk.name AS fk_name,
    c1.name AS column_name,
    s2.name AS referenced_schema,
    t2.name AS referenced_table,
    c2.name AS referenced_column
FROM sys.foreign_keys fk
INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
INNER JOIN sys.tables t1 ON fkc.parent_object_id = t1.object_id
INNER JOIN sys.schemas s1 ON t1.schema_id = s1.schema_id
INNER JOIN sys.columns c1 ON fkc.parent_object_id = c1.object_id
    AND fkc.parent_column_id = c1.column_id
INNER JOIN sys.tables t2 ON fkc.referenced_object_id = t2.object_id
INNER JOIN sys.schemas s2 ON t2.schema_id = s2.schema_id
INNER JOIN sys.columns c2 ON fkc.referenced_object_id = c2.object_id
    AND fkc.referenced_column_id = c2.column_id
ORDER BY s1.name, t1.name, fk.name, fkc.constraint_column_id
"""

# Query to get indexes
INDEX_QUERY = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.type_desc AS index_type,
    i.is_unique,
    c.name AS column_name,
    ic.key_ordinal,
    ic.is_descending_key,
    ic.is_included_column
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id
    AND i.index_id = ic.index_id
INNER JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
INNER JOIN sys.tables t ON i.object_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE i.is_primary_key = 0 AND i.name IS NOT NULL
ORDER BY s.name, t.name, i.name, ic.key_ordinal, ic.index_column_id
"""

# Query to get views
VIEWS_QUERY = """
SELECT
    s.name AS schema_name,
    v.name AS view_name,
    m.definition AS view_definition
FROM sys.views v
INNER JOIN sys.schemas s ON v.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON v.object_id = m.object_id
ORDER BY s.name, v.name
"""

# Query to get stored procedures
PROCEDURES_QUERY = """
SELECT
    s.name AS schema_name,
    p.name AS procedure_name,
    p.create_date,
    p.modify_date,
    m.definition AS procedure_definition,
    CAST(ep.value AS NVARCHAR(MAX)) AS procedure_description
FROM sys.procedures p
INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON p.object_id = m.object_id
LEFT JOIN sys.extended_properties ep ON ep.class = 1
    AND ep.major_id = p.object_id
    AND ep.minor_id = 0
    AND ep.name = 'MS_Description'
ORDER BY s.name, p.name
"""

# Query to get stored procedure parameters
PROCEDURE_PARAMS_QUERY = """
SELECT
    s.name AS schema_name,
    p.name AS procedure_name,
    par.name AS parameter_name,
    par.parameter_id,
    ty.name AS data_type,
    par.max_length,
    par.precision,
    par.scale,
    par.is_output,
    par.has_default_value,
    CAST(par.default_value AS NVARCHAR(MAX)) AS default_value
FROM sys.parameters par
INNER JOIN sys.procedures p ON par.object_id = p.object_id
INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
INNER JOIN sys.types ty ON par.user_type_id = ty.user_type_id
ORDER BY s.name, p.name, par.parameter_id
"""

# Query to get functions
FUNCTIONS_QUERY = """
SELECT
    s.name AS schema_name,
    o.name AS function_name,
    o.type AS function_type_code,
    o.type_desc AS function_type,
    o.create_date,
    o.modify_date,
    m.definition AS function_definition,
    CAST(ep.value AS NVARCHAR(MAX)) AS function_description
FROM sys.objects o
INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
LEFT JOIN sys.sql_modules m ON o.object_id = m.object_id
LEFT JOIN sys.extended_properties ep ON ep.class = 1
    AND ep.major_id = o.object_id
    AND ep.minor_id = 0
    AND ep.name = 'MS_Description'
WHERE o.type IN ('FN', 'IF', 'TF')
ORDER BY s.name, o.name
"""

# Query to get database-level extended properties
DB_EXTENDED_PROPERTIES_QUERY = """
SELECT
    ep.name AS property_name,
    CAST(ep.value AS NVARCHAR(MAX)) AS property_value
FROM sys.extended_properties ep
WHERE ep.class = 0
    AND ep.name NOT LIKE 'MS_Diagram%'
ORDER BY ep.name
"""

# Query to get all extended properties for tables (object-level, not column-level)
TABLE_EXTENDED_PROPERTIES_QUERY = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    ep.name AS property_name,
    CAST(ep.value AS NVARCHAR(MAX)) AS property_value
FROM sys.extended_properties ep
INNER JOIN sys.tables t ON ep.major_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE ep.minor_id = 0
    AND ep.class = 1
    AND ep.name NOT LIKE 'MS_Diagram%'
ORDER BY s.name, t.name, ep.name
"""

# Query to get all extended properties for stored procedures
PROCEDURE_EXTENDED_PROPERTIES_QUERY = """
SELECT
    s.name AS schema_name,
    p.name AS procedure_name,
    ep.name AS property_name,
    CAST(ep.value AS NVARCHAR(MAX)) AS property_value
FROM sys.extended_properties ep
INNER JOIN sys.procedures p ON ep.major_id = p.object_id
INNER JOIN sys.schemas s ON p.schema_id = s.schema_id
WHERE ep.class = 1
    AND ep.minor_id = 0
    AND ep.name NOT LIKE 'MS_Diagram%'
ORDER BY s.name, p.name, ep.name
"""

# Query to get all extended properties for functions
FUNCTION_EXTENDED_PROPERTIES_QUERY = """
SELECT
    s.name AS schema_name,
    o.name AS function_name,
    ep.name AS property_name,
    CAST(ep.value AS NVARCHAR(MAX)) AS property_value
FROM sys.extended_properties ep
INNER JOIN sys.objects o ON ep.major_id = o.object_id
INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
WHERE o.type IN ('FN', 'IF', 'TF')
    AND ep.class = 1
    AND ep.minor_id = 0
    AND ep.name NOT LIKE 'MS_Diagram%'
ORDER BY s.name, o.name, ep.name
"""

# Query to get all extended properties for columns (all properties, not just
# MS_Description)
COLUMN_EXTENDED_PROPERTIES_QUERY = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS column_name,
    ep.name AS property_name,
    CAST(ep.value AS NVARCHAR(MAX)) AS property_value
FROM sys.extended_properties ep
INNER JOIN sys.tables t ON ep.major_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN sys.columns c ON ep.major_id = c.object_id AND ep.minor_id = c.column_id
WHERE ep.class = 1
    AND ep.minor_id > 0
    AND ep.name NOT LIKE 'MS_Diagram%'
ORDER BY s.name, t.name, c.name, ep.name
"""

# Query to get function parameters
FUNCTION_PARAMS_QUERY = """
SELECT
    s.name AS schema_name,
    o.name AS function_name,
    par.name AS parameter_name,
    par.parameter_id,
    ty.name AS data_type,
    par.max_length,
    par.precision,
    par.scale,
    par.is_output,
    par.has_default_value,
    CAST(par.default_value AS NVARCHAR(MAX)) AS default_value
FROM sys.parameters par
INNER JOIN sys.objects o ON par.object_id = o.object_id
INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
INNER JOIN sys.types ty ON par.user_type_id = ty.user_type_id
WHERE o.type IN ('FN', 'IF', 'TF')
    AND par.parameter_id > 0  -- 0 is a scalar function's return value
ORDER BY s.name, o.name, par.parameter_id
"""

# Whether the current user may read module definitions. Without VIEW DEFINITION,
# sys.sql_modules.definition is NULL for views, procedures and functions.
VIEW_DEFINITION_PERMISSION_QUERY = """
SELECT
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'VIEW DEFINITION') AS has_permission,
    USER_NAME() AS user_name,
    DB_NAME() AS database_name
"""

# The statement that fixes a missing VIEW DEFINITION permission. ``{database}``
# and ``{user}`` must already be quoted identifiers.
VIEW_DEFINITION_GRANT = "USE {database}; GRANT VIEW DEFINITION TO {user};"
