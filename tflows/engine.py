import re

class Engine:
    def __init__(self, registry):
        self.registry = registry

    # -----------------------
    # VARIABLES
    # -----------------------
    def replace_vars(self, ctx, text: str):

        if "$ping" in text:
            latency = ctx._state._get_client().latency * 1000
            text = text.replace("$ping", f"{latency:.2f}ms")

        if self.registry.vars:
            def var_replacer(match):
                name = match.group(1)
                args = match.group(2) or ""

                handler = self.registry.get_var(name)
                if handler:
                    return str(handler(ctx, args))

                return match.group(0)

            text = re.sub(
                r"\$(\w+)(?:\((.*?)\))?",
                var_replacer,
                text,
                flags=re.DOTALL
            )

        return text

    # -----------------------
    # EMBED PARSER
    # -----------------------
    async def parse_embed(self, ctx, block: str):
        import discord

        block = block.replace("\r\n", "\n")

        e = discord.Embed()

        def grab(key):
            m = re.search(rf"\${key}\[(.*?)\]", block, re.DOTALL)
            return m.group(1).strip() if m else None

        title = grab("title")
        desc = grab("desc")
        footer = grab("footer")
        color = grab("color")

        clean = re.sub(r"\$(title|desc|footer|color)\[.*?\]", "", block, flags=re.DOTALL).strip()

        def apply(text):
            if not text:
                return None
            return self.replace_vars(ctx, text)

        if title:
            e.title = apply(title)

        full_desc = desc if desc else clean
        e.description = self.replace_vars(ctx, full_desc or "No content")

        if footer:
            e.set_footer(text=apply(footer))

        if color:
            try:
                e.color = discord.Color(int(color.replace("#", ""), 16))
            except:
                pass

        await ctx.channel.send(embed=e)

    # -----------------------
    # MAIN ENGINE (FIXED FLOW)
    # -----------------------
    async def run(self, ctx, code: str):

        lines = code.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            if not line.strip():
                i += 1
                continue

            # -----------------------
            # -----------------------
            # EMBED BLOCK (FIXED SAFE CAPTURE)
            if line.strip() == "embed":
                block = []
                i += 1

                depth = 0
                started = False

                while i < len(lines):
                    current = lines[i]

                    if "$desc[" in current:
                        started = True

                    if started:
                        block.append(current)

                        depth += current.count("[")
                        depth -= current.count("]")

                        if depth <= 0:
                            i += 1
                            break

                    i += 1

                raw = "\n".join(block)
                await self.parse_embed(ctx, raw)
                continue
            # -----------------------
            # NORMAL COMMANDS
            # -----------------------
            line = self.replace_vars(ctx, line)

            parts = line.split(" ", 1)
            name = parts[0]
            args = parts[1] if len(parts) > 1 else ""

            func = self.registry.get(name)

            if func:
                await func(ctx, args)
            else:
                print(f"[tflow] Unknown function: {name}")

            i += 1