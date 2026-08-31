"""Central registry for tflows script functions and variables.

The :class:`FunctionRegistry` maps script instruction names to callables and
``$variable`` names to resolver callables. A process-wide default instance
(:data:`registry`) is shared by all :class:`~tflows.FlowBot` instances unless a
custom registry is passed in.
"""


class FunctionRegistry:
    """Stores script functions and variables.

    Functions are plain callables ``fn(ctx, args) -> Optional[Awaitable]``.
    Variables are callables ``var(ctx, args) -> Union[str, Awaitable[str]]``.
    """

    def __init__(self):
        self.functions = {}
        self.vars = {}

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------
    def register(self, name, func=None):
        """Register ``func`` under ``name`` or return a decorator.

        Usage::

            @registry.register("greet")
            async def greet(ctx, args):
                await ctx.channel.send(f"Hello {args}")

            registry.register("greet", greet)
        """
        if func is None:

            def wrapper(f):
                self.functions[name] = f
                return f

            return wrapper

        self.functions[name] = func
        return func

    def register_alias(self, name, target):
        """Register ``name`` as an alias of an already registered function."""
        self.functions[name] = self.functions[target]
        return self.functions[name]

    def get(self, name):
        """Return the function registered under ``name`` (or ``None``)."""
        return self.functions.get(name)

    def unregister(self, name):
        """Remove a function by name. Returns the removed callable or ``None``."""
        return self.functions.pop(name, None)

    def function_names(self):
        """Return the sorted list of registered function names."""
        return sorted(self.functions)

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------
    def register_var(self, name, func=None):
        """Register ``func`` as a ``$name`` variable or return a decorator.

        Usage::

            @registry.register_var("owner")
            def owner_var(ctx, args):
                return ctx.guild.owner.mention
        """
        if func is None:

            def wrapper(f):
                self.vars[name] = f
                return f

            return wrapper

        self.vars[name] = func
        return func

    def register_var_alias(self, name, target):
        """Register ``name`` as an alias of an already registered variable."""
        self.vars[name] = self.vars[target]
        return self.vars[name]

    def get_var(self, name):
        """Return the variable resolver registered under ``name`` (or ``None``)."""
        return self.vars.get(name)

    def unregister_var(self, name):
        """Remove a variable by name. Returns the removed callable or ``None``."""
        return self.vars.pop(name, None)

    def var_names(self):
        """Return the sorted list of registered variable names."""
        return sorted(self.vars)


registry = FunctionRegistry()
