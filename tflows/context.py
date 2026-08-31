"""Execution context passed through tflows scripts.

:class:`FlowContext` wraps the Discord message that triggered a script and
forwards every attribute needed by script functions (``channel``, ``author``,
``guild``, ``mentions``, ...) to the underlying message. This keeps the
scripting API identical whether the script is run from a raw
:class:`discord.Message` or from a :class:`FlowContext`.
"""


class FlowContext:
    """A lightweight context object available to every scripted function.

    Parameters
    ----------
    message:
        The :class:`discord.Message` that triggered the script.
    bot:
        The :class:`~tflows.FlowBot` instance executing the script.
    command_name:
        The script command name that was invoked (``None`` when run directly).
    args:
        Raw argument string that followed the command name.
    """

    __slots__ = ("message", "bot", "command_name", "args")

    def __init__(self, message, bot=None, command_name=None, args=""):
        self.message = message
        self.bot = bot
        self.command_name = command_name
        self.args = args

    # ------------------------------------------------------------------
    # Forwarded attributes (kept identical to discord.Message)
    # ------------------------------------------------------------------
    @property
    def channel(self):
        return self.message.channel

    @property
    def author(self):
        return self.message.author

    @property
    def guild(self):
        return self.message.guild

    @property
    def mentions(self):
        return self.message.mentions

    @property
    def content(self):
        return self.message.content

    @property
    def _state(self):
        return self.message._state

    def __getattr__(self, item):
        # Any other attribute delegates to the underlying message, so existing
        # script functions that touch extra fields keep working unchanged.
        return getattr(self.message, item)

    @classmethod
    def from_message(cls, message, args=""):
        """Build a :class:`FlowContext` from a raw message.

        The bot is discovered from the message's connection state when
        possible, so ``engine.run(message, code)`` keeps working.
        """
        bot = None
        try:
            bot = message._state._get_client()
        except Exception:
            bot = None
        return cls(message=message, bot=bot, args=args)

    def __repr__(self):
        return (
            f"<FlowContext command_name={self.command_name!r} "
            f"author={self.author!r} channel={self.channel!r}>"
        )
