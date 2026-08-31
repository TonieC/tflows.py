from ..utils import random_int


def _random_var(ctx, args):
    if not args:
        return str(random_int(0, 100))

    parts = [p.strip() for p in args.split(",") if p.strip()]
    if not parts:
        return ""

    if len(parts) == 1:
        result = random_int(0, parts[0])
    else:
        result = random_int(parts[0], parts[1])

    if result is None:
        return ""
    return str(result)


def setup(registry):
    registry.register_var("random", _random_var)
