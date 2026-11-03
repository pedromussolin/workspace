#!/usr/bin/env bash
# The fixture of the daily evals plus the period fields the PR search of a period reads. "Today" is
# the fixed Monday 2026-10-26, so "semana passada" is 2026-10-19 to 2026-10-25.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/../lib/fixture.sh"
build_fixture

cat > "$HOME/.eval-gh-search.json" <<'JSON'
{"data":{"search":{"issueCount":2,"pageInfo":{"hasNextPage":false,"endCursor":null},"nodes":[
{"number":42,"title":"TS-103 ajusta a resposta da rota","state":"MERGED","mergedAt":"2026-10-23T18:00:00Z","createdAt":"2026-10-22T12:00:00Z","closedAt":"2026-10-23T18:00:00Z","updatedAt":"2026-10-23T18:00:00Z","baseRefName":"master","headRefName":"feature/TS-103-resposta","url":"https://github.com/example/demo-api/pull/42","repository":{"name":"demo-api"}},
{"number":43,"title":"TS-101 corrige a validação do formulário","state":"OPEN","mergedAt":null,"createdAt":"2026-10-23T12:00:00Z","closedAt":null,"updatedAt":"2026-10-23T17:40:00Z","baseRefName":"main","headRefName":"feature/TS-101-validacao","url":"https://github.com/example/demo-front/pull/43","repository":{"name":"demo-front"}}
]}}}
JSON
