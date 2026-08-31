"""Loads built-in function modules into a registry."""

import importlib
import logging
import os

logger = logging.getLogger("tflows.loader")


def load_function(registry):
    """Register core built-ins and every ``tflows.function`` module.

    Built-ins from :mod:`tflows.builtins` are registered first, then every
    ``tflows.function`` module's ``setup(registry)`` is called in alphabetical
    order. A failing module is logged and skipped so a single broken function
    cannot take down the whole bot.
    """
    from . import builtins

    try:
        builtins.setup(registry)
    except Exception:
        logger.exception("[tflow] Failed to set up built-ins")

    base = os.path.join(os.path.dirname(__file__), "function")

    if not os.path.isdir(base):
        logger.warning("[tflow] Function directory not found: %s", base)
        return

    for file in sorted(os.listdir(base)):
        if file.endswith(".py") and file != "__init__.py":
            module_name = f"tflows.function.{file[:-3]}"
            try:
                module = importlib.import_module(module_name)
            except Exception:
                logger.exception("[tflow] Failed to import function module: %s", module_name)
                continue

            setup = getattr(module, "setup", None)
            if callable(setup):
                try:
                    setup(registry)
                except Exception:
                    logger.exception("[tflow] Failed to set up function module: %s", module_name)
