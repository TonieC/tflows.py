class Engine:
    def __init__(self, registry):
        self.registry = registry

    async def run(self, ctx, code: str):
        lines = code.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            parts = line.split(" ", 1)
            command = parts[0]
            args = parts[1] if len(parts) > 1 else ""

            func = self.registry.get(command)

            if func:
                await func(ctx, args)
            else:
                print(f"[tflow] Unknown function: {command}")