\set ON_ERROR_STOP on
-- Afrouxa NOT NULL das colunas que não são chave, para gerar só o que o fechamento lê.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT c.table_name, c.column_name FROM information_schema.columns c
           WHERE c.table_schema='public' AND c.is_nullable='NO'
             AND c.table_name IN ('produto','produto_config','fundo','contrato_processo','contrato','contrato_parcela',
                                  'liquidacao_processo','liquidacao_pagamento','liquidacao_lote_processo','liquidacao_lote_vigente')
             AND c.column_name NOT IN ('id','uuid')
  LOOP
    EXECUTE format('ALTER TABLE %I ALTER COLUMN %I DROP NOT NULL', r.table_name, r.column_name);
  END LOOP;
END $$;

-- Só a FK que o UPDATE do fechamento confere fica (pagamento -> lote); as outras
-- apontam para tabelas que a massa não popula.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tc.table_name, tc.constraint_name FROM information_schema.table_constraints tc
           WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
             AND tc.table_name IN ('produto','produto_config','fundo','contrato_processo','contrato','contrato_parcela',
                                   'liquidacao_processo','liquidacao_pagamento','liquidacao_lote_processo','liquidacao_lote_vigente',
                                   'liquidacao_lote_log')
             AND tc.constraint_name NOT LIKE 'fk_liquidacao_pagamento_liquidacao_lote_id%'
  LOOP
    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.table_name, r.constraint_name);
  END LOOP;
END $$;

INSERT INTO fundo (id, nome) VALUES (1, 'Fundo A'), (2, 'Fundo B');
INSERT INTO produto (id, nome, uuid) VALUES
  (101, 'Tela', uuid_generate_v4()), (102, 'Acumula', uuid_generate_v4()),
  (103, 'Gigante', uuid_generate_v4()), (104, 'Por proc_id', uuid_generate_v4());
INSERT INTO produto_config (id, produto_id, acumula_liquidacoes, fechar_lote_por_proc_id, lote_liquidacao, liquidacao_automatico)
VALUES (1,101,false,false,false,false),(2,102,true,false,false,false),(3,103,false,false,false,false),(4,104,false,true,false,false);

-- Uma linha por grupo; n múltiplo de 10 (10 parcelas por contrato).
CREATE TABLE gen_keys (key_id serial PRIMARY KEY, produto_id int, originador_id int, fundo_id int, origem text,
                       n int, kind text);
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
SELECT 101, 11, 1, 'tela-p-' || g, 10 * (1 + (g % 3)), 'tela' FROM generate_series(1, 300) g;
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
SELECT 101, 11, 1, 'tela-m-' || g, 10 * (20 + (g * 37) % 180), 'tela' FROM generate_series(1, 80) g;
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
SELECT 101, 12, 1, 'tela-g-' || g, 10 * (500 + (g * 71) % 1000), 'tela' FROM generate_series(1, 18) g;
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
VALUES (101, 12, 1, 'tela-x-1', 30000, 'tela'), (101, 12, 1, 'tela-x-2', 30000, 'tela');
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
SELECT 102, 11, 1, 'acum-' || g, 50, 'acumula' FROM generate_series(1, 30) g;
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
SELECT 102, 11, 1, 'acum-' || g, 500, 'vigente' FROM generate_series(1, 30) g;
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
VALUES (103, 13, 2, 'gigante-100k', 100000, 'gigante'), (103, 13, 2, 'gigante-300k', 300000, 'gigante'),
       (103, 13, 2, 'gigante-600k', 600000, 'gigante');
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
SELECT CASE WHEN g % 2 = 0 THEN 101 ELSE 103 END, 11, 1 + g % 2, 'fechado-' || g, 10000, 'fechado' FROM generate_series(1, 200) g;
INSERT INTO gen_keys (produto_id, originador_id, fundo_id, origem, n, kind)
VALUES (104, 11, 1, 'proc-1', 100, 'proc');

ALTER TABLE gen_keys ADD COLUMN first_id bigint;
UPDATE gen_keys k SET first_id = s.first_id
FROM (SELECT key_id, 1 + coalesce(sum(n) OVER (ORDER BY key_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS first_id
      FROM gen_keys) s WHERE s.key_id = k.key_id;

-- Lotes antigos: um por grupo já fechado e um vigente (aberto) por linha do produto que acumula.
INSERT INTO liquidacao_lote_processo (id, identificador, estado_atual, produto_id, data_criacao)
SELECT key_id, uuid_generate_v4(), CASE kind WHEN 'vigente' THEN 'pendente' ELSE 'concluido' END, produto_id, now() - interval '30 days'
FROM gen_keys WHERE kind IN ('fechado', 'vigente');
SELECT setval(pg_get_serial_sequence('liquidacao_lote_processo', 'id'), 100000);
INSERT INTO liquidacao_lote_vigente (id, produto_id, fundo_id, originador_id, origem_pagamento, liquidacao_lote_id, fechado)
SELECT key_id, produto_id, fundo_id, originador_id, origem, key_id, false FROM gen_keys WHERE kind = 'vigente';

INSERT INTO liquidacao_processo (uuid, estado_atual, produto_id, proc_id, data_criacao)
SELECT md5('lp' || key_id)::uuid, 'cadastrado', produto_id, md5('proc' || key_id)::uuid, now() - interval '1 day' FROM gen_keys;

-- Contratos: um processo por contrato (processo_uuid é único), 10 parcelas por contrato.
-- 8% das cessões ainda não concluídas e 2% excluídas, só nos grupos da tela (regra D9).
INSERT INTO contrato_processo (uuid, estado_atual, data_delete, produto_id, fundo_id, data_criacao)
SELECT md5('cp' || c)::uuid,
       CASE WHEN k.kind = 'tela' AND c % 25 IN (1, 2) THEN 'registrando' ELSE 'cadastrado' END,
       CASE WHEN k.kind = 'tela' AND c % 50 = 7 THEN now() ELSE NULL END,
       k.produto_id, k.fundo_id, now() - interval '60 days'
FROM gen_keys k, generate_series((k.first_id + 9) / 10, (k.first_id + k.n - 1) / 10) c;
INSERT INTO contrato (id, processo_uuid, originador_id)
SELECT c, md5('cp' || c)::uuid, k.originador_id
FROM gen_keys k, generate_series((k.first_id + 9) / 10, (k.first_id + k.n - 1) / 10) c;
INSERT INTO contrato_parcela (id, contrato_id, fundo_id)
SELECT p, (p + 9) / 10, k.fundo_id FROM gen_keys k, generate_series(k.first_id, k.first_id + k.n - 1) p;
INSERT INTO liquidacao_pagamento (id, liquidacao_processo_uuid, parcela_id, origem_pagamento, liquidacao_lote_id, valor_pago, data_criacao)
SELECT p, md5('lp' || k.key_id)::uuid, p, k.origem,
       CASE WHEN k.kind IN ('fechado', 'vigente') THEN k.key_id END, 100, now() - interval '1 day'
FROM gen_keys k, generate_series(k.first_id, k.first_id + k.n - 1) p;
SELECT setval(pg_get_serial_sequence('liquidacao_pagamento', 'id'), (SELECT max(id) FROM liquidacao_pagamento));

ANALYZE;
SELECT kind, count(*) AS grupos, sum(n) AS pagamentos FROM gen_keys GROUP BY kind ORDER BY 3 DESC;
