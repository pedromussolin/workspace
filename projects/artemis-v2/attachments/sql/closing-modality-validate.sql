-- Validação da modalidade de fechamento (TS-5435), depois da migration c3f81d7a5e24.
-- Somente leitura. Esperado: nulos = 0 e divergentes = 0. Regra: a de closing-modality-preview.sql.
WITH derivada AS (
    SELECT produto_id,
           modalidade_fechamento_lote::text AS gravada,
           CASE
               WHEN COALESCE(lote_liquidacao, FALSE) AND COALESCE(fechar_lote_por_proc_id, FALSE)
                   THEN 'automatico_por_remessa'
               WHEN COALESCE(acumula_liquidacoes, FALSE) THEN 'acumulado'
               WHEN COALESCE(baixa_por_agendamento, FALSE) THEN 'agendado'
               WHEN COALESCE(lote_liquidacao, FALSE) THEN 'automatico_por_chave'
               ELSE 'manual'
           END AS esperada
      FROM produto_config
)
SELECT count(*) AS produtos,
       count(*) FILTER (WHERE gravada IS NULL) AS nulos,
       count(*) FILTER (WHERE gravada IS DISTINCT FROM esperada) AS divergentes,
       string_agg(produto_id || ': ' || COALESCE(gravada, 'nula') || ' <> ' || esperada, '; ' ORDER BY produto_id)
           FILTER (WHERE gravada IS DISTINCT FROM esperada) AS quais
  FROM derivada;

SELECT modalidade_fechamento_lote::text AS modalidade, count(*) AS produtos
  FROM produto_config
 GROUP BY 1
 ORDER BY 2 DESC;
