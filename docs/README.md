# tflows docs

- [README](../README.md) — user guide, variables, functions, events
- [CHANGELOG](../CHANGELOG.md) — released versions
- [ROADMAP](../ROADMAP.md) — planned work
- [1.2 technical spec](v1.2-technical-spec.md)

## 1.3.0

Delete/edit events, `sendto` / `embedto`, `$dm`, `$before` / `$after` / `$errormsg`.

Scripts (no custom Python):

```
on delete
    sendto 143700000000000000 deleted: $content

on edit
    sendto 143700000000000000 before: $before after: $after

on error
    sendto 143700000000000000 ERROR: $errormsg
```

```
$dm $user Hello!
$dm $users Server maintenance starts soon.
```

See `examples/message_logger.tflow`, `examples/dm.tflow`, and `examples/embedto.tflow`.
