#!/usr/bin/env bash
# Abre o portal de uma worktree do front com o BFF falso e dados fictícios, para navegar à mão.
# Uso: portal-local.sh <worktree-do-front> [dados.json]
#   Sem dados, usa $PRIV/smoke-dados/todas-acesso-21.json (todas as telas, com o controle de acesso).
#   BUILD=1 refaz o build antes. THEME_KEY troca a marca (chave real em privado.md).
#   ORG troca a organização: plgn (padrão) é a visão interna; outro valor (ex.: ORG=parceiro) é a de parceiro.
#   Com o portal no ar, http://localhost:4300/__marcas troca a marca (cookie), sem reiniciar.
# Abra http://localhost:4300 (no Windows também, pelo WSL). As mudanças ficam numa cópia dos dados
# ($PRIV/smoke-dados/alteracoes/), que sobrevive a reiniciar; http://localhost:4300/__reset volta ao original.
set -e
PRIV=${PRIV:-$HOME/repos/.reestrutura_whitelabel}
WT=$(cd "${1:?worktree do front}" && pwd)
DADOS=${2:-$PRIV/smoke-dados/todas-acesso-21.json}
DIST=$WT/dist/apl-credit-whitelabel/browser
if [ -n "${BUILD:-}" ] || [ ! -f "$DIST/index.html" ]; then
  (cd "$WT" && flock "$PRIV/ng.lock" npx ng build)
fi
SERVE=1 FIXTURES=$DADOS PW_DIR=$PRIV/pw/node_modules \
  node "$(dirname "$0")/smoke.mjs" "$DIST" "$(mktemp -d)"
