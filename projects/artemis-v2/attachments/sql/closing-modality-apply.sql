-- Aplica a modalidade de fechamento (TS-5435) a partir das flags, só nos produtos divergentes.
-- Uso: se a migration c3f81d7a5e24 parar no meio, ou se uma flag for mudada direto no banco.
-- Escreve no banco principal. Idempotente: sem divergência, não muda nada.
-- Tudo numa transação: se no fim ainda houver divergência ou nulo, o bloco levanta erro e nada fica.
-- Regra: a de closing-modality-preview.sql. Rodar com psql -v ON_ERROR_STOP=1.
SET lock_timeout = '5s';      -- a coluna pede trava na produto_config; não ficar na fila atrás de transação longa
SET statement_timeout = '60s';

BEGIN;

CREATE TEMP TABLE modalidade_esperada ON COMMIT DROP AS
SELECT produto_id,
       CASE
           WHEN COALESCE(lote_liquidacao, FALSE) AND COALESCE(fechar_lote_por_proc_id, FALSE)
               THEN 'automatico_por_remessa'
           WHEN COALESCE(acumula_liquidacoes, FALSE) THEN 'acumulado'
           WHEN COALESCE(baixa_por_agendamento, FALSE) THEN 'agendado'
           WHEN COALESCE(lote_liquidacao, FALSE) THEN 'automatico_por_chave'
           ELSE 'manual'
       END AS esperada
  FROM produto_config;

-- O que vai mudar (antes de mudar).
SELECT pc.produto_id, pc.modalidade_fechamento_lote::text AS gravada, e.esperada
  FROM produto_config pc
  JOIN modalidade_esperada e USING (produto_id)
 WHERE pc.modalidade_fechamento_lote::text IS DISTINCT FROM e.esperada
 ORDER BY 1;

UPDATE produto_config pc
   SET modalidade_fechamento_lote = CAST(e.esperada AS enumbatchclosingmodality)
  FROM modalidade_esperada e
 WHERE e.produto_id = pc.produto_id
   AND pc.modalidade_fechamento_lote::text IS DISTINCT FROM e.esperada;

DO $$
DECLARE
    restantes integer;
BEGIN
    SELECT count(*) INTO restantes
      FROM produto_config pc
      JOIN modalidade_esperada e USING (produto_id)
     WHERE pc.modalidade_fechamento_lote::text IS DISTINCT FROM e.esperada;
    IF restantes > 0 THEN
        RAISE EXCEPTION 'Ainda há % produto(s) com a modalidade divergente; nada foi gravado', restantes;
    END IF;
END $$;

COMMIT;
