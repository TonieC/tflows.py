"""tflows — a lightweight scripting framework for Discord bots."""

from .bot import FlowBot, ScriptCommand
from .context import FlowContext
from .engine import Engine
from .loader import load_function
from .registry import FunctionRegistry, registry
from .version import __version__

__all__ = [
    "FlowBot",
    "ScriptCommand",
    "FlowContext",
    "Engine",
    "FunctionRegistry",
    "registry",
    "load_function",
    "__version__",
]
