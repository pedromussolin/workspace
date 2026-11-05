#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/fixture.sh"
build_fixture

# TS-103 is only on demo-api's sandbox branch of the remote (not on its main), so it proves
# validation; TS-102 stays a local branch and proves in progress.
git init -q --bare "$HOME/remotes/demo-api.git"
git -C "$HOME/repos/demo-api" remote add origin "$HOME/remotes/demo-api.git"
git -C "$HOME/repos/demo-api" push -q origin main:sandbox
git -C "$HOME/repos/demo-api" fetch -q origin
