import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
  name="test",
  code="""
embed
$title[All Variables Test]

$desc[
=== SERVER ===
$server
$server(name)
$server(boost)
$server(boostlvl)

=== MEMBERCOUNT ===
$membercount
$membercount(all)
$membercount(user)
$membercount(bots)

=== ID ===
$id
$id(user)
$id(mention)
$id(act)

=== IMAGE ===
$image
$image(user)
$image(mention)
$image(act)

=== TIME ===
$time()
$time(12h)
$time(nodate)
$time(nodate;24h)

=== PING ===
$ping
]

$image[$image(act)]
endembed
"""
)

bot.run("BOT_TOKEN")