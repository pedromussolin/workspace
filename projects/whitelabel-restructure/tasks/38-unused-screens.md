# 38 — Telas sem uso removidas

- **TS:** TS-5440 (épico TS-5357) · **Branch:** juntada na `release/20261027` (front e BFF)
- **Status:** **em produção** (27/10). Não passou pela sandbox antes do deploy; validada pelos testes.
- **Decisão:** D135.

## O que é

Saem Acompanhamento de Clientes, Desempenho de Carteira (e o item do menu) e Simulação de Propostas, além das rotas
`/controllership/portfolio/*` do BFF. Nenhuma das três teve visita em produção de 21 a 27/10 (RUM do Datadog). O
catálogo de permissões passa de 148 para 145.

## Depois do deploy (com o Pietro)

Passado o período de rollback: apagar os grupos das telas removidas e, na aba Permissões, `clients:read`,
`portfolio-performance:read` e `simulate-proposal:read`. Link salvo para uma tela removida cai em "não encontrada".
