#!/usr/bin/env bash
# Builds the made-up observation the observe evals run against, inside the run's HOME.
#
# Task TS-5 of project demo: a job switched off on Friday 2026-11-06, observed for 5 business days.
# "Today" is Thursday 2026-11-12, so the latest closed day is 2026-11-11 (day 3). The variant
# names the checks: `database` has one database count, `full` adds two observability counts and a
# yes/no question. `ws observe` itself answers from scripts/eval_observe.py (see the ws shim):
# the replica host is db.invalid and is never reached.
set -euo pipefail

build_observe_fixture() {
  local variant=$1
  echo 2026-11-12 > "$HOME/.eval-today"
  echo "$variant" > "$HOME/.eval-observe"

  mkdir -p "$HOME/.config/workspace"
  cat > "$HOME/.config/workspace/config.toml" <<'TOML'
[observability]
provider = "datadog"

[database.replica]
engine = "postgres"
host = "db.invalid"
port = 5432
name = "demo"
user = "leitura"
TOML

  local folder="$HOME/.local/share/workspace/projects/demo/observations"
  mkdir -p "$folder"
  chmod 700 "$HOME/.local/share/workspace/projects/demo" "$folder"
  {
    cat <<'TOML'
version = 1
task = "TS-5"
job = "job de exemplo que copia a fila"
switched_off = 2026-11-06
days = 5
timezone = "America/Sao_Paulo"

[[checks]]
id = "fila-pendente"
kind = "database"
label = "itens novos na fila de exemplo"
database = "replica"
sql = "select count(*) from fila_exemplo where criado_em >= :day_from and criado_em < :day_to"
expect = "== 0"
TOML
    if [ "$variant" = full ]; then
      cat <<'TOML'

[[checks]]
id = "chamadas-rota"
kind = "observability"
label = "chamadas da rota que o job usava"
signal = "metrics"
query = "sum:trace.http.request.hits{service:demo-api,resource_name:post_/exemplo}.as_count()"
expect = "== 0"

[[checks]]
id = "logs-job"
kind = "observability"
label = "logs do job"
signal = "logs"
query = "service:demo-job status:info"
expect = "== 0"

[[checks]]
id = "conciliacao-ok"
kind = "manual"
question = "A conciliação de ontem fechou sem diferença?"
TOML
    fi
  } > "$folder/TS-5.toml"
  chmod 600 "$folder/TS-5.toml"
}
