"""Mix tflows scripts with regular discord.py commands.

Script commands use the ``!`` prefix via ``bot.command(name, code)``. Normal
discord.py commands (added through cogs or ``add_command``) keep working as a
fallback for anything a script cannot express.

Run with:  python examples/mixing.py
"""

from discord.ext import commands

from tflows import FlowBot
import os



class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="purge")
    async def purge(self, ctx, limit: int):
        await ctx.channel.purge(limit=limit)


bot = FlowBot(prefix="!")

# A script command.
bot.command(
    name="hello",
    code="""
reply Hi $user(display)!
    """,
    description="Says hello.",
)

# A regular discord.py command (via a cog).
bot.add_cog(Moderation(bot))


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

TOKEN = os.getenv("DISCORD_TOKEN")