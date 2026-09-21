"""tflows 1.3.0: delete/edit events, sendto/embedto, $dm, $errormsg, $before/$after."""

import asyncio

import pytest

from tests.fakes import FakeChannel, FakeGuild, FakeMessage, FakeUser, make_bot, make_ctx
from tflows.diagnostics import check_source
from tflows.events import EVENT_MAP, normalize_event
from tflows.function.send import expand_recipients


@pytest.fixture
def bot():
    return make_bot()


def sent(channel):
    return [args[0] for args, _ in channel.sent if args]


def dms(user):
    return [args[0] for args, _ in user.dms if args]


def attach_channel(bot, channel):
    cache = getattr(bot, "_tflow_channels", None)
    if cache is None:
        cache = {}
        bot._tflow_channels = cache

        def get_channel(cid):
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                return None
            return cache.get(cid)

        async def fetch_channel(cid):
            try:
                cid = int(cid)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid channel id: {cid}") from exc
            found = cache.get(cid)
            if found is None:
                raise LookupError(f"channel not found: {cid}")
            return found

        bot.get_channel = get_channel
        bot.fetch_channel = fetch_channel
    cache[int(channel.id)] = channel
    return channel


def attach_user(bot, user):
    cache = getattr(bot, "_tflow_users", None)
    if cache is None:
        cache = {}
        bot._tflow_users = cache

        def get_user(uid):
            try:
                uid = int(uid)
            except (TypeError, ValueError):
                return None
            return cache.get(uid)

        async def fetch_user(uid):
            try:
                uid = int(uid)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid user id: {uid}") from exc
            found = cache.get(uid)
            if found is None:
                raise LookupError(f"user not found: {uid}")
            return found

        bot.get_user = get_user
        bot.fetch_user = fetch_user
    cache[int(user.id)] = user
    return user


def deleted_message(bot, *, content="gone", author=None, channel=None, guild=None):
    return FakeMessage(
        content=content,
        author=author or FakeUser(id=123456789, name="Alice"),
        channel=channel or FakeChannel(),
        guild=guild or FakeGuild(),
        client=bot,
    )


# ---------------------------------------------------------------------------
# Event mapping / aliases
# ---------------------------------------------------------------------------
def test_delete_edit_event_map():
    assert EVENT_MAP["delete"] == "on_message_delete"
    assert EVENT_MAP["edit"] == "on_message_edit"
    assert EVENT_MAP["message_delete"] == "on_message_delete"
    assert EVENT_MAP["message_edit"] == "on_message_edit"
    assert normalize_event("delete") == "on_message_delete"
    assert normalize_event("message_delete") == "on_message_delete"
    assert normalize_event("edit") == "on_message_edit"
    assert normalize_event("message_edit") == "on_message_edit"


async def test_delete_event_dispatch(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("delete", "sendto 1437 deleted: $content")
    message = deleted_message(bot, content="secret")
    await bot.dispatch_event("on_message_delete", message)
    assert sent(dest) == ["deleted: secret"]


async def test_delete_alias_message_delete(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("message_delete", "sendto 1437 deleted: $content")
    await bot.dispatch_event("on_message_delete", deleted_message(bot, content="alias"))
    assert sent(dest) == ["deleted: alias"]


async def test_edit_event_dispatch(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("edit", "sendto 1437 before: $before after: $after")
    channel = FakeChannel()
    author = FakeUser(id=9, name="Ed")
    before = FakeMessage(content="old text", author=author, channel=channel, client=bot)
    after = FakeMessage(content="new text", author=author, channel=channel, client=bot)
    await bot.dispatch_event("on_message_edit", before, after)
    assert sent(dest) == ["before: old text after: new text"]


async def test_edit_alias_message_edit(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=99))
    bot.on_event("message_edit", "sendto 99 $before|$after")
    channel = FakeChannel()
    author = FakeUser(id=9, name="Ed")
    before = FakeMessage(content="a", author=author, channel=channel, client=bot)
    after = FakeMessage(content="b", author=author, channel=channel, client=bot)
    await bot.dispatch_event("on_message_edit", before, after)
    assert sent(dest) == ["a|b"]


async def test_delete_ignores_bot_authors(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("delete", "sendto 1437 deleted: $content")
    message = deleted_message(bot, content="botmsg", author=FakeUser(id=1, name="Bot", bot=True))
    await bot._tflow_on_message_delete(message)
    assert dest.sent == []


async def test_edit_ignores_bot_authors(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("edit", "sendto 1437 edited")
    bot_user = FakeUser(id=1, name="Bot", bot=True)
    channel = FakeChannel()
    before = FakeMessage(content="a", author=bot_user, channel=channel, client=bot)
    after = FakeMessage(content="b", author=bot_user, channel=channel, client=bot)
    await bot._tflow_on_message_edit(before, after)
    assert dest.sent == []


async def test_delete_script_failure_does_not_crash_bot(bot, caplog):
    bot.on_event("delete", "explode now")

    @bot.engine.registry.register("explode")
    async def explode(ctx, args):
        raise RuntimeError("boom")

    try:
        with caplog.at_level("ERROR"):
            await bot.dispatch_event("on_message_delete", deleted_message(bot))
    finally:
        bot.engine.registry.unregister("explode")


# ---------------------------------------------------------------------------
# Context: $content $message $before $after
# ---------------------------------------------------------------------------
async def test_delete_before_after_and_message_vars(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=7))
    bot.on_event(
        "delete",
        "sendto 7 content=$content before=$before after=[$after] id=$message(id)",
    )
    message = deleted_message(bot, content="bye")
    message.id = 4242
    await bot.dispatch_event("on_message_delete", message)
    assert sent(dest) == ["content=bye before=bye after=[] id=4242"]


async def test_edit_content_is_after(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=8))
    bot.on_event("edit", "sendto 8 $content|$message|$before|$after")
    channel = FakeChannel()
    author = FakeUser(id=3, name="Ed")
    before = FakeMessage(content="old", author=author, channel=channel, client=bot)
    after = FakeMessage(content="new", author=author, channel=channel, client=bot)
    after.id = 77
    await bot.dispatch_event("on_message_edit", before, after)
    assert sent(dest) == ["new|new|old|new"]


# ---------------------------------------------------------------------------
# where filtering
# ---------------------------------------------------------------------------
async def test_where_user_matches_name_not_id(bot):
    channel = FakeChannel(name="welcome")
    guild = FakeGuild()
    guild.system_channel = channel
    tester = FakeUser(id=7, name="Tester")
    tester.guild = guild
    bot.on_event("join", "send Welcome", where="user == Tester")
    await bot.dispatch_event("on_member_join", tester)
    assert [a[0] for a, _ in channel.sent] == ["Welcome"]
    other = FakeUser(id=8, name="Other")
    other.guild = guild
    await bot.dispatch_event("on_member_join", other)
    assert [a[0] for a, _ in channel.sent] == ["Welcome"]


async def test_delete_where_user_name(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("delete", "sendto 1437 deleted: $content", where="user == Alice")
    match = deleted_message(bot, content="keep", author=FakeUser(id=99, name="Alice"))
    other = deleted_message(bot, content="skip", author=FakeUser(id=1, name="Bob"))
    await bot.dispatch_event("on_message_delete", match)
    await bot.dispatch_event("on_message_delete", other)
    assert sent(dest) == ["deleted: keep"]


async def test_delete_where_user_id(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("delete", "sendto 1437 deleted: $content", where="user_id == 123456789")
    match = deleted_message(bot, content="keep", author=FakeUser(id=123456789, name="Alice"))
    other = deleted_message(bot, content="skip", author=FakeUser(id=1, name="Bob"))
    await bot.dispatch_event("on_message_delete", match)
    await bot.dispatch_event("on_message_delete", other)
    assert sent(dest) == ["deleted: keep"]


async def test_edit_where_user_id_var(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=5))
    bot.on_event("edit", "sendto 5 hit", where="$user_id == 99")
    channel = FakeChannel()
    ok = FakeUser(id=99, name="Ok")
    no = FakeUser(id=1, name="No")
    await bot.dispatch_event(
        "on_message_edit",
        FakeMessage(content="a", author=ok, channel=channel, client=bot),
        FakeMessage(content="b", author=ok, channel=channel, client=bot),
    )
    await bot.dispatch_event(
        "on_message_edit",
        FakeMessage(content="a", author=no, channel=channel, client=bot),
        FakeMessage(content="b", author=no, channel=channel, client=bot),
    )
    assert sent(dest) == ["hit"]


# ---------------------------------------------------------------------------
# sendto
# ---------------------------------------------------------------------------
async def test_sendto_uses_get_channel_then_fetch(bot):
    dest = FakeChannel(name="log", id=1437)
    order = []

    def get_channel(cid):
        order.append(("get", int(cid)))
        return None

    async def fetch_channel(cid):
        order.append(("fetch", int(cid)))
        return dest

    bot.get_channel = get_channel
    bot.fetch_channel = fetch_channel
    message = FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, message=message)
    await bot.engine.run(ctx, "sendto 1437 deleted: hello")
    assert order == [("get", 1437), ("fetch", 1437)]
    assert sent(dest) == ["deleted: hello"]


async def test_sendto_uses_cached_channel_without_fetch(bot):
    dest = FakeChannel(name="log", id=42)
    fetched = []
    bot.get_channel = lambda cid: dest if int(cid) == 42 else None

    async def fetch_channel(cid):
        fetched.append(cid)
        return dest

    bot.fetch_channel = fetch_channel
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "sendto 42 hi")
    assert sent(dest) == ["hi"]
    assert fetched == []


async def test_sendto_invalid_id_does_not_crash(bot, caplog):
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    with caplog.at_level("WARNING"):
        await bot.engine.run(ctx, "sendto nope hello")
    assert ctx.channel.sent == []
    assert "invalid channel id" in (ctx.last_error or "")


async def test_sendto_missing_channel_does_not_crash(bot, caplog):
    bot.get_channel = lambda cid: None

    async def fetch_channel(cid):
        raise LookupError("missing")

    bot.fetch_channel = fetch_channel
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    with caplog.at_level("WARNING"):
        await bot.engine.run(ctx, "sendto 999 missing")
    assert "channel" in (ctx.last_error or "").lower() or "fetch" in (ctx.last_error or "").lower()


async def test_sendto_send_failure_does_not_crash(bot, caplog):
    class BoomChannel(FakeChannel):
        async def send(self, *args, **kwargs):
            raise PermissionError("nope")

    dest = BoomChannel(name="log", id=3)
    bot.get_channel = lambda cid: dest if int(cid) == 3 else None
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    with caplog.at_level("ERROR"):
        await bot.engine.run(ctx, "sendto 3 hi")
    assert "failed to send" in (ctx.last_error or "").lower()


# ---------------------------------------------------------------------------
# embedto
# ---------------------------------------------------------------------------
async def test_embedto_routes_to_channel(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=55))
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(
        ctx,
        "embedto 55\n$title[Hello]\n$desc[World]\nendembed",
    )
    assert dest.sent
    embed = dest.sent[0][1]["embed"]
    assert embed.title == "Hello"
    assert embed.description == "World"
    assert ctx.channel.sent == []


async def test_embedto_failure_does_not_crash(bot, caplog):
    bot.get_channel = lambda cid: None

    async def fetch_channel(cid):
        raise LookupError("gone")

    bot.fetch_channel = fetch_channel
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    with caplog.at_level("WARNING"):
        await bot.engine.run(ctx, "embedto 1\n$title[X]\nendembed")
    assert ctx.last_error


# ---------------------------------------------------------------------------
# $errormsg
# ---------------------------------------------------------------------------
async def test_errormsg_unknown_function(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=11))
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "not_a_real_fn foo\nsendto 11 ERROR: $errormsg")
    out = sent(dest)
    assert out
    assert "unknown function" in out[0].lower()
    assert "not_a_real_fn" in out[0]


async def test_errormsg_sendto_invalid_channel(bot):
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "sendto nope x\nsend ERROR: $errormsg")
    out = sent(ctx.channel)
    assert out
    assert "ERROR:" in out[0]
    assert "invalid channel" in out[0].lower() or "channel" in out[0].lower()


async def test_errormsg_cleared_between_runs(bot):
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "not_a_real_fn foo")
    assert ctx.last_error
    await bot.engine.run(ctx, "send ERROR:[$errormsg]")
    assert sent(ctx.channel) == ["ERROR:[]"]
    assert ctx.last_error == ""


async def test_on_error_event_uses_errormsg(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("error", "sendto 1437 ERROR: $errormsg")
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "not_a_real_fn foo")
    assert sent(dest)
    assert "unknown function" in sent(dest)[0].lower()


async def test_concurrent_on_error_does_not_drop(bot):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    first_entered = asyncio.Event()
    release = asyncio.Event()
    in_handler = 0

    @bot.engine.registry.register("slowerr")
    async def slowerr(ctx, args):
        nonlocal in_handler
        in_handler += 1
        if in_handler == 1:
            first_entered.set()
            await release.wait()

    try:
        bot.on_event("error", "slowerr\nsendto 1437 ERROR: $errormsg")
        ctx1 = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
        ctx2 = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
        task1 = asyncio.create_task(bot.engine.run(ctx1, "nope_fn_one"))
        await asyncio.wait_for(first_entered.wait(), timeout=2)
        task2 = asyncio.create_task(bot.engine.run(ctx2, "nope_fn_two"))
        await asyncio.sleep(0.05)
        release.set()
        await asyncio.gather(task1, task2)
        texts = sent(dest)
        assert len(texts) == 2
        assert all("unknown function" in text.lower() for text in texts)
    finally:
        bot.engine.registry.unregister("slowerr")


async def test_condition_eval_error_emits_on_error(bot, monkeypatch):
    dest = attach_channel(bot, FakeChannel(name="log", id=1437))
    bot.on_event("error", "sendto 1437 ERROR: $errormsg")

    async def boom(ctx, engine, expr):
        raise RuntimeError("boom-cond")

    monkeypatch.setattr("tflows.engine.evaluate_condition", boom)
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "if 1 == 1:\n    send should-not\nsend after")
    assert ctx._error_pending is False
    texts = sent(dest)
    assert len(texts) == 1
    assert "boom-cond" in texts[0]
    assert "failed to evaluate condition" in texts[0]
    assert sent(ctx.channel) == ["after"]
    dest.sent.clear()
    await bot.engine.run(ctx, "send reused")
    assert sent(ctx.channel)[-1] == "reused"
    assert sent(dest) == []


# ---------------------------------------------------------------------------
# $dm
# ---------------------------------------------------------------------------
async def test_dm_one_user(bot):
    user = FakeUser(id=123, name="Tester")
    message = FakeMessage(content="!t", author=user, client=bot)
    ctx = make_ctx(bot, message=message)
    await bot.engine.run(ctx, "$dm $user Hello!")
    assert dms(user) == ["Hello!"]


async def test_dm_user_id(bot):
    target = attach_user(bot, FakeUser(id=123456789012345678, name="IdUser"))
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    await bot.engine.run(ctx, "$dm 123456789012345678 Hello!")
    assert dms(target) == ["Hello!"]


async def test_dm_variable(bot):
    target = FakeUser(id=55, name="VarUser")
    attach_user(bot, target)
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    ctx.set_local("who", target)
    await bot.engine.run(ctx, "$dm $who Hello!")
    assert dms(target) == ["Hello!"]


async def test_dm_collection(bot):
    a = FakeUser(id=1, name="A")
    b = FakeUser(id=2, name="B")
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    ctx.extras["users"] = [a, b]
    await bot.engine.run(ctx, "$dm $users Server maintenance starts soon.")
    assert dms(a) == ["Server maintenance starts soon."]
    assert dms(b) == ["Server maintenance starts soon."]


async def test_dm_one_failure_does_not_block_others(bot, caplog):
    class BoomUser(FakeUser):
        async def send(self, *args, **kwargs):
            raise RuntimeError("blocked")

    boom = BoomUser(id=1, name="Boom")
    ok = FakeUser(id=2, name="Ok")
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    ctx.extras["users"] = [boom, ok]
    with caplog.at_level("ERROR"):
        await bot.engine.run(ctx, "$dm $users hi")
    assert dms(ok) == ["hi"]
    assert dms(boom) == []


async def test_dm_invalid_recipient_does_not_crash(bot, caplog):
    ctx = make_ctx(bot, message=FakeMessage(content="!t", client=bot))
    with caplog.at_level("WARNING"):
        await bot.engine.run(ctx, "$dm not-a-user hi")
    assert ctx.last_error


def test_expand_recipients_does_not_split_snowflake():
    snowflake = "123456789012345678"
    assert expand_recipients(snowflake) == [snowflake]
    assert expand_recipients(123456789012345678) == [123456789012345678]


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
def test_check_recognizes_v13_syntax():
    source = """
on delete
    sendto 1437 deleted: $content
on edit
    sendto 1437 before: $before after: $after
on error
    sendto 1437 ERROR: $errormsg
on message_delete where user == 1
    sendto 1 x
$dm $user Hello!
embedto 1437
$title[Hi]
endembed
"""
    diags = check_source(source)
    messages = [d.message for d in diags]
    assert not any("unknown event" in m for m in messages)
    assert not any("unknown function" in m for m in messages)


def test_check_unknown_event_still_warned():
    diags = check_source("on explosion\n    send boom")
    assert any("unknown event" in d.message for d in diags)


# ---------------------------------------------------------------------------
# 1.2 regression
# ---------------------------------------------------------------------------
async def test_v12_script_still_works(bot):
    message = FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args="ping", message=message)
    await bot.engine.run(
        ctx,
        """
switch $arg(0):
    case ping:
        send pong
    default:
        send nope
choose a, b, a
send $config(missing)
""",
    )
    texts = sent(message.channel)
    assert "pong" in texts
