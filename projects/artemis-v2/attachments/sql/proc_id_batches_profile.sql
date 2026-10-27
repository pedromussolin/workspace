-- Tarefa 02: perfil dos produtos que fecham por proc_id.
-- Rodar na réplica de leitura, uma consulta por vez, com
-- default_transaction_read_only=on e statement_timeout de 120 s.
-- Medido em 27/10/2026 (resultado no plano 02-03-implementation-plan.md).
-- A mesma janela com 30 dias estoura 90 s: são três buscas por índice por
-- pagamento; ficar em 7 dias.

-- 1. Produtos por modo e acúmulo (decide a D7).
SELECT pc.produto_id,
       coalesce(pc.fechar_lote_por_proc_id, false) AS por_proc_id,
       coalesce(pc.acumula_liquidacoes, false) AS acumula,
       pc.lote_liquidacao, pc.liquidacao_automatico, pc.baixa_por_agendamento
FROM produto_config pc
WHERE pc.fechar_lote_por_proc_id OR pc.acumula_liquidacoes
ORDER BY 2 DESC, 3 DESC, 1;

-- 2. Fundos e ADM dos produtos por proc_id. Trocar a lista.
SELECT pf.produto_id, pf.fundo_id, f.adm, f.arquivo_liquidacao
FROM produto_fundo pf
JOIN fundo f ON f.id = pf.fundo_id
WHERE pf.produto_id IN (0)
ORDER BY 1, 2;

-- 3. Lotes reais dos últimos 7 dias, um resumo por lote (LATERAL por lote,
-- para o Postgres usar o índice de liquidacao_lote_id).
WITH x AS (
  SELECT l.produto_id, l.id, s.*
  FROM liquidacao_lote_processo l
  CROSS JOIN LATERAL (
    SELECT count(*) AS pagamentos,
           count(DISTINCT pr.proc_id) AS remessas,
           min(pr.proc_id::text) AS proc_id,
           count(DISTINCT c.originador_id) AS originadores,
           count(DISTINCT pa.fundo_id) AS fundos,
           count(DISTINCT coalesce(lp.origem_pagamento, '')) AS origens
    FROM liquidacao_pagamento lp
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
    JOIN contrato_parcela pa ON pa.id = lp.parcela_id
    JOIN contrato c ON c.id = pa.contrato_id
    WHERE lp.liquidacao_lote_id = l.id
  ) s
  WHERE l.produto_id IN (0) AND l.data_criacao >= now() - interval '7 days'
)
SELECT produto_id, count(*) AS lotes, count(DISTINCT proc_id) AS remessas_distintas,
       sum(pagamentos) AS pagamentos, max(pagamentos) AS maior_lote,
       count(*) FILTER (WHERE remessas > 1) AS lote_multi_remessa,
       count(*) FILTER (WHERE originadores > 1) AS lote_multi_originador,
       count(*) FILTER (WHERE fundos > 1) AS lote_multi_fundo,
       count(*) FILTER (WHERE origens > 1) AS lote_multi_origem,
       count(*) - count(DISTINCT proc_id) AS lotes_irmaos
FROM x GROUP BY 1 ORDER BY 1;

-- 4. Remessas que viraram mais de um lote, e por qual dimensão. Mesmo CTE x
-- da consulta 3, trocando os count(DISTINCT ...) por min(...) por lote.
-- Linha com pagamentos = 0 e proc_id nulo: lotes sem nenhum pagamento (B21).
WITH x AS (
  SELECT l.produto_id, l.id, s.*
  FROM liquidacao_lote_processo l
  CROSS JOIN LATERAL (
    SELECT count(*) AS pagamentos, min(pr.proc_id::text) AS proc_id,
           min(c.originador_id) AS originador_id, min(pa.fundo_id) AS fundo_id,
           min(coalesce(lp.origem_pagamento, '')) AS origem
    FROM liquidacao_pagamento lp
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
    JOIN contrato_parcela pa ON pa.id = lp.parcela_id
    JOIN contrato c ON c.id = pa.contrato_id
    WHERE lp.liquidacao_lote_id = l.id
  ) s
  WHERE l.produto_id IN (0) AND l.data_criacao >= now() - interval '7 days'
)
SELECT produto_id, count(*) AS lotes,
       count(DISTINCT originador_id) AS originadores,
       count(DISTINCT fundo_id) AS fundos,
       count(DISTINCT origem) AS origens,
       sum(pagamentos) AS pagamentos
FROM x GROUP BY produto_id, proc_id HAVING count(*) > 1
ORDER BY 1, 2 DESC;
