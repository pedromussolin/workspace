-- Tamanho dos grupos que cada rodada do fechamento por horário pegaria no Mercato Libero
-- (TS-5570, decisão 6 / D20). Rodar na réplica, somente leitura, uma vez.
--
-- Sem o acúmulo (TS-5567), fechar uma chave é um UPDATE em todos os pagamentos dela. O limite do
-- fechamento novo é 480 s; no ritmo medido do 1901 (170 a 290 pagamentos/s) cabem de 80 mil a
-- 140 mil pagamentos. Grupo acima de 80 mil por rodada pede fechamento em blocos antes de ligar o
-- produto.
--
-- Rodadas: 16h, 17h, 18h e 20h45 de Brasília, em dia útil. O pagamento entra na próxima rodada
-- depois da chegada (`data_criacao`); o que chega depois das 20h45 ou no fim de semana vai para a
-- rodada das 16h do próximo dia útil. Feriado não é tratado (cai num dia a mais). A regra D9
-- (cessão `cadastrado`) não é aplicada: o número é um teto, não o grupo exato.
-- `data_criacao` é timestamp sem fuso gravado por now(); a conversão usa o fuso da sessão.
SET statement_timeout = '180s';

WITH pagamento AS (
    SELECT pr.produto_id,
           c.originador_id,
           coalesce(lp.origem_pagamento, '') AS origem,
           pa.fundo_id,
           (lp.data_criacao AT TIME ZONE current_setting('TimeZone'))
               AT TIME ZONE 'America/Sao_Paulo' AS chegada
    FROM liquidacao_pagamento lp
    JOIN liquidacao_processo pr ON pr.uuid = lp.liquidacao_processo_uuid
    JOIN contrato_parcela pa ON pa.id = lp.parcela_id
    JOIN contrato c ON c.id = pa.contrato_id
    WHERE pr.produto_id IN (4, 15, 80, 81, 581, 1406)
      AND lp.data_criacao >= now() - interval '14 days'
), rodada AS (
    SELECT produto_id, originador_id, origem, fundo_id,
           CASE WHEN chegada::time >= '20:45' THEN chegada::date + 1 ELSE chegada::date END AS dia,
           CASE WHEN chegada::time >= '20:45' OR chegada::time < '16:00' THEN '16:00'
                WHEN chegada::time < '17:00' THEN '17:00'
                WHEN chegada::time < '18:00' THEN '18:00'
                ELSE '20:45' END AS horario
    FROM pagamento
), rodada_util AS (
    SELECT produto_id, originador_id, origem, fundo_id,
           dia + CASE extract(dow FROM dia) WHEN 6 THEN 2 WHEN 0 THEN 1 ELSE 0 END AS dia_util,
           CASE WHEN extract(dow FROM dia) IN (0, 6) THEN '16:00' ELSE horario END AS horario
    FROM rodada
), grupo AS (
    SELECT produto_id, dia_util, horario, originador_id, origem, fundo_id, count(*) AS pagamentos
    FROM rodada_util
    GROUP BY 1, 2, 3, 4, 5, 6
)
SELECT produto_id,
       count(*) AS grupos,
       max(pagamentos) AS maior,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY pagamentos) AS p95,
       count(*) FILTER (WHERE pagamentos >= 50000) AS acima_de_50_mil,
       count(*) FILTER (WHERE pagamentos >= 80000) AS acima_de_80_mil,
       (array_agg(horario || ' ' || dia_util ORDER BY pagamentos DESC))[1] AS rodada_do_maior
FROM grupo
GROUP BY produto_id
ORDER BY maior DESC;
