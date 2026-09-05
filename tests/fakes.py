"""Shared fake Discord objects used across the test suite.

These fakes implement just enough of the discord.py API surface for the tflows
engine, bot, and function modules to run without a network connection.
"""

import asyncio
from datetime import datetime, timezone

from tflows import FlowBot
from tflows.context import FlowContext


class FakeUser:
    def __init__(self, id=123, name="Tester", bot=False):
        self.id = id
        self.name = name
        self.display_name = name
        self.bot = bot
        self.mention = f"<@{id}>"
        self.created_at = datetime(2020, 1, 1)
        self.joined_at = datetime(2021, 6, 1)
        self.display_avatar = type("A", (), {"url": f"https://example.com/{id}.png"})()
        self.roles = []
        self.guild_permissions = FakePermissions()

    def __str__(self):
        return self.name


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakePermissions:
    def __init__(self, **kwargs):
        self.manage_messages = kwargs.get("manage_messages", True)
        self.administrator = kwargs.get("administrator", False)
        self.kick_members = kwargs.get("kick_members", False)
        self.ban_members = kwargs.get("ban_members", False)
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeGuild:
    def __init__(self, members=None):
        self.name = "Test Guild"
        self.id = 999
        self.member_count = 10
        self.premium_subscription_count = 3
        self.premium_tier = 2
        self.icon = None
        self.owner = None
        self.description = "A test guild"
        self.created_at = datetime(2019, 1, 1)
        self.members = members or [FakeUser(i, f"User{i}") for i in range(8)]
        self.me = FakeUser(id=1, name="TestBot", bot=True)
        self.system_channel = None

    def permissions_for(self, user):
        return FakePermissions()


class FakeChannel:
    def __init__(self, name="general", permissions=None):
        self.name = name
        self.id = 555
        self.topic = "General discussion"
        self.nsfw = False
        self.type = "text"
        self.position = 1
        self.created_at = datetime(2020, 5, 5)
        self.category = type("C", (), {"name": "Text Channels"})()
        self.mention = f"<#{self.id}>"
        self.sent = []
        self.purged = []
        self._permissions = permissions if permissions is not None else FakePermissions()

    def permissions_for(self, user):
        return self._permissions

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))
        return None

    async def purge(self, *, limit, check=None):
        self.purged.append(limit)
        return []


class FakeState:
    def __init__(self, client=None):
        self._client = client

    def _get_client(self):
        return self._client


class FakeMessage:
    def __init__(self, content="", author=None, channel=None, guild=None, client=None):
        self.content = content
        self.author = author or FakeUser()
        self.channel = channel or FakeChannel()
        self.guild = guild or FakeGuild()
        self.mentions = []
        self._state = FakeState(client)
        self.created_at = datetime(2022, 2, 2, tzinfo=timezone.utc)
        self.deleted = False
        self.replied = []
        self.reactions = []
        self.attachments = []
        self.embeds = []
        self.components = []
        self.sticker_items = []
        self.stickers = []
        self.nonce = None
        self.reference = None
        self.pinned = False
        self.tts = False
        self.edited_at = None
        self.type = 0

    async def reply(self, *args, **kwargs):
        self.replied.append((args, kwargs))
        return None

    async def add_reaction(self, emoji):
        self.reactions.append(emoji)
        return None

    async def delete(self):
        self.deleted = True
        return None


def make_bot(**kwargs):
    kwargs.setdefault("state_path", ":memory:")
    bot = FlowBot(prefix=kwargs.pop("prefix", "!"), **kwargs)
    bot._connection.user = FakeUser(id=1, name="TestBot", bot=True)
    return bot


def make_bot_ready(bot):
    """Simulate a connected bot so ``process_commands`` works in tests."""
    bot.loop = asyncio.get_running_loop()
    bot._ready = asyncio.Event()
    bot._ready.set()
    return bot


def make_ctx(bot=None, content="!test", args="", command_name="test", message=None):
    bot = bot or make_bot()
    message = message or FakeMessage(content=content, client=bot)
    return FlowContext(message=message, bot=bot, command_name=command_name, args=args)
