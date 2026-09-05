def _split_args(ctx):
    raw = getattr(ctx, "args", "")
    return raw.split() if raw else []


def _args_var(ctx, args):
    return getattr(ctx, "args", "") or ""


def _arg_var(ctx, args):
    parts = _split_args(ctx)
    spec = (args or "").strip()

    if not spec:
        return ""

    if ":" in spec:
        start_spec, end_spec = spec.split(":", 1)
        try:
            start = int(start_spec) if start_spec.strip() else 0
        except ValueError:
            return ""
        try:
            end = int(end_spec) if end_spec.strip() else None
        except ValueError:
            return ""
        return " ".join(parts[start:end])

    try:
        index = int(spec)
    except ValueError:
        # Named slash-command parameter: $arg(name).
        kwargs = getattr(ctx, "kwargs", None) or {}
        for key, value in kwargs.items():
            if key.lower() == spec.lower():
                return str(value)
        return ""

    if index < 0:
        index += len(parts)
    if 0 <= index < len(parts):
        return parts[index]
    return ""


def _argcount_var(ctx, args):
    return str(len(_split_args(ctx)))


def setup(registry):
    registry.register_var("args", _args_var)
    registry.register_var("arg", _arg_var)
    registry.register_var("argcount", _argcount_var)
