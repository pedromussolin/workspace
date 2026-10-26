#!/usr/bin/env bash
# Valida uma branch de área do front contra a base da 04, num comando só.
# Uso: validate-batch.sh <worktree-do-front> [rota-ou-cena ...]
#   Sem rotas, pula o smoke. Com SCENES no ambiente, o smoke usa as cenas (ver smoke.mjs).
# Ambiente (opcional):
#   FIXTURES=<json>       dados fictícios do BFF falso no smoke
#   SKIP_TESTS=1          pula build/lint/testes (só commits e smoke)
#   BASE=<branch>         base da comparação (padrão: a 04)
#   BASE_FALHAS=<arquivo> falhas de teste da base (padrão: base-04-falhas.txt; da master: base-master-falhas.txt)
#   BASE_LINT=<e/a>       erros/avisos de lint da base, só para o texto (padrão: 59/281, da 04)
# Arquivos locais, fora do repositório (PRIV): o lock comum, as listas de falhas da base, os logs
# e o playwright-core, e o `tema-secundario` (a chave real da marca Dots, usada no terceiro smoke).
# A lista de falhas e os logs são de código da empresa e não entram aqui.
set -u
WT=$(realpath "$1"); shift
ROUTES=("$@")
BASE=${BASE:-feature/TS-5361-componentes-overlay-tabela}
PRIV=${PRIV:-$HOME/repos/.reestrutura_whitelabel}
LOCK=$PRIV/ng.lock
BASE_FALHAS=${BASE_FALHAS:-$PRIV/base-04-falhas.txt}
BASE_LINT=${BASE_LINT:-59/281}
CHROME=${CHROME_BIN:-$HOME/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome}
SMOKE=$(dirname "$(realpath "$0")")/smoke.mjs
NAME=$(git -C "$WT" rev-parse --abbrev-ref HEAD | tr '/' '_')
LOG=$PRIV/logs/$NAME
mkdir -p "$LOG"
strip() { sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g'; }
ok=1

echo "## $NAME ($(git -C "$WT" rev-list --count "$BASE..HEAD") commits sobre $BASE)"
[ -z "$(git -C "$WT" status --porcelain)" ] || { echo "- working tree com mudanças não commitadas"; ok=0; }

long=$(git -C "$WT" log --format=%s "$BASE..HEAD" | awk 'length > 72')
[ -z "$long" ] || { echo "- assuntos com mais de 72 caracteres:"; echo "$long" | sed 's/^/    /'; ok=0; }
git -C "$WT" log --format=%B "$BASE..HEAD" | grep -qiE "co-authored-by|generated with" && { echo "- há trailer Co-Authored-By/Generated with"; ok=0; }

# tsc de app e specs em cada commit, numa worktree separada para não mexer na do agente.
TSC=$PRIV/tsc-$NAME
[ -d "$TSC" ] || git -C "$WT" worktree add -q --detach "$TSC" HEAD
# node_modules da worktree do agente, copiado de novo quando o lock muda (dependência nova).
lock=$(sha1sum < "$WT/package-lock.json")
if [ "$(cat "$TSC/.lock-sha" 2>/dev/null)" != "$lock" ]; then
  rm -rf "$TSC/node_modules" && cp -al "$WT/node_modules" "$TSC/node_modules" && echo "$lock" > "$TSC/.lock-sha"
fi
broken=""
for c in $(git -C "$WT" rev-list --reverse "$BASE..HEAD"); do
  git -C "$TSC" checkout -q --detach "$c"
  a=$(cd "$TSC" && npx tsc -p tsconfig.app.json --noEmit 2>&1 | grep -c "error TS")
  s=$(cd "$TSC" && npx tsc -p tsconfig.spec.json --noEmit 2>&1 | grep -c "error TS")
  [ "$a$s" = "00" ] || broken+="    $(git -C "$WT" log -1 --format='%h %s' "$c") (app $a, spec $s)"$'\n'
done
[ -z "$broken" ] && echo "- commits: todos compilam sozinhos" || { echo "- commits que não compilam sozinhos:"; printf "%s" "$broken"; ok=0; }

if [ -z "${SKIP_TESTS:-}" ]; then
  flock "$LOCK" bash -c "cd '$WT' && npx ng build > '$LOG/build.log' 2>&1; echo \$? > '$LOG/build.rc'; npx ng lint > '$LOG/lint.log' 2>&1; CHROME_BIN='$CHROME' npx ng test --watch=false --browsers=ChromeHeadless > '$LOG/test.log' 2>&1"
  [ "$(cat "$LOG/build.rc")" = 0 ] && echo "- build: ok" || { echo "- build: FALHOU (ver $LOG/build.log)"; ok=0; }
  initial=$(strip < "$LOG/build.log" | grep -m1 "Initial total" | awk -F'|' '{gsub(/ /,"",$3); gsub(/ /,"",$4); print $3" ("$4" na rede)"}')
  [ -n "$initial" ] && echo "- bundle inicial: $initial"
  echo "- lint: $(grep -cE '^\s+[0-9]+:[0-9]+\s+error' "$LOG/lint.log") erros / $(grep -cE '^\s+[0-9]+:[0-9]+\s+warning' "$LOG/lint.log") avisos (base $BASE_LINT)"
  echo "- testes: $(strip < "$LOG/test.log" | grep -E '^TOTAL' || echo 'sem TOTAL, ver o log')"
  strip < "$LOG/test.log" | sed -E 's/^Chrome Headless [^)]*\) //' | grep -E " FAILED$" | sort -u > "$LOG/falhas.txt"
  new=$(comm -13 "$BASE_FALHAS" "$LOG/falhas.txt")
  fixed=$(comm -23 "$BASE_FALHAS" "$LOG/falhas.txt" | wc -l)
  if [ -n "$new" ]; then
    # Falha nova pode ser spec instável (depende da ordem aleatória do Jasmine): roda a suíte de novo
    # e só conta como real o que falhar nas duas vezes.
    flock "$LOCK" bash -c "cd '$WT' && CHROME_BIN='$CHROME' npx ng test --watch=false --browsers=ChromeHeadless > '$LOG/test2.log' 2>&1"
    strip < "$LOG/test2.log" | sed -E 's/^Chrome Headless [^)]*\) //' | grep -E " FAILED$" | sort -u > "$LOG/falhas2.txt"
    flaky=$(comm -23 <(echo "$new") "$LOG/falhas2.txt")
    new=$(comm -12 <(echo "$new") "$LOG/falhas2.txt")
    [ -z "$flaky" ] || { echo "- instáveis (falharam só numa de duas rodadas):"; echo "$flaky" | sed 's/^/    /'; }
  fi
  [ -z "$new" ] && echo "- falhas novas: nenhuma ($fixed da base corrigidas)" || { echo "- FALHAS NOVAS (nas duas rodadas):"; echo "$new" | sed 's/^/    /'; ok=0; }
fi

if [ ${#ROUTES[@]} -gt 0 ] || [ -n "${SCENES:-}" ]; then
  export CHROME_BIN=$CHROME PW_DIR=$PRIV/pw/node_modules
  out=$PRIV/logs/$NAME/prints
  rm -rf "$out"
  smoke() { flock "$LOCK" env "$@" node "$SMOKE" "$WT/dist/apl-credit-whitelabel/browser" "$out/${1#*=}" "${ROUTES[@]}" 2>&1; }
  res=$( { smoke VARIANTE=claro; smoke SCHEME=dark ONLY=desktop; smoke THEME_KEY="$(cat "$PRIV/tema-secundario" 2>/dev/null || echo default)" ONLY=desktop; } | grep -vE " ok$|-> |navegação interna" )
  # Sem print nenhum, o smoke nem subiu (ex.: porta 4300 ou 8765 ocupada pelo portal local).
  if [ "$(find "$out" -name '*.png' 2>/dev/null | wc -l)" = 0 ]; then echo "- smoke: NÃO RODOU (nenhum print; porta ocupada?)"; echo "$res" | tail -3 | cut -c1-220 | sed 's/^/    /'; ok=0
  elif echo "$res" | grep -q "ERROS NO CONSOLE"; then echo "- smoke: com erros"; echo "$res" | grep -v "sem erros" | cut -c1-220 | sed 's/^/    /'; ok=0
  else echo "- smoke: claro (desktop e celular), escuro e Dots sem erro de página, de console nem rolagem lateral"; fi
  echo "- prints: $out"
fi

[ $ok = 1 ] && echo "RESULTADO: ok" || echo "RESULTADO: com pendências"
