"""Tests for slash commands: registration, params, and execution."""

import pytest

from tests.fakes import FakeChannel, FakeGuild, FakeMessage, FakeUser, make_bot
from tflows.slash import parse_slash_params


class FakeSlashResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeSlashFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeInteraction:
    def __init__(self, user=None, channel=None, guild=None):
        self.user = user or FakeUser()
        self.channel = channel or FakeChannel()
        self.guild = guild if guild is not None else FakeGuild()
        self.response = FakeSlashResponse()
        self.followup = FakeSlashFollowup()


@pytest.fixture
def bot():
    return make_bot()


def test_parse_slash_params():
    assert parse_slash_params(None) == []
    assert parse_slash_params(["name"]) == [("name", str)]
    assert parse_slash_params(["count: int"]) == [("count", int)]
    assert parse_slash_params([("x", float)]) == [("x", float)]
    assert parse_slash_params({"flag": bool}) == [("flag", bool)]
    with pytest.raises(ValueError):
        parse_slash_params(["a", "a"])
    with pytest.raises(ValueError):
        parse_slash_params([("x", list)])


async def test_slash_registers_tree_command(bot):
    bot.command("greet", "send hi", slash=True)
    app_cmd = bot.tree.get_command("greet")
    assert app_cmd is not None
    assert bot.slash_commands["greet"] is app_cmd


async def test_slashcommand_helper(bot):
    cmd = bot.slashcommand("roll", "send rolled $arg(0)", params=["sides: int"])
    assert cmd.slash is True
    assert cmd.slash_params == [("sides", int)]
    assert bot.tree.get_command("roll") is not None


async def test_prefix_still_works_with_slash(bot):
    bot.command("greet", "reply Hello $args!", slash=True)
    message = FakeMessage(content="!greet Bob", client=bot)
    await bot.on_message(message)
    assert message.replied == [(("Hello Bob!",), {})]


async def test_slash_executes_script_with_positional_args(bot):
    bot.command("greet", "send Hello $arg(0)! Count $argcount", slash=True, slash_params=["name"])
    app_cmd = bot.tree.get_command("greet")
    interaction = FakeInteraction()
    await app_cmd.callback(interaction, name="Bob")
    assert interaction.response.messages[0][0] == "Hello Bob! Count 1"


async def test_slash_named_arg_access(bot):
    bot.command("greet", "send Hi $arg(name)", slash=True, slash_params=["name"])
    app_cmd = bot.tree.get_command("greet")
    interaction = FakeInteraction()
    await app_cmd.callback(interaction, name="Ada")
    assert interaction.response.messages[0][0] == "Hi Ada"


async def test_slash_no_params(bot):
    bot.command("ping", "send pong $argcount", slash=True)
    app_cmd = bot.tree.get_command("ping")
    interaction = FakeInteraction()
    await app_cmd.callback(interaction)
    assert interaction.response.messages[0][0] == "pong 0"


async def test_slash_typed_params(bot):
    bot.command(
        "add",
        "send Sum $arg(0) $arg(1)",
        slash=True,
        slash_params=["a: int", "b: int"],
    )
    app_cmd = bot.tree.get_command("add")
    interaction = FakeInteraction()
    await app_cmd.callback(interaction, a=2, b=3)
    assert interaction.response.messages[0][0] == "Sum 2 3"


async def test_slash_uses_interaction_user(bot):
    bot.command("who", "send I am $user(name)", slash=True)
    app_cmd = bot.tree.get_command("who")
    interaction = FakeInteraction(user=FakeUser(id=5, name="Slashy"))
    await app_cmd.callback(interaction)
    assert interaction.response.messages[0][0] == "I am Slashy"


async def test_slash_reregister_replaces(bot):
    bot.command("dup", "send one", slash=True)
    first = bot.tree.get_command("dup")
    bot.command("dup", "send two", slash=True)
    second = bot.tree.get_command("dup")
    assert second is not first
    interaction = FakeInteraction()
    await second.callback(interaction)
    assert interaction.response.messages[0][0] == "two"


async def test_slash_and_prefix_and_events_coexist(bot):
    channel = FakeChannel()
    guild = FakeGuild()
    guild.system_channel = channel
    member = FakeUser(id=21, name="Joiner")
    member.guild = guild
    bot.command("ping", "send pong", slash=True)
    bot.on_event("join", "send welcome")
    await bot.dispatch_event("on_member_join", member)
    message = FakeMessage(content="!ping", client=bot)
    await bot.on_message(message)
    interaction = FakeInteraction()
    await bot.tree.get_command("ping").callback(interaction)
    assert channel.sent == [(("welcome",), {})]
    assert message.channel.sent == [(("pong",), {})]
    assert interaction.response.messages[0][0] == "pong"
