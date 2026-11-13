+++
card = "TS-5372"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 15 — Vitrine do design system

- **TS:** TS-5372 · **Branch:** `feature/TS-5372-vitrine-design-system` (da 04)
- **Status:** commits feitos, sem push (15/10)
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

## O que foi feito (15/10/2026)

Duas branches, as duas sem push:
- **front:** `feature/TS-5372-vitrine-design-system`, criada da 04 com as
  três correções de 15/10 (`779aa13`), com 31 commits;
- **BFF:** `feature/TS-5372-vitrine-design-system`, criada da
  `origin/master` (`946dce3`), com 1 commit.

| Commits | O quê |
|---|---|
| 19 primeiros (`23ff388` … `4b21556`) | cópias (cherry-pick) das peças comuns das áreas, com conteúdo idêntico: select e multiselect (05), pílula/KPI/estado vazio (05), combobox com "Adicionar" (07), `app-switch` (10), tabela com rodapé e cabeçalho agrupado, `app-chart` e as peças de gráfico, aviso, botão com menu e cartão (09), ícone `more-vertical` (12). Assim a vitrine mostra o `shared/ui` inteiro |
| `57a5c1c`, `a12e9de` | rodapé da sidebar com os atalhos "Docs da API" e "Design system" (selo "Nova", só para quem tem o caminho, também recolhida e na gaveta) e trilha no cabeçalho das páginas dos atalhos. Os dois commits também estão na 14, idênticos |
| `064de1b`, `c5a634c`, `19f08f8` | valor vazio (cópia da 05); a conta de contraste WCAG sai do `themes.spec.ts` para `shared/utils/contrast.ts`; `app-code-block` copiado da 14 |
| `538cb1d` | escopo de tema em `core/theme`: marca e esquema trocam só dentro de um contêiner, inclusive nos diálogos, menus, tooltips e toasts abertos de dentro dele. O `_tokens.scss` foi dividido: o que muda por marca e esquema vale para `:root, [data-theme-scope]`; o resto continua só no `:root` |
| `1c99729` … `6983780` | a vitrine: marca e esquema, tokens com valor e contraste medido, os 149 ícones com busca pelo nome antigo do Material, 31 componentes com estados e uso copiável, e padrões de tela montados com os componentes de verdade (cards que filtram, toolbar, tabela com linha que abre, pílulas e diálogo) |
| BFF `dcc6be4` | `/design-system` no `FRONTEND_ROUTE_PERMISSIONS`, logo depois do `/home`, com `admin:read` ou `design-system:read` (D15), e teste |

O spec de registro da vitrine lê do código compilado todos os componentes
e diretivas de `shared/ui` e falha se algum não tiver exemplo. No merge de
teste com todas as áreas, ele passou: tudo que existe em `shared/ui` está
na vitrine.

**Mudanças visíveis para listar na PR:**
- página nova "Design system" (`/design-system`), para quem tem
  `design-system:read` ou `admin:read`;
- rodapé da sidebar com os atalhos (sem nenhum atalho liberado, o rodapé
  fica como antes);
- fora da vitrine, nada muda: a Home e o Pré-Trade foram comparados pixel a
  pixel com a base em claro, celular, escuro e Dots. As únicas diferenças
  são animações.

**Para a infraestrutura:** criar a app role `design-system:read`. Até lá,
só quem tem `admin:read` vê a página.

**Ajustes sugeridos para a passada de consistência** (o agente não mexeu
em peça comum):
- `app-kpi`: KPI filtrável e não filtrável lado a lado ficam com alturas
  diferentes (o host é `display: block`);
- `app-card`: `flush` sem `booleanAttribute` (`<app-card flush>` não
  compila);
- `app-code-block`: usar o `Clipboard` do CDK (funciona fora de HTTPS) e o
  `LiveAnnouncer` no "Copiado";
- tooltip: o id do painel é fixo; com o escopo da vitrine pode haver dois
  painéis com o mesmo id.

**Validação** (base da 04: 678 testes, 77 falhando, lint 59/281):

| Item | 15 |
|---|---|
| Build | ok |
| Lint | 59 erros / 281 avisos |
| Testes | 840, com 77 falhando, nenhuma falha nova |
| Commits | todos compilam sozinhos |
| Smoke | vitrine (tokens, ícones, componentes, padrões, troca para Dots e escuro), Home e Pré-Trade, em claro, escuro, Dots e celular, sem erro de página, de console nem rolagem lateral |
| BFF | 509 testes, com as mesmas 8 falhas da base; `ruff` e `black` limpos |

Não deu para exercitar por print: foco visível pelo teclado e diálogo,
menu e toast abertos (cobertos pelos specs do escopo).
