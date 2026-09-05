"""Tests for `cooldown` / `require` guard directives and role variables."""

import pytest

from tests.fakes import FakeMessage, FakePermissions, FakeRole, FakeUser, make_bot, make_ctx


async def run(bot, code, args="", message=None):
    message = message or FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message


def sent_text(message):
    return [args[0] for args, _ in message.channel.sent if args]


@pytest.fixture
def bot():
    return make_bot()


# ---------------------------------------------------------------------------
# Cooldowns
# ---------------------------------------------------------------------------
async def test_cooldown_first_run_executes(bot):
    message = await run(bot, "cooldown 60s per user\nsend hi")
    assert sent_text(message) == ["hi"]


async def test_cooldown_blocks_second_run(bot):
    m1 = FakeMessage(content="!t", client=bot)
    await bot.engine.run(make_ctx(bot, message=m1, command_name="limited"), "cooldown 60s per user\nsend hi")
    assert sent_text(m1) == ["hi"]
    m2 = FakeMessage(content="!t", client=bot)
    await bot.engine.run(make_ctx(bot, message=m2, command_name="limited"), "cooldown 60s per user\nsend hi")
    texts = sent_text(m2)
    assert len(texts) == 1 and "wait" in texts[0].lower()
    assert "hi" not in texts


async def test_cooldown_scope_per_user(bot):
    code = "cooldown 60s per user\nsend hi"
    m1 = FakeMessage(content="!t", client=bot)
    await bot.engine.run(make_ctx(bot, message=m1, command_name="scoped"), code)
    assert sent_text(m1) == ["hi"]
    # Different user is not on cooldown.
    m2 = FakeMessage(content="!t", client=bot, author=FakeUser(id=999, name="Other"))
    await bot.engine.run(make_ctx(bot, message=m2, command_name="scoped"), code)
    assert sent_text(m2) == ["hi"]


async def test_cooldown_scope_guild(bot):
    code = "cooldown 60s per guild\nsend hi"
    await bot.engine.run(make_ctx(bot, message=FakeMessage(content="!t", client=bot), command_name="gscope"), code)
    m2 = FakeMessage(content="!t", client=bot, author=FakeUser(id=999, name="Other"))
    ctx2 = make_ctx(bot, message=m2, command_name="gscope")
    await bot.engine.run(ctx2, code)
    assert "hi" not in sent_text(m2)


async def test_cooldown_reset_allows_rerun(bot):
    code = "cooldown 60s per user\nsend hi"
    await bot.engine.run(make_ctx(bot, message=FakeMessage(content="!t", client=bot), command_name="rc"), code)
    bot.cooldowns.reset("rc")
    m2 = FakeMessage(content="!t", client=bot)
    await bot.engine.run(make_ctx(bot, message=m2, command_name="rc"), code)
    assert sent_text(m2) == ["hi"]


async def test_cooldown_entries_pruned(bot):
    manager = bot.cooldowns
    now = manager._time()
    manager._expires = {(f"cmd{i}", "user", "user:1"): now - 1 for i in range(600)}
    manager._expires[("fresh", "user", "user:1")] = now + 60
    manager.check("newcmd", "user", "user:2", 60)
    assert len(manager._expires) < 600
    assert ("fresh", "user", "user:1") in manager._expires


async def test_invalid_cooldown_syntax_warns_and_continues(bot):
    message = await run(bot, "cooldown banana\nsend hi")
    texts = sent_text(message)
    assert "hi" in texts
    assert any("cooldown" in t.lower() for t in texts)


async def test_cooldown_in_prefix_command(bot):
    bot.command("fast", "cooldown 60s per user\nsend zoom")
    m1 = FakeMessage(content="!fast", client=bot)
    await bot.on_message(m1)
    assert sent_text(m1) == ["zoom"]
    m2 = FakeMessage(content="!fast", client=bot)
    await bot.on_message(m2)
    assert "zoom" not in sent_text(m2)


# ---------------------------------------------------------------------------
# Permission guards
# ---------------------------------------------------------------------------
def deny_all(message):
    message.author.guild_permissions = FakePermissions(manage_messages=False)
    message.channel._permissions = FakePermissions(manage_messages=False)
    return message


async def test_require_passes_by_default(bot):
    message = await run(bot, "require manage_messages\nsend ok")
    assert sent_text(message) == ["ok"]


async def test_require_blocks_without_permission(bot):
    message = deny_all(FakeMessage(content="!t", client=bot))
    ctx = make_ctx(bot, message=message)
    await bot.engine.run(ctx, "require manage_messages\nsend secret")
    texts = sent_text(message)
    assert texts == ["You do not have permission to use this command."]


async def test_require_role(bot):
    author = FakeUser()
    author.roles = [FakeRole("Moderator")]
    message = await run(bot, "require role Moderator\nsend ok", message=FakeMessage(content="!t", client=bot, author=author))
    assert sent_text(message) == ["ok"]
    plain = deny_all(FakeMessage(content="!t", client=bot))
    ctx = make_ctx(bot, message=plain)
    await bot.engine.run(ctx, "require role Moderator\nsend secret")
    assert "secret" not in sent_text(plain)


async def test_require_owner(bot):
    author = FakeUser(id=42, name="Owner")
    guild_owner = FakeMessage(content="!t", client=bot, author=author)
    guild_owner.guild.owner = author
    message = await run(bot, "require owner\nsend ok", message=guild_owner)
    assert sent_text(message) == ["ok"]
    stranger = FakeMessage(content="!t", client=bot)
    message2 = await run(bot, "require owner\nsend secret", message=stranger)
    assert "secret" not in sent_text(message2)


async def test_invalid_require_fails_closed(bot):
    message = await run(bot, "require\nsend secret")
    # `require` alone is not a valid directive; engine treats it as such.
    assert "secret" not in sent_text(message)


async def test_hasrole_hasperm_isowner_vars(bot):
    author = FakeUser()
    author.roles = [FakeRole("Helper")]
    message = await run(
        bot,
        "send $hasrole(Helper) $hasrole(Admin) $hasperm(manage_messages) $isowner",
        message=FakeMessage(content="!t", client=bot, author=author),
    )
    assert sent_text(message) == ["true false true false"]


async def test_guards_combine_with_conditionals(bot):
    code = "require manage_messages\nif $argcount > 0:\n    send $args\nelse:\n    send empty"
    message = await run(bot, code, args="hello")
    assert sent_text(message) == ["hello"]
