"""
Tflows Everything Bot
=====================

A showcase Discord bot demonstrating many different things
that can be built with Tflows.

Set your token:
    Windows:
        set DISCORD_TOKEN=your_token

    Linux/macOS:
        export DISCORD_TOKEN=your_token
"""

from tflows import FlowBot
import os
import random
import time


bot = FlowBot(prefix="!")


# ============================================================
# AUTOMATION
# ============================================================

bot.command(
    name="ping",
    code="""
delete
send Pong! $ping ms
""",
    description="Shows bot latency.",
)


bot.command(
    name="slow",
    code="""
react ⏳
wait 3s
react ✅
reply Done waiting!
""",
    description="Demonstrates delayed execution.",
)


bot.command(
    name="clear",
    code="""
clear 5
""",
    description="Deletes the last 5 messages.",
)


# ============================================================
# COMMUNITY
# ============================================================

bot.command(
    name="hello",
    code="""
react 👋
send Hello, $user!
""",
    description="Greets the user.",
)


bot.command(
    name="welcome",
    code="""
embed
title Welcome!
desc Welcome to $server, $user!
footer Enjoy your stay.
endembed
""",
    description="Creates a welcome-style embed.",
)


bot.command(
    name="serverinfo",
    code="""
embed
title Server Information
desc Server: $server
desc Members: $membercount
desc Channel: $channel
desc Owner: $owner
endembed
""",
    description="Displays server information.",
)


bot.command(
    name="userinfo",
    code="""
embed
title User Information
desc User: $user
desc ID: $userid
desc Server: $server
endembed
""",
    description="Displays information about the current user.",
)


# ============================================================
# FUN
# ============================================================

bot.command(
    name="coinflip",
    code="""
send The coin landed on $random(Heads,Tails)!
""",
    description="Flips a coin.",
)


bot.command(
    name="dice",
    code="""
send You rolled: $random(1,2,3,4,5,6)
""",
    description="Rolls a dice.",
)


bot.command(
    name="8ball",
    code="""
send 🎱 $random(Yes,No,Maybe,Probably,Probably not,Ask again later)
""",
    description="Ask the magic 8-ball.",
)


# ============================================================
# MODERATION
# ============================================================

def warn_user(ctx, member_id, reason="No reason provided"):
    """
    Example custom moderation function.

    This demonstrates how Tflows can be extended with
    normal Python/discord.py functionality.
    """
    return f"⚠️ User {member_id} warned: {reason}"


def kick_user(ctx, member_id, reason="No reason provided"):
    """
    Example custom kick function.

    Replace this with the appropriate discord.py member
    lookup and kick implementation for production use.
    """
    return f"👢 User {member_id} would be kicked: {reason}"


def ban_user(ctx, member_id, reason="No reason provided"):
    """
    Example custom ban function.
    """
    return f"🔨 User {member_id} would be banned: {reason}"


def timeout_user(ctx, member_id, minutes=10):
    """
    Example custom timeout function.
    """
    return f"⏱️ User {member_id} would be timed out for {minutes} minutes."


# Register custom Python functions if the registry is available.
try:
    bot.registry.register("warn", warn_user)
    bot.registry.register("kick", kick_user)
    bot.registry.register("ban", ban_user)
    bot.registry.register("timeout", timeout_user)
except AttributeError:
    pass


bot.command(
    name="warn",
    code="""
warn $arg1 $args
""",
    description="Warns a member.",
)


bot.command(
    name="kick",
    code="""
kick $arg1 $args
""",
    description="Kicks a member.",
)


bot.command(
    name="ban",
    code="""
ban $arg1 $args
""",
    description="Bans a member.",
)


bot.command(
    name="timeout",
    code="""
timeout $arg1 $arg2
""",
    description="Times out a member.",
)


# ============================================================
# EMBEDS
# ============================================================

bot.command(
    name="rules",
    code="""
embed
title Server Rules
desc 1. Be respectful.
desc 2. No spam.
desc 3. No harassment.
desc 4. Follow Discord's Terms of Service.
desc 5. Have fun.
footer Server Rules
endembed
""",
    description="Displays server rules.",
)


bot.command(
    name="announce",
    code="""
embed
title Announcement
desc $args
footer Server Announcement
endembed
""",
    description="Creates an announcement embed.",
)


# ============================================================
# POLL
# ============================================================

bot.command(
    name="poll",
    code="""
embed
title 📊 Poll
desc $args
footer React below to vote.
endembed
react 👍
react 👎
""",
    description="Creates a simple poll.",
)


# ============================================================
# ECONOMY
# ============================================================

economy = {}
daily_claims = {}


def get_balance(ctx, user_id):
    return economy.get(str(user_id), 0)


def add_money(ctx, user_id, amount):
    user_id = str(user_id)
    economy[user_id] = economy.get(user_id, 0) + int(amount)
    return economy[user_id]


def work(ctx, user_id):
    amount = random.randint(50, 250)

    user_id = str(user_id)
    economy[user_id] = economy.get(user_id, 0) + amount

    return amount


def daily(ctx, user_id):
    user_id = str(user_id)

    now = time.time()
    last = daily_claims.get(user_id, 0)

    if now - last < 86400:
        remaining = int(86400 - (now - last))
        hours = remaining // 3600

        return f"Daily already claimed. Try again in {hours}h."

    amount = 500

    economy[user_id] = economy.get(user_id, 0) + amount
    daily_claims[user_id] = now

    return f"You received ${amount}!"


try:
    bot.registry.register("balance", get_balance)
    bot.registry.register("addmoney", add_money)
    bot.registry.register("work", work)
    bot.registry.register("daily", daily)
except AttributeError:
    pass


bot.command(
    name="balance",
    code="""
send 💰 Balance: $$balance $userid
""",
    description="Checks your balance.",
)


bot.command(
    name="work",
    code="""
send 💼 You earned $$work $userid!
""",
    description="Works for money.",
)


bot.command(
    name="daily",
    code="""
send 🎁 $daily $userid
""",
    description="Claims the daily reward.",
)


# ============================================================
# XP / LEVELING
# ============================================================

xp = {}


def give_xp(ctx, user_id):
    user_id = str(user_id)

    amount = random.randint(10, 25)

    xp[user_id] = xp.get(user_id, 0) + amount

    level = int((xp[user_id] / 100) ** 0.5)

    return amount, level


def get_xp(ctx, user_id):
    return xp.get(str(user_id), 0)


try:
    bot.registry.register("givexp", give_xp)
    bot.registry.register("getxp", get_xp)
except AttributeError:
    pass


bot.command(
    name="xp",
    code="""
send ⭐ You have $getxp $userid XP.
""",
    description="Shows your XP.",
)


bot.command(
    name="level",
    code="""
send 🏆 Your current level is based on $getxp $userid XP.
""",
    description="Shows your level.",
)


# ============================================================
# REMINDER
# ============================================================

bot.command(
    name="remind",
    code="""
send ⏰ Reminder created: $args
wait 10s
send 🔔 Reminder: $args
""",
    description="Demonstrates delayed reminders.",
)


# ============================================================
# REACTION ROLE STYLE COMMAND
# ============================================================

bot.command(
    name="roles",
    code="""
embed
title Choose Your Role
desc React with the appropriate emoji to select a role.
desc
desc 🟦 — Gamer
desc 🟩 — Programmer
desc 🟥 — Artist
desc 🟨 — Student
endembed
react 🟦
react 🟩
react 🟥
react 🟨
""",
    description="Creates a reaction-based role menu.",
)


# ============================================================
# STATUS
# ============================================================

bot.command(
    name="status",
    code="""
embed
title Bot Status
desc 🟢 Online
desc Ping: $ping ms
desc Server: $server
desc Channel: $channel
endembed
""",
    description="Shows bot status.",
)


# ============================================================
# HELP
# ============================================================

bot.command(
    name="about",
    code="""
embed
title Tflows Everything Bot
desc A demonstration bot built using Tflows.
desc
desc Features:
desc • Automation
desc • Moderation
desc • Economy
desc • XP
desc • Polls
desc • Embeds
desc • Utilities
desc • Community tools
desc • Custom Python functions
desc
desc Prefix: !
endembed
""",
    description="Shows information about this bot.",
)


# ============================================================
# START BOT
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN environment variable is not set."
    )

bot.run(TOKEN)