import re
import asyncio

class Engine:
    def __init__(self, registry):
        self.registry = registry

    # -----------------------
    # VARIABLES (FIXED)
    # -----------------------
    async def replace_vars(self, ctx, text: str):

        # $ping (keep simple)
        if "$ping" in text:
            latency = ctx._state._get_client().latency * 1000
            text = text.replace("$ping", f"{latency:.2f}ms")

        async def var_replacer(match):
            name = match.group(1)
            args = match.group(2) or ""

            handler = self.registry.get_var(name)
            if handler:
                result = handler(ctx, args)

                # ✅ SUPPORT ASYNC NOW
                if asyncio.iscoroutine(result):
                    result = await result

                return str(result)

            return match.group(0)

        # IMPORTANT: async replace loop
        pattern = r"\$(\w+)(?:\((.*?)\))?"
        matches = list(re.finditer(pattern, text, re.DOTALL))

        for match in reversed(matches):
            replacement = await var_replacer(match)
            start, end = match.span()
            text = text[:start] + replacement + text[end:]

        return text

    # -----------------------
    # EMBED PARSER
    # -----------------------
    async def parse_embed(self, ctx, block: str):

        import discord
        import re

        e = discord.Embed()
        block = block.replace("\r\n", "\n")

        # -----------------------
        # EXTRACT HELPERS
        # -----------------------
        def grab(key):
            m = re.search(rf"\${key}\[(.*?)\]", block, re.DOTALL)
            return m.group(1).strip() if m else None

        title = grab("title")
        desc = grab("desc")
        footer = grab("footer")
        color = grab("color")

        clean = re.sub(
            r"\$(title|desc|footer|color)\[.*?\]",
            "",
            block,
            flags=re.DOTALL
        ).strip()

        # -----------------------
        # SAFE APPLY (ALWAYS AWAIT VAR ENGINE)
        # -----------------------
        async def apply(v):
            if not v:
                return None
            return await self.replace_vars(ctx, v)

        # -----------------------
        # TITLE
        # -----------------------
        if title:
            e.title = await apply(title)

        # -----------------------
        # DESCRIPTION
        # -----------------------
        full_desc = desc if desc else clean
        e.description = await self.replace_vars(ctx, full_desc or "No content")

        # -----------------------
        # FOOTER
        # -----------------------
        if footer:
            e.set_footer(text=await apply(footer))

        # -----------------------
        # COLOR
        # -----------------------
        if color:
            try:
                c = color.replace("#", "").lower()

                if c == "white":
                    e.color = discord.Color.white()
                else:
                    e.color = discord.Color(int(c, 16))

            except Exception:
                pass

        # -----------------------
        # SEND
        # -----------------------
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
            # EMBED BLOCK
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
            line = await self.replace_vars(ctx, line)

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