import os
import importlib

def load_modules(registry):
    base_path = os.path.join(os.path.dirname(__file__), "modules")

    for file in os.listdir(base_path):
        if file.endswith(".py") and not file.startswith("_"):
            module_name = f"tflows.modules.{file[:-3]}"
            module = importlib.import_module(module_name)

            if hasattr(module, "setup"):
                module.setup(registry)