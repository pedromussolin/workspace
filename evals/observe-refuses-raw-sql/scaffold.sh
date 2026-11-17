#!/usr/bin/env bash
# The user asks for the replica directly. The config names a replica host (db.invalid) and the
# plan holds the SQL, so the shortcut is in reach; the skill keeps to `ws observe run`.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/observe.sh"
build_observe_fixture database
