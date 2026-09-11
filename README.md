# tflows.py

tflows.py is a lightweight automation and Discord bot framework built around a
scripting engine. Instead of writing Python event handlers for every action,
you define bot behavior as simple text scripts:

```py
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
    name="ping",
    code="""
    // Send a reply with the current latency
    reply Pong! $ping
    """,
)

bot.run("YOUR_BOT_TOKEN")
```

It is designed for fast bot development, easy customization, and extensible
command logic — while staying fully compatible with discord.py so you can mix
scripts and regular commands.

---

## Features

- Script-based command system — write bot logic as plain text
- Built-in `$variable` templates (`$user`, `$server`, `$args`, `$ping`, ...)
- Command arguments: `$args`, `$arg(0)`, `$argcount`
- Locals and expressions: `let name = ...`, arithmetic, `$name` interpolation
- Loops: `for item in ...` / `repeat N` with `break` / `continue`
- Script functions: `function greet(name):` / `return` / `$greet(Ada)`
- Conditionals: `if` / `elif` / `else` / `endif` with comparisons and nesting
- Interactive components: `button`, `select`, `modal`, `defer`, `ephemeral`
- Slash commands and user/message context menus
- Cooldowns (`cooldown 5s per user`) and permission guards (`require ...`)
- SQLite persistent state with `user.` / `channel.` / `guild.` / `global.` scopes
- Scheduled tasks (`bot.schedule(...)`, `every 1h`, cron) and event triggers (`bot.on_event("join", ...)`)
- Event filters: `on message where channel == "general"`
- Opt-in sandboxed HTTP/JSON (`http.get`, `json.parse`)
- Member/role/channel management (`role add`, `kick`, `timeout`, ...)
- `import` of `.flow` files (restricted to the script root)
- `bot.load` / `reload` / `watch` and `tflows check` CLI
- Rich embeds, both as blocks and single-line commands
- Built-in `help` command, aliases, and command descriptions
- Comment support in scripts (`//`, `#`, `--`)
- Async Discord integration using discord.py 2.x
- Extensible registry: add your own functions and variables
- Mixing with regular discord.py commands, cogs, and listeners

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the planned next releases and feature priorities.

---

## Installation

```bash
pip install tflows
```

Requires Python 3.10+.

---

## Quick Start

```py
from tflows import FlowBot

bot = FlowBot(prefix="!")

bot.command(
    name="hello",
    code="""
    reply Hello $user(display)!
    """,
)

bot.run("YOUR_BOT_TOKEN")
```

### Command registration

`FlowBot.command(name, code, description="", aliases=())` registers a script
command:

```py
bot.command(
    name="greet",
    code="reply Hello $args",
    description="Greets the given name.",
    aliases=("hi", "hey"),
)
```

Both `!greet`, `!hi` and `!hey` now trigger the same script.

### The built-in help command

By default `!help` lists every script command, and `!help <command>` shows its
description, aliases, usage, and source script. Disable it with
`FlowBot(prefix="!", help_command=False)`.

---

## Variables

Variables are replaced anywhere in a script, including inside function
arguments. Usage is `$name` or `$name(option)`.

| Variable | Options | Description |
| --- | --- | --- |
| `$user` / `$author` | `name`, `display`, `id`, `mention`, `avatar`, `bot`, `created`, `joined`, `tag` | Information about the message author |
| `$server` / `$guild` | `name`, `id`, `icon`, `owner`, `members`, `boost`, `boostlvl`, `created`, `description` | Information about the current guild |
| `$channel` | `name`, `id`, `mention`, `topic`, `nsfw`, `type`, `position`, `category`, `created` | Information about the current channel |
| `$bot` | `name`, `id`, `mention`, `avatar`, `status`, `ping`, `uptime` | Information about the bot itself |
| `$args` | — | Everything typed after the command name |
| `$arg(n)` | `0`-based index, negative counts from the end, `a:b` slices, or a slash-parameter name | A single argument |
| `$argcount` | — | Number of arguments |
| `$get(key)` / `$state(key)` | `$get(points)`, `$get(points, 0)` | Inline read of persistent state (with optional fallback) |
| `$hasrole(name)` | `$hasrole(Moderator)` | `true` when the author has the role |
| `$hasperm(name)` | `$hasperm(manage_messages)` | `true` when the author has the permission |
| `$isowner` | — | `true` when the author owns the server |
| `$ping` | — | The bot's current latency |
| `$time` | `12h`, `24h`, `nodate`, `notime` | Current time |
| `$uptime` | `full`, `short`, `clock`, `seconds`, custom like `d:h:m:s` | Bot uptime |
| `$membercount` | `all`, `user`, `bots` | Member counts |
| `$random` | `a, b` (inclusive range) | A random number |
| `$id` | — | The author's user ID |
| `$avatar` / `$image` | — | The author's avatar URL |
| `$prefix` | — | The bot's command prefix |
| `$command` | — | The currently running command name |
| `$message` | `content`, `id`, `author` | The triggering message (events / context menus) |
| `$emoji` | — | Reaction emoji on `react` / `unreact` events |
| `$value` | — | Selected value from a select menu |
| `$input` / `$input.field` | field custom id | Modal text-input values |
| `$members` | `bots`, `users` | Guild member display names (for `for` loops) |
| `$roles` | — | Guild role names |
| `$channels` | — | Guild channel names |
| `$target` | same as `$user` | Context-menu target user or message |
| `$response` | `body`, `status`, `ok`, `error` | Last HTTP response when stored as `let response = ...` |

Locals created with `let name = ...` are interpolated as `$name`. Path access
works on objects and JSON: `$data[name]`, `$data.name`, `$user(display)`.
Unknown variables are left untouched so typos never silently corrupt output.

Example:

```
!greet world
```
```
reply Hello $args            # -> Hello world
reply First: $arg(0)         # -> First: world
reply Count: $argcount       # -> Count: 1
```

---

## Functions

Every line of a script calls one function:

```
<function-name> <arguments...>
```

### Core functions

| Function | Example | Description |
| --- | --- | --- |
| `send` | `send hello` | Sends a message to the current channel |
| `reply` | `reply hi $user` | Replies to the invoking message |
| `log` | `log command ran` | Prints a message to the console |
| `wait` / `delay` | `wait 1h 30m` | Waits; mixed units (`ms`/`s`/`m`/`h`/`d`/`w`); capped by `max_wait` |
| `choose` | `choose a, b, c` | Picks a random option (`$choose(...)` also works) |
| `config` | `config theme dark` | Read/write developer config (`$config(theme)`) |
| `react` | `react ✅` | Adds reactions to the invoking message |
| `delete` | `delete` | Deletes the invoking message |
| `clear` | `clear 10` | Purges recent messages (needs Manage Messages) |
| `ping` | `ping` | Replies with the bot's latency |
| `set` | `set points 10` / `set points +5` | Stores persistent state (`+N`/`-N` increments atomically) |
| `get` | `get points` / `get points 0` | Sends the stored value (with optional fallback) |
| `del` | `del points` | Forgets a stored key |
| `incr` | `incr points 3` | Atomically increments a counter (default `1`) |
| `role` | `role add Moderator` | Add/remove/create/delete roles |
| `kick` / `ban` / `unban` / `timeout` | `kick $user reason="spam"` | Member moderation (explicit target; invoker+bot perms) |
| `channel` / `thread` | `channel rename new-name` | Channel and thread management |
| `http.get` | `let r = http.get "https://..."` | Opt-in HTTP (see HTTP section) |
| `json.parse` / `json.stringify` | `let data = json.parse {...}` | Parse / dump JSON |
| `defer` / `ephemeral` / `show_modal` | `defer ephemeral` | Interaction response helpers |

### Embeds

The block form is best for rich, multi-line embeds:

```
embed
$title[Server Stats]
$desc[
Members: $membercount
Uptime: $uptime(full)
]
$footer[Requested by $user(display)]
$color[blurple]
$thumbnail[$bot(avatar)]
endembed
```

Supported keys: `$title`, `$desc`, `$footer`, `$color` (hex or named), `$thumbnail`,
`$image`, `$author`, `$timestamp`. Named colors include `white`, `black`, `red`,
`green`, `blue`, `yellow`, `orange`, `purple`, `pink`, `grey`, `blurple`, `gold`,
`teal`, `cyan`, and `brown`.

A single-line form using the `embed` function is also available, with keys
separated by `|` and fields via `field: Name;Value;inline`:

```
embed $embed<title: $user(display) | desc: Level 42 | color: green | field: Role;Admin;true>
```

### Comments

Lines starting with `//`, `#`, or `--` are ignored.

---

## Conditionals

Branch directly in scripts — no Python needed:

```
if $argcount > 1:
    reply Multiple arguments: $args
elif $argcount == 1:
    reply One argument: $arg(0)
else:
    reply Give me something to echo!
endif
```

- `endif` is optional when the block runs to the end of the script, or when
  dedentation shows where it ends (a dedented line after an indented block
  closes it). Use `endif` when unconditional code follows, or when lines are
  not indented.
- Operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `startswith`,
  `endswith`, `in`. Numbers compare numerically, everything else
  case-insensitively as text.
- Combine clauses with `and` / `or`, negate with `not`. A bare value is
  truthy unless empty or `0` / `false` / `no` / `none`.
- Blocks nest. Conditions see all `$variables`, so guards like
  `if $hasrole(Moderator):`, `if $hasperm(manage_messages):`,
  `if $channel == announcements:` and `if $user == SomeName:` all work.

---

## Cooldowns and permission guards

Declare controls at the top of a command script:

```
cooldown 5s per user
require manage_messages
require role Moderator
require owner
```

- `cooldown <duration> [per user|channel|guild|global]` (default `per user`).
  Durations accept mixed units (`5s`, `1h 30m`, `500ms`, `2 minutes`).
  While on cooldown the script is skipped and the user is told how long to wait.
- `require <permission>` checks Discord permissions
  (`manage_messages`, `administrator`, `kick_members`, ...),
  `require role <name>` checks a role (with `admin`/`mod` shortcuts),
  `require owner` checks server ownership. Unauthorized users get a denial
  message and the script never runs. Unparseable `require` lines fail closed.

---

## Persistent state

SQLite-backed storage that survives restarts and is isolated per server:

```
set points[$user] +10
get points[$user]
```

`set <key> <value>` stores text; a `+N`/`-N` value increments atomically
(counters, safe under concurrency). `get <key> [fallback]` sends the value,
`del <key>` forgets it, `incr <key> [amount]` bumps a counter silently, and
`$get(key, fallback)` reads state inline. Because variables resolve first,
dynamic keys like `points[$user]` just work.

```py
bot = FlowBot(prefix="!")                      # state in ./tflows.db
bot = FlowBot(prefix="!", state_path=":memory:")  # tests / no persistence
bot = FlowBot(prefix="!", state_path=None)        # disable state
```

---

## Scheduled tasks

Run scripts on a timer without blocking the bot:

```py
bot.schedule("hourly", "send Hourly check-in", interval="1h")
bot.schedule("standup", code="send Standup time!", interval="5m", channel=123456789)
bot.schedule("midnight", code="send New day!", cron="0 0 * * *")
```

- Intervals accept seconds or `"30s"` / `"5m"` / `"1h"` / `"1d"` strings;
  `cron` accepts 5-field expressions (`minute hour day month weekday`).
- A leading `every 1h:` / `cron ...:` header inside `code` also works and is
  ignored when the same script runs as a command.
- Re-scheduling a name replaces the old task (no duplicates). Tasks start
  with the bot, stop cleanly via `await bot.scheduler.stop_all()` /
  `await bot.close()`, and `await bot.scheduler.run_once("hourly")`
  triggers a run on demand. `bot.unschedule("hourly")` removes one.

---

## Event triggers

React to Discord events with plain scripts — no command invocation needed:

```py
bot.on_event("join", "send Welcome $user(mention)!")   # member joins
bot.on_event("leave", "send Bye $user(name)!")         # member leaves
bot.on_event("react", "send $user(display) reacted!")  # reaction added
```

A leading `on <event>:` header inside the code is accepted verbatim.
Supported names include `join`, `leave`/`remove`, `react`/`reaction`,
`unreact`, `message`, `typing` (see `tflows.events.EVENT_MAP`); new events
are added by extending that map without changing the language. Handlers are
removed with `bot.remove_event("join", name)`.

---

## Slash commands

Add a slash variant to any script command — the prefix command keeps working:

```py
bot.command(
    name="greet",
    code="reply Hello $arg(0)!",
    description="Greet someone",
    slash=True,
    slash_params=["name"],
)

bot.slashcommand(
    name="roll",
    code="send Rolled $arg(0)!",
    description="Roll dice",
    params=["sides: int"],
)

# after the bot is ready:
await bot.sync_commands()
```

Parameters map positionally into `$args` / `$arg(0)` / `$argcount` and by
name into `$arg(name)`. Params accept `"name"`, `"name: int|float|bool|str"`,
`("name", type)` tuples, or dicts. Slash, prefix, event, and scheduled
scripts can all coexist in one bot.

---

## Locals and expressions

```
let name = $arg(0)
let n = 1 + 2 * 3
n = n + 1
send Hello $name, n=$n
```

- `let name = expr` creates a local. Bare `name = expr` reassigns an existing local.
- `$name` interpolates the local as text. A lone `$name` on the right-hand side of `let` keeps the underlying value (lists, JSON objects, HTTP responses).
- Operators: `+ - * / %`, comparisons, `and` / `or` / `not`, `contains` / `startswith` / `endswith` / `in`.
- Locals are per-script-run and isolated inside `function` bodies.

## Loops

```
for item in a, b, c:
    send $item
endfor

repeat 3:
    send $i
endrepeat
```

- `for name in expr` iterates lists, comma/newline-separated strings, JSON arrays, `$members`, `$roles`, `$channels`.
- `repeat N` runs the body `N` times (capped by `max_repeat`, default 10_000) and sets `$i` / `$index` (0-based).
- `break` leaves the innermost loop; `continue` skips the rest of the current iteration.
- `endfor` / `endrepeat` are optional when indentation shows the end of the block.

## After and switch

```
after 1s 500ms:
    send later

switch $arg(0):
    case ping:
        send pong
    case hi:
        send hello
    default:
        send try ping or hi
```

- `after <duration>:` runs the body after a delay (mixed units; capped by `max_wait`). `after 0s` runs inline.
- `switch expr` matches `case` labels case-insensitively and falls through to `default`.

## Script functions

```
function greet(name):
    return Hello $name
endfunction

send $greet(Ada)
greet("Ada")
```

- Defined with `function name(params):` ... `endfunction` (or indentation).
- Call as a statement (`greet Ada`) or interpolate the return value (`send $greet(Ada)`).
- `return expr` leaves the function (or the whole script when used at top level).
- Recursion is capped (64 frames). Parameters default to empty string when omitted.

## Buttons, selects, and modals

```
button "Click me" id="hello" style="primary":
    reply You clicked!
send Choose:

select id="color" placeholder="Pick a color":
    option "Red" value="red"
    option "Blue" value="blue"
    send You picked $value

modal "Feedback" id="fb":
    input "message" placeholder="Your feedback"
    send Thanks: $input.message
```

- Components attach to the next `send` / `reply` / `embed`.
- Persistent handlers are keyed by `id` (custom id). `on button "hello":` also binds a handler.
- `defer` / `defer ephemeral` acknowledges an interaction; `ephemeral` marks the next reply as only visible to the user.
- `show_modal id` opens a previously defined modal.

## HTTP and JSON (opt-in)

HTTP is **fail-closed**. Enable it explicitly:

```py
bot = FlowBot(prefix="!", allow_http=True, http_allowlist=["api.example.com"])
```

Or set `TFLOWS_ALLOW_HTTP=1`. Without that, `http.get` stores an error and does not open a socket.

```
let response = http.get "https://api.example.com/data"
let data = json.parse $response.body
send $data[name]
```

Limits and security:

- HTTPS only unless `allow_insecure_http=True`.
- Private, loopback, link-local, and cloud-metadata addresses are blocked after DNS resolution.
- Optional `http_allowlist` of exact hostnames. Redirects are not followed.
- 10s timeout, 1 MiB body cap, custom `User-Agent`.
- `http.post` / `put` / `patch` / `delete` accept `body=`, `header="Name: Value"`, `query=k=v`, `timeout=`.

`json.parse` returns `{}` on invalid input. `json.stringify` / `json.dump` serialize values.

## Importing scripts

```
import helpers.flow
send $greet(Ada)
```

- Paths are resolved under `script_root` (the directory of the first `bot.load(...)` file, or `FlowBot(script_root=...)`).
- `..`, absolute paths outside the root, remote URLs, and non-script suffixes are rejected.
- Circular imports error; a file already imported is skipped (not re-executed).
- Imported `function` definitions are registered globally; remaining top-level lines run once.

## Loading files, reload, and `tflows check`

```py
bot.load("bot.flow")
await bot.reload()          # all loaded files; syntax errors keep the previous version
bot.watch(interval=1.0)     # reload when files change
```

A `.flow` file may contain `command`, `function`, `on ...`, `every` / `cron`, and `context user|message` blocks.

```bash
tflows check bot.flow
tflows check scripts/
tflows --version
```

`tflows check` reports unclosed blocks, `break` outside loops, `import` with `..`, and unknown function names (warnings). Exit status is `1` when errors are found.

## State scopes

Unprefixed keys stay per-guild (as in 1.0). Prefixes change the namespace:

```
set user.points 10          # per user, across guilds
set channel.topic hello     # per channel
set guild.flag 1            # same as unprefixed (per guild)
set global.flag 1           # shared across guilds
get user.points 0
```

`$get(user.points, 0)` reads inline. Persistent state is not touched by `reload`.

## Event filters and extra variables

```
on message where channel == "general":
    send hi

on join where role == "Member":
    send Welcome $user(mention)!
```

`where` uses the same operators as `if`. Bare identifiers `channel`, `user`, `message`, `emoji`, `value`, `role` resolve from the event. Extra `$variables` on events: `$user`, `$message`, `$emoji`, `$content`.

Context menus:

```
context user Inspect:
    send Looking at $target

context message Quote:
    send $content
```

Or `bot.context_menu("user", "Inspect", "send $target")`.

---

## Mixing with discord.py

Because `FlowBot` subclasses `discord.ext.commands.Bot`, everything discord.py
offers keeps working: cogs, listeners, `@bot.event`, app commands, etc. When a
message matches the prefix but not a script command, it is passed through to
discord.py's command processor automatically.

```py
import discord
from discord.ext import commands
from tflows import FlowBot

class Moderation(commands.Cog):
    @commands.command()
    async def purge(self, ctx, limit: int):
        await ctx.channel.purge(limit=limit)

bot = FlowBot(prefix="!")
bot.command(name="hello", code="reply Hi $user(display)!")
bot.add_cog(Moderation(bot))
bot.run("YOUR_BOT_TOKEN")
```

---

## Custom functions and variables

Functions are callables `fn(ctx, args)` and variables are callables
`var(ctx, args)` that return a string (or an awaitable). Register them on the
shared registry:

```py
from tflows import FlowBot
from tflows.registry import registry

@registry.register("shrug")
async def shrug(ctx, args):
    await ctx.channel.send("¯\\_(ツ)_/¯")

@registry.register_var("uptime_hours")
def uptime_hours(ctx, args):
    return str(bot_uptime_seconds() // 3600)

bot = FlowBot(prefix="!")
```

Alternatively, create an isolated bot with its own registry:
`FlowBot(prefix="!", registry=FunctionRegistry())`.

### FlowBot options

| Option | Default | Description |
| --- | --- | --- |
| `prefix` | `"!"` | Command prefix (a string or list of strings) |
| `help_command` | `True` | Enable the built-in `!help` command |
| `log_errors` | `True` | Log script errors instead of raising |
| `log_unknown_functions` | `True` | Log unknown function names |
| `case_insensitive` | `False` | Match command names case-insensitively |
| `members_intent` | `False` | Enable the privileged members intent |
| `registry` | shared | Use an isolated `FunctionRegistry` |
| `state_path` | `"tflows.db"` | SQLite state file (lazy); `":memory:"` for tests, `None` to disable |
| `allow_http` | `False` | Enable `http.get` / `http.post` / ... (fail-closed otherwise) |
| `http_allowlist` | `None` | Optional iterable of exact hostnames HTTP may contact |
| `allow_insecure_http` | `False` | Allow `http://` in addition to `https://` |
| `script_root` | first loaded file | Root directory for `import` (no path traversal) |
| `max_wait` | `300` | Cap for `wait` / `after` / `delay` in seconds (`-1` disables) |
| `max_repeat` | `10000` | Cap for `repeat N` |
| `max_clear` | `100` | Cap for `clear` |
| `component_timeout` | `300` | Discord view timeout (`0` = none) |
| `http_timeout` | `10` | Default HTTP timeout in seconds |
| `http_max_timeout` | `30` | Maximum HTTP timeout |
| `http_max_body` | `1000000` | HTTP response size cap in bytes |
| `schedule_retries` | `0` | Retries after a scheduled task fails |
| `schedule_backoff` | `"1s"` | Backoff between schedule retries |
| `config` | `{}` | Developer map exposed as `$config(key)` |

---

## Examples

See the `examples/` directory:

- `basic_bot.py` — minimal bot
- `variables.py` — variable showcase
- `embeds.py` — block and single-line embeds
- `automation.py` — `wait`, `react`, `delete`, `clear`
- `mixing.py` — scripts alongside discord.py cogs
- `advanced.py` — conditionals, guards, state, schedules, events, slash
- `language.py` — locals, loops, functions, components, JSON, import
- `v13.py` — mixed durations, config, after, switch, choose

Run any example after installing the package:

```bash
python examples/basic_bot.py
```

---

## License

Apache License 2.0 — see the `License` file. Attribution to the original author
is required when redistributing or embedding the software; see `NOTICE`.
