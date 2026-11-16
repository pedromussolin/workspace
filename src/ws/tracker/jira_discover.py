"""Old path of ws.tracker.jira.discover, removed in Task 18."""

import sys

from ws.tracker.jira import discover

sys.modules[__name__] = discover
