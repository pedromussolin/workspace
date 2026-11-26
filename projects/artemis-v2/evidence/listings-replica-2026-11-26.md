# As quatro listagens na réplica: onde vai o tempo (26/11/2026)

**Conclusão:** nas quatro listagens, o lento é o mesmo padrão. Uma contagem, uma soma ou um filtro
passa por **todas** as linhas de um lote ou de um dia, e cada linha precisa de uma a três buscas pelo
número em tabelas de cadastro grandes (parcela, contrato, processo do contrato, cedente). Essas buscas
saem do disco. As linhas mostradas na página custam milissegundos. O custo cresce com o tamanho do
lote: no ritmo medido, um lote de 1 milhão de pagamentos levaria cerca de 19 minutos por carga da L3.

## Medição

- **Fonte:** réplica de leitura de produção, `EXPLAIN (ANALYZE, BUFFERS)`, 26/11/2026 de manhã;
  sessão só leitura, `statement_timeout` de 120 s, uma consulta por vez. Cache frio na primeira
  execução de cada consulta.
- **SQL:** escrito à mão a partir do código da cessão `origin/master` c6f88ce39, com o filtro que o
  `ContratoSoftDeleteListener` (`cessao/database/listeners.py:540`) acrescenta. Os ids saíram por
  `\gset`, sem impressão.
- **Cenário:** o que a tela manda por padrão: dia 25/11/2026 e 5 linhas por página.

| Listagem | Comando | Tempo | O que pesa |
|---|---|---|---|
| L1 lotes reais (fundo com mais lotes no dia: 34) | página com total e valores (`repository.py:526`) | 21,6 s frio; 0,1 s quente | a regra do fundo do lote: pagamento → `contrato_parcela.fundo_id`; em 12 lotes, 20 mil parcelas, 22,5 mil páginas do disco, 21 s de I/O |
| L1 | lotes das remessas (`repository.py:778`, duas consultas) | 0,3 s e 0,2 ms | — |
| L2 lotes fake | ver [fake-listing-open-batches-replica-2026-11-26](fake-listing-open-batches-replica-2026-11-26.md) | mais de 120 s | soma dos lotes abertos com a cadeia do contrato apagado: 50 s só no maior lote (73.559 pagamentos) |
| L3 pagamentos de um lote real (13.868 pagamentos) | remessas do lote (`repository.py:914`) | 0,06 s | — |
| L3 | contagem do lote (`repository.py:1179`) | 6,8 s | cadeia parcela → contrato → processo por pagamento; 16 mil páginas do disco |
| L3 | a página (`repository.py:1196`) | 3 ms | — |
| L3 | métricas do lote (`repository.py:1336`) | 8,6 s | a mesma cadeia sobre as remessas do lote; 29 mil páginas do disco |
| L3 rota fake (linha do lote aberto) | totais da linha (`refact.py:2316`) | não medida | a mesma soma com a cadeia do contrato apagado da L2 [H] |
| L4 lotes de cessão, em aberto (padrão da tela) | contagem | 24,3 s frio | plano ruim: junta pelo `proc_id` (4.084 linhas reais, 20 milhões estimadas) e percorre o índice inteiro de `cedente` (2,87 milhões de linhas, 22 s) |
| L4 em aberto | página | 2,1 s quente | o mesmo plano |
| L4 fechados | contagem | 94,7 s | cerca de 350 mil processos de contrato no dia, cada um buscando o contrato pelo `uuid`: 270 s de I/O somando os processos paralelos |
| L4 fechados | página | mais de 120 s | o mesmo |

## Para repetir

O SQL de cada listagem, com as variáveis do `psql` e as consultas que escolhem valores realistas, está
nos anexos: [L1](../attachments/sql/listing-l1-real-batches-2026-11-26.sql),
[L2](../attachments/sql/fake-listing-open-batches-2026-11-26.sql),
[L3](../attachments/sql/listing-l3-batch-payments-2026-11-26.sql) e
[L4](../attachments/sql/listing-l4-assignment-batches-2026-11-26.sql). Rodar uma consulta por vez;
passar ids entre consultas com `\gset`, sem imprimi-los.
