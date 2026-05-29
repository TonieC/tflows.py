import os
import importlib

def load_function(registry):
    base = os.path.join(os.path.dirname(__file__), "function")

    for file in os.listdir(base):
        if file.endswith(".py") and file != "__init__.py":
            module_name = f"tflows.function.{file[:-3]}"
            module = importlib.import_module(module_name)

            if hasattr(module, "setup"):
                module.setup(registry)