# 03 — Componentes: ícones, botões e formulário

- **TS:** TS-5360 · **Branch:** `feature/TS-5360-componentes-formulario` (da 02)
- **Status:** commits feitos, sem push (11/10)
- **Depende de:** 02. D6 decidida: datepicker próprio sobre o CDK.

## Escopo

| Novo (`shared/ui`) | Substitui | Componentes atuais reescritos em cima dele |
|---|---|---|
| `app-icon` + registro dos 148 SVGs ([anexos/icones](../anexos/icones/)) | `mat-icon` | todos |
| `app-button`, `app-icon-button` | `mat-button`, `mat-icon-button` | `components/button` |
| `app-field` + estilos de `input`/`textarea` | `mat-form-field`, `matInput` | `text-input`, `textbox`, `forms/*` |
| `app-select`, `app-multiselect`, `app-combobox` | `mat-select`, `mat-autocomplete` | `select`, `select-list`, `multiselect`, `combobox` |
| `app-checkbox`, `app-radio`, `app-toggle-group` | `mat-checkbox`, `mat-radio`, `mat-button-toggle` | `button-toggle` |
| `app-date-picker` | `mat-datepicker` + `material-moment-adapter` | `date-picker` |
| `app-file-chip` | — | `file-chip` |

Inventário (`d0bc3de`): 51 arquivos, 106 cores fixas, 57 `::ng-deep` e 12
specs.

## Regras

- **Entradas e saídas iguais** às dos componentes atuais. As telas não mudam
  nesta tarefa. Onde um nome era ruim, o antigo fica como alias até a 13.
- `app-icon`:
  - `name: IconName` (tipo fechado);
  - tamanho por `size` ou pelo `font-size` do pai;
  - `aria-hidden` por padrão, e `label` quando o ícone for o único conteúdo
    de um botão.
- Formulário: compatível com `ReactiveForms` (`ControlValueAccessor`),
  estados de `disabled`, erro e foco visível, com navegação por teclado.

## Validação

- Specs atuais dos componentes passando. Specs novos para teclado e
  `ControlValueAccessor` dos selects e do datepicker.
- Uma página interna de vitrine, só em dev, mostrando cada componente em
  claro e escuro.

## O que foi feito (11/10/2026)

| Commit | O quê |
|---|---|
| `ec5bb22` chore | mixins de estilo para os componentes de shared/ui |
| `73cb7af` feat | app-icon com os 148 ícones próprios |
| `921beee` feat | botões appButton e appIconButton tom sobre tom |
| `f6f2698` feat | app-field e appInput com rótulo, ajuda e erro ligados |
| `47d33c1` feat | app-date-picker próprio sobre o overlay do CDK |
| `6b6ebf7` refact | date-picker sobre o app-date-picker, sem Material |
| `b828e62` feat | app-checkbox com estado misto, teclado e formulário |
| `c9946b3` feat | app-radio-group e app-radio com navegação pelas setas |
| `225ee67` feat | app-toggle-group, o controle segmentado do portal |
| `2605a19` refact | app-button-toggle-component sobre o app-toggle-group |
| `0f96da8` refact | app-button-component sobre appButton e appIconButton |
| `8daa70c` refact | app-file-chip-component com ícones próprios e tokens |
| `e32f5da` refact | app-text-input-component sobre app-field e appInput |
| `296eb3b` refact | app-textbox-component sem Material, com ícones e tokens |
| `c8588d2` refact | app-form-simulation sobre app-field, botões e ícones |
| `2546f8e` feat | id no rótulo do app-field para o aria-labelledby |
| `788be20` feat | select, multiselect, combobox e listbox próprios no CDK |
| `664d8d6` feat | estado de carregamento nos selects de shared/ui |
| `5a23ba0` refact | app-select-component sobre o app-select, sem Material |
| `273011e` refact | app-select-list-component sobre o app-listbox |
| `e0b31b1` refact | app-multiselect-component sobre o app-multiselect |
| `d937db8` refact | app-combobox-component sobre o app-combobox |

Os componentes de hoje (`components/<nome>`) continuam onde estão, agora
como adaptadores finos sobre `shared/ui`, com as mesmas entradas e saídas.
As telas trocam para os componentes de `shared/ui` nas tarefas de área, e a
13 apaga os adaptadores que sobrarem. Movê-los agora só geraria mudança de
import em dezenas de telas sem ganho.

Diferenças de comportamento (para a descrição da PR):
- Combobox (Usuários, Lotes de Cessão, Desempenho da Carteira): escolher de
  novo a opção já selecionada não dispara outra busca; texto digitado sem
  escolher uma opção volta para a opção selecionada ao fechar.
- Multiselect, combobox, select e select-list ignoram opções repetidas
  (mesma chave e texto).
- Visual: botões, campos, selects, datepicker, checkbox, radio e seletor de
  visão no padrão novo (tom sobre tom, tokens, Inter), nas telas que usam
  esses componentes.

### Validação

| Checagem | Resultado |
|---|---|
| `npm run build` | passa |
| `npm run lint` | 64 erros / 278 avisos (antes 71 / 285; nenhum novo) |
| Testes | 445 testes, 80 falhando. Nenhuma falha nova em relação à 02; 8 que falhavam passaram a passar (componentes reescritos) |
| Material nos componentes reescritos | só o `matTooltip` do `app-button-component`, que sai na 04 |

