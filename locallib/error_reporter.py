"""Report errors on stderr without leaking local variable values.

Tracebacks use the standard ``traceback`` module, never ``logger.exception``:
loguru's ``diagnose=True`` prints the locals of every frame, which can include
connection strings and passwords.
"""

import traceback

import click


class ErrorReporter:
    def print_traceback(self, exc: BaseException) -> None:
        click.echo("".join(traceback.format_exception(exc)).rstrip(), err=True)

    def report_unexpected(self, exc: BaseException, show_traceback: bool) -> None:
        click.echo(f"Unexpected error: {type(exc).__name__}: {exc}", err=True)
        if show_traceback:
            self.print_traceback(exc)
        else:
            click.echo("Rerun with --traceback for the full traceback.", err=True)
