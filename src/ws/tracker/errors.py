"""Errors every tracker adapter raises; the core maps them to exit codes."""


class TrackerSetup(Exception):
    """The tracker is not configured or reachable by configuration (exit 2)."""


class TrackerError(Exception):
    """The tracker answered wrongly or not at all (exit 3). `status` is the HTTP status (None
    without an answer); `uncertain` means a write may have been applied anyway."""

    def __init__(self, message: str, status: int | None = None, uncertain: bool = False):
        super().__init__(message)
        self.status = status
        self.uncertain = uncertain
