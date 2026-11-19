from pathlib import Path

import click
from sqlalchemy.exc import ArgumentError

from locallib.commands import CliOptions, pass_factory
from locallib.db import build_connection, describe_database, describe_server
from locallib.db_errors import is_db_error
from locallib.dbschemer_config import ConfigError, DbschemerConfig
from locallib.dependencies import ServiceFactory


def _safe_server(connection_string: str) -> str:
    """The server for error messages, or ``""`` if the string can't be parsed."""
    try:
        return describe_server(connection_string)
    except ArgumentError:
        return ""


@click.command("export")
@click.argument("database_name")
@click.option(
    "--file",
    "file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path(".dbschemer.toml"),
    show_default=True,
    help="Config file to read.",
)
@click.option(
    "--row-count",
    is_flag=True,
    default=False,
    help="Include table row counts in the output.",
)
@pass_factory
def export_command(
    factory: ServiceFactory, database_name: str, file: Path, row_count: bool
) -> None:
    """Export the schema of DATABASE_NAME (a [databases.<name>] in the config)."""
    try:
        config = DbschemerConfig.load(file)
        connection_string = build_connection(config.get(database_name))
    except ConfigError as e:
        raise click.ClickException(str(e)) from e
    except KeyError as e:  # unknown database name (only config.get raises it)
        raise click.ClickException(str(e.args[0])) from e
    try:
        service = factory.create_export_service(config, database_name, row_count)
        database = describe_database(connection_string) or database_name
        result = service.run(database)
    except ArgumentError as e:
        # The parser's message echoes the whole string; keep it out of output.
        raise click.ClickException(
            f"Invalid connection settings for '{database_name}' in {file}"
        ) from e
    except (ValueError, OSError) as e:
        raise click.ClickException(str(e)) from e
    except Exception as e:
        if not is_db_error(e):
            raise
        options = click.get_current_context().find_object(CliOptions)
        if options is not None and options.traceback:
            factory.create_error_reporter().print_traceback(e)
        message = factory.create_db_error_translator().translate(
            e, database_name, _safe_server(connection_string)
        )
        raise click.ClickException(message) from e
    click.echo(
        f"Exported {database_name} to {result.output_dir}: "
        f"{result.tables} tables, {result.views} views, "
        f"{result.procedures} procedures, {result.functions} functions"
    )
