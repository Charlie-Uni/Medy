"""Safe fixed transport codes and local queue-capacity failures."""


class ScoreExportError(Exception):
    """Only safe fixed codes; never attach remote response bodies or credentials."""


class ScoreQueueFull(Exception):
    """The bounded local queue needs operator attention before more scores can be accepted."""
