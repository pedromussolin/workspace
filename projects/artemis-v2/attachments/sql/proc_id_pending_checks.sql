-- TS-5435: conferências antes da GMUD e depois da produção.
-- Rodar na réplica de leitura, uma consulta por vez, com
-- default_transaction_read_only=on e statement_timeout de 120 s.
-- Rodada em 28/10/2026; resultados em tasks/02-03-sandbox-tests.md.

-- 1. Modalidade que a migração c3f81d7a5e24 vai gravar em cada produto, com a
-- mesma precedência do backfill, e as combinações das flags que a modalidade
-- não representa. b22: fecha por proc_id sem lote automático (a linha proc:
-- não fecha pela tela). perde_*: a combinação some se alguém mandar a
-- modalidade no cadastro, porque as flags passam a seguir a modalidade.
SELECT CASE
         WHEN coalesce(lote_liquidacao, false) AND coalesce(fechar_lote_por_proc_id, false)
           THEN 'automatico_por_remessa'
         WHEN coalesce(acumula_liquidacoes, false) THEN 'acumulado'
         WHEN coalesce(baixa_por_agendamento, false) THEN 'agendado'
         WHEN coalesce(lote_liquidacao, false) THEN 'automatico_por_chave'
         ELSE 'manual'
       END AS modalidade,
       count(*) AS produtos,
       count(*) FILTER (WHERE coalesce(fechar_lote_por_proc_id, false)
                          AND NOT coalesce(lote_liquidacao, false)) AS b22,
       count(*) FILTER (WHERE coalesce(acumula_liquidacoes, false)
                          AND coalesce(lote_liquidacao, false)) AS perde_lote_no_acumulado,
       count(*) FILTER (WHERE coalesce(acumula_liquidacoes, false)
                          AND coalesce(baixa_por_agendamento, false)) AS perde_agendado_no_acumulado,
       count(*) FILTER (WHERE coalesce(baixa_por_agendamento, false)
                          AND coalesce(lote_liquidacao, false)
                          AND NOT coalesce(acumula_liquidacoes, false)
                          AND NOT coalesce(fechar_lote_por_proc_id, false)) AS perde_lote_no_agendado
FROM produto_config
GROUP BY 1
ORDER BY 1;

-- 1c. Critério completo: produtos cujas flags diferem das que a modalidade
-- derivada gravaria (legacy_flags). Zero quer dizer que nenhuma combinação se
-- perde se alguém mandar a modalidade no cadastro.
WITH f AS (
  SELECT produto_id,
         coalesce(lote_liquidacao, false) AS lote,
         coalesce(fechar_lote_por_proc_id, false) AS proc,
         coalesce(acumula_liquidacoes, false) AS acum,
         coalesce(baixa_por_agendamento, false) AS agend
  FROM produto_config
), m AS (
  SELECT f.*, CASE WHEN lote AND proc THEN 'automatico_por_remessa'
                   WHEN acum THEN 'acumulado' WHEN agend THEN 'agendado'
                   WHEN lote THEN 'automatico_por_chave' ELSE 'manual' END AS modalidade
  FROM f
)
SELECT modalidade, count(*) AS produtos,
       count(*) FILTER (WHERE (lote, proc, acum, agend) IS DISTINCT FROM (
         modalidade IN ('automatico_por_chave', 'automatico_por_remessa'),
         modalidade = 'automatico_por_remessa',
         modalidade = 'acumulado',
         modalidade = 'agendado')) AS flags_diferentes
FROM m GROUP BY 1 ORDER BY 1;

-- 1b. Depois da produção: produtos cuja modalidade gravada já não bate com as
-- flags (flag mudada direto no banco). Só roda depois da migração.
-- SELECT produto_id, modalidade_fechamento_lote, lote_liquidacao,
--        fechar_lote_por_proc_id, acumula_liquidacoes, baixa_por_agendamento
-- FROM produto_config
-- WHERE modalidade_fechamento_lote::text <> <mesma expressão CASE da consulta 1>;

-- 2. Remessas presas (B19) dos produtos que fecham por proc_id (trocar a
-- lista se a consulta 1 mostrar outros). Uma remessa está presa quando todos os
-- processos estão em estado terminal, há pagamento cadastrado sem lote e o
-- último processo foi criado há mais de 2 horas.
-- Custo: liquidacao_processo tem ~800 milhões de linhas e não há índice
-- (produto_id, data_criacao). Com 30 dias e EXISTS direto, estourou 120 s duas
-- vezes; com 7 dias e LATERAL por remessa (OFFSET 0 segura o plano por linha),
-- levou 64 s. Não passar de 7 dias.
WITH remessa AS (
  SELECT pr.proc_id, pr.produto_id,
         bool_and(pr.estado_atual IN ('cadastrado', 'rejeitado', 'errado')) AS terminal,
         bool_or(pr.estado_atual IN ('rejeitado', 'errado')) AS tem_falha,
         max(pr.data_criacao) AS ultimo
  FROM liquidacao_processo pr
  WHERE pr.produto_id IN (1505, 1637)
    AND pr.data_criacao >= now() - interval '7 days'
  GROUP BY 1, 2
)
SELECT r.produto_id, count(*) AS remessas,
       count(*) FILTER (WHERE NOT r.terminal) AS em_processamento,
       count(*) FILTER (WHERE r.terminal AND r.tem_falha) AS com_rejeitado_ou_errado,
       count(*) FILTER (WHERE r.terminal AND r.ultimo < now() - interval '2 hours' AND s.solto) AS presas,
       min(r.ultimo) FILTER (WHERE r.terminal AND r.ultimo < now() - interval '2 hours' AND s.solto) AS presa_mais_antiga
FROM remessa r
CROSS JOIN LATERAL (
  SELECT EXISTS (
    SELECT 1
    FROM liquidacao_processo p2
    JOIN liquidacao_pagamento lp ON lp.liquidacao_processo_uuid = p2.uuid
    WHERE p2.proc_id = r.proc_id
      AND p2.estado_atual = 'cadastrado'
      AND lp.liquidacao_lote_id IS NULL
    LIMIT 1
  ) AS solto
  OFFSET 0
) s
GROUP BY 1 ORDER BY 1;
