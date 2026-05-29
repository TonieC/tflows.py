import discord
import re

def setup(registry):

    async def embed(ctx, args):

        e = discord.Embed()
        raw = args.strip()

        # -----------------------
        # EXTRACT BLOCK
        # -----------------------
        match = re.search(r"\$embed<([\s\S]*?)>", raw)
        if not match:
            return await ctx.channel.send("Invalid embed format")

        block = match.group(1)

        # -----------------------
        # PARSE LINES
        # -----------------------
        data = {}

        for line in block.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue

            key, value = line.split(":", 1)
            data[key.strip().lower()] = value.strip()

        engine = ctx.bot.engine

        # -----------------------
        # APPLY FIELDS
        # -----------------------
        if "title" in data:
            e.title = engine.replace_vars(ctx, data["title"])

        if "desc" in data:
            e.description = engine.replace_vars(ctx, data["desc"])

        if "footer" in data:
            e.set_footer(text=engine.replace_vars(ctx, data["footer"]))

        if "color" in data:
            try:
                c = data["color"].replace("#", "")
                if c == "white":
                    e.color = discord.Color.white()
                else:
                    e.color = discord.Color(int(c, 16))
            except:
                pass

        await ctx.channel.send(embed=e)

    # -----------------------
    # REGISTER PROPERLY HERE
    # -----------------------
    registry.register("embed", embed)