# GMUD — TS-5279: lotes reais passa a ler da réplica

Tipo: Mudança não programada

## Summary

platform-cessao: listagem de lotes reais de liquidação passa a ler da réplica

## Descrição

**Contexto**
Desde 08/10/2026 (PR #2628, `prod-6bb6111`), os endpoints de consulta da tela
de lotes de liquidação leem da réplica de leitura do banco (cópia que só
aceita leitura), para aliviar o banco principal. Quatro deles já estão na
réplica, confirmado no Datadog. O `GET /liquidacao/lotes/reais`, que é o mais
pesado e o que tinha 18% de timeouts (504), continuou no banco principal.

**Causa**
A listagem de lotes reais roda `SET LOCAL statement_timeout` (limite de 120 s
por consulta) antes das consultas. A regra de roteamento mandava qualquer SQL
escrito à mão para o banco principal e prendia a requisição nele, então as
consultas seguintes também iam para o principal.

**O que muda**
A regra de roteamento foi simplificada: nos endpoints marcados com
`@consulta_replica`, todas as consultas vão para a réplica; nos demais, tudo
continua no banco principal. Com isso, a listagem de lotes reais passa a ler
da réplica, mantendo o limite de 120 s.

Arquivos: `cessao/extensions.py`, `cessao/decorators.py` (documentação) e
`test/test_extensions.py`. Nenhum outro endpoint muda de banco.

## Prioridade

Medium

## Link Tarefa

<link do Jira da TS-5279>

## Risco

Baixo.

- Só afeta os 5 endpoints já marcados com `@consulta_replica`, todos só de
  leitura. Fora deles, o comportamento é o mesmo de hoje (banco principal).
- Se algum endpoint marcado tentar gravar, a réplica recusa e a requisição dá
  erro na hora, sem gravar dado errado.
- Consulta longa na réplica pode ser cancelada por conflito com a replicação;
  a listagem já tem limite de 120 s.

## Impacto

- Tela de lotes de liquidação (aba lotes reais): nenhuma mudança visual;
  expectativa de menos timeouts (504).
- Banco principal: deixa de receber as consultas pesadas da listagem de lotes
  reais.
- Sem indisponibilidade no deploy, sem migration e sem variável nova.

## Plano de implantação

1. Merge do PR #<número> na `master` da platform-cessao.
2. Deploy padrão da platform-cessao em produção.
3. Conferir pods na nova versão e healthcheck ok.
4. Abrir a aba de lotes reais no Portal e conferir que carrega normalmente.
5. No Datadog, conferir que as consultas de `GET /liquidacao/lotes/reais`
   mostram `network.destination.ip` igual ao host da réplica (o do Parameter
   Store).

## Plano de Rollback

1. Reverter o PR #<número> e fazer deploy da versão anterior
   (`prod-6bb6111`). A listagem de lotes reais volta ao banco principal; os
   outros 4 endpoints seguem na réplica.
2. Alternativa sem deploy, se a réplica em si der problema: remover
   `DB_POSTGRESQL_PLATFORM_CESSAO_REPLICA` do Parameter Store e reiniciar os
   pods; todas as consultas voltam ao banco principal.

## Evidências de validação

- Testes unitários (`test/test_extensions.py`), 5 passando: endpoint marcado
  vai para a réplica; sem marca vai ao principal; sem réplica configurada vai
  ao principal; `SET LOCAL` + consulta seguinte vão para a réplica; a marca
  vale só durante o endpoint.
- Antes da correção, trace de produção `6ac8134b000000007b1057644b2bcf93`
  (`GET /liquidacao/lotes/reais`, 08/10/2026): `SET LOCAL statement_timeout`
  e as consultas da listagem no banco principal.
- Os outros endpoints marcados já leem da réplica em produção (traces
  `6ac80fc1000000002c9ddb6ced6c6746`, `6ac80fc100000000d47b0d372517f6af`,
  `6ac80fac000000008d8a769d9741e03d`).
