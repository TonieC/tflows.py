import re
import asyncio

class Engine:
    def __init__(self, registry):
        self.registry = registry

    # -----------------------
    # VARIABLES
    # -----------------------
    def replace_vars(self, ctx, text: str):

        # ❌ NEVER execute embed here
        # embed must ONLY be handled in run()

        if "$ping" in text:
            latency = ctx._state._get_client().latency * 1000
            text = text.replace("$ping", f"{latency:.2f}ms")

        def var_replacer(match):
            name = match.group(1)
            args = match.group(2) or ""

            handler = self.registry.get_var(name)
            if handler:
                result = handler(ctx, args)

                if asyncio.iscoroutine(result):
                    raise RuntimeError(f"Async var not supported here: ${name}")

                return str(result)

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

        e = discord.Embed()
        block = block.replace("\r\n", "\n")

        def grab(key):
            m = re.search(rf"\${key}\[(.*?)\]", block, re.DOTALL)
            return m.group(1).strip() if m else None

        title = grab("title")
        desc = grab("desc")
        footer = grab("footer")
        color = grab("color")

        clean = re.sub(r"\$(title|desc|footer|color)\[.*?\]", "", block, flags=re.DOTALL).strip()

        def apply(v):
            if not v:
                return None
            return self.replace_vars(ctx, v)

        if title:
            e.title = apply(title)

        full_desc = desc if desc else clean
        e.description = self.replace_vars(ctx, full_desc or "No content")

        if footer:
            e.set_footer(text=apply(footer))

        if color:
            try:
                c = color.replace("#", "")
                if c == "white":
                    e.color = discord.Color.white()
                else:
                    e.color = discord.Color(int(c, 16))
            except:
                pass

        await ctx.channel.send(embed=e)

    # -----------------------
    # MAIN ENGINE
    # -----------------------
    async def run(self, ctx, code: str):

        lines = code.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # -----------------------
            # EMBED BLOCK (FIXED)
            # -----------------------
            if line == "embed":
                i += 1
                block = []

                while i < len(lines):
                    if lines[i].strip() == "endembed":
                        break
                    block.append(lines[i])
                    i += 1

                await self.parse_embed(ctx, "\n".join(block))
                i += 1
                continue

            # -----------------------
            # NORMAL FUNCTIONS
            # -----------------------
            line = self.replace_vars(ctx, line)

            parts = line.split(" ", 1)
            name = parts[0]
            args = parts[1] if len(parts) > 1 else ""

            func = self.registry.get(name)

            if func:
                result = func(ctx, args)

                if asyncio.iscoroutine(result):
                    await result
            else:
                print(f"[tflow] Unknown function: {name}")

            i += 1