"""Old path of ws.tracker.jira.adf, removed in Task 18."""

import sys

from ws.tracker.jira import adf

sys.modules[__name__] = adf
