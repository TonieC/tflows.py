"""A minimal tflows bot.

Run with:  python examples/basic_bot.py
"""

from tflows import FlowBot
import os


bot = FlowBot(prefix="!")

bot.command(
    name="ping",
    code="""
    // Show the current WebSocket latency
    reply Pong! $ping
    """,
    description="Replies with the bot's latency.",
)

bot.command(
    name="greet",
    code="""
    // Use the raw command arguments
    reply Hello $args!
    """,
    description="Greets the given name.",
)

TOKEN = os.getenv("DISCORD_TOKEN")