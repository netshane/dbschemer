"""Sample ``.dbschemer.toml`` written by ``dbschemer init``.

Must stay byte-for-byte identical to the ``toml`` sample in README.md
(``tests/unit/test_init_service.py`` checks this).
"""


def _database_block(name: str) -> str:
    return (
        f"# run with: dbschemer export {name}\n"
        f"[databases.{name}]\n"
        "# type is one of: sqlserver, postgres, mysql\n"
        'type="sqlserver"\n'
        'server="<server>"\n'
        'database="<database>"\n'
        "# omit user for sqlserver to use integrated (trusted) authentication\n"
        'user="<user>"\n'
        "# or read the user from an environment variable (user takes precedence)\n"
        f'# user_env_var="DBSCHEMER_USER_{name}"\n'
        "# port=1433\n"
        "# environment variable that holds the database password (if needed)\n"
        f'password_env_var="DBSCHEMER_PWD_{name}"\n'
        f'output="./docs/db/{name}"\n'
        "# connection/login timeout in seconds (optional)\n"
        "# connect_timeout=15\n"
        "# advanced: replace type/server/database/user/port with a full\n"
        "# connection string (SQLAlchemy URL, or mssql+mssql-python://<ODBC string>)\n"
        '# connection_string="..."\n'
    )


CONFIG_TEMPLATE = "\n".join(_database_block(name) for name in ("sample", "sample2"))
