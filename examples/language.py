"""tflows 1.1 language: locals, loops, functions, components, JSON, import.

Run with:  python examples/language.py
"""

from tflows import FlowBot
import os


bot = FlowBot(prefix="!")

bot.command(
    name="hello",
    code="""
let name = $arg(0)
if name == "":
    let name = $user(display)
send Hello $name
    """,
    description="Greet someone with a local.",
)

bot.command(
    name="count",
    code="""
repeat 3:
    send $i
    """,
    description="Count 0, 1, 2.",
)

bot.command(
    name="greetfn",
    code="""
function greet(name):
    return Hello $name
send $greet($arg(0))
    """,
    description="Call a script function.",
)

bot.command(
    name="menu",
    code="""
button "Click me" id="hello-btn":
    reply You clicked the button!
send Pick a button:
    """,
    description="Send a button.",
)

bot.command(
    name="colors",
    code="""
select id="color" placeholder="Pick a color":
    option "Red" value="red"
    option "Blue" value="blue"
    send You picked $value
    """,
    description="Send a select menu.",
)

bot.command(
    name="parse",
    code="""
let data = json.parse {"name": "Ada", "role": "admin"}
send $data[name] is $data[role]
    """,
    description="Parse JSON in a script.",
)

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Set DISCORD_TOKEN to run this example.")
