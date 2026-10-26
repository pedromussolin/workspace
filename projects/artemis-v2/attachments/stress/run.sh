#!/bin/bash
# Orquestra os cenários: troca código/concorrência do worker e injeta falhas.
set -u
cd "$(dirname "$0")"
MASTER=${MASTER:?caminho da cópia da master}
BRANCH=${BRANCH:?caminho da cópia da branch}

use() {  # use <master|branch> <concorrência> [LOCK_TIMEOUT_MS] [STATEMENT_TIMEOUT_MS]
  local dir=$BRANCH; [ "$1" = master ] && dir=$MASTER
  CODE_DIR=$dir CONCURRENCY=$2 LOCK_TIMEOUT_MS=${3:-60000} STATEMENT_TIMEOUT_MS=${4:-480000} \
    docker compose up -d --force-recreate worker driver >/dev/null 2>&1
  docker compose exec -T driver sh -c "cp -r /ww /tmp/ww && pip install -q --no-deps --user /tmp/ww >/dev/null 2>&1"
  for _ in $(seq 60); do docker compose logs worker 2>&1 | grep -q "ready\." && break; sleep 2; done
  echo "== $(date +%T) código=$1 concorrência=$2 lock_timeout=${3:-60000} statement_timeout=${4:-480000}"
}

drive() { docker compose exec -T driver sh -c "cd /app && python /estresse/driver.py $*" > logs/$2.out 2>&1; \
          python3 -c "import json;d=json.load(open('results/$2.json'))['summary'];print('   ', d['label'], '| finais:', d['finals'], '| sumidos:', d['vanished'], '| invariantes:', {k:v for k,v in d['invariants'].items() if v})" 2>/dev/null || tail -3 logs/$2.out; }

mkdir -p logs results
for step in "$@"; do
  case $step in
    quente-*) v=${step#quente-}; use $v 2; drive rajada $v-c2-rajada-quente;;
    base-c16) use branch 16; for s in clique_repetido acumula gigante; do drive $s branch-c16-$s; done;;
    escala-*) v=${step#escala-}; use $v 16 60000 10000; drive gigante $v-c16-gigante-escala;;
    trava16-*) v=${step#trava16-}; use $v 16; drive trava_externa $v-c16-trava_externa --locked 20 --others 30 --hold 400 --timeout 1000;;
    parado16-*) v=${step#parado16-}; use $v 16
      docker compose pause worker >/dev/null
      ( sleep 360; docker compose unpause worker >/dev/null ) &
      drive worker_parado $v-c16-worker_parado --rate 2 --timeout 600; wait;;
    morto16-*) v=${step#morto16-}; use $v 16
      ( sleep 12; docker compose kill -s KILL worker >/dev/null; sleep 5; \
        CODE_DIR=$([ $v = master ] && echo $MASTER || echo $BRANCH) CONCURRENCY=16 docker compose up -d worker >/dev/null 2>&1 ) &
      drive worker_morto $v-c16-worker_morto --rate 2 --timeout 700; wait;;
    mortotrava-*) v=${step#mortotrava-}; use $v 16
      rm -f logs/$v-c16-morto_com_trava.started
      ( until [ -f logs/$v-c16-morto_com_trava.started ]; do sleep 0.5; done; sleep 8; docker compose kill -s KILL worker >/dev/null; sleep 5; \
        CODE_DIR=$([ $v = master ] && echo $MASTER || echo $BRANCH) CONCURRENCY=16 docker compose up -d worker >/dev/null 2>&1 ) &
      drive morto_com_trava $v-c16-morto_com_trava --rate 2 --hold 45 --timeout 700; wait;;
    redis16-*) v=${step#redis16-}; use $v 16
      rm -f logs/$v-c16-redis_fora.started
      ( until [ -f logs/$v-c16-redis_fora.started ]; do sleep 0.5; done; sleep 3; docker compose pause redis >/dev/null; sleep 30; docker compose unpause redis >/dev/null ) &
      drive redis_fora $v-c16-redis_fora --rate 4 --timeout 420; wait;;
    teste) use branch 2; drive clique_repetido teste-clique;;
    branch-c2)  use branch 2;  for s in rajada clique_repetido acumula gigante status; do drive $s branch-c2-$s; done;;
    branch-c16) use branch 16; drive rajada branch-c16-rajada;;
    master-c16) use master 16; for s in rajada clique_repetido; do drive $s master-c16-$s; done;;
    master-c2)  use master 2;  drive rajada master-c2-rajada;;
    trava-branch) use branch 2; drive trava_externa branch-c2-trava_externa --hold 400 --timeout 900;;
    trava-master2) use master 2; drive trava_externa master-c2-trava_externa --hold 400 --timeout 900;;
    trava-master16) use master 16; drive trava_externa master-c16-trava_externa --hold 400 --timeout 900;;
    gigante-timeout) use branch 2 60000 15000; drive gigante branch-c2-gigante-timeout;;
    parado-*) v=${step#parado-}; use $v 2
      docker compose pause worker >/dev/null
      ( sleep 360; docker compose unpause worker >/dev/null ) &
      drive worker_parado $v-c2-worker_parado --rate 2 --timeout 600; wait;;
    morto-*) v=${step#morto-}; use $v 2
      ( sleep 12; docker compose kill -s KILL worker >/dev/null; sleep 5; \
        CODE_DIR=$([ $v = master ] && echo $MASTER || echo $BRANCH) CONCURRENCY=2 docker compose up -d worker >/dev/null 2>&1 ) &
      drive worker_morto $v-c2-worker_morto --rate 2 --timeout 700; wait;;
    redis-*) v=${step#redis-}; use $v 2
      ( sleep 4; docker compose pause redis >/dev/null; sleep 30; docker compose unpause redis >/dev/null ) &
      drive redis_fora $v-c2-redis_fora --rate 4 --timeout 300; wait;;
  esac
done
