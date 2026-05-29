import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
  name="test",
  code="""
embed
$title[Tflow Time System Demo]
$desc[Ping: $ping\n--- TIME TESTS ---\n\nDefault: $time(nodate;24h)\nNo Date: $time(nodate)\nNo Time: $time(notime)\n24h: $time(24h)\n12h: $time(12h)\n\nCombined 1: $time(nodate;24h)\nCombined 2: $time(nodate;12h)\nCombined 3: $time(notime;24h)\nCombined 4: $time(notime;12h)]
"""
)

bot.run("BOT_TOKEN")