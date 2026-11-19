"""Turn database driver errors into short, user-facing messages.

Messages name the config entry and the server only; they never include the
connection string, user name or password.
"""

import re
from dataclasses import dataclass

import mssql_python
from sqlalchemy.exc import DBAPIError

# mssql_python raises a bare RuntimeError from its C++ binding (ddbc_bindings)
# when a connection fails at the TCP/ODBC layer; these prefixes identify it.
ODBC_PREFIXES = ("[Microsoft]", "[unixODBC]")


def is_db_error(exc: BaseException) -> bool:
    """True for database driver errors (not for other ``RuntimeError``s)."""
    if isinstance(exc, (DBAPIError, mssql_python.Error)):
        return True
    return isinstance(exc, RuntimeError) and str(exc).lstrip().startswith(ODBC_PREFIXES)


@dataclass(frozen=True)
class DbErrorRule:
    pattern: re.Pattern[str]
    summary: str
    hint: str


def _rule(pattern: str, summary: str, hint: str) -> DbErrorRule:
    return DbErrorRule(re.compile(pattern, re.IGNORECASE), summary, hint)


DEFAULT_RULES: tuple[DbErrorRule, ...] = (
    _rule(
        r"0x2AF9|0x2AFC",
        "the server name could not be resolved (DNS lookup failed)",
        "Check Server= in the connection string and your network/VPN.",
    ),
    _rule(
        r"0x274C|Login timeout expired|\bHYT00\b",
        "the server did not respond (timeout)",
        "Check the host, port, firewall and VPN. The connect_timeout setting "
        "controls how long to wait.",
    ),
    _rule(
        r"0x274D",
        "the connection was refused",
        "SQL Server is not listening on that host/port.",
    ),
    _rule(
        r"0x2751",
        "the host is unreachable (no network route)",
        "Check your network/VPN.",
    ),
    _rule(
        r"0x2746",
        "the connection was reset by the server",
        "This is often caused by TLS/encryption settings; check Encrypt and "
        "TrustServerCertificate.",
    ),
    # Before "login failed": SQL Server's 4060 text ends "The login failed."
    # and is usually followed by an 18456 record.
    _rule(
        r"\b4060\b|Cannot open database",
        "cannot open the database",
        "Check Database= in the connection string and that the user has access.",
    ),
    _rule(
        r"\b18456\b|\b28000\b|Login failed",
        "login failed",
        "Check UID and the password environment variable.",
    ),
    _rule(
        r"SSL Provider|certificate",
        "TLS/certificate failure",
        "Check Encrypt and TrustServerCertificate in the connection string.",
    ),
    _rule(
        r"Data source name not found|Can't open lib|\bIM002\b",
        "the ODBC driver is missing",
        "Install ODBC Driver 18 for SQL Server.",
    ),
)


class DbErrorTranslator:
    """Maps driver error messages to a summary and hint (first matching rule)."""

    def __init__(self, rules: tuple[DbErrorRule, ...] = DEFAULT_RULES):
        self.rules = rules

    @staticmethod
    def driver_message(exc: BaseException) -> str:
        if isinstance(exc, DBAPIError) and exc.orig is not None:
            return str(exc.orig)
        return str(exc)

    def match(self, message: str) -> DbErrorRule | None:
        for rule in self.rules:
            if rule.pattern.search(message):
                return rule
        return None

    def translate(self, exc: BaseException, database_name: str, server: str) -> str:
        raw = self.driver_message(exc)
        where = f"'{database_name}'" + (f" (server '{server}')" if server else "")
        rule = self.match(raw)
        if rule is not None:
            return (
                f"Cannot connect to {where}: {rule.summary}. {rule.hint}\n"
                f"Driver error: {raw}"
            )
        return (
            f"Database error for {where}: {type(exc).__name__}: {raw}\n"
            "Rerun with --traceback for details."
        )
