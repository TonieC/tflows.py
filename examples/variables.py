"""A tour of the variables available in tflows scripts.

Run with:  python examples/variables.py
"""

from tflows import FlowBot  
import os


bot = FlowBot(prefix="!")

bot.command(
    name="info",
    code="""
embed
$title[About $user(display)]

$desc[
**You**
User: $user(name)
Display: $user(display)
ID: $id
Mention: $user(mention)
Avatar: $user(avatar)
Bot: $user(bot)

**This server**
Name: $server
ID: $server(id)
Members: $membercount
Boosts: $server(boost) (level $server(boostlvl))

**This channel**
Channel: $channel
Topic: $channel(topic)
NSFW: $channel(nsfw)

**Bot**
Name: $bot(name)
Ping: $bot(ping)
Prefix: $prefix
Command: $command

**Other**
Time: $time
Date: $time(notime)
Uptime: $uptime
Random: $random(1, 100)
]
endembed
    """,
    description="Shows a rich overview using variables.",
)

bot.command(
    name="args",
    code="""
// $args is everything after the command name
reply You typed: "$args"
reply Words: $argcount | First: $arg(0) | Last: $arg(-1)
    """,
    description="Demonstrates argument variables.",
)
TOKEN = os.getenv("DISCORD_TOKEN")