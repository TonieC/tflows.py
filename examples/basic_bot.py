import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
  name="uptime",
  code="""
embed
$title[Uptime Variants]

$desc[
Default: $uptime
Full: $uptime(full)
Short: $uptime(short)
Clock: $uptime(clock)
Seconds: $uptime(seconds)
Custom: $uptime(d, h, m, s)
]
"""
)

bot.run("BOT_TOKEN") 