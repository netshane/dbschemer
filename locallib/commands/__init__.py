from collections.abc import Callable
from dataclasses import dataclass
from functools import update_wrapper
from typing import Any, Concatenate

import click

from locallib.dependencies import ServiceFactory

_FACTORY_KEY = "locallib.service_factory"

# CLI choice -> loguru level name
LOG_LEVELS = {
    "debug": "DEBUG",
    "info": "INFO",
    "warn": "WARNING",
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
    "trace": "TRACE",
}


@dataclass(frozen=True)
class CliOptions:
    """Global CLI options, stored in ``ctx.obj`` by the click group."""

    env: str | None = None
    log_level: str | None = None
    traceback: bool = False


def get_factory(ctx: click.Context) -> ServiceFactory:
    """Return the ServiceFactory for this invocation, creating it on first use.

    Creation is deferred until a command actually runs, so ``--help`` and usage
    errors work without valid settings and without starting logging sinks.
    Tests can pre-seed a factory with ``ctx.meta[_FACTORY_KEY]``.
    """
    root = ctx.find_root()
    factory = root.meta.get(_FACTORY_KEY)
    if factory is None:
        options = ctx.find_object(CliOptions) or CliOptions()
        factory = ServiceFactory.from_environment(
            options.env, log_level=options.log_level
        )
        root.meta[_FACTORY_KEY] = factory
        root.call_on_close(factory.dispose)
    return factory


def pass_factory[**P, R](
    f: Callable[Concatenate[ServiceFactory, P], R],
) -> Callable[P, R]:
    """Like ``click.pass_obj``, but passes the lazily created ServiceFactory."""

    def new_func(*args: Any, **kwargs: Any) -> R:
        ctx = click.get_current_context()
        return ctx.invoke(f, get_factory(ctx), *args, **kwargs)

    return update_wrapper(new_func, f)
