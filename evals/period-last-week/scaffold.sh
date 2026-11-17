#!/usr/bin/env bash
# The daily fixture plus the PR search of a period. "Today" is the fixed Monday 2026-10-26, so
# "semana passada" is 2026-10-19 to 2026-10-25. The sandbox has no tracker API key, so the cards
# come from the mocked tracker MCP, as in tracker-mcp-fallback.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/fixture.sh"
build_fixture
add_period_prs
