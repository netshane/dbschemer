import mssql_python
import pytest
from sqlalchemy.exc import OperationalError

from locallib.db_errors import DbErrorTranslator, is_db_error

ODBC = "[Microsoft][ODBC Driver 18 for SQL Server]"


@pytest.fixture
def translator() -> DbErrorTranslator:
    return DbErrorTranslator()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("message", "summary"),
    [
        ("TCP Provider: Error code 0x2AF9", "could not be resolved"),
        ("TCP Provider: Error code 0x2afc", "could not be resolved"),
        ("TCP Provider: Error code 0x274C", "did not respond (timeout)"),
        ("Login timeout expired", "did not respond (timeout)"),
        ("(HYT00) something", "did not respond (timeout)"),
        ("TCP Provider: Error code 0x274D", "connection was refused"),
        ("TCP Provider: Error code 0x2751", "host is unreachable"),
        ("TCP Provider: Error code 0x2746", "reset by the server"),
        ("Login failed for user 'u'. (18456) (SQLDriverConnect)", "login failed"),
        ("(28000) denied", "login failed"),
        ('Cannot open database "X" requested by the login. (4060)', "cannot open"),
        ("SSL Provider: [error:0A000086]", "TLS/certificate"),
        ("The certificate chain was issued by an untrusted authority", "TLS/cert"),
        ("Data source name not found and no default driver", "ODBC driver is"),
        ("Can't open lib 'ODBC Driver 18 for SQL Server'", "ODBC driver is"),
    ],
)
def test_known_errors(translator, message, summary):
    raw = ODBC + message
    text = translator.translate(RuntimeError(raw), "db", "sql01")
    first, second = text.split("\n")
    assert first.startswith("Cannot connect to 'db' (server 'sql01'): ")
    assert summary in first
    assert second == f"Driver error: {raw}"


@pytest.mark.unit
def test_cannot_open_database_wins_over_login_failed(translator):
    raw = (
        ODBC + '[SQL Server]Cannot open database "X" requested by the login. '
        "The login failed. (4060); [28000] Login failed for user 'u'. (18456)"
    )
    text = translator.translate(RuntimeError(raw), "db", "sql01")
    assert "cannot open the database" in text.split("\n")[0]


@pytest.mark.unit
def test_timeout_hint_mentions_setting(translator):
    text = translator.translate(RuntimeError(ODBC + "Login timeout expired"), "d", "")
    assert "connect_timeout" in text


@pytest.mark.unit
def test_unknown_error(translator):
    raw = ODBC + "Something odd (42000) (99999)"
    text = translator.translate(RuntimeError(raw), "db", "sql01")
    assert text == (
        f"Database error for 'db' (server 'sql01'): RuntimeError: {raw}\n"
        "Rerun with --traceback for details."
    )


@pytest.mark.unit
def test_dbapi_error_uses_orig(translator):
    exc = OperationalError("SELECT 1", {}, Exception("Login failed for user 'u'"))
    text = translator.translate(exc, "db", "sql01")
    assert "login failed" in text
    assert "Driver error: Login failed for user 'u'" in text
    assert "SELECT 1" not in text


@pytest.mark.unit
def test_empty_server_is_omitted(translator):
    text = translator.translate(RuntimeError(ODBC + "x"), "db", "")
    assert text.startswith("Database error for 'db': RuntimeError:")
    assert "server" not in text.split("\n")[0]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RuntimeError(ODBC + "TCP Provider"), True),
        (RuntimeError("[unixODBC][Driver Manager]Can't open lib"), True),
        (OperationalError("s", {}, Exception("x")), True),
        (mssql_python.Error("x", ""), True),
        (RuntimeError("boom"), False),
        (ValueError(ODBC), False),
        (KeyError("precision"), False),
    ],
)
def test_is_db_error(exc, expected):
    assert is_db_error(exc) is expected
