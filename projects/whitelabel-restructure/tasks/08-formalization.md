+++
card = "TS-5365"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 08 — Formalização

- **TS:** TS-5365 · **Branch:** `refact/TS-5365-formalizacao-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** publicada (15/10), sem merge em ambiente
- **Depende de:** 04
- **Passos e critério de pronto:** [area-playbook.md](area-playbook.md)

## Telas e rotas

| URL | Hoje |
|---|---|
| `/formalization` | `pages/operations/formalization/formalization.page` |

## O que vai para `features/formalization/`

- A tela.
- `services/operations/formalization/*` e
  `interfaces/operations/formalization/*` → `data-access/`.

Inventário (`d0bc3de`): 6 arquivos, 3.013 linhas (página grande), 138
cores fixas e **nenhum** uso de token, 2 specs. Material: icon, dialog,
tooltip e snack-bar.

## Fluxos críticos

- Listagem com ordenação própria (`sortIcon`, `arrow_upward` e
  `arrow_downward`), filtros e edição.

## Pontos de atenção

- A página tem ordenação feita na mão. Avaliar trocar pelo `appSort` da 04
  **sem** mudar o comportamento, ou deixar como está e anotar.
- É a tela com mais cara de "defasada" (zero tokens hoje). É a que mais vai
  mudar visualmente.

## O que foi feito (15/10/2026)

Branch `refact/TS-5365-formalizacao-nova-arquitetura`, criada da 04 com as
duas correções de 15/10. São 7 commits:

| Commit | O quê |
|---|---|
| `440db34` | move para `features/formalization` (+ `data-access/`) e rota com `loadChildren`, mesma URL e mesmo `iamGuard` |
| `0de2db3` | specs da área ganham o `HttpClient` de teste. Antes falhavam todos com NG0201 |
| `fe0bb94`, `3973852` | cópia (cherry-pick) da pílula, do indicador, do estado vazio e do texto de valor vazio da 05. O conteúdo é idêntico, então o merge das duas não conflita |
| `bbeb9ad` | modelo, regras e visão em funções puras (`formalization.model/rules/view/dates`, `registration.rules`) |
| `627ef96` | resumo, filtros, ações em lote, exportar e tabela viram componentes próprios |
| `833c94d` | página e diálogo sobre `shared/ui`, sem Material, com o estado em signals |

**Mudanças visíveis para listar na PR:**
- **Paginação:** os botões numerados viraram o paginador comum: primeira,
  anterior, próxima, última, "1–10 de N" e tamanho 10/25/50. Trocar o tamanho
  continua voltando para a página 1.
- **Cabeçalho:** "Exportar" e "Cadastrar Condomínio" foram para o cabeçalho
  da página, à direita. O menu de escopo da exportação é o menu comum, com Esc,
  setas e foco de volta.
- **KPIs:** usam o card comum. A porcentagem fica no valor ("2 · 25%").
- **Controle segmentado:** Status, Coobrigação, status em lote e as abas do
  diálogo usam o padrão dos Lotes. No diálogo, a Coobrigação deixou de ser uma
  caixa de marcar e virou Sim/Não.
- **Pílulas de status tonais:** Ativo verde, Inativo neutro, Pendente Cerys
  em atenção e Pendente Poliedro na cor da marca.
- **Datas:** filtros e diálogo usam o calendário próprio no lugar do campo
  nativo.
- **"Informações Adicionais":** virou o accordion animado.
- **Toasts:**
  - usam a pilha comum com as durações padrão;
  - o texto "Fechar" saiu e o X fecha;
  - a falha ao criar as unidades, depois do condomínio criado, virou um
    aviso.
- **Valor vazio:** aparece "—" no lugar de "-".
- **VGV:** o ícone de ajuda substitui o "(?)".
- **Nomes longos:** terminam em reticências, com tooltip.
- **Tela estreita:** os filtros empilham, e a tabela rola de lado a partir de
  1100 px.

**Validação** (base: a 04 rebaseada, 675 testes com 77 falhando e lint
59/281):

| Item | 08 |
|---|---|
| Build | ok |
| Lint | 58 erros / 279 avisos |
| Testes | 818, com 55 falhando, nenhuma falha nova. Specs da área: 150/150 (reconferido na 04 com as três correções) |
| Smoke (mock) | 29 rotas, sem erro de página |
| Prints | cabeçalho da tabela e controle segmentado no celular conferidos depois das correções da 04 |

Não deu para exercitar com dados, porque o mock não tem condomínios:
cadastro, edição, ações em lote e exportação. Esses fluxos ficam cobertos
pelos specs e precisam ser conferidos na sandbox.

## Merge da master (15/10/2026, noite)

Depois da publicação, a `master` recebeu o `e4e13a5` (PR #224,
"improve responsiveness"), que mexe na tela antiga da Formalização. Sem
levar a mudança para a 08, o merge dela na `sandbox` daria conflito
(arquivo movido × arquivo alterado) e a melhoria se perderia.

| Commit | O quê |
|---|---|
| `7d2cad1` | merge da `origin/master` (`576957c`). O conflito modify/delete fica com a versão refatorada |
| `dabea02` | leva a mudança para os filtros novos: o status de cinco opções vira uma lista (`app-select`), e as duas datas viram um campo de período (`app-date-picker range`) |

**Mudanças visíveis para listar na PR** (vêm da master):
- o filtro de Status vira uma lista: Todos, Pendente Cerys, Pendente
  Poliedro, Ativo e Inativo;
- a Data de Cadastro vira um campo só de período, com um calendário que
  escolhe início e fim.

A master fazia isso com um `select` nativo e com um painel próprio de duas
datas. Aqui são as peças de `shared/ui`, que têm o mesmo efeito no celular.

Depois dos prints, um ajuste: o campo de período deixou de esticar na
linha inteira, e o rótulo "Coobrigação" ganhou o mesmo estilo dos campos ao
lado (`fix(TS-5365): período sem esticar e rótulo da coobrigação
padronizado`).

**Situação:** 3 commits a mais, sem push.
- Os specs da Formalização passam (150 de 150).
- O `validate-batch.sh` passa:
  - build ok;
  - lint 58/279;
  - 818 testes, nenhuma falha nova e 22 da base corrigidas;
  - smoke sem erro em claro, escuro, Dots e celular.
- As duas "pendências" que o script aponta são os commits da própria
  master (`e4e13a5`, `576957c`), que não compilam os specs (A21). Não são da
  08.
- Em 1440 px a tabela ainda corta a coluna Status. Isso já vinha da 08, e
  a 13b ficou com o ajuste.
