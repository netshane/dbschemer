"""Engine construction. Pure functions: nothing here reads settings."""

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url

from locallib.dbschemer_config import DbschemerDatabase

MSSQL_PYTHON_PREFIX = "mssql+mssql-python://"
POSTGRES_DRIVER = "postgresql+psycopg"
MYSQL_DRIVER = "mysql+pymysql"


def _odbc_value(value: str) -> str:
    """Quote ``value`` only if it contains characters that need it."""
    if any(c in value for c in ";{}=") or value != value.strip():
        return quote_odbc_value(value)
    return value


def build_connection(db: DbschemerDatabase) -> str:
    """The connection string for a configured database; never includes a password.

    Uses ``connection_string`` when set, otherwise builds it from ``type``,
    ``server``, ``database``, ``user`` and ``port``. sqlserver gets an ODBC
    string (``Trusted_Connection=yes`` without a ``user``); postgres and mysql
    get a SQLAlchemy URL, so special characters are escaped.
    """
    if db.connection_string is not None:
        return db.connection_string
    if db.type is None or db.server is None or db.database is None:
        raise ValueError("Database config has no connection_string or type/server")
    if db.type == "sqlserver":
        server = db.server if db.port is None else f"{db.server},{db.port}"
        parts = [
            f"Server={_odbc_value(server)}",
            f"Database={_odbc_value(db.database)}",
        ]
        if db.user:
            parts.append(f"UID={_odbc_value(db.user)}")
        else:
            parts.append("Trusted_Connection=yes")
        parts += ["TrustServerCertificate=yes", "Encrypt=yes"]
        return MSSQL_PYTHON_PREFIX + ";".join(parts) + ";"
    driver = POSTGRES_DRIVER if db.type == "postgres" else MYSQL_DRIVER
    url = URL.create(
        driver,
        username=db.user,
        host=db.server,
        port=db.port,
        database=db.database,
    )
    return url.render_as_string(hide_password=False)


def dialect_for(conn_str: str) -> str:
    """``sqlserver``, ``postgres`` or ``mysql`` for a connection string.

    Anything that is not clearly postgres or mysql is treated as sqlserver.
    """
    if conn_str.startswith(MSSQL_PYTHON_PREFIX):
        return "sqlserver"
    backend = make_url(conn_str).get_backend_name()
    if backend in ("postgresql", "postgres"):
        return "postgres"
    if backend in ("mysql", "mariadb"):
        return "mysql"
    return "sqlserver"


def quote_odbc_value(value: str) -> str:
    """Quote a value for an ODBC-style ``key=value;`` connection string.

    Wrapping in braces (and doubling any closing brace) lets the value contain
    ``;``, ``{``, ``}`` or ``=`` safely.
    """
    return "{" + value.replace("}", "}}") + "}"


def parse_odbc_keys(conn_str: str) -> dict[str, str]:
    """Return ``{lowercased key: value}`` for an ODBC connection string.

    Handles brace-quoted values (``{...}`` with ``}}`` as an escaped brace), so a
    ``;`` inside a quoted value does not split the entry.
    """
    result: dict[str, str] = {}
    i, n = 0, len(conn_str)
    while i < n:
        eq = conn_str.find("=", i)
        if eq == -1:
            break
        key = conn_str[i:eq].strip().lower()
        i = eq + 1
        if i < n and conn_str[i] == "{":
            i += 1
            chars: list[str] = []
            while i < n:
                if conn_str[i] == "}":
                    if i + 1 < n and conn_str[i + 1] == "}":
                        chars.append("}")
                        i += 2
                        continue
                    i += 1
                    break
                chars.append(conn_str[i])
                i += 1
            value = "".join(chars)
            semi = conn_str.find(";", i)
            i = n if semi == -1 else semi + 1
        else:
            semi = conn_str.find(";", i)
            end = n if semi == -1 else semi
            value = conn_str[i:end].strip()
            i = end + 1
        if key:
            result[key] = value
    return result


def add_odbc_password(conn_str: str, password: str) -> str:
    """Append ``PWD=`` to an ODBC connection string.

    Raises ``ValueError`` if the string already has a password or uses
    integrated (Windows) authentication, rather than producing a conflicting
    credential whose handling depends on the driver.
    """
    keys = parse_odbc_keys(conn_str)
    if "pwd" in keys or "password" in keys:
        raise ValueError(
            "Connection string already contains a password; remove PWD/Password "
            "from it or remove the separate password setting"
        )
    if keys.get("trusted_connection", "").lower() in ("yes", "true"):
        raise ValueError(
            "Connection string uses Trusted_Connection; a separate password "
            "cannot be combined with integrated authentication"
        )
    conn_str = conn_str.rstrip()
    if conn_str and not conn_str.endswith(";"):
        conn_str += ";"
    return f"{conn_str}PWD={quote_odbc_value(password)};"


def create_db_engine(
    conn_str: str,
    isolation_level: str = "AUTOCOMMIT",
    password: str | None = None,
    connect_timeout: int | None = None,
) -> Engine:
    """Create an engine for ``conn_str``.

    ``mssql+mssql-python://<odbc connection string>`` connects with the
    mssql-python driver. SQLAlchemy 2.0.44 has no native mssql-python dialect, so
    the engine is created as ``mssql://`` (which uses the pyodbc dialect for SQL
    generation, so ``pyodbc`` must stay installed) and connections come from
    ``mssql_python.connect`` via ``creator``.

    Any other value is treated as a normal SQLAlchemy URL.

    ``password`` is injected separately rather than formatted into the string,
    so it may contain any character.

    ``connect_timeout`` (seconds) is the login timeout. It is supported for
    mssql-python (``SQL_ATTR_LOGIN_TIMEOUT``), ``+pyodbc``, ``+psycopg`` and
    ``+pymysql`` URLs; any other driver raises ``ValueError``.
    """
    if conn_str.startswith(MSSQL_PYTHON_PREFIX):
        odbc_str = conn_str[len(MSSQL_PYTHON_PREFIX) :]
        if password is not None:
            odbc_str = add_odbc_password(odbc_str, password)

        def mssql_creator() -> Any:
            import mssql_python

            if connect_timeout is None:
                return mssql_python.connect(odbc_str)
            # timeout= is the query timeout; the login timeout is an attribute.
            return mssql_python.connect(
                odbc_str,
                attrs_before={mssql_python.SQL_ATTR_LOGIN_TIMEOUT: connect_timeout},
            )

        return create_engine(
            "mssql://",
            creator=mssql_creator,
            isolation_level=isolation_level,
        )

    url = make_url(conn_str)
    if password is not None:
        url = url.set(password=password)
    kwargs: dict[str, Any] = {}
    if connect_timeout is not None:
        # DBAPI keyword for the login timeout, by driver
        timeout_args = {
            "+pyodbc": "timeout",
            "+psycopg": "connect_timeout",
            "+pymysql": "connect_timeout",
        }
        for suffix, arg in timeout_args.items():
            if url.drivername.endswith(suffix):
                kwargs["connect_args"] = {arg: connect_timeout}
                break
        else:
            raise ValueError(
                f"connect_timeout is not supported for driver '{url.drivername}'"
            )
    return create_engine(url, isolation_level=isolation_level, **kwargs)


def describe_server(conn_str: str) -> str:
    """The server name in ``conn_str`` (ODBC ``Server=`` or URL host), or ``""``.

    Never returns credentials or the full connection string.
    """
    if conn_str.startswith(MSSQL_PYTHON_PREFIX):
        return parse_odbc_keys(conn_str[len(MSSQL_PYTHON_PREFIX) :]).get("server", "")
    return make_url(conn_str).host or ""


def describe_database(conn_str: str) -> str:
    """The database name in ``conn_str`` (ODBC ``Database=`` or URL database),
    or ``""``."""
    if conn_str.startswith(MSSQL_PYTHON_PREFIX):
        return parse_odbc_keys(conn_str[len(MSSQL_PYTHON_PREFIX) :]).get("database", "")
    return make_url(conn_str).database or ""
