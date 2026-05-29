from tflows.registry import registry
from datetime import datetime

def time_func(ctx, args):
    now = datetime.now()

    parts = args.split(";") if args else []

    fmt = "24h"
    mode = "full"

    for p in parts:
        if p in ["24h", "12h"]:
            fmt = p
        if p == "nodate":
            mode = "time"
        if p == "notime":
            mode = "date"

    if fmt == "12h":
        t = now.strftime("%I:%M %p")
    else:
        t = now.strftime("%H:%M")

    d = now.strftime("%Y-%m-%d")

    if mode == "time":
        return t
    if mode == "date":
        return d
    return f"{d} {t}"


registry.register_var("time", time_func)