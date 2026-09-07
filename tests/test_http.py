"""HTTP/JSON helpers and fail-closed security."""

import pytest

from tests.fakes import FakeMessage, make_bot, make_ctx
from tflows.http import HttpResponse, json_parse, json_stringify, _validate_url


async def run(bot, code, args=""):
    message = FakeMessage(content="!t", client=bot)
    ctx = make_ctx(bot, args=args, message=message)
    await bot.engine.run(ctx, code)
    return message, ctx


def sent(message):
    return [args[0] for args, _ in message.channel.sent]


@pytest.fixture
def bot():
    return make_bot()


async def test_http_disabled_stores_error(bot):
    message, ctx = await run(bot, 'let response = http.get "https://example.com"\nsend $response.error')
    local = ctx.get_local("response")
    assert local is not None
    obj = local.value
    assert isinstance(obj, HttpResponse)
    assert obj.ok is False
    assert "disabled" in obj.error
    assert sent(message)[0].startswith("http disabled")


async def test_http_localhost_blocked():
    bot = make_bot(allow_http=True, allow_insecure_http=True)
    ctx = make_ctx(bot)
    with pytest.raises(PermissionError):
        _validate_url(ctx, "http://127.0.0.1/secret")


async def test_http_metadata_blocked():
    bot = make_bot(allow_http=True)
    ctx = make_ctx(bot)
    with pytest.raises(PermissionError):
        _validate_url(ctx, "https://169.254.169.254/latest")


async def test_http_allowlist_rejects_other_hosts():
    bot = make_bot(allow_http=True, http_allowlist=["api.example.com"])
    ctx = make_ctx(bot)
    with pytest.raises(PermissionError):
        _validate_url(ctx, "https://evil.example/x")
    assert _validate_url(ctx, "https://api.example.com/v1") == "https://api.example.com/v1"


async def test_http_http_scheme_blocked_by_default():
    bot = make_bot(allow_http=True)
    ctx = make_ctx(bot)
    with pytest.raises(PermissionError):
        _validate_url(ctx, "http://example.com")


async def test_json_parse_object(bot):
    message, ctx = await run(bot, 'let data = json.parse {"name": "Ada"}\nsend $data[name]')
    assert sent(message) == ["Ada"]
    assert ctx.get_local("data").value["name"] == "Ada"


async def test_json_parse_invalid_returns_empty(bot):
    message, ctx = await run(bot, "let data = json.parse not-json\nsend empty")
    assert ctx.get_local("data").value == {}
    assert sent(message) == ["empty"]


async def test_json_stringify_roundtrip():
    assert json_parse('{"a": 1}') == {"a": 1}
    dumped = json_stringify({"a": 1})
    assert '"a"' in dumped


async def test_json_dump_in_script(bot):
    message, _ = await run(bot, 'let data = json.parse {"x": 1}\nlet text = json.stringify $data\nsend $text')
    assert '"x"' in sent(message)[0]
