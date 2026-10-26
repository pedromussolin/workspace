-- Configuração de um par produto + fundo, num JSON só.
-- Troque os dois números em params. Validada contra o schema do master 9ddb97f.
WITH params AS (
    SELECT 0::int AS produto_id,
           0::int AS fundo_id
)
SELECT jsonb_pretty(jsonb_build_object(
    'produto', (
        SELECT jsonb_build_object('id', p.id, 'nome', p.nome)
        FROM produto p, params WHERE p.id = params.produto_id
    ),
    'produto_config', (
        SELECT to_jsonb(pc)
        FROM produto_config pc, params WHERE pc.produto_id = params.produto_id
    ),
    'produto_fundo', (
        SELECT to_jsonb(pf)
        FROM produto_fundo pf, params
        WHERE pf.produto_id = params.produto_id AND pf.fundo_id = params.fundo_id
    ),
    'fundo', (
        SELECT jsonb_build_object(
            'id', f.id, 'nome', f.nome, 'adm', f.adm, 'codigo_adm', f.codigo_adm,
            'codigo_fundo', f.codigo_fundo, 'arquivo_liquidacao', f.arquivo_liquidacao
        )
        FROM fundo f, params WHERE f.id = params.fundo_id
    ),
    'fundo_contas', (
        SELECT jsonb_agg(to_jsonb(fc) ORDER BY fc.id)
        FROM fundo_conta fc, params WHERE fc.fundo_id = params.fundo_id
    ),
    'regras', (
        SELECT jsonb_agg(jsonb_build_object(
                   'id', r.id, 'nome', r.nome, 'tipo_regra', r.tipo_regra,
                   'ativada', r.ativada, 'fundo_id', r.fundo_id, 'kwargs', r.kwargs
               ) ORDER BY r.tipo_regra, r.id)
        FROM regra r, params
        WHERE r.produto_id = params.produto_id
          AND (r.fundo_id IS NULL OR r.fundo_id = params.fundo_id)
          AND r.tipo_regra::text IN ('liquidacao', 'estorno', 'cancelamento',
                                     'renegociacao', 'conciliacao')
    ),
    'lotes_vigentes', (
        SELECT jsonb_agg(to_jsonb(v) ORDER BY v.id)
        FROM liquidacao_lote_vigente v, params
        WHERE v.produto_id = params.produto_id AND v.fundo_id = params.fundo_id
    )
)) AS configuracao;
