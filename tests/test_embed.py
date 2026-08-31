from tests.fakes import FakeMessage


async def test_embed_function_single_line(bot):
    bot.command("info", "embed $embed<title: Hello>")
    message = FakeMessage(content="!info", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.title == "Hello"


async def test_embed_function_multiple_keys(bot):
    bot.command("info", "embed $embed<title: Hi | desc: Welcome | footer: Bye>")
    message = FakeMessage(content="!info", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.title == "Hi"
    assert embed.description == "Welcome"
    assert embed.footer.text == "Bye"


async def test_embed_function_resolves_vars(bot):
    bot.command("info", "embed $embed<title: Hello $user(name)>")
    message = FakeMessage(content="!info", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.title == "Hello Tester"


async def test_embed_function_fields(bot):
    bot.command("info", "embed $embed<field: A;B | field: C;D;true>")
    message = FakeMessage(content="!info", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert [(f.name, f.value) for f in embed.fields] == [("A", "B"), ("C", "D")]
    assert embed.fields[0].inline is False
    assert embed.fields[1].inline is True


async def test_embed_function_named_color(bot):
    bot.command("info", "embed $embed<title: X | color: green>")
    message = FakeMessage(content="!info", client=bot)
    await bot.on_message(message)
    embed = message.channel.sent[0][1]["embed"]
    assert embed.color.value == 0x2ECC71


async def test_embed_function_invalid_format(bot):
    bot.command("info", "embed invalid")
    message = FakeMessage(content="!info", client=bot)
    await bot.on_message(message)
    assert message.channel.sent[0][0][0] == "Invalid embed format"
