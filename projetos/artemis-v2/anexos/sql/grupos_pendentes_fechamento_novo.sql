-- Tamanho dos grupos que o fechamento novo (TS-5377) pegaria hoje.
-- Rodar na réplica. Mesma regra do UPDATE de refact.py:135-176 (commit
-- f19ef2cef): pagamento sem lote, liquidação e cessão do contrato em
-- `cadastrado`, processo não excluído. Fundo da parcela, como a chave da tela.
-- Responde ao L3 (tarefa 03) e à D20: o maior grupo define se o UPDATE único
-- cabe no limite da task (soft 540 s).
SET statement_timeout = '300s';

-- 1. Os 30 maiores grupos por chave, com o modo de fechamento do produto e a
-- faixa de datas (a chave não tem data: fechar leva todas).
SELECT pr.produto_id,
       c.originador_id,
       coalesce(lp.origem_pagamento, '') AS origem,
       pa.fundo_id,
       coalesce(pc.fechar_lote_por_proc_id, false) AS fecha_por_proc_id,
       coalesce(pc.acumula_liquidacoes, false) AS acumula,
       count(*) AS pagamentos,
       min(lp.data_criacao)::date AS mais_antigo,
       max(lp.data_criacao)::date AS mais_novo
FROM liquidacao_pagamento lp
JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
JOIN contrato_parcela pa ON pa.id = lp.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
LEFT JOIN produto_config pc ON pc.produto_id = pr.produto_id
WHERE lp.liquidacao_lote_id IS NULL
  AND pr.estado_atual = 'cadastrado'
  AND pe.data_delete IS NULL
  AND pe.estado_atual = 'cadastrado'
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY pagamentos DESC
LIMIT 30;

-- 2. Plano e tempo do SELECT equivalente ao UPDATE, para o maior grupo da
-- consulta 1 que não fecha por proc_id. Trocar os quatro valores. Se a origem
-- for vazia, trocar a linha da origem por
-- `(lp.origem_pagamento IS NULL OR lp.origem_pagamento = '')`.
EXPLAIN (ANALYZE, BUFFERS)
SELECT lp.id
FROM liquidacao_pagamento lp
JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
JOIN contrato_parcela pa ON pa.id = lp.parcela_id
JOIN contrato c ON c.id = pa.contrato_id
JOIN contrato_processo pe ON pe.uuid = c.processo_uuid
WHERE lp.liquidacao_lote_id IS NULL
  AND pr.estado_atual = 'cadastrado'
  AND pr.produto_id = 0
  AND pe.data_delete IS NULL
  AND pe.estado_atual = 'cadastrado'
  AND c.originador_id = 0
  AND coalesce(lp.origem_pagamento, '') = ''
  AND pa.fundo_id = 0;

-- 3. Pagamentos "em trânsito" (B14): liquidação já `cadastrado` e sem lote em
-- produto que acumula. Deveria ser quase zero fora de remessa em
-- processamento; valor alto e estável indica pagamento que não entrou no
-- vigente.
SELECT pr.produto_id, count(*) AS pagamentos, max(lp.data_criacao) AS mais_novo
FROM liquidacao_pagamento lp
JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
JOIN produto_config pc ON pc.produto_id = pr.produto_id
WHERE lp.liquidacao_lote_id IS NULL
  AND pr.estado_atual = 'cadastrado'
  AND pc.acumula_liquidacoes
  AND lp.data_criacao >= now() - interval '7 days'
GROUP BY 1
ORDER BY 2 DESC;
