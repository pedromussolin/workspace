# 40 — Ações em lote nas tabelas do Controle de acesso

- **TS:** TS-5463 (épico TS-5357) · **Branch:** `feature/TS-5463-acoes-em-lote-nas-tabelas` (front), da `master`,
  worktree `~/repos/apl-credit-whitelabel-wt/5463`
- **Status:** **em implementação** (28/10), sem commit até a revisão do Pietro.
- **Decisão:** D137. **Depende de:** 39 em produção, para apagar role em lote passar na primeira tentativa.

## Desenho combinado

- Só o front muda. O lote do BFF já tem as quatro remoções (excluir grupo, apagar role, remover membro, tirar
  atribuição), com prévia, confirmação, ordem entre os itens e auditoria, até 500 operações.
- A barra de ações em lote da Formalização sobe para `shared/ui`; a Formalização passa a usá-la sem mudar a tela.
- Pessoas, Grupos e Permissões ganham a caixa de marcar no cabeçalho (tudo o que o filtro mostra, inclusive o que
  não carregou), a caixa por linha e a barra com "N selecionadas de M" e "Limpar seleção". Mudar o filtro limpa a
  seleção.
- Ações:
  - Grupos: excluir grupos;
  - Permissões: apagar permissões (o BFF tira as atribuições antes);
  - Pessoas: remover de um grupo escolhido e tirar uma permissão direta.
- A ação abre a mesma prévia da aba Lote. Linha bloqueada aparece como bloqueada e o resto segue; remoção pede
  "REMOVER"; depois vem o resultado, a tabela atualiza e a seleção limpa.
- Acima de 500 operações, a barra avisa e a ação fica desligada.
- A barra só aparece para quem pode aplicar lote.

## Pronto quando

- As três abas selecionam, montam as operações e aplicam pela prévia.
- A Formalização continua igual, usando a barra compartilhada.
- Testes de componente da barra, da seleção e de cada aba; `validate.sh` ok.
