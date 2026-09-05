"""Advanced tflows features: conditionals, guards, state, schedules, events, slash.

Run with:  python examples/advanced.py
"""

from tflows import FlowBot
import os


bot = FlowBot(prefix="!")

# --- Conditionals -----------------------------------------------------------
bot.command(
    name="greet",
    code="""
if $argcount > 0:
    reply Hello $args!
else:
    reply Hello $user(display)!
endif
    """,
    description="Greets you or the given name.",
)

# --- Cooldowns + permission guards ------------------------------------------
bot.command(
    name="shout",
    code="""
cooldown 10s per user
require manage_messages
send $args
    """,
    description="Shout something (mods only, 10s cooldown).",
)

# --- Persistent per-server state --------------------------------------------
bot.command(
    name="points",
    code="""
if $arg(0) == add:
    set points[$user] +10
    reply +10! You now have $get(points[$user], 0) points.
else:
    reply You have $get(points[$user], 0) points.
endif
    """,
    description="Check or earn your points.",
)

# --- Slash command (prefix !roll keeps working too) -------------------------
bot.slashcommand(
    name="roll",
    code="send Rolled $arg(sides)!",
    description="Roll dice with the given sides.",
    params=["sides: int"],
)

# --- Scheduled task ----------------------------------------------------------
# bot.schedule("hourly", "send Hourly check-in!", interval="1h")

# --- Event triggers ----------------------------------------------------------
bot.on_event("join", "send Welcome $user(mention)!")
bot.on_event("react", "send $user(display) reacted!")

TOKEN = os.getenv("DISCORD_TOKEN")
