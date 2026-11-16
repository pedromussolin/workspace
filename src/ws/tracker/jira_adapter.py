"""Old path of ws.tracker.jira.adapter, removed in Task 18."""

import sys

from ws.tracker.jira import adapter

sys.modules[__name__] = adapter
