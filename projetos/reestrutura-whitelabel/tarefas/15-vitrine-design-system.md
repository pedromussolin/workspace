# 15 — Vitrine do design system

- **TS:** TS-5372 · **Branch:** `feature/TS-5372-vitrine-design-system` (da 04)
- **Status:** em andamento (15/10, 4ª leva)
- **Depende de:** 04. Pode começar parcial depois da 03.

## Objetivo

Uma página interna, viva, que mostra o design system do portal como ele é
de verdade. Nada é salvo (decisão de 10/10).

## Conteúdo

- Seletor de **marca** (Poliedro, Dots, Cerys, Viva) e de **esquema** (claro,
  escuro), trocando na hora só nesta página, sem mexer no tema do resto do
  portal.
- Tokens:
  - cores de marca e semânticas, com o valor e o contraste medido;
  - raio, espaçamento, sombras e escala de fonte.
- Ícones: os 148, com busca pelo nome novo e pelo nome antigo do Material.
- Componentes de `shared/ui`:
  - cada componente com seus estados (padrão, foco, desabilitado, erro,
    carregando, vazio);
  - exemplo de uso copiável.
- Padrões de tela, montados com os componentes de verdade: cards de resumo,
  toolbar de filtros, tabela com linha expandida, pílulas de status e
  diálogo.

## Regras

- Rota `/design-system` com `iamGuard` (escopo a definir com o Pietro, ex.:
  `design-system:read`).
- A vitrine usa os mesmos componentes das telas. Não pode existir versão
  "de mostruário".
- Responsiva. Serve também para conferir o layout no celular.

## Testes

- Spec que percorre o registro de componentes da vitrine e garante que todo
  componente de `shared/ui` aparece nela. Componente novo sem exemplo
  quebra o teste.
