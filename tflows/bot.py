import discord
from discord.ext import commands
from .engine import Engine
from .loader import load_function
import tflows.builtins
from .registry import registry

from tflows import function


class FlowBot(commands.Bot):
    def __init__(self, prefix="!"):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix=prefix, intents=intents)

        self.commands_map = {}
        self.engine = Engine(registry)

        load_function(registry)

    def command(self, name, code):
        self.commands_map[name] = code

    async def on_message(self, message):
        if message.author.bot:
            return

        prefix = self.command_prefix
        if not message.content.startswith(prefix):
            return

        cmd_name = message.content[len(prefix):].split()[0]

        if cmd_name in self.commands_map:
            code = self.commands_map[cmd_name]
            await self.engine.run(message, code)