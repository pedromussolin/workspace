# Artemis V2 — Planejamento

Pasta de trabalho da V2 do Projeto Artemis: um arquivo por tarefa, com o
problema, as evidências, a proposta, os riscos e como vamos provar que
funcionou. O objetivo é estressar as ideias **antes** de abrir branch.

- Início do desenvolvimento: 05/10/2026 (Pietro Nett e Heitor Shim).
- Ata da reunião de descoberta: [ata-2026-09-23.md](ata-2026-09-23.md).
- Escopo inicial: tela de **lotes de liquidação** (fake e reais) da
  platform-cessao, ou seja, todo o fechamento e a conciliação dos lotes.
- Ponto principal: **performance**. A DBA revisa as queries; a parte de
  aplicação fica com a gente.

## Como ler esta pasta

> Valores sensíveis (hosts, IPs, usuários de banco) e os nomes reais por trás
> dos análogos usados aqui ficam fora do repo, em
> `~/repos/.artemis_v2/privado.md` (local). Ver o `CLAUDE.md`.

| Arquivo | Para que serve |
|---|---|
| [decisoes.md](decisoes.md) | Decisões tomadas e pendentes, com quem decide |
| [evidencias/baseline-datadog-2026-10-05.md](evidencias/baseline-datadog-2026-10-05.md) | Números de produção antes de qualquer mudança, e as consultas para medir de novo |
| [bugs-encontrados.md](bugs-encontrados.md) | Bugs achados no mapeamento que ainda não viraram tarefa |
| [depois-da-v2.md](depois-da-v2.md) | Melhorias adiadas para depois da V2, com o que falta para retomar |
| `tarefas/` | Uma tarefa por arquivo (lista abaixo) |
| `anexos/` | Protótipos e SQL citados nas tarefas |

Todas as referências de código (`arquivo:linha`) apontam para estes commits:

| Repositório | Commit (origin/master em 05/10/2026) |
|---|---|
| platform-cessao | `9ddb97f` (é a imagem `prod-9ddb97f` em produção) |
| apl-credit-whitelabel-api (BFF) | `d8512aa` |
| apl-credit-whitelabel (front) | `e49c9b6` |
| genius-sftp-listener | `9b3b19c` |

## Tarefas

| # | Tarefa | Repos | Depende de | Status | TS |
|---|---|---|---|---|---|
| 01 | [Réplica de leitura no init do SQLAlchemy](tarefas/01-replica-de-leitura.md) | cessão | — | **concluída** (PR #2628, 07/10; variável no Parameter Store) | TS-5279 |
| 02 | [Dois modos de fechamento: chave ou proc_id](tarefas/02-fechar-lote-por-proc-id.md) | cessão, BFF, front | D7 (D3 adiada) | desenho alinhado | a definir |
| 03 | [Fechamento: mais rápido, sem espera e sem 429](tarefas/03-fechamento-assincrono-e-429.md) | cessão, BFF, front | 02 | proposta | a definir |
| 04 | [Performance das listagens de lotes](tarefas/04-performance-listagens.md) | cessão, front | revisão da DBA | mapeado | a definir |
| 05 | [Tipo de baixa na tabela de pagamentos](tarefas/05-tipo-de-baixa.md) | cessão, front | — | mapeado | a definir |
| 06 | [Nome do CNAB na tela](tarefas/06-nome-do-cnab-na-tela.md) | cessão, BFF, front | decisão D4 | mapeado | a definir |
| 07 | [Filtro por identificador de contrato](tarefas/07-filtro-identificador-contrato.md) | cessão, BFF, front | — | mapeado | a definir |
| 08 | [Genius: reenvio e logs de erro](tarefas/08-genius-reenvio-e-logs.md) | cessão, westworld, listener | — | mapeado | a definir |
| 09 | [Lote automático da Voltis](tarefas/09-lote-automatico-voltis.md) | cessão | configs do produto | aguardando dados | a definir |
| 11 | [Fechamento automático por horário de corte, com bypass](tarefas/11-fechamento-por-horario-de-corte.md) | cessão, BFF, front | 02, D8 | ideia | a definir |
| 10 | [Fluxo da Genius para a Dayvale](tarefas/10-adm-dayvale.md) | cessão, westworld | APIs Dayvale, TS-5207 | aguardando descoberta | a definir |

## Fases propostas

A ordem prioriza o que tira carga do banco e o que causa erro em produção.
É uma proposta para discutir, não um compromisso.

1. **Estancar a carga no banco**
   - 01 Réplica de leitura, com `statement_timeout` na conexão da réplica.
   - 02 Fechar por proc_id: além de corrigir o comportamento, elimina a
     consulta que mais consome o banco (88 h em 7 dias).
   - 04 Revisão das listagens junto com a DBA.
2. **Fechamento confiável**
   - 03 Fechamento mais rápido e assíncrono, sem 429 nem 500 por clique repetido.
   - 11 Fechamento por horário de corte, com bypass.
   - Bugs B1–B5 de [bugs-encontrados.md](bugs-encontrados.md).
3. **Acabamento da tela**
   - 05 Tipo de baixa, 06 nome do CNAB, 07 filtro por contrato.
4. **Integrações com as ADMs**
   - 08 Reenvio da Genius, 09 Voltis, 10 Dayvale.

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
