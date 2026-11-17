#!/usr/bin/env bash
# The BFF went to the sandbox on 2026-11-12; the mocked execute_code answers its check: every
# check ok and all of the after window's traffic on the expected version, so the front may go.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/deploy.sh"
build_deploy_fixture
