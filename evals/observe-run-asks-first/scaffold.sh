#!/usr/bin/env bash
# One database check: `ws observe run` is the only way to the replica, and the approval box of
# Claude Code sees it only when it is a Bash call of its own.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/observe.sh"
build_observe_fixture database
