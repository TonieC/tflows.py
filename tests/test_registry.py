from tflows.registry import FunctionRegistry


def test_register_and_get():
    r = FunctionRegistry()

    def fn(ctx, args):
        return args

    r.register("greet", fn)
    assert r.get("greet") is fn
    assert r.get("missing") is None


def test_register_decorator():
    r = FunctionRegistry()

    @r.register("hello")
    def hello(ctx, args):
        return "hi"

    assert r.get("hello") is hello


def test_register_overwrites():
    r = FunctionRegistry()

    def a(ctx, args):
        return "a"

    def b(ctx, args):
        return "b"

    r.register("x", a)
    r.register("x", b)
    assert r.get("x") is b


def test_register_alias():
    r = FunctionRegistry()

    @r.register("main")
    def main(ctx, args):
        return "ok"

    r.register_alias("secondary", "main")
    assert r.get("secondary") is main


def test_unregister():
    r = FunctionRegistry()

    @r.register("temp")
    def temp(ctx, args):
        pass

    assert r.unregister("temp") is temp
    assert r.get("temp") is None


def test_function_names_sorted():
    r = FunctionRegistry()
    r.register("b", lambda ctx, args: None)
    r.register("a", lambda ctx, args: None)
    assert r.function_names() == ["a", "b"]


def test_register_var_and_get():
    r = FunctionRegistry()

    def var(ctx, args):
        return "42"

    r.register_var("count", var)
    assert r.get_var("count") is var
    assert r.get_var("nope") is None


def test_register_var_decorator():
    r = FunctionRegistry()

    @r.register_var("version")
    def version(ctx, args):
        return "1.0"

    assert r.get_var("version") is version


def test_register_var_alias():
    r = FunctionRegistry()

    @r.register_var("original")
    def original(ctx, args):
        return "v"

    r.register_var_alias("copy", "original")
    assert r.get_var("copy") is original


def test_unregister_var():
    r = FunctionRegistry()

    @r.register_var("temp")
    def temp(ctx, args):
        return "x"

    assert r.unregister_var("temp") is temp
    assert r.get_var("temp") is None


def test_var_names_sorted():
    r = FunctionRegistry()
    r.register_var("z", lambda ctx, args: "")
    r.register_var("a", lambda ctx, args: "")
    assert r.var_names() == ["a", "z"]


def test_default_registry_is_singleton():
    from tflows import registry as exported_registry
    from tflows.registry import registry as default_registry

    assert default_registry is exported_registry
