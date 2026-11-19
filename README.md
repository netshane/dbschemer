# dbschemer

A tool for dumping database schemas for use by LLM agents.

This tool is intended to be installed using `uv tool install`.
It expects a config file with the name `.dbschemer.toml` in the current directory with the following layout:
```toml
# run with: dbschemer export sample
[databases.sample]
# type is one of: sqlserver, postgres, mysql
type="sqlserver"
server="<server>"
database="<database>"
# omit user for sqlserver to use integrated (trusted) authentication
user="<user>"
# or read the user from an environment variable (user takes precedence)
# user_env_var="DBSCHEMER_USER_sample"
# port=1433
# environment variable that holds the database password (if needed)
password_env_var="DBSCHEMER_PWD_sample"
output="./docs/db/sample"
# connection/login timeout in seconds (optional)
# connect_timeout=15
# advanced: replace type/server/database/user/port with a full
# connection string (SQLAlchemy URL, or mssql+mssql-python://<ODBC string>)
# connection_string="..."

# run with: dbschemer export sample2
[databases.sample2]
# type is one of: sqlserver, postgres, mysql
type="sqlserver"
server="<server>"
database="<database>"
# omit user for sqlserver to use integrated (trusted) authentication
user="<user>"
# or read the user from an environment variable (user takes precedence)
# user_env_var="DBSCHEMER_USER_sample2"
# port=1433
# environment variable that holds the database password (if needed)
password_env_var="DBSCHEMER_PWD_sample2"
output="./docs/db/sample2"
# connection/login timeout in seconds (optional)
# connect_timeout=15
# advanced: replace type/server/database/user/port with a full
# connection string (SQLAlchemy URL, or mssql+mssql-python://<ODBC string>)
# connection_string="..."
```

## Installation

```sh
uv tool install --from git+ssh://git@nsforge.netshane.com:222/shane/dbschemer.git dbschemer

# upgrade with
uv tool upgrade dbschemer
```

## Usage

```sh
# export the database configured as [databases.<database_name>]
uv run dbschemer export <database_name> [--file <config_file>] [--row-count]

# create a config file in the current directory
uv run dbschemer init
```

- `--file` defaults to `./.dbschemer.toml`.
- `--row-count` includes table row counts (JSON, README, schema and table files). They are
  left out by default so the output only changes when the schema changes.
- `output` is resolved relative to the directory that holds the config file (not the
  current directory) and is created if missing.
- `user_env_var` (optional) names an environment variable that holds the database user.
  Precedence: `user` > `user_env_var` > integrated credentials (SQL Server). If `user` is set,
  `user_env_var` is ignored; if only `user_env_var` is set it must hold a non-empty value
  (no fallback to integrated credentials). Cannot be combined with `connection_string`.
- If `password_env_var` is set, that environment variable must hold a non-empty password.
- `connect_timeout` (optional, seconds > 0) limits how long the login waits for the server.
  Supported for `mssql+mssql-python://` and `mssql+pyodbc://` connection strings. The OS
  DNS lookup may take longer than this limit.
- Connection failures print a short message with the likely cause (DNS, timeout, login
  failed, ...) and the raw driver error. Pass the global `--traceback` flag
  (`dbschemer --traceback export <name>`) to also print the full Python traceback.
- SQL Server only. Running the export twice against an unchanged schema gives identical files.

Output layout (written directly into `output`):

```
<output>/schema.json                     # the extracted schema
<output>/README.md                       # index
<output>/views.md
<output>/schemas/<schema>.md
<output>/tables/<schema>.<table>.md
<output>/stored_procedures.md            # only if any
<output>/procedures/<schema>.<proc>.md
<output>/functions.md                    # only if any
<output>/functions/<schema>.<func>.md
```

Each export first deletes the generated items above (`schema.json`, `README.md`, `views.md`,
`stored_procedures.md`, `functions.md` and the `schemas/`, `tables/`, `procedures/`,
`functions/` directories), so stale files disappear. Any other file in `output` is left alone.
If the database cannot be read, the previous output is kept unchanged.


## Dev Setup

```sh
uv sync                     # installs dependencies and the dev group (pytest, mypy, ...)

# Upgrade packages
uv lock --upgrade
```

`nscomponents` is pinned to a git revision in `[tool.uv.sources]`. To upgrade it,
change `rev` and run `uv lock --upgrade-package nscomponents`.

## Configuration

Databases are configured per project in `.dbschemer.toml` (see above; `dbschemer init` creates
one). Passwords are never stored in that file: each database names the environment variable
that holds its password (`password_env_var`).

Application settings (logging, etc.) come only from the tool's own `settings.toml`. They are
never read from the directory the tool runs in, so a project's own `settings.toml` is ignored.

- `settings.toml` - committed application defaults (logging). Packaged into the wheel as
  `locallib/settings.toml`; a source checkout uses the repo-root copy.
- `settings.local.toml` - gitignored, source checkout only; local overrides (e.g. log streams).
  Merged over `settings.toml`.
- `secrets.toml` - gitignored, source checkout only; not needed for database passwords.

## Project layout

```
dbschemer.py           # runs locallib.cli without the console script
locallib/
  cli.py               # click group + main() entry point; stores CliOptions in ctx.obj
  appsettings.py       # AppSettings model + AppSettings.load(env)
  settings.py          # settings helpers (default_settings_dir, environment resolution)
  dependencies.py      # ServiceFactory: logging, cached engines, create_* methods
  db.py                # create_db_engine(...) - no settings access
  dbschemer_config.py  # .dbschemer.toml model (DbschemerConfig.load)
  services/            # domain classes; dependencies injected via constructor
  commands/            # thin click commands: args -> factory -> service.run()
                       # @pass_factory builds the ServiceFactory when a command runs
```

To add a feature, follow the `init`/`export` pattern: a thin command in `commands/`
-> a service in `services/` (e.g. `init_service.py`) -> a unit test in `tests/unit/`,
add a `create_*` method to `ServiceFactory`, and register the command in
`locallib/cli.py`.

To add a database, add a `[databases.<name>]` table to `.dbschemer.toml` in the project
being documented (run `dbschemer init` to create a sample).

## Development

```sh
uvx ruff format             # format
uvx ruff check --fix        # lint
uv run mypy                 # type check (paths set in pyproject.toml)
```

## Testing

Unit tests do not read the real `settings.toml` or `.dbschemer.toml` and need no network access. See `tests/README.md`.

```sh
# Run tests
uv run pytest tests/unit/

# With coverage
uv run pytest tests/unit/ --cov=locallib --cov-report=term-missing

# Run single test
uv run pytest tests/unit/ -k "test_name"

# Run tests excluding slow tests
uv run pytest tests/unit/ -m "unit and not slow"
```

## Template update

```sh
# Update the project template
uv run copier update
```