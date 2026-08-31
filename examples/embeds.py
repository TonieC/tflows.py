"""Embed examples, both the block form and the single-line form.

Run with:  python examples/embeds.py
"""

from tflows import FlowBot
import os


bot = FlowBot(prefix="!")

# The block form is great for multi-line descriptions.
bot.command(
    name="embed",
    code="""
embed
$title[Server Stats]

$desc[
Members: $membercount
Owner: $server(owner)
Uptime: $uptime(full)
]

$footer[Requested by $user(display)]
$color[blurple]
$thumbnail[$bot(avatar)]
endembed
    """,
    description="Sends a styled embed.",
)

# The single-line form uses | to separate keys and supports fields.
bot.command(
    name="card",
    code="""
embed $embed<title: $user(display) | desc: Level 42 | color: green | field: Role;Admin;true | field: Joined;$user(joined)>
    """,
    description="Sends a quick user card.",
)

TOKEN = os.getenv("DISCORD_TOKEN")