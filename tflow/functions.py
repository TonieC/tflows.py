class FunctionRegistry:
    def __init__(self):
        self.functions = {}

    def register(self, name):
        def wrapper(func):
            self.functions[name] = func
            return func
        return wrapper

    def get(self, name):
        return self.functions.get(name)


registry = FunctionRegistry()