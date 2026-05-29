class FunctionRegistry:
    def __init__(self):
        self.functions = {}
        self.vars = {}

    # commands like embed, send, etc.
    def register(self, name, func=None):
        if func is None:
            def wrapper(f):
                self.functions[name] = f
                return f
            return wrapper

        self.functions[name] = func
        return func

    def get(self, name):
        return self.functions.get(name)

    # variables like $time, $ping-style vars
    def register_var(self, name, func):
        self.vars[name] = func
        return func

    def get_var(self, name):
        return self.vars.get(name)


registry = FunctionRegistry()