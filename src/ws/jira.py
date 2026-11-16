"""Old path of ws.tracker.jira.client, removed in Task 18."""

import sys

from ws.tracker.jira import client

sys.modules[__name__] = client
