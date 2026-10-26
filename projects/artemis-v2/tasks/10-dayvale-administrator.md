# 10 — Fluxo da Genius para a Dayvale

- **Status:** aguardando a descoberta das APIs da Dayvale (Edu Romano e
  Gus Furla, prazo 05/10/2026).
- **Repos:** platform-cessao, westworld.

## Objetivo

Replicar para a Dayvale o fluxo feito para a Genius (fechamento, conciliação,
envio e retorno), já corrigindo o que deu errado na Genius
([08](08-genius-resend-and-logs.md), [09](09-voltis-automatic-batch.md)).
Dayvale é a prioridade antes do BGT (ata de 23/09).

## O que já existe

Branch `feature/ts-5207-Admin-Dayvale` (Filipe dos R. Ferraz, TS-5207 e
TS-5233), **sem merge** em 05/10/2026 — 37 arquivos, +4.094 linhas:

- geradores de remessa: `remessa_dayvale_base.py`, `_cessao.py`,
  `_liquidacao.py`, `_renegociacao.py`;
- `cessao/tasks/dayvale.py`;
- migrations (incluindo limite de contratos por envio em `produto_config`);
- westworld `1.36.5.dev1`;
- testes dos geradores e das tasks.

## O que o fluxo da Genius tem e a Dayvale ainda não

| Peça | Na Genius | Na Dayvale |
|---|---|---|
| Geração do CNAB | `Cnab500LiquidacaoGenius` | branch TS-5207 |
| Envio | SFTP (paramiko) | definir pelas APIs |
| Retorno | Lambda `genius-sftp-listener` + consumers | definir; a ata pede retorno formal (e-mail/callback) |
| Conciliação por saldo/extrato | SKFlow (Synkia) via `conta_client_factory` | depende de a API dar acesso às contas (impeditivo da ata) |
| Gate de saldo e compromissos | `shared/saldo_liquidacao` | reaproveitar (é por agência+conta, não por ADM) |
| Verificação D0 | `verificar_liquidacao_d0` | reaproveitar |
| Logs estruturados | a melhorar (08) | nascer no padrão |

## Pontos para estressar

- Polling na Synkia foi apontado como gargalo na ata. A Dayvale também usa
  Synkia? Se sim, o polling precisa de limite e backoff desde o início.
- Gestão de rejeitadas: o motivo da rejeição vem da Dayvale? (oportunidade
  da ata)
- Fechamento por proc_id ([02](02-close-batch-by-proc-id.md)) precisa estar
  definido antes, porque a granularidade do lote decide o arquivo enviado.

## Próximo passo

Receber o resultado da descoberta das APIs e revisar a branch TS-5207 com o
Filipe.
