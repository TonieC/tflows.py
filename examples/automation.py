"""Automation-style commands: wait, react, delete, and clear.

Run with:  python examples/automation.py
"""

from tflows import FlowBot
import os


bot = FlowBot(prefix="!")

# The command message is deleted immediately and a temporary notice is sent.
bot.command(
    name="ping",
    code="""
delete
send Pong! $ping
    """,
    description="Deletes the command and replies with latency.",
)

# Simulate a small delay before responding.
bot.command(
    name="slow",
    code="""
react ⏳
wait 3s
react ✅
reply Done waiting!
    """,
    description="Waits 3 seconds before replying.",
)

# Delete the command message and the last few messages in the channel.
# The bot needs the "Manage Messages" permission.
bot.command(
    name="clear",
    code="""
clear 5
    """,
    description="Clears the last 5 messages (Manage Messages required).",
)

TOKEN = os.getenv("DISCORD_TOKEN")