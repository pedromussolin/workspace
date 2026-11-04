# Artemis V2 — Planejamento

Pasta de trabalho da V2 do Projeto Artemis: um arquivo por tarefa, com o
problema, as evidências, a proposta, os riscos e como vamos provar que
funcionou. O objetivo é estressar as ideias **antes** de abrir branch.

- Início do desenvolvimento: 05/10/2026 (Pietro Nett e Heitor Shim).
- Ata da reunião de descoberta: [minutes-2026-09-23.md](minutes-2026-09-23.md).
- Escopo inicial: tela de **lotes de liquidação** (fake e reais) da
  platform-cessao, ou seja, todo o fechamento e a conciliação dos lotes.
- Ponto principal: **performance**. A DBA revisa as queries; a parte de
  aplicação fica com a gente.
- Desde 04/11/2026: absorver a liquidação do Mercato Libero, que o Rafael
  Frankl rodava sozinho fora dos repositórios e que passa para nós com a
  saída dele ([tarefa 13](tasks/13-mercato-libero-settlement.md)).

## Como ler esta pasta

> Valores sensíveis (hosts, IPs, usuários de banco) e os nomes reais por trás
> dos análogos usados aqui ficam fora do repo, em
> `~/.config/workspace/private/artemis-v2.md` (local). Ver o `CLAUDE.md`.

| Arquivo | Para que serve |
|---|---|
| [decisions.md](decisions.md) | Decisões tomadas e pendentes, com quem decide |
| [evidence/baseline-datadog-2026-10-05.md](evidence/baseline-datadog-2026-10-05.md) | Números de produção antes de qualquer mudança, e as consultas para medir de novo |
| [evidence/real-batches-datadog-2026-10-14.md](evidence/real-batches-datadog-2026-10-14.md) | Lotes reais depois da réplica: 19,5% de 500, causa nos lotes irmãos |
| [evidence/sweep-datadog-2026-10-14.md](evidence/sweep-datadog-2026-10-14.md) | Varredura com 4 chaves e 1 rodada: fim das chamadas longas, saldo ainda inconclusivo |
| [evidence/mercato-libero-ec2-calls-2026-11-04.md](evidence/mercato-libero-ec2-calls-2026-11-04.md) | O que a EC2 de automações chama na cessão (14 dias até 04/11): ponto de partida da tarefa 13 |
| [bugs-found.md](bugs-found.md) | Bugs achados no mapeamento que ainda não viraram tarefa |
| [after-v2.md](after-v2.md) | Melhorias adiadas para depois da V2, com o que falta para retomar |
| `tasks/` | Uma tarefa por arquivo (lista abaixo) |
| `attachments/` | Protótipos e SQL citados nas tarefas |

Todas as referências de código (`arquivo:linha`) apontam para estes commits:

| Repositório | Commit (origin/master em 05/10/2026) |
|---|---|
| platform-cessao | `9ddb97f` (é a imagem `prod-9ddb97f` em produção) |
| apl-credit-whitelabel-api (BFF) | `d8512aa` |
| apl-credit-whitelabel (front) | `e49c9b6` |
| genius-sftp-listener | `9b3b19c` |
| westworld | `195e01e` (tag 1.36.5, a versão usada pela cessão) |

## Tarefas

| # | Tarefa | Repos | Depende de | Status | TS |
|---|---|---|---|---|---|
| 12 | [Lotes reais: buscar os lotes antes dos valores](tasks/12-real-batches-before-values.md) | cessão | D21 | **prioridade máxima** (14/10); mapeada | a definir |
| 01 | [Réplica de leitura no init do SQLAlchemy](tasks/01-read-replica.md) | cessão | — | **concluída** (PR #2628, 07/10; variável no Parameter Store) | TS-5279 |
| 02 | [Dois modos de fechamento: chave ou proc_id](tasks/02-close-batch-by-proc-id.md) | cessão, BFF, front | D7 (D3 adiada) | em sandbox (PRs de 27/10); [plano](tasks/02-03-implementation-plan.md) | TS-5435 |
| 03 | [Fechamento: mais rápido, sem espera e sem 429](tasks/03-async-closing-and-429.md) | cessão, BFF, front, argocd | — | em produção (cessão 19/10, BFF e front 20/10); fase 2 em sandbox (27/10); [casos](tasks/03-post-production-cases.md) e [plano](tasks/02-03-implementation-plan.md) | TS-5377 |
| 04 | [Performance das listagens de lotes](tasks/04-listing-performance.md) | cessão, front | revisão da DBA | mapeado | a definir |
| 05 | [Tipo de baixa na tabela de pagamentos](tasks/05-settlement-type.md) | cessão, front | — | mapeado | a definir |
| 06 | [Nome do CNAB na tela](tasks/06-cnab-name-on-screen.md) | cessão, BFF, front | decisão D4 | mapeado | a definir |
| 07 | [Filtro por identificador de contrato](tasks/07-contract-identifier-filter.md) | cessão, BFF, front | — | mapeado | a definir |
| 08 | [Genius: reenvio e logs de erro](tasks/08-genius-resend-and-logs.md) | cessão, westworld, listener | D12–D16 | mapeado (revisado 13/10) | a definir |
| 09 | [Lote automático da Voltis](tasks/09-voltis-automatic-batch.md) | cessão | configs do produto | aguardando dados | a definir |
| 11 | [Fechamento automático por horário de corte, com bypass](tasks/11-closing-by-cutoff-time.md) | cessão, BFF, front | 02, D8 | ideia; núcleo da 13 desde 04/11 | a definir |
| 10 | [Fluxo da Genius para a Dayvale](tasks/10-dayvale-administrator.md) | cessão, westworld | APIs Dayvale, TS-5207 | aguardando descoberta | a definir |
| 13 | [Absorver a liquidação do Mercato Libero](tasks/13-mercato-libero-settlement.md) | cessão (do sistema em diante; a chegada dos dados fica com o time) | 11, D25 | recorte definido (04/11); a mapear | a definir |

## Fases propostas

A ordem prioriza o que tira carga do banco e o que causa erro em produção.
É uma proposta para discutir, não um compromisso.

0. **Antes de tudo (14/10):** 12 Lotes reais, lotes antes dos valores. A aba
   de lotes reais continua falhando em 19,5% das cargas mesmo com a réplica.
1. **Estancar a carga no banco**
   - 01 Réplica de leitura, com `statement_timeout` na conexão da réplica.
   - 02 Fechar por proc_id: além de corrigir o comportamento, elimina a
     consulta que mais consome o banco (88 h em 7 dias).
   - 04 Revisão das listagens junto com a DBA.
2. **Fechamento confiável**
   - 03 Fechamento mais rápido e assíncrono, sem 429 nem 500 por clique repetido.
   - 11 Fechamento por horário de corte, com bypass.
   - Bugs B1–B5 de [bugs-found.md](bugs-found.md).
3. **Acabamento da tela**
   - 05 Tipo de baixa, 06 nome do CNAB, 07 filtro por contrato.
4. **Integrações com as ADMs**
   - 08 Reenvio da Genius, 09 Voltis, 10 Dayvale.
5. **Absorver a liquidação do Mercato Libero (desde 04/11)**
   - 13 com a 11: o fechamento automático por horário de corte substitui a
     varredura do Rafael Frankl; a chegada dos dados fica com o time. O prazo
     é a saída dele.

## Glossário

- **Lote fake:** pagamentos já processados que ainda não têm
  `liquidacao_lote_id`. Não existe tabela; o agrupamento é calculado na
  consulta.
- **Lote real:** registro em `liquidacao_lote_processo`, criado ao fechar.
- **proc_id:** identificador de uma remessa (um arquivo ou envio do parceiro).
- **ADM:** administrador do fundo (Genius, Dayvale, BGT...), quem recebe o
  CNAB e devolve o retorno.
- **Conciliação:** checagem do lote contra o saldo da conta do fundo antes do
  envio à ADM.
- **Réplica de leitura:** cópia do banco atualizada com atraso pelo primário,
  que só aceita leitura.
- **Atraso de replicação (lag):** tempo entre o commit no primário e o dado
  aparecer na réplica.
- **p50 / p95:** metade / 95% das requisições terminam abaixo desse tempo.
- **504:** o BFF desistiu de esperar a cessão (o limite em produção é 120 s).
