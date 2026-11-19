from pathlib import Path

import click

from locallib.commands import pass_factory
from locallib.dependencies import ServiceFactory


@click.command("init")
@click.option(
    "--file",
    "file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path(".dbschemer.toml"),
    show_default=True,
    help="Path of the config file to create.",
)
@click.option(
    "--force", is_flag=True, default=False, help="Overwrite an existing file."
)
@pass_factory
def init_command(factory: ServiceFactory, file: Path, force: bool) -> None:
    """Create a sample .dbschemer.toml config file."""
    try:
        path = factory.create_init_service().run(file, force=force)
    except OSError as e:
        # FileExistsError / FileNotFoundError carry a ready-made message; other
        # OS errors (e.g. PermissionError) fall back to their own text.
        raise click.ClickException(str(e)) from e
    click.echo(f"Created {path}")
