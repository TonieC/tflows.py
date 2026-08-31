from tflows import FunctionRegistry
from tflows.loader import load_function


def test_load_function_registers_core_functions():
    registry = FunctionRegistry()
    load_function(registry)

    for name in (
        "send",
        "reply",
        "log",
        "ping",
        "embed",
        "react",
        "delete",
        "clear",
        "wait",
        "server",
        "membercount",
    ):
        assert registry.get(name) is not None, f"function {name!r} not registered"


def test_load_function_registers_core_vars():
    registry = FunctionRegistry()
    load_function(registry)

    for name in (
        "ping",
        "time",
        "uptime",
        "server",
        "guild",
        "membercount",
        "id",
        "avatar",
        "image",
        "user",
        "author",
        "channel",
        "bot",
        "args",
        "arg",
        "argcount",
        "random",
        "prefix",
        "command",
    ):
        assert registry.get_var(name) is not None, f"variable {name!r} not registered"


def test_load_function_idempotent():
    registry = FunctionRegistry()
    load_function(registry)
    load_function(registry)
    assert registry.get("send") is not None
    assert registry.get("log") is not None
    assert registry.get_var("ping") is not None
    assert registry.get_var("uptime") is not None
