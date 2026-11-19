import sys

import click
from loguru import logger

from locallib.commands import LOG_LEVELS, CliOptions
from locallib.commands.export import export_command
from locallib.commands.init import init_command
from locallib.error_reporter import ErrorReporter
from locallib.settings import ENV_VAR_NAMES, ENVIRONMENTS


@click.group()
@click.option(
    "--env",
    type=click.Choice(ENVIRONMENTS, case_sensitive=False),
    default=None,
    help=(
        "Settings environment. Defaults to the first set of "
        + ", ".join(f"${name}" for name in ENV_VAR_NAMES)
        + ", then production."
    ),
)
@click.option(
    "--traceback",
    "show_traceback",
    is_flag=True,
    default=False,
    help="Show full Python tracebacks for errors.",
)
@click.option(
    "--log-level",
    type=click.Choice(list(LOG_LEVELS), case_sensitive=False),
    default=None,
    help="Force the logging level, overriding the level in settings.toml.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    env: str | None,
    show_traceback: bool,
    log_level: str | None,
) -> None:
    # Until settings are loaded and nslog.init_logging replaces all handlers,
    # only emit errors so early failures (e.g. bad settings) stay visible.
    logger.remove()
    logger.add(sys.stderr, level="ERROR")

    # Only record options here. Commands decorated with @pass_factory load
    # settings, configure logging and build the ServiceFactory when they run,
    # so --help and usage errors never need valid settings.
    ctx.obj = CliOptions(
        env=env,
        log_level=LOG_LEVELS[log_level.lower()] if log_level else None,
        traceback=show_traceback,
    )


cli.add_command(init_command)
cli.add_command(export_command)


def main() -> None:
    """Console-script entry point (``[project.scripts]`` in pyproject.toml)."""
    try:
        # Standalone mode handles click's own errors; anything else propagates.
        cli()
    except Exception as e:
        # Never logger.exception here: loguru's diagnose=True prints local
        # variable values (connection strings, passwords).
        # The click context is gone once cli() raises, so --traceback is read
        # from sys.argv. The ServiceFactory may not exist yet (e.g. bad
        # settings), so ErrorReporter (no dependencies) is built directly.
        ErrorReporter().report_unexpected(
            e, show_traceback="--traceback" in sys.argv[1:]
        )
        sys.exit(1)
