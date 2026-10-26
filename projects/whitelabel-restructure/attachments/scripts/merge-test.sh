#!/usr/bin/env bash
# Junta as branches do épico sobre a 04 numa worktree descartável e confere se o conjunto compila.
# Uso: merge-test.sh <repo-do-front> [branch ...]
#   Sem branches, junta as áreas (`refact/TS-535x`/`TS-536x`) e as fatias 14/15 (`feature/TS-5371/5372`).
# Ambiente: FULL=1 também roda build e a suíte inteira (com o lock comum) e compara com a base.
# Conflito conhecido tem resolução em $PRIV/resolucoes/<branch com _ no lugar de />.sh (fora do repo,
# porque cita caminhos com nomes reais). Os outros param a worktree no conflito, para estudar.
set -u
REPO=$(realpath "$1"); shift
BASE=${BASE:-feature/TS-5361-componentes-overlay-tabela}
PRIV=${PRIV:-$HOME/repos/.reestrutura_whitelabel}
WT=$PRIV/merge-teste
CHROME=${CHROME_BIN:-$HOME/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome}
BRANCHES=("$@")
[ ${#BRANCHES[@]} -gt 0 ] || mapfile -t BRANCHES < <(git -C "$REPO" for-each-ref --format='%(refname:short)' 'refs/heads/refact/TS-53[56]*' 'refs/heads/feature/TS-537[0-2]-*' | sort)

[ -d "$WT" ] || { git -C "$REPO" worktree add -q --detach "$WT" "$BASE" && cp -al "$REPO/node_modules" "$WT/node_modules"; }
cd "$WT" || exit 1
git merge --abort 2>/dev/null
git checkout -q --detach "$BASE"
for b in "${BRANCHES[@]}"; do
  if git merge -q --no-edit "$b" >/dev/null 2>&1; then
    echo "ok        $b"
  else
    files=$(git diff --name-only --diff-filter=U | tr '\n' ' ')
    fix=$PRIV/resolucoes/$(echo "$b" | tr '/' '_').sh
    if [ -x "$fix" ] && "$fix" && git commit -q --no-edit; then
      echo "resolvido $b (conflito conhecido: $files)"
    else
      echo "CONFLITO  $b: $files"
      echo "(worktree parada no conflito: $WT)"
      exit 1
    fi
  fi
done
echo "tsc: app $(npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -c 'error TS') erros, specs $(npx tsc -p tsconfig.spec.json --noEmit 2>&1 | grep -c 'error TS') erros"
if [ -n "${FULL:-}" ]; then
  LOG=$PRIV/logs/merge-teste; mkdir -p "$LOG"
  flock "$PRIV/ng.lock" bash -c "npx ng build > '$LOG/build.log' 2>&1; echo \$? > '$LOG/build.rc'; CHROME_BIN='$CHROME' npx ng test --watch=false --browsers=ChromeHeadless > '$LOG/test.log' 2>&1"
  echo "build: $([ "$(cat "$LOG/build.rc")" = 0 ] && echo ok || echo FALHOU)"
  sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g' "$LOG/test.log" | grep -E '^TOTAL'
  sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g; s/^Chrome Headless [^)]*\) //' "$LOG/test.log" | grep -E " FAILED$" | sort -u > "$LOG/falhas.txt"
  echo "falhas fora da base: $(comm -13 "$PRIV/base-04-falhas.txt" "$LOG/falhas.txt" | wc -l)"
fi
