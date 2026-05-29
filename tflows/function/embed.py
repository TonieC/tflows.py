import discord
import re

def setup(registry):

    @registry.register("embed")
    async def embed(ctx, args):

        e = discord.Embed()
        raw = args

        # -----------------------
        # SAFE BRACKET GRABBER
        # -----------------------
        def grab(key):
            start = f"${key}["
            idx = raw.find(start)

            if idx == -1:
                return None

            i = idx + len(start)
            depth = 1
            out = []

            while i < len(raw):
                c = raw[i]

                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        break

                out.append(c)
                i += 1

            return "".join(out).strip()

        # -----------------------
        # CLEAN RAW (SAFE REMOVE TAGS)
        # -----------------------
        def strip_tags(text):
            for key in ["title", "desc", "footer", "color"]:
                text = re.sub(rf"\${key}\[.*?\]", "", text, flags=re.DOTALL)
            return text.strip()

        # -----------------------
        # EXTRACT FIELDS
        # -----------------------
        title = grab("title")
        desc = grab("desc")
        footer = grab("footer")
        color = grab("color")

        clean = strip_tags(raw)

        # -----------------------
        # APPLY EMBED VALUES
        # -----------------------
        if title:
            e.title = title

        if desc:
            e.description = desc
        else:
            e.description = clean if clean else "No content"

        if footer:
            e.set_footer(text=footer)

        if color:
            try:
                e.color = discord.Color(int(color.replace("#", ""), 16))
            except:
                pass

        await ctx.channel.send(embed=e)