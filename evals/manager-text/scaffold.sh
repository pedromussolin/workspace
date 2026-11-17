#!/usr/bin/env bash
# Same fixture as period-last-week: the manager text is written from the same period summary.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/fixture.sh"
build_fixture
add_period_prs
