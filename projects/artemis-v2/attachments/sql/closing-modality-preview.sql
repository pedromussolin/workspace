-- Prévia da modalidade de fechamento (TS-5435): o que a migration c3f81d7a5e24 grava em cada produto.
-- Somente leitura. Roda antes da migration (a coluna ainda não existe), na réplica.
-- Regra (a mesma da migration, em ordem de precedência):
--   lote_liquidacao e fechar_lote_por_proc_id -> automatico_por_remessa
--   acumula_liquidacoes                       -> acumulado
--   baixa_por_agendamento                     -> agendado
--   lote_liquidacao                           -> automatico_por_chave
--   nenhuma                                   -> manual
-- Flag nula conta como desligada.
SELECT pg_is_in_recovery() AS replica;

WITH derivada AS (
    SELECT produto_id,
           CASE
               WHEN COALESCE(lote_liquidacao, FALSE) AND COALESCE(fechar_lote_por_proc_id, FALSE)
                   THEN 'automatico_por_remessa'
               WHEN COALESCE(acumula_liquidacoes, FALSE) THEN 'acumulado'
               WHEN COALESCE(baixa_por_agendamento, FALSE) THEN 'agendado'
               WHEN COALESCE(lote_liquidacao, FALSE) THEN 'automatico_por_chave'
               ELSE 'manual'
           END AS modalidade,
           -- Combinações em que a precedência decide (a modalidade não diz tudo o que as flags dizem).
           (COALESCE(acumula_liquidacoes, FALSE) AND COALESCE(fechar_lote_por_proc_id, FALSE)) AS acumula_e_proc_id,
           (COALESCE(fechar_lote_por_proc_id, FALSE) AND NOT COALESCE(lote_liquidacao, FALSE)) AS proc_id_sem_lote,
           (COALESCE(acumula_liquidacoes, FALSE)::int + COALESCE(baixa_por_agendamento, FALSE)::int
            + COALESCE(lote_liquidacao, FALSE)::int) > 1 AS mais_de_uma_flag
      FROM produto_config
)
SELECT modalidade, count(*) AS produtos,
       count(*) FILTER (WHERE acumula_e_proc_id) AS acumula_e_proc_id,
       count(*) FILTER (WHERE proc_id_sem_lote) AS proc_id_sem_lote,
       count(*) FILTER (WHERE mais_de_uma_flag) AS mais_de_uma_flag,
       string_agg(produto_id::text, ',' ORDER BY produto_id) FILTER (WHERE modalidade <> 'manual') AS produtos_fora_de_manual
  FROM derivada
 GROUP BY 1
 ORDER BY 2 DESC;
