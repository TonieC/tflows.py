import discord
from discord.ext import commands
from .engine import Engine
from .functions import registry
from .loader import load_modules
import tflows.builtins


class FlowBot(commands.Bot):
    def __init__(self, prefix="!"):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix=prefix, intents=intents)

        self.commands_map = {}
        self.engine = Engine(registry)

        # ✅ LOAD MODULES HERE
        load_modules(registry)

    def command(self, name, code):
        self.commands_map[name] = code

    async def on_message(self, message):
        if message.author.bot:
            return

        await self.process_commands(message)

        prefix = self.command_prefix
        if not message.content.startswith(prefix):
            return

        cmd_name = message.content[len(prefix):].split()[0]

        if cmd_name in self.commands_map:
            code = self.commands_map[cmd_name]
            await self.engine.run(message, code)