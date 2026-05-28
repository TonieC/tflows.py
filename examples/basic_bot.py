from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
    name="test",
    code="""
send Hello from tflow
log Command executed
"""
)

bot.run("BOT_TOKEN")