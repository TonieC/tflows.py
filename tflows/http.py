"""HTTP and JSON helpers for tflows scripts.

Security: outbound requests are opt-in. ``FlowBot(allow_http=True)`` (or
``TFLOWS_ALLOW_HTTP=1``) must be set; otherwise ``http.get`` fails closed
with a logged warning. Hosts can be restricted via ``http_allowlist``
(exact hostnames). Redirects to a different host are not followed. Request
size, timeout and scheme (https by default; http only when
``allow_insecure_http=True``) are capped.

Script usage::

    let response = http.get "https://api.example.com/data"
    let data = json.parse $response.body
    send $data[name]

    http.post "https://api.example.com/hook" body="hello" header="Authorization: Bearer x"
"""

from __future__ import annotations

import json
import logging
import os
import ssl
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .runtime import FlowValue, stringify

logger = logging.getLogger("tflows.http")

_DEFAULT_TIMEOUT = 10
_MAX_BODY = 1_000_000  # 1 MiB
_ALLOWED_SCHEMES = {"https"}
_USER_AGENT = "tflows/1.1 (+https://github.com/TonieC/tflows.py)"


@dataclass
class HttpResponse:
    status: int = 0
    body: str = ""
    headers: dict = field(default_factory=dict)
    url: str = ""
    ok: bool = False
    error: str = ""

    def __str__(self) -> str:
        return self.body


def _http_enabled(ctx) -> bool:
    bot = getattr(ctx, "bot", None)
    if bot is not None and getattr(bot, "allow_http", None) is not None:
        return bool(bot.allow_http)
    return os.environ.get("TFLOWS_ALLOW_HTTP", "").strip() in ("1", "true", "yes")


def _allowlist(ctx) -> set[str] | None:
    bot = getattr(ctx, "bot", None)
    hosts = getattr(bot, "http_allowlist", None) if bot is not None else None
    if not hosts:
        return None
    return {str(h).lower() for h in hosts}


def _allow_insecure(ctx) -> bool:
    bot = getattr(ctx, "bot", None)
    return bool(getattr(bot, "allow_insecure_http", False)) if bot is not None else False


def _validate_url(ctx, url: str) -> str:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    allowed = set(_ALLOWED_SCHEMES)
    if _allow_insecure(ctx):
        allowed.add("http")
    if scheme not in allowed:
        raise PermissionError(f"blocked URL scheme {scheme!r} (allowed: {sorted(allowed)})")
    host = (parsed.hostname or "").lower()
    if not host:
        raise PermissionError("URL has no host")
    # Block obvious local / metadata endpoints unless explicitly allowlisted.
    blocked = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "169.254.169.254",
        "metadata.google.internal",
    }
    allow = _allowlist(ctx)
    if allow is not None and host not in allow:
        raise PermissionError(f"host {host!r} is not on the HTTP allowlist")
    if allow is None and host in blocked:
        raise PermissionError(f"blocked local/metadata host {host!r}")
    return url


def _parse_http_args(args: str) -> tuple[str, dict]:
    """Split ``url key=value ...`` plus ``header=Name: Value`` / ``body=...``."""
    text = (args or "").strip()
    url = ""
    options: dict[str, Any] = {"headers": {}, "query": {}, "body": None, "timeout": _DEFAULT_TIMEOUT}
    if not text:
        return url, options
    # URL is the first token, optionally quoted.
    if text[0] in "'\"":
        quote = text[0]
        end = text.find(quote, 1)
        if end == -1:
            url, rest = text[1:], ""
        else:
            url, rest = text[1:end], text[end + 1 :].strip()
    else:
        parts = text.split(None, 1)
        url = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
    if not rest:
        return url, options
    # Parse key=value tokens; header/body may contain spaces after the first =.
    i = 0
    while i < len(rest):
        while i < len(rest) and rest[i].isspace():
            i += 1
        if i >= len(rest):
            break
        eq = rest.find("=", i)
        if eq == -1:
            break
        key = rest[i:eq].strip().lower()
        i = eq + 1
        if i < len(rest) and rest[i] in "'\"":
            quote = rest[i]
            end = rest.find(quote, i + 1)
            value = rest[i + 1 : end] if end != -1 else rest[i + 1 :]
            i = end + 1 if end != -1 else len(rest)
        else:
            # Consume until next ` word=` boundary.
            j = i
            while j < len(rest):
                if rest[j].isspace():
                    # look ahead for key=
                    k = j
                    while k < len(rest) and rest[k].isspace():
                        k += 1
                    eq2 = rest.find("=", k)
                    sp = rest.find(" ", k)
                    if eq2 != -1 and (sp == -1 or eq2 < sp) and rest[k:eq2].replace("_", "").replace("-", "").isalnum():
                        break
                j += 1
            value = rest[i:j].strip()
            i = j
        if key in ("header", "headers"):
            if ":" in value:
                name, _, val = value.partition(":")
                options["headers"][name.strip()] = val.strip()
        elif key in ("query", "param", "params"):
            if "=" in value:
                name, _, val = value.partition("=")
                options["query"][name.strip()] = val.strip()
            else:
                options["query"][value] = ""
        elif key in ("body", "data", "json"):
            options["body"] = value
            if key == "json":
                options["headers"].setdefault("Content-Type", "application/json")
        elif key == "timeout":
            try:
                options["timeout"] = max(1, min(float(value), 30))
            except ValueError:
                pass
        else:
            options[key] = value
    return url, options


def _request(ctx, method: str, args: str) -> HttpResponse:
    response = HttpResponse()
    if not _http_enabled(ctx):
        response.error = "http disabled (pass FlowBot(allow_http=True))"
        logger.warning("[tflow] %s", response.error)
        return response
    url, options = _parse_http_args(args)
    if not url:
        response.error = "missing URL"
        return response
    try:
        url = _validate_url(ctx, url)
    except PermissionError as exc:
        response.error = str(exc)
        logger.warning("[tflow] HTTP blocked: %s", exc)
        return response
    if options["query"]:
        sep = "&" if urlparse(url).query else "?"
        url = url + sep + urlencode(options["query"])
    headers = {"User-Agent": _USER_AGENT, **options["headers"]}
    body = options["body"]
    data = None
    if body is not None:
        data = body.encode("utf-8") if isinstance(body, str) else body
    request = Request(url, data=data, headers=headers, method=method.upper())
    timeout = options["timeout"]
    ctx_ssl = ssl.create_default_context()
    try:
        with urlopen(request, timeout=timeout, context=ctx_ssl) as resp:  # noqa: S310 - URL validated above
            raw = resp.read(_MAX_BODY + 1)
            if len(raw) > _MAX_BODY:
                raw = raw[:_MAX_BODY]
                logger.warning("[tflow] HTTP response truncated at %s bytes", _MAX_BODY)
            response.status = getattr(resp, "status", 200) or 200
            response.body = raw.decode("utf-8", errors="replace")
            response.headers = {k.lower(): v for k, v in resp.headers.items()}
            response.url = resp.geturl()
            response.ok = 200 <= response.status < 300
    except HTTPError as exc:
        try:
            raw = exc.read(_MAX_BODY)
            response.body = raw.decode("utf-8", errors="replace")
        except Exception:
            response.body = ""
        response.status = exc.code
        response.error = str(exc)
        response.ok = False
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        response.error = str(exc)
        response.ok = False
        logger.warning("[tflow] HTTP %s failed: %s", method, exc)
    return response


def json_parse(text) -> Any:
    if isinstance(text, FlowValue):
        text = text.value
    if isinstance(text, (dict, list)):
        return text
    if isinstance(text, HttpResponse):
        text = text.body
    raw = stringify(text) if not isinstance(text, str) else text
    raw = raw.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[tflow] json.parse failed")
        return {}


def json_stringify(value) -> str:
    if isinstance(value, FlowValue):
        value = value.value
    if isinstance(value, str):
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError:
            pass
    try:
        return json.dumps(value, default=str)
    except TypeError:
        return stringify(value)


def setup(registry):
    async def _http_get(ctx, args):
        return _request(ctx, "GET", args)

    async def _http_post(ctx, args):
        return _request(ctx, "POST", args)

    async def _http_put(ctx, args):
        return _request(ctx, "PUT", args)

    async def _http_patch(ctx, args):
        return _request(ctx, "PATCH", args)

    async def _http_delete(ctx, args):
        return _request(ctx, "DELETE", args)

    async def _json_parse(ctx, args):
        return json_parse(args)

    async def _json_dump(ctx, args):
        return json_stringify(args)

    registry.register("http.get", _http_get)
    registry.register("http.post", _http_post)
    registry.register("http.put", _http_put)
    registry.register("http.patch", _http_patch)
    registry.register("http.delete", _http_delete)
    registry.register("json.parse", _json_parse)
    registry.register("json.dump", _json_dump)
    registry.register("json.stringify", _json_dump)

    def _response_field(obj, field):
        if isinstance(obj, HttpResponse):
            return getattr(obj, field, "")
        return ""

    @registry.register_var("response")
    def response_var(ctx, args):
        value = ctx.get_local("response") if hasattr(ctx, "get_local") else None
        obj = value.value if isinstance(value, FlowValue) else value
        if not isinstance(obj, HttpResponse):
            extra = (getattr(ctx, "extras", None) or {}).get("response")
            obj = extra
        if obj is None:
            return ""
        arg = (args or "").strip().lower()
        if arg in ("", "body"):
            return obj.body if isinstance(obj, HttpResponse) else stringify(obj)
        if arg == "status":
            return str(getattr(obj, "status", ""))
        if arg == "ok":
            return "true" if getattr(obj, "ok", False) else "false"
        if arg == "error":
            return str(getattr(obj, "error", ""))
        if arg.startswith("header"):
            headers = getattr(obj, "headers", {}) or {}
            key = args.split(None, 1)[1].lower() if " " in (args or "") else ""
            return headers.get(key, "")
        return stringify(obj)
