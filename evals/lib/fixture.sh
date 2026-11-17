#!/usr/bin/env bash
# Builds the made-up workspace the daily-skill evals run against, inside the run's HOME.
#
# "Today" is a fixed Monday, so the window opens on the Friday before it. TS-107 is a Thursday
# commit (before the window), the two demo-notes commits carry no key, and TS-106 has no card.
set -euo pipefail

TODAY=2026-10-26

commit() {
  local repo=$1 when=$2 subject=$3
  GIT_AUTHOR_NAME="Dev Example" GIT_AUTHOR_EMAIL=dev@example.com GIT_AUTHOR_DATE="$when" \
    GIT_COMMITTER_NAME="Dev Example" GIT_COMMITTER_EMAIL=dev@example.com GIT_COMMITTER_DATE="$when" \
    git -C "$repo" commit -q --allow-empty -m "$subject"
}

new_repo() {
  local repo="$HOME/repos/$1"
  mkdir -p "$repo"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email dev@example.com
  git -C "$repo" config user.name "Dev Example"
}

build_fixture() {
  echo "$TODAY" > "$HOME/.eval-today"

  mkdir -p "$HOME/.config/workspace"
  cat > "$HOME/.config/workspace/config.toml" <<'TOML'
[tracker]
kind = "jira"

[tracker.jira]
site = "https://example.atlassian.net"
email = "dev@example.com"

[tracker.jira.status_overrides]
"Em validação" = "validation"
"Ready Deploy" = "ready_deploy"

[standup]
repo_roots = ["~/repos"]

[board]
fetch = false
default_profile = "trunk"

[[board.profiles.trunk.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["sandbox"]

[[board.profiles.trunk.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["main"]

[board.statuses]
in_progress = "Em andamento"
validation = "Em validação"
ready_deploy = "Ready Deploy"
TOML

  new_repo demo-front
  commit "$HOME/repos/demo-front" 2026-10-22T16:20:00-03:00 "TS-101 monta a tela de exemplo"
  commit "$HOME/repos/demo-front" 2026-10-22T17:45:00-03:00 "TS-107 mexe no cabeçalho"
  commit "$HOME/repos/demo-front" 2026-10-23T11:05:00-03:00 "TS-106 ajusta o contraste do botão"
  commit "$HOME/repos/demo-front" 2026-10-23T17:30:00-03:00 "TS-101 corrige a validação do formulário"

  new_repo demo-notes
  commit "$HOME/repos/demo-notes" 2026-10-23T09:30:00-03:00 "atualiza as anotações"
  commit "$HOME/repos/demo-notes" 2026-10-23T09:40:00-03:00 "ajusta o índice"

  new_repo demo-api
  commit "$HOME/repos/demo-api" 2026-10-21T10:00:00-03:00 "TS-103 ajusta a resposta da rota"
  git -C "$HOME/repos/demo-api" switch -q -c feature/TS-102-rota
  commit "$HOME/repos/demo-api" 2026-10-23T15:10:00-03:00 "TS-102 cria a rota de exemplo"
  git -C "$HOME/repos/demo-api" switch -q main

  cat > "$HOME/.eval-gh-search.json" <<'JSON'
{"data":{"search":{"issueCount":1,"nodes":[{"number":42,"title":"TS-103 ajusta a resposta da rota","state":"MERGED","mergedAt":"2026-10-23T18:00:00Z","updatedAt":"2026-10-23T18:00:00Z","headRefName":"feature/TS-103-resposta","url":"https://github.com/example/demo-api/pull/42","repository":{"name":"demo-api"}}]}}}
JSON

  mkdir -p "$HOME/workspace/projects/demo-project"
  cat > "$HOME/workspace/projects/demo-project/CONTINUE.md" <<'MD'
# Continuar

## Próximo passo

Revisar a rota de exemplo (TS-102) e abrir o PR.
MD
}

# TS-103 is only on demo-api's sandbox branch of the remote (not on its main), so it proves
# validation; TS-102 stays a local branch and proves in progress.
add_sandbox_remote() {
  git init -q --bare "$HOME/remotes/demo-api.git"
  git -C "$HOME/repos/demo-api" remote add origin "$HOME/remotes/demo-api.git"
  git -C "$HOME/repos/demo-api" push -q origin main:sandbox
  git -C "$HOME/repos/demo-api" fetch -q origin
}
