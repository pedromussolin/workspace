-- Configuração do fluxo Pre-Trade na sandbox (só leitura)

-- 1) Etapas: quem aprova (xN vagas), quem edita e regras de aprovação automática
SELECT s.id, s.name, s.label, s.is_initial, s.is_terminal, s.is_editable,
  (SELECT string_agg(p.name || ' x' || ac.required_approvals
                     || CASE WHEN ac.is_active THEN '' ELSE ' (inativa)' END, ', ' ORDER BY p.name)
     FROM workflows.approval_config ac JOIN workflows.permission p ON p.id = ac.permission_id
    WHERE ac.stage_id = s.id) AS aprovacoes,
  (SELECT string_agg(p.name, ', ' ORDER BY p.name)
     FROM workflows.editor_permission ep JOIN workflows.permission p ON p.id = ep.permission_id
    WHERE ep.stage_id = s.id) AS editores,
  (SELECT string_agg(r.name || ' -> ' || coalesce(
            (SELECT string_agg(p.name, '+') FROM workflows.rule_permission rp
               JOIN workflows.permission p ON p.id = rp.permission_id
              WHERE rp.rule_id = r.id), '-'), '; ')
     FROM workflows.rule r WHERE r.stage_id = s.id) AS regras
FROM workflows.stage s JOIN workflows.workflow w ON w.id = s.workflow_id
WHERE w.name = 'Pre-Trade'
ORDER BY s.id;

-- 2) Transições e quem pode fazer cada uma
SELECT t.id, ps.name AS de, ns.name AS para, t.on_decision,
  (SELECT string_agg(p.name, ', ' ORDER BY p.name)
     FROM workflows.authorized_permission ap JOIN workflows.permission p ON p.id = ap.permission_id
    WHERE ap.transition_id = t.id) AS quem
FROM workflows.transition t
JOIN workflows.workflow w ON w.id = t.workflow_id
JOIN workflows.stage ps ON ps.id = t.previous_stage_id
JOIN workflows.stage ns ON ns.id = t.next_stage_id
WHERE w.name = 'Pre-Trade'
ORDER BY t.id;

-- 3) Permissões (com quantos usuários cada) e avisos ligados
SELECT p.id, p.scope, p.group_name, p.policy, p.name, p.alias,
  (SELECT count(*) FROM workflows.user_permission up WHERE up.permission_id = p.id) AS usuarios
FROM workflows.permission p
ORDER BY p.scope, p.id;

SELECT nc.notification_type, nc.template_name, nc.is_active
FROM workflows.notification_config nc JOIN workflows.workflow w ON w.id = nc.workflow_id
WHERE w.name = 'Pre-Trade'
ORDER BY nc.notification_type;

-- 4) Versão das migrations aplicada na sandbox
SELECT version_num FROM alembic_version;
