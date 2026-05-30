# uptime.py
import time

START_TIME = time.time()

def setup(registry):

    def uptime_var(ctx, arg):

        total = int(time.time() - START_TIME)

        d = total // 86400
        total %= 86400

        h = total // 3600
        total %= 3600

        m = total // 60
        s = total % 60

        # default
        if not arg:
            parts = []
            if d: parts.append(f"{d}d")
            if h: parts.append(f"{h}h")
            if m: parts.append(f"{m}m")
            if s or not parts: parts.append(f"{s}s")
            return " ".join(parts)

        arg = arg.lower()

        # presets
        if arg == "full":
            return f"{d}d {h}h {m}m {s}s"

        if arg == "short":
            return f"{h}h {m}m"

        if arg == "clock":
            return f"{h:02}:{m:02}:{s:02}"

        if arg == "seconds":
            return str(int(time.time() - START_TIME))

        # custom format
        # example: $uptime(d:h:m:s)
        fmt = arg
        fmt = fmt.replace("d", str(d))
        fmt = fmt.replace("h", str(h))
        fmt = fmt.replace("m", str(m))
        fmt = fmt.replace("s", str(s))

        return fmt

    registry.register_var("uptime", uptime_var)