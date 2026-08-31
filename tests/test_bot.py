from discord.ext import commands as dpy_commands

from tests.fakes import FakeMessage, make_bot, make_bot_ready


async def test_command_registration(bot):
    bot.command("greet", "send hi", description="Says hi", aliases=("hello",))
    assert bot.commands_map["greet"] == "send hi"
    assert bot.commands_map["hello"] == "send hi"
    assert bot.script_commands["greet"].name == "greet"
    assert bot.script_commands["greet"].description == "Says hi"
    assert bot.script_commands["greet"].aliases == ("hello",)
    assert bot.script_commands["greet"].all_names == ("greet", "hello")


async def test_command_returns_script_command(bot):
    command = bot.command("x", "log x")
    assert command.name == "x"
    assert command.code == "log x"


async def test_on_message_runs_script(bot):
    bot.command("greet", "reply hi $user(name)")
    message = FakeMessage(content="!greet john", client=bot)
    await bot.on_message(message)
    assert message.replied == [(("hi Tester",), {})]


async def test_on_message_passes_args(bot):
    bot.command("echo", "send $args")
    message = FakeMessage(content="!echo one two", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == [(("one two",), {})]


async def test_on_message_alias_runs_command(bot):
    bot.command("greet", "reply hello", aliases=("hello", "hey"))
    message = FakeMessage(content="!hello", client=bot)
    await bot.on_message(message)
    assert message.replied == [(("hello",), {})]


async def test_on_message_ignores_bot_authors(bot):
    bot.command("greet", "send hi")
    message = FakeMessage(content="!greet", client=bot)
    message.author.bot = True
    await bot.on_message(message)
    assert message.channel.sent == []


async def test_on_message_no_prefix_falls_through(bot):
    message = FakeMessage(content="plain text", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == []


async def test_case_insensitive_commands(bot):
    bot = make_bot(case_insensitive=True)
    bot.command("GREET", "send hi")
    message = FakeMessage(content="!greet", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == [(("hi",), {})]


async def test_case_sensitive_by_default(bot):
    bot.command("GREET", "send hi")
    message = FakeMessage(content="!greet", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == []


async def test_multiple_prefixes(bot):
    bot = make_bot(prefix=["!", "?"])
    bot.command("ping", "send pong")
    message = FakeMessage(content="?ping", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == [(("pong",), {})]


async def test_script_error_logged_not_raised(bot, caplog):
    bot.command("bad", "explode")

    @bot.engine.registry.register("explode")
    async def explode(ctx, args):
        raise RuntimeError("kaboom")

    try:
        message = FakeMessage(content="!bad", client=bot)
        with caplog.at_level("ERROR", logger="tflows.engine"):
            await bot.on_message(message)
        assert any("Error in line: explode" in r.message for r in caplog.records)
    finally:
        bot.engine.registry.unregister("explode")


async def test_discord_commands_still_work(bot):
    make_bot_ready(bot)
    invoked = []

    async def my_cmd(ctx):
        invoked.append(ctx.message.content)

    bot.add_command(dpy_commands.Command(my_cmd, name="dpy"))
    message = FakeMessage(content="!dpy", client=bot)
    await bot.on_message(message)
    assert invoked == ["!dpy"]


async def test_script_command_takes_precedence_over_discord(bot):
    make_bot_ready(bot)
    invoked = []

    async def my_cmd(ctx):
        invoked.append("discord")

    bot.add_command(dpy_commands.Command(my_cmd, name="overlap"))
    bot.command("overlap", "send script")

    message = FakeMessage(content="!overlap", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == [(("script",), {})]
    assert invoked == []


# ---------------------------------------------------------------------------
# Built-in help command
# ---------------------------------------------------------------------------
async def test_help_lists_commands(bot):
    bot.command("greet", "reply hi", description="Says hi")
    bot.command("ping", "send pong")
    message = FakeMessage(content="!help", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.title == "Script Commands"
    names = [f.name for f in embed.fields]
    assert "!greet" in names
    assert "!ping" in names


async def test_help_command_details(bot):
    bot.command("greet", "reply hi $user(name)", description="Says hi", aliases=("hello",))
    message = FakeMessage(content="!help greet", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert "greet" in embed.title
    assert any("Says hi" in f.value for f in embed.fields)
    assert any("hello" in f.value for f in embed.fields)


async def test_help_unknown_command(bot):
    message = FakeMessage(content="!help nope", client=bot)
    await bot.on_message(message)
    assert message.channel.sent[0][0][0] == "No command named `nope` was found."


async def test_help_disabled(bot):
    bot = make_bot(help_command=False)
    bot.command("greet", "send hi")
    message = FakeMessage(content="!help", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == []


async def test_user_defined_help_overrides_builtin(bot):
    bot.command("help", "send custom help")
    message = FakeMessage(content="!help", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == [(("custom help",), {})]


async def test_custom_registry_isolation():
    from tflows import FunctionRegistry

    reg = FunctionRegistry()

    @reg.register("special")
    async def special(ctx, args):
        await ctx.channel.send("custom")

    bot = make_bot(registry=reg)
    bot.command("run", "special")
    message = FakeMessage(content="!run", client=bot)
    await bot.on_message(message)
    assert message.channel.sent == [(("custom",), {})]

    # The shared default registry is untouched.
    from tflows.registry import registry as default_registry

    assert default_registry.get("special") is None


async def test_help_no_commands(bot):
    message = FakeMessage(content="!help", client=bot)
    await bot.on_message(message)
    assert message.channel.sent[0][0][0] == "No script commands registered yet."
