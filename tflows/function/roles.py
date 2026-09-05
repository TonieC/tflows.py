"""Role / permission variables for conditionals and templates.

- ``$hasrole(Moderator)`` -> ``"true"`` / ``"false"``
- ``$hasperm(manage_messages)`` -> ``"true"`` / ``"false"``
- ``$isowner`` -> ``"true"`` / ``"false"`` (server owner)

Typical use with conditionals::

    if $hasrole(Moderator):
        reply "Hello, mod!"
    endif
"""

from ..guards import author_has_role, check_permission


def setup(registry):
    registry.register_var("hasrole", lambda ctx, args: "true" if author_has_role(ctx, args or "") else "false")
    registry.register_var(
        "hasperm", lambda ctx, args: "true" if check_permission(ctx, "perm", (args or "").strip().lower().replace(" ", "_")) else "false"
    )
    registry.register_var("isowner", lambda ctx, args: "true" if check_permission(ctx, "owner", "") else "false")
