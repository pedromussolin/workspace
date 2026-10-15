# 08 — Formalização

- **TS:** TS-5365 · **Branch:** `refact/TS-5365-formalizacao-nova-arquitetura` (da 04, ou da `origin/master` depois do merge da 04)
- **Status:** commits feitos, sem push (15/10)
- **Depende de:** 04
- **Passos e critério de pronto:** [roteiro-de-area.md](roteiro-de-area.md)

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
| Testes | 815, com 55 falhando, nenhuma falha nova. Specs da área: 150/150 |
| Smoke (mock) | 29 rotas, sem erro de página |
| Prints | cabeçalho da tabela e controle segmentado no celular conferidos depois das correções da 04 |

Não deu para exercitar com dados, porque o mock não tem condomínios:
cadastro, edição, ações em lote e exportação. Esses fluxos ficam cobertos
pelos specs e precisam ser conferidos na sandbox.
