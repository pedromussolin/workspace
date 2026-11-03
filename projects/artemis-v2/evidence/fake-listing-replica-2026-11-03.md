# Listagem de lotes fake nova × antiga na réplica (03/11/2026)

**Conclusão:** a listagem nova da TS-5536 (chave pela modalidade e `qtd_aptos` pela D9) custa o
mesmo que a antiga. A opção (b) do R7 (mostrar os aptos e desabilitar o Fechar sem apto) fica.

## Medição

- **Fonte:** réplica de leitura de produção, `EXPLAIN (ANALYZE, BUFFERS)`, uma consulta por vez,
  sessão só leitura com `statement_timeout` de 120 s, em 03/11/2026 à tarde.
- **SQL:** o gerado pelo código da branch `feature/TS-5536-listagem-fluxo-novo` (cessão), com
  valores literais: dia 30/10/2026, página 1, 10 por página, ordem padrão.
- **Ajuste para medir:** a coluna `produto_config.modalidade_fechamento_lote` ainda não existe em
  produção (vem com a migration da TS-5435). A condição da chave foi trocada pela equivalente nas
  flags (`fechar_lote_por_proc_id` e `lote_liquidacao` ligados), que tem o mesmo custo.

| Cenário (cache quente) | Antiga | Nova |
|---|---|---|
| Fundo 836 | 533 a 537 ms | 533 a 552 ms |
| Todos os fundos | 614 ms | 640 ms |

A primeira execução de cada cenário, com cache frio, levou de 3,5 s a 5,1 s, nas duas.

## O que muda no SQL

- a condição da chave: modalidade `automatico_por_remessa` no lugar da flag `fechar_lote_por_proc_id`;
- a coluna `qtd_aptos`: `count(distinct parcela_id) FILTER (WHERE liquidação cadastrada AND cessão
  do contrato cadastrada AND contrato não apagado)`;
- o anti-join do contrato apagado vira `LEFT JOIN contrato_processo` com `data_delete IS NULL` no
  WHERE.

## Para repetir

Gerar o SQL com valores literais a partir do repositório da listagem nova
(`RefactLiquidacaoRepository.listar_lotes_fake`) e rodar `EXPLAIN (ANALYZE, BUFFERS)` na réplica
duas vezes por cenário, descartando a primeira (cache frio). Depois da migration da TS-5435 em
produção, medir sem o ajuste da condição.
