"""Old path of ws.tracker.jira.rules, removed in Task 18."""

import sys

from ws.tracker.jira import rules

sys.modules[__name__] = rules
