-- TS-5435: conferências antes da GMUD e depois da produção.
-- Rodar na réplica de leitura, uma consulta por vez, com
-- default_transaction_read_only=on e statement_timeout de 120 s.
-- Escrita em 28/10/2026 e ainda não rodada (réplica fora de alcance nesse dia).

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

-- 1b. Depois da produção: produtos cuja modalidade gravada já não bate com as
-- flags (flag mudada direto no banco). Só roda depois da migração.
-- SELECT produto_id, modalidade_fechamento_lote, lote_liquidacao,
--        fechar_lote_por_proc_id, acumula_liquidacoes, baixa_por_agendamento
-- FROM produto_config
-- WHERE modalidade_fechamento_lote::text <> <mesma expressão CASE da consulta 1>;

-- 2. Remessas presas (B19) dos produtos que fecham por proc_id: todos os
-- processos já em estado terminal, há pagamento cadastrado sem lote e o último
-- processo foi criado há mais de 2 horas. Janela de 30 dias. LATERAL por
-- remessa, para usar o índice de proc_id (lição da TS-5377).
WITH remessa AS (
  SELECT pr.proc_id, pr.produto_id,
         bool_and(pr.estado_atual IN ('cadastrado', 'rejeitado', 'errado')) AS terminal,
         bool_or(pr.estado_atual IN ('rejeitado', 'errado')) AS tem_falha,
         max(pr.data_criacao) AS ultimo
  FROM liquidacao_processo pr
  JOIN produto_config pc ON pc.produto_id = pr.produto_id
  WHERE pc.fechar_lote_por_proc_id
    AND pr.data_criacao >= now() - interval '30 days'
  GROUP BY 1, 2
)
SELECT r.produto_id, r.proc_id, r.ultimo, r.tem_falha, s.sem_lote
FROM remessa r
CROSS JOIN LATERAL (
  SELECT count(*) AS sem_lote
  FROM liquidacao_pagamento lp
  JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
  WHERE pr.proc_id = r.proc_id
    AND pr.estado_atual = 'cadastrado'
    AND lp.liquidacao_lote_id IS NULL
) s
WHERE r.terminal
  AND r.ultimo < now() - interval '2 hours'
  AND s.sem_lote > 0
ORDER BY r.ultimo;
