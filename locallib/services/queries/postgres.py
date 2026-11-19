"""PostgreSQL catalog queries used by ``SchemaExtractor``.

Covers every non-system schema of the connected database. Every query has an
``ORDER BY`` so the export is deterministic. Comments map to the description
fields; ``row_count`` is the planner estimate (``pg_class.reltuples``), which is
``NULL`` for a table that has never been analyzed.
"""

_USER_SCHEMA = (
    "n.nspname NOT IN ('pg_catalog', 'information_schema') "
    "AND n.nspname NOT LIKE 'pg_%'"
)

# Routines that belong to an extension (e.g. pgcrypto) are not part of the schema.
_NOT_EXTENSION = (
    "NOT EXISTS (SELECT 1 FROM pg_depend dep "
    "WHERE dep.objid = p.oid AND dep.deptype = 'e')"
)


def _routine_name(alias: str) -> str:
    """Routine name; overloaded routines get their argument list appended so
    each (schema, name) is unique."""
    return f"""CASE WHEN (
        SELECT COUNT(*) FROM pg_proc p2
        WHERE p2.pronamespace = {alias}.pronamespace
            AND p2.proname = {alias}.proname AND p2.prokind = {alias}.prokind
    ) > 1 THEN {alias}.proname
        || '(' || pg_get_function_identity_arguments({alias}.oid) || ')'
    ELSE {alias}.proname END"""


TABLES_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    CASE c.relkind WHEN 'p' THEN 'PARTITIONED_TABLE' ELSE 'USER_TABLE' END
        AS table_type,
    CASE WHEN c.reltuples < 0 THEN NULL ELSE CAST(c.reltuples AS bigint) END
        AS row_count
FROM pg_class c
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p') AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname
"""

# data_type is the full formatted type (e.g. ``character varying(50)``), so the
# separate length/precision/scale fields are NULL.
COLUMNS_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    a.attname AS column_name,
    a.attnum AS ordinal_position,
    pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
    CAST(NULL AS integer) AS max_length,
    CAST(NULL AS integer) AS precision,
    CAST(NULL AS integer) AS scale,
    NOT a.attnotnull AS is_nullable,
    (a.attidentity <> ''
        OR COALESCE(pg_get_expr(ad.adbin, ad.adrelid) LIKE 'nextval(%', FALSE))
        AS is_identity,
    pg_get_expr(ad.adbin, ad.adrelid) AS default_value,
    d.description AS column_description
FROM pg_attribute a
INNER JOIN pg_class c ON c.oid = a.attrelid
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
LEFT JOIN pg_description d ON d.objoid = a.attrelid
    AND d.objsubid = a.attnum
    AND d.classoid = CAST('pg_class' AS regclass)
WHERE a.attnum > 0 AND NOT a.attisdropped
    AND c.relkind IN ('r', 'p') AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname, a.attnum
"""

PK_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    con.conname AS pk_name,
    a.attname AS column_name,
    k.ord AS key_ordinal
FROM pg_constraint con
INNER JOIN pg_class c ON c.oid = con.conrelid
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord)
INNER JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
WHERE con.contype = 'p' AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname, k.ord
"""

FK_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    con.conname AS fk_name,
    a.attname AS column_name,
    fn.nspname AS referenced_schema,
    fc.relname AS referenced_table,
    fa.attname AS referenced_column
FROM pg_constraint con
INNER JOIN pg_class c ON c.oid = con.conrelid
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
INNER JOIN pg_class fc ON fc.oid = con.confrelid
INNER JOIN pg_namespace fn ON fn.oid = fc.relnamespace
CROSS JOIN LATERAL unnest(con.conkey, con.confkey)
    WITH ORDINALITY AS k(attnum, fattnum, ord)
INNER JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
INNER JOIN pg_attribute fa ON fa.attrelid = con.confrelid
    AND fa.attnum = k.fattnum
WHERE con.contype = 'f' AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname, con.conname, k.ord
"""

# Key columns come first (ord <= indnkeyatts); the rest are INCLUDE columns.
# Expression columns (attnum 0) show their expression as the column name.
INDEX_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    ic.relname AS index_name,
    UPPER(am.amname) AS index_type,
    i.indisunique AS is_unique,
    COALESCE(a.attname, pg_get_indexdef(i.indexrelid, CAST(k.ord AS integer), TRUE))
        AS column_name,
    k.ord AS key_ordinal,
    COALESCE(pg_index_column_has_property(i.indexrelid, CAST(k.ord AS integer),
        'desc'), FALSE) AS is_descending_key,
    k.ord > i.indnkeyatts AS is_included_column
FROM pg_index i
INNER JOIN pg_class c ON c.oid = i.indrelid
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
INNER JOIN pg_class ic ON ic.oid = i.indexrelid
INNER JOIN pg_am am ON am.oid = ic.relam
CROSS JOIN LATERAL unnest(CAST(i.indkey AS int2[])) WITH ORDINALITY AS k(attnum, ord)
LEFT JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
    AND k.attnum > 0
WHERE NOT i.indisprimary AND c.relkind IN ('r', 'p') AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname, ic.relname, k.ord
"""

VIEWS_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS view_name,
    'CREATE ' || CASE c.relkind WHEN 'm' THEN 'MATERIALIZED ' ELSE '' END
        || 'VIEW ' || quote_ident(n.nspname) || '.' || quote_ident(c.relname)
        || ' AS ' || pg_get_viewdef(c.oid, TRUE) AS view_definition
FROM pg_class c
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('v', 'm') AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname
"""

PROCEDURES_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    {_routine_name("p")} AS procedure_name,
    CAST(NULL AS timestamp) AS create_date,
    CAST(NULL AS timestamp) AS modify_date,
    pg_get_functiondef(p.oid) AS procedure_definition,
    d.description AS procedure_description
FROM pg_proc p
INNER JOIN pg_namespace n ON n.oid = p.pronamespace
LEFT JOIN pg_description d ON d.objoid = p.oid AND d.objsubid = 0
    AND d.classoid = CAST('pg_proc' AS regclass)
WHERE p.prokind = 'p' AND {_USER_SCHEMA} AND {_NOT_EXTENSION}
ORDER BY n.nspname, 2
"""

# Arguments are unnested from proallargtypes/proargmodes/proargnames; modes
# o/b/t (OUT, INOUT, TABLE) are outputs. Defaults are flagged only for routines
# without OUT parameters; the default expression itself is not extracted.
_PARAMS_SELECT = """
SELECT
    n.nspname AS schema_name,
    {name} AS {prefix}_name,
    CAST(a.ord AS integer) AS parameter_id,
    COALESCE(a.name, '$' || a.ord) AS parameter_name,
    pg_catalog.format_type(a.type_oid, NULL) AS data_type,
    CAST(NULL AS integer) AS max_length,
    CAST(NULL AS integer) AS precision,
    CAST(NULL AS integer) AS scale,
    COALESCE(a.mode IN ('o', 'b', 't'), FALSE) AS is_output,
    (p.pronargdefaults > 0 AND p.proargmodes IS NULL
        AND a.ord > p.pronargs - p.pronargdefaults) AS has_default_value,
    CAST(NULL AS text) AS default_value
FROM pg_proc p
INNER JOIN pg_namespace n ON n.oid = p.pronamespace
CROSS JOIN LATERAL unnest(
    COALESCE(p.proallargtypes, CAST(p.proargtypes AS oid[])),
    p.proargmodes,
    p.proargnames
) WITH ORDINALITY AS a(type_oid, mode, name, ord)
WHERE p.prokind = '{kind}' AND {schema} AND {ext}
ORDER BY n.nspname, 2, a.ord
"""

PROCEDURE_PARAMS_QUERY = _PARAMS_SELECT.format(
    name=_routine_name("p"),
    prefix="procedure",
    kind="p",
    schema=_USER_SCHEMA,
    ext=_NOT_EXTENSION,
)

FUNCTIONS_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    {_routine_name("p")} AS function_name,
    CASE WHEN p.proretset THEN 'TF' ELSE 'FN' END AS function_type_code,
    CASE WHEN p.proretset THEN 'TABLE_FUNCTION' ELSE 'SCALAR_FUNCTION' END
        AS function_type,
    CAST(NULL AS timestamp) AS create_date,
    CAST(NULL AS timestamp) AS modify_date,
    pg_get_functiondef(p.oid) AS function_definition,
    d.description AS function_description
FROM pg_proc p
INNER JOIN pg_namespace n ON n.oid = p.pronamespace
LEFT JOIN pg_description d ON d.objoid = p.oid AND d.objsubid = 0
    AND d.classoid = CAST('pg_proc' AS regclass)
WHERE p.prokind = 'f' AND {_USER_SCHEMA} AND {_NOT_EXTENSION}
ORDER BY n.nspname, 2
"""

FUNCTION_PARAMS_QUERY = _PARAMS_SELECT.format(
    name=_routine_name("p"),
    prefix="function",
    kind="f",
    schema=_USER_SCHEMA,
    ext=_NOT_EXTENSION,
)

# The database comment is the only database-level property.
DB_EXTENDED_PROPERTIES_QUERY = """
SELECT
    'Comment' AS property_name,
    shobj_description(d.oid, 'pg_database') AS property_value
FROM pg_database d
WHERE d.datname = current_database()
    AND shobj_description(d.oid, 'pg_database') IS NOT NULL
ORDER BY 1
"""

# Table comments. Column and routine comments are already in the description
# fields, so those property queries do not apply.
TABLE_EXTENDED_PROPERTIES_QUERY = f"""
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    'Comment' AS property_name,
    d.description AS property_value
FROM pg_class c
INNER JOIN pg_namespace n ON n.oid = c.relnamespace
INNER JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = 0
    AND d.classoid = CAST('pg_class' AS regclass)
WHERE c.relkind IN ('r', 'p') AND {_USER_SCHEMA}
ORDER BY n.nspname, c.relname
"""

PROCEDURE_EXTENDED_PROPERTIES_QUERY: str | None = None
FUNCTION_EXTENDED_PROPERTIES_QUERY: str | None = None
COLUMN_EXTENDED_PROPERTIES_QUERY: str | None = None
VIEW_DEFINITION_PERMISSION_QUERY: str | None = None
VIEW_DEFINITION_GRANT: str | None = None
