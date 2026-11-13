+++
card = "TS-5279"
type = "task"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Highest"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 01 — Réplica de leitura no init do SQLAlchemy

- **Status:** concluída no código em 07/10/2026 — TS-5279, PR #2628 (merge
  `7469008` na master da platform-cessao). Variável da réplica já no
  Parameter Store; pendente: conferência no Datadog e medição pós-deploy (ver "Como foi feito").
- **Repos:** platform-cessao.
- **Decisões:** [D1 (tomada) e D2 (pendente)](../decisions.md).

## Problema

As consultas pesadas da tela (listagens de lotes, pagamentos) disputam o
mesmo banco com o processamento do Celery (entrada de pagamentos, fechamento,
conciliação). A ideia é mandar as leituras da tela para uma **réplica de
leitura** e deixar o primário para quem grava.

## O que a stack permite

Versões em produção (conferidas na imagem `platform-cessao_devcontainer-web`):
Flask-SQLAlchemy **2.5.1**, SQLAlchemy **1.3.24**, Python 3.8.

- **Não existe configuração pronta** de leitura/escrita. O
  `SQLALCHEMY_BINDS` cria a segunda engine (conexão) com as mesmas opções de
  pool, mas só sabe ligar um *model* inteiro a um banco, não separar leitura
  de escrita.
- A escolha de banco por comando é feita no `Session.get_bind`. Por isso a
  solução é: `SQLALCHEMY_BINDS` + uma Session própria que sobrescreve
  `get_bind`.
- O Alembic (`cessao/migrations/env.py`) usa só `SQLALCHEMY_DATABASE_URI`; a
  réplica não entra nas migrations.

## Proposta

1. **Config** (`cessao/config/__init__.py`): nova variável opcional
   `DB_POSTGRESQL_PLATFORM_CESSAO_REPLICA`. Não entra em `nao_encontradas`,
   porque é opcional.
2. **Init** (`cessao/app_factory.py`, `configure_app`): se a variável existir,
   `app.config["SQLALCHEMY_BINDS"] = {"replica": uri}`. Sem ela, comportamento
   idêntico ao de hoje — é também o botão de desligar.
3. **Session** (`cessao/extensions.py`): `db` passa a ser
   `SQLAlchemyComReplica`, cuja Session decide o banco:

```python
class SessaoComReplica(SignallingSession):
    _fixada_no_primario = False

    def get_bind(self, mapper=None, clause=None):
        e_leitura = (
            not self._flushing
            and isinstance(clause, GenerativeSelect)
            and not _trava_linhas(clause)
        )
        if not e_leitura:
            self._fixada_no_primario = True
        elif not self._fixada_no_primario and _replica_liberada(self.app):
            return get_state(self.app).db.get_engine(self.app, bind="replica")
        return super().get_bind(mapper, clause)
```

Protótipo completo: [attachments/replica/routing.py](../attachments/replica/routing.py).

### Regras de roteamento

| Comando | Vai para | Por quê |
|---|---|---|
| `SELECT` puro (ORM ou Core), paginação, lazy load | réplica | é o que queremos aliviar |
| flush, INSERT/UPDATE/DELETE, `query.update()` | primário | réplica não aceita escrita |
| `SELECT ... FOR UPDATE`, inclusive só na subquery | primário | trava linhas; não roda em réplica. O SQLAlchemy 1.3 coloca o `FOR UPDATE OF` só na subquery quando há eager load + LIMIT, por isso a checagem percorre o statement inteiro |
| `text(...)` e strings SQL | primário | pode ser DML ou advisory lock; não dá para saber |
| `session.connection()` sem argumentos | primário | intenção desconhecida |
| qualquer coisa depois da primeira escrita | primário até o fim da requisição | a réplica ainda não tem o que esta sessão acabou de gravar |

A Session é criada por requisição (o Flask-SQLAlchemy faz `session.remove()`
no teardown), então a "fixação no primário" morre junto com a requisição.

### Quem pode ler da réplica (D1)

- **(a) Recomendado — só os GETs da tela**, com um decorator
  `@le_da_replica` (pode morar em `cessao/decorators.py`):
  `GET /liquidacao/lotes/reais`, `/lotes/fake`, `/pagamentos/query`,
  `/pagamentos/rejeitados`, `/conciliacao/saldo`. Todos são só leitura.
- **(b) Todo GET** (`request.method in ("GET", "HEAD")`): nenhuma mudança nos
  endpoints, mas pega casos arriscados:
  - GETs que gravam, como `GET /liquidacao/<produto_id>/<liquidacao_id>/arquivo`,
    que reserva número de arquivo (`FOR UPDATE` em `Fundo`, `models.py:7182`);
  - GETs que outros serviços chamam logo depois de um POST e podem não achar o
    dado ainda (ex.: `GET /titulo/contratos`, 311 mil chamadas por semana na
    vivo).

Trocar (a) por (b) é mudar a função `_replica_liberada`.

### Por que não mandar toda leitura (inclusive Celery) para a réplica

Evidências no código:

- `with_for_update` no lote vigente (`cessao/api/liquidacao/repository.py:371`)
  e no `Fundo` para numerar arquivos (`cessao/database/models.py:7182` e `7250`).
- O gate de saldo da conciliação pega `pg_advisory_xact_lock` e em seguida soma
  os compromissos (`cessao/shared/saldo_liquidacao/repository.py:50` e `78`).
  Advisory lock só vale no servidor onde foi pego: com a soma lida na réplica,
  dois lotes da mesma conta seriam aprovados juntos — exatamente o que o lock
  existe para impedir.
- 72 chamadas `.delay()`/`apply_async()`. O padrão comum é commit seguido de
  enfileirar a task; a task leria da réplica antes de o dado chegar.

## Riscos

| Risco | Mitigação |
|---|---|
| Tela mostra estado defasado logo após uma ação (ex.: fechar e recarregar) | Lag costuma ser de milissegundos; o fechamento já é assíncrono hoje (202 do BFF). Aceitar e documentar |
| Consulta longa cancelada na réplica por conflito com a replicação (`canceling statement due to conflict with recovery`) | DBA avalia `hot_standby_feedback` / `max_standby_streaming_delay` (D2). A tarefa 04 reduz essas consultas |
| Mais conexões | ~72 na réplica em asgard produção (18 pods × 4 processos uwsgi × 1 thread). Workers do Celery não abrem conexão na réplica |
| Réplica fora do ar derruba a tela | Não incluir a réplica no healthcheck (derrubaria todos os pods). Desligar removendo a variável |
| `session.merge()` em GET com réplica defasada poderia inserir em vez de atualizar | Nenhum GET da opção (a) usa merge |

## Complemento: `statement_timeout`

O BFF desiste em 120 s, mas a cessão continuou uma consulta por até 2h12 nos
últimos 7 dias. Um `statement_timeout` de ~120 s na conexão da réplica corta
esse desperdício. Pode ir na URI (`?options=-c%20statement_timeout%3D120000`)
ou no papel do banco usado pela réplica (DBA). Só afeta quem lê da réplica.

## Plano

1. Branch `chore/TS-xxxx-leitura-replica` (ou `feature/`), a partir de
   `origin/master` com `--no-track`.
2. Commits atômicos:
   - config: variável opcional da réplica;
   - init: `SQLALCHEMY_BINDS` quando a variável existir;
   - extensions: Session com roteamento;
   - decorator `@le_da_replica` nos GETs escolhidos (se D1 = a);
   - testes.
3. Provisionar a variável no Parameter Store (staging → sandbox → produção).
4. Medir de novo com o [baseline](../evidence/baseline-datadog-2026-10-05.md).

## Validação

Feita no protótipo (Postgres 13.10 descartável; réplica simulada com conexão
`default_transaction_read_only=on`, que recusa qualquer escrita), 15 testes
passando — [attachments/replica/test_routing.py](../attachments/replica/test_routing.py):

- GET lê da réplica; POST e contexto sem requisição (Celery) leem do primário.
- Depois de `add` + `flush` num GET, a sessão vê o próprio dado (primário).
- `with_for_update()` vai ao primário, inclusive `FOR UPDATE OF` em subquery.
- Advisory lock via `text()` vai ao primário e fixa a sessão.
- `query.update()` em massa vai ao primário.
- Paginação e lazy load ficam na réplica.
- Objeto lido da réplica e alterado grava no primário.
- Sem réplica configurada, tudo no primário.
- Modo opt-in: só o endpoint marcado lê da réplica.

A fazer na implementação real:

- Testes unitários no repo sem banco (comparar a engine devolvida por
  `get_bind`; criar engine não abre conexão).
- Em staging com a réplica: conferir no Datadog que os spans `postgres` das
  rotas escolhidas mostram o host da réplica em `network.destination.ip`.

## Como foi feito

Entregue na TS-5279, branch
`feature/TS-5279-apontar-consultas-liquidacao-replica-leitura`, PR #2628,
merge `7469008` em 07/10/2026. Seguiu a proposta acima com D1 = (a); as
diferenças em relação ao protótipo estão marcadas.

| Arquivo | O que mudou |
|---|---|
| `cessao/config/__init__.py` | Lê `DB_POSTGRESQL_PLATFORM_CESSAO_REPLICA` com `os.getenv` (opcional, fora de `nao_encontradas`) e devolve em `get_database()["uri_replica"]` |
| `cessao/app_factory.py` | Em `configure_app`, se `uri_replica` existir, `SQLALCHEMY_BINDS = {BIND_REPLICA: uri_replica}`. Sem a variável, nada muda |
| `cessao/extensions.py` | `SessaoComReplica` (sobrescreve `get_bind`, igual ao protótipo) e `SQLAlchemyComReplica`, que cria a sessão com ela via `create_session`. `db` passou a ser `SQLAlchemyComReplica`. Constante `BIND_REPLICA = "replica"` |
| `cessao/decorators.py` | Decorator **`@consulta_replica`** (no planejamento chamava `@le_da_replica`). Liga `g.consulta_replica` durante o endpoint e desliga no `finally` |
| `cessao/api/liquidacao/viewer.py` | Decorator aplicado em 5 GETs: lotes reais, lotes fake, `/pagamentos/query`, `/pagamentos/rejeitados` e `/conciliacao/saldo` |
| `test/test_extensions.py` | 9 testes unitários sem banco, comparando a engine devolvida por `get_bind` |

Como a sessão decide (`_replica_liberada` + `get_bind`):

- vai à réplica só se: a réplica está em `SQLALCHEMY_BINDS`, há app context,
  o endpoint tem `@consulta_replica`, o comando é um `SELECT` (sem flush e
  sem `FOR UPDATE` em nenhum ponto do statement) e a sessão ainda não foi
  fixada no primário;
- qualquer outro comando (escrita, `FOR UPDATE`, `text()`,
  `session.connection()` sem argumentos) vai ao primário e fixa a sessão nele
  até o fim da requisição;
- Celery e contexto sem requisição nunca têm a flag, então sempre leem do
  primário.

Testes do repo: `select` vai à réplica; sem decorator vai ao primário; sem
réplica configurada vai ao primário; `FOR UPDATE` (inclusive só na subquery)
vai ao primário; `text()` vai ao primário; escrita e `connection()` fixam a
sessão no primário; o decorator só libera a réplica durante o endpoint.

Último ajuste antes do merge: commit `e70af24` ("usa session com replica na
instancia do db"), que trocou o `db = SQLAlchemy(...)` por
`db = SQLAlchemyComReplica(...)`.

O `statement_timeout` (complemento acima) **não** entrou no código: depende
da URI configurada ou do papel do banco (D2).

### Pendente

- ~~Cadastrar `DB_POSTGRESQL_PLATFORM_CESSAO_REPLICA`~~ — já cadastrada no
  Parameter Store (confirmado pelo Pietro em 09/10/2026).
- Conferir se a URI cadastrada já leva o `statement_timeout` (D2).
- **Conferência no Datadog em 09/10/2026.** Variável corrigida e pods
  recriados em 07/10 ~19h. Traces de produção de 08/10 (`prod-6bb6111`):
  - `/pagamentos/query`, `/conciliacao/saldo` e `/lotes/fake` **leem da
    réplica** (`asgard-postgres-production-cessao-replica`), ex.: traces
    `6ac80fc1000000002c9ddb6ced6c6746`, `6ac80fc100000000d47b0d372517f6af`,
    `6ac80fac000000008d8a769d9741e03d`.
  - `/lotes/reais` **continua no primário** (trace
    `6ac8134b000000007b1057644b2bcf93`). Causa: o hotfix `0ef1d4f` (06/10)
    roda `SET LOCAL statement_timeout` via `text()` no início da listagem
    (`RepositoryLiquidacao.limitar_tempo_das_consultas`, chamado em
    `service.py:1320`). Pela regra da sessão, `text()` vai ao primário e fixa
    a sessão nele até o fim da requisição.
  - **Correção (09/10/2026), decisão do Pietro:** o `@consulta_replica` vira
    contrato — quem marca o endpoint garante que ele só lê. Dentro dele,
    todo comando vai para a réplica; fora, tudo vai para o primário. Saíram
    a detecção de `FOR UPDATE` e a fixação no primário. Erro de uso aparece
    na hora (a réplica recusa escrita e `FOR UPDATE`), exceto advisory lock,
    que a réplica aceita sem proteger nada — aviso no docstring. O hotfix
    `limitar_tempo_das_consultas` ficou intacto. Commits locais na branch da
    TS-5279 (até `02682ad`), 5 testes passando; falta push e novo PR.
- Depois de corrigir, conferir no Datadog que os spans `postgres` das 5 rotas mostram
  o host da réplica.
- Medir de novo com o [baseline](../evidence/baseline-datadog-2026-10-05.md).
