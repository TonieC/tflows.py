"""tflows 1.3: mixed durations, config knobs, after, switch, choose.

Run with:  python examples/v13.py
"""

import os

from tflows import FlowBot


bot = FlowBot(
    prefix="!",
    max_wait=60,
    config={"theme": "dark", "welcome": "hey"},
)

bot.command(
    name="later",
    code="""
send now
after 0s:
    send $config(welcome) from after
    """,
    description="Runs an after-block inline (0s).",
)

bot.command(
    name="route",
    code="""
switch $arg(0):
    case ping:
        send pong
    case hi:
        send $config(welcome)
    default:
        send try ping or hi
    """,
    description="switch/case routing.",
)

bot.command(
    name="pick",
    code="""
send $choose(red, green, blue)
    """,
    description="Random pick.",
)

bot.command(
    name="slow",
    code="""
cooldown 1s 500ms per user
wait 500ms
send done in $duration(500ms)
    """,
    description="Mixed-unit wait and cooldown.",
)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("Set DISCORD_TOKEN before running this example.")
bot.run(TOKEN)
