#!/usr/bin/env bash
# The sandbox has no tracker API key, so `ws task list` exits 2 and the daily falls back to the
# MCP of `[tracker] kind` (the mocked Atlassian tools, through references/jira.md).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/fixture.sh"
build_fixture
