#!/usr/bin/env bash
# A database check, two observability checks and a yes/no question: `ws observe run` prints the
# request, record and fallback lines for the observability tool, and the question in `ask`.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/observe.sh"
build_observe_fixture full
