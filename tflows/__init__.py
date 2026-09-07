"""tflows — a lightweight scripting framework for Discord bots."""

from .bot import EVENT_NAMES, FlowBot, ScriptCommand
from .context import FlowContext
from .diagnostics import Diagnostic, check_file, check_source
from .engine import Engine
from .events import EVENT_MAP, EventRegistry
from .guards import CooldownManager
from .loader import load_function
from .registry import FunctionRegistry, registry
from .runtime import FlowValue, ScriptFunction
from .scheduler import Scheduler
from .state import StateStore
from .version import __version__

__all__ = [
    "FlowBot",
    "ScriptCommand",
    "FlowContext",
    "Engine",
    "FunctionRegistry",
    "registry",
    "load_function",
    "StateStore",
    "Scheduler",
    "EventRegistry",
    "CooldownManager",
    "EVENT_MAP",
    "EVENT_NAMES",
    "FlowValue",
    "ScriptFunction",
    "Diagnostic",
    "check_file",
    "check_source",
    "__version__",
]
