# Changelog

All notable changes to tflows are documented here.

## [Unreleased]

No changes yet.

## [1.0.1] - 2026-09-06

### Added

- **Conditionals**: `if` / `elif` / `else` / `endif` with `==`, `!=`, `>`,
  `<`, `>=`, `<=`, `contains`, `startswith`, `endswith`, `in`, `and` / `or` /
  `not`, and nesting (`tflows/conditionals.py`).
- **Slash commands**: `bot.command(..., slash=True, slash_params=[...])` and
  `bot.slashcommand(...)`; params map to `$args` / `$arg(n)` / `$arg(name)`.
  Sync with `await bot.sync_commands()`.
- **Cooldowns and permission guards**: `cooldown 5s per user|channel|guild|global`
  and `require manage_messages` / `require role Mod` / `require owner`, plus
  `$hasrole()` / `$hasperm()` / `$isowner` variables.
- **Persistent per-server state**: SQLite-backed `set` / `get` / `del` /
  `incr` functions and `$get(key, fallback)` (lazy `tflows.db` by default,
  `state_path=":memory:"` / `None` supported).
- **Scheduled tasks**: `bot.schedule(name, code, interval=...)` with duration
  strings and 5-field cron, `every 1h:` headers, no-duplicate replacement,
  clean start/stop, and `run_once` for on-demand runs.
- **Event triggers**: `bot.on_event("join"|"leave"|"react"|..., code)` with an
  extensible `tflows.events.EVENT_MAP`; `bot.remove_event()` to detach.
- `examples/advanced.py` showcasing all of the above; README documents every
  feature with complete examples.
- 84 new tests covering all six features (169 total, all passing).

## [1.0.0] - 2026-08-31

First stable release.

### Added

- Command **arguments**: `$args`, `$arg(n)` (including negative indexing and
  `a:b` slices) and `$argcount`.
- New variables: `$user`/`$author`, `$channel`, `$bot`, `$random`, `$prefix`,
  `$command`, plus extended `$server`/`$guild` fields (`id`, `icon`, `owner`,
  `members`, `created`, `description`).
- New functions: `reply`, `wait` (with `s`/`m`/`h`/`d` suffixes), `react`,
  `delete`, `clear`.
- Built-in `help` command with per-command details.
- Command `description` and `aliases` support.
- Comment lines in scripts (`//`, `#`, `--`).
- Embed enhancements: `$thumbnail`, `$image`, `$author`, `$timestamp`, named
  colors, and fields in the single-line `embed` form.
- `FlowBot` options: `help_command`, `log_errors`, `case_insensitive`,
  `members_intent`, and isolated `registry`.
- Script errors are logged instead of crashing the bot; unknown functions are
  logged (both configurable).
- `FlowContext` object that carries the invoking command name and arguments
  while remaining drop-in compatible with raw discord messages.
- Mixing with regular discord.py commands, cogs, and listeners via
  `process_commands` fallback.
- Full pytest test suite (85 tests) with a fake Discord context.
- `tflows.__version__`, `CHANGELOG.md`, and expanded examples.

### Fixed

- **Packaging**: the `tflows.function` subpackage was missing from built
  distributions, breaking the loader at runtime. Packages are now discovered
  with `setuptools.find`.
- `embed` function awaited missing coroutines; embed fields previously showed
  `<coroutine object ...>`.
- Removed duplicate function/variable registrations between `registry.py` and
  the `function/` modules.
- Removed deprecated `datetime.utcnow()` usage.
- Resolved the MIT vs Apache-2.0 license inconsistency — the project is now
  consistently Apache-2.0 across metadata, `License`, and `NOTICE`.
- Added proper `.gitignore` for build artifacts.

### Changed

- `engine.run()` now accepts either a raw `discord.Message` (backward
  compatible) or a `FlowContext`.
- Internal logger migrated from `print` to the `logging` module
  (`tflows.engine`, `tflows.bot`, ...).
- README rewritten to document the full variable/function catalog.

### Removed

- None (all existing public APIs remain backward compatible).

## [0.0.8] - 2026-05-30

- Initial script engine with `send`, `log`, and a small set of variables.
