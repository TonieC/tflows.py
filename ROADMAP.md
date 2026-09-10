# Roadmap

This document outlines the near-term direction for the project and the features most likely to land in upcoming releases.

For the detailed implementation plan for the 1.2 milestone, see [docs/v1.2-technical-spec.md](docs/v1.2-technical-spec.md).

## 1.1.2 — Security and correctness (shipped 2026-09-10)

Shipped as a patch on 1.1. Not a substitute for the 1.2 validation work.

- HTTP SSRF hardening (DNS resolve-then-check, private/metadata blocked, no redirects)
- Permission gates on moderation, `clear`, and slash commands
- `wait` / component timeouts, import suffix sandbox, non-calling field access
- Isolated default registries, fail-closed cooldowns, owner_id, scheduler overlap lock

## 1.2 — Stability, validation, and workflow tooling

Priority: High

### Goals
- Make scripts easier to reason about and safer to deploy
- Reduce runtime surprises and improve diagnostics
- Lay the groundwork for a small plugin ecosystem

### Planned features
- Script validation and linting
  - catch undefined variables/functions
  - detect invalid flow syntax before execution
  - show clear diagnostics in `tflows check`
- Better error reporting
  - file, line, and step-level tracebacks
  - friendly runtime errors for bad expressions and invalid state access
- Plugin/module architecture
  - load reusable script modules and packages
  - explicit exports/imports
  - version metadata and compatibility checks
- Scheduler improvements
  - timezone-aware jobs
  - retries/backoff for failed scheduled tasks
  - easier cron presets and natural-language scheduling inputs
  - (1.1.2 already: wait off the event loop, skip overlapping runs)
- Observability
  - command execution logs
  - per-guild stats and health summaries
  - failure summaries for debugging

## 1.3 — Data and automation primitives

Priority: High

### Goals
- Make bots easier to build for real-world workflows
- Add simple but powerful ways to persist and query structured data

### Planned features
- SQLite data helpers
  - higher-level `db` helpers for common bot data patterns
  - table creation helpers and migrations
  - simple query wrappers for bot state and automation records
- Workflow triggers
  - event-driven automation chains
  - reusable trigger/action blocks
- Queue/job runner
  - async background jobs
  - delayed processing and retry handling
- Better HTTP tooling
  - response/schema helpers
  - request debug mode
  - clearer policy errors (host/IP blocking and no-redirects shipped in 1.1.2)

## 1.4 — UX and extensibility

Priority: Medium

### Goals
- Improve developer experience and bot management
- Reduce repetitive boilerplate in script authoring

### Planned features
- Improved UI components
  - paginated buttons and selects
  - validation-aware modals
  - persistent interaction state
- Permission and access controls
  - command groups and scopes
  - clearer audit logs
  - (1.1.2 already: invoker+bot permission checks on moderation, `clear`, slash)
- Bot management tools
  - status commands and runtime dashboards
  - script health checks
  - centralized config management

## 2.0 — Platform features

Priority: Medium

### Goals
- Support richer bot ecosystems without breaking the lightweight scripting model

### Potential features
- Webhook and REST helpers for external service integration
- OAuth/web app integration hooks
- Dashboard or admin panel for monitoring and config
- Cross-bot shared registry/plugin standards
- Extension points for custom runtime services and commands

## Backlog / long-term ideas

These are not guaranteed for upcoming releases, but they are valuable candidates:

- natural-language script generation / scaffolding
- AI-assisted debugging and diagnostics
- marketplace-style examples and starter templates
- formal type system for script variables and state values
- stronger sandboxing and execution policy controls (partially shipped in 1.1.2)
- template packs for moderation, ticketing, onboarding, and automation

## Release principles

The roadmap is guided by a few core principles:

- Keep the scripting model simple and readable
- Preserve backward compatibility where possible
- Prioritize reliability over feature count
- Build tools that help real bot owners maintain and debug scripts
- Keep the core framework lightweight while enabling extension

## Notes

This roadmap is intentionally flexible. Features may be adjusted based on user feedback, stability concerns, or ecosystem changes. The top priorities remain validation, plugin structure, scheduling improvements, and observability.
