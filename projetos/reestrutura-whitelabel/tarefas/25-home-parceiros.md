# 25 / R60 — Home dos parceiros com a operação do dia

- **TS:** TS-5395 (refinamento) · **Branch:** `refact/TS-5395-refinamento-visual`, worktree
  `~/repos/apl-credit-whitelabel-wt/25`
- **Status:** **em implementação** (20/10): desenho aprovado em três partes no chat
- **Convive com a 28** (TS-5406, outro chat): ela muda a home interna (POLI e mascotes) em
  `features/general/home/home.page.*`. Aqui a home dos parceiros vira um componente próprio, e o
  `home.page.html` só troca o bloco dos parceiros por ele. A 28 recebe isto por merge.

## Por quê

Pedido do Pietro em 20/10: a home dos parceiros ("Seja bem-vindo(a)!" com Seguro, Integrado e
Intuitivo) "não serve pra nada, é sem graça e horrível". Escolhido o "painel da operação".

## Desenho

**Topo:** "Bom dia / Boa tarde / Boa noite, {primeiro nome}" (antes das 12h, das 12h às 18h, depois)
e a data por extenso ("segunda-feira, 20 de outubro").

**"Hoje na sua operação":** um cartão por tela que a pessoa pode abrir (`iam/paths`), com o ícone, o
nome, até três números e o link "Ver …". Cada módulo dá o seu resumo pela entrada pública
`features/<módulo>/home-summary` (contrato `ModuleSummarySource` em
`shared/utils/module-summary.ts`); a home só monta. Os números usam as rotas que as telas já
chamam (lista com 1 por página, lendo só o total), com a permissão e o escopo de parceiro do BFF.

| Módulo | Números | Link |
|---|---|---|
| Lotes de Liquidação | Hoje; Em conciliação (aguardando + manual, alerta se > 0); Concluídos | Ver lotes |
| Lotes de Cessão | Em aberto; Aguardando lastro (ou os dois grupos de status que a tela usa) | Ver lotes |
| Formalização | Pendentes (alerta se > 0); Ativos (do `summary` da lista) | Ver pendências |

Cada cartão carrega sozinho (skeleton), e erro fica nele ("Não foi possível carregar." e "Tentar de
novo"). Tudo zero: "Nada hoje".

**"Acesso rápido":** as telas liberadas da seção Módulos do menu (`filterNavigation`), com ícone,
nome e o grupo embaixo.

**"Continuar de onde parou":** as últimas 5 páginas abertas (título do menu e, na tela de detalhe, o
último trecho da URL: "Pré-Trade · 123"), guardadas só no navegador (`portal.recent-pages`). Sem
histórico, a seção não aparece.

**Sem nenhum módulo liberado:** estado vazio "Ainda não há telas liberadas para você. Fale com o
administrador do portal.".

**Layout:** cartões em grade; abaixo, duas colunas (Acesso rápido | Continuar de onde parou). No
celular, um cartão por linha e as colunas empilhadas, sem rolagem lateral. Cada cartão é uma região
com o nome do módulo; os números têm rótulo em texto; com movimento reduzido, sem animação de
entrada. A home interna (POLI) não muda aqui.

## Plano

**Já feito pelo main:** `shared/utils/module-summary.ts` (contrato) e, no `eslint.config.js`, as três
entradas `<módulo>/home-summary` em `PUBLIC_FEATURE_ENTRIES` e `app-shell/navigation` em
`PUBLIC_SHELL_ENTRIES`.

**Parte A — resumos dos módulos** (`features/{liquidation-batches,assignment-batches,formalization}/home-summary/`):

- [ ] Em cada módulo: `<módulo>-home-summary.ts` com uma classe `@Injectable({ providedIn: 'root' })`
  que implementa `ModuleSummarySource` (`LiquidationHomeSummary`, `AssignmentHomeSummary`,
  `FormalizationHomeSummary`), o spec e o `index.ts` que só reexporta a classe.
- [ ] `route`, `title` (`PAGE_TITLES`) e `icon` iguais aos do menu; `load()` usa o serviço do
  `data-access` do próprio módulo, com `per_page`/`perPage` 1, e lê o total; a data de hoje é a
  mesma que a tela usa como padrão; os status vêm do mapa de status do módulo.
- [ ] O `link` só leva filtros na URL se a tela já os lê da URL; senão, só a rota.
- [ ] Specs: os números e o tom a partir das respostas simuladas, os parâmetros enviados e o erro
  propagado.

**Parte B — home e páginas recentes** (`features/general/home/`, `core/navigation/`, `layouts/app-shell/`):

- [ ] `core/navigation/recent-pages.ts`: `RecentPagesService` (root) com `pages` (sinal),
  `record(url, label)`; 5 no máximo, sem repetir a URL, a mais nova primeiro; ignora `/home`,
  login e páginas de erro; `localStorage` em try/catch.
- [ ] Shell: no `NavigationEnd` que já existe, `record(url, rótulo)`, com o rótulo de `findPageNav`
  (item do menu e, quando o caminho passa da rota do item, o último trecho).
- [ ] `features/general/home/partner-home/`: o componente do desenho, com `partner-home.view.ts`
  (funções puras: saudação pela hora, data por extenso, "Nada hoje", fontes liberadas por
  `iam/paths`).
- [ ] `home.page.html`: o bloco dos parceiros vira `<app-partner-home />`.
- [ ] Specs: cartão por tela liberada; erro de um não afeta os outros; "Nada hoje"; sem módulos;
  saudação pela hora; recentes (limite, sem repetir, ignorados, armazenamento bloqueado).

**Main, no fim:** dados fictícios das três listas no portal local, smoke da home de parceiro (claro,
escuro, celular), `.ai` (`reference-screens.md` e a regra das entradas públicas em
`architecture.md`), validação e commits:
`feat(TS-5395): resumo da home por módulo`, `feat(TS-5395): home dos parceiros com a operação do
dia`, `chore(TS-5395): .ai com a home dos parceiros`.
