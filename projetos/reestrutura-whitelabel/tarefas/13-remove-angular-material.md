# 13 — Remove Angular Material

- **TS:** TS-5370 · **Branch:** `chore/TS-5370-remove-angular-material`
- **Status:** em andamento (5ª leva, 15/10)
- **Depende de:** 01–12, 14 e 15

## Como está sendo feita (15/10)

- **Base `2dbb699`:** a 04 (com `e031e31`) mais o merge, nesta ordem, da
  14, da 15 e das áreas 05 a 12.
  - Cada merge é um commit `chore(TS-5370): junta a NN (...)`.
  - A 08 entra já com a master (`dabea02`).
  - O conflito conhecido da 11 com a 10 usa a resolução de sempre.
- **Números da base:**
  - build ok, com bundle inicial de 587,87 kB (156,06 kB na rede);
  - lint com 20 erros e 166 avisos;
  - 1.822 testes, com 1 falha ("App should render title").
- **Duas metades em paralelo, com fronteira de arquivos:**
  - **13a**, na própria branch: tira o Material e as bibliotecas, migra ou
    apaga as sobras de `components/`, `interfaces/` e `constants/`, cuida
    da configuração, das variáveis antigas, do seletor de tema, do A13, do
    A18, do lint e da documentação no repo;
  - **13b**, em `wip/TS-5370-consistencia`: faz a passada de consistência,
    com `app-kpi`, `app-card`, `app-code-block`, id do tooltip, A19,
    `app-search-field`, `kpi-grid`, Formalização, Report Transfer, A14, A15
    e o "baixar imagem" no `app-chart`.
  - Cada ajuste em peça comum fica num commit isolado.
  - No fim, os commits da 13b entram por cima da 13a.

## Escopo

1. Remover `@angular/material`, `@angular/material-moment-adapter`, `ngx-skeleton-loader`, `apexcharts` e `ng-apexcharts` (D10; a 09 já tira o script do `angular.json`) do
   `package.json` e do lockfile. O `@angular/cdk` fica. Avaliar se o
   `moment` ainda é usado fora do adapter.
2. Remover o `azure-blue.css` do `angular.json`, os `<link>` das fontes
   Material Icons e Material Symbols do `index.html` e os overrides
   `.mat-*` de `styles.scss`.
3. Apagar o `<app-layout>` antigo, as variáveis CSS antigas
   (`--color-primary`...) e os aliases de entradas mantidos na 03.
4. **Ligar o seletor Claro / Escuro / Sistema no menu do usuário.**
5. Lint:
   - `no-restricted-imports` para `@angular/material` e para imports entre
     features;
   - uma checagem que barra cor hex nova em `.scss` fora de
     `styles/_tokens.scss`.
6. Documentação no repo: `docs/architecture.md` (estrutura, regras de
   dependência, rotas, tokens, como criar uma feature nova) e `AGENTS.md`
   (regras estáveis para quem mexer no repo).

## Validação

- `grep -r "@angular/material\|mat-icon\|material-icons" src` sem resultado.
- Build de produção: comparar o tamanho do bundle inicial com o baseline da 01.
- Volta completa no navegador: todas as rotas, em Poliedro e Dots, claro e
  escuro, e no celular.

- Ao tirar `azure-blue.css` do `angular.json`, incluir `@angular/cdk/overlay-prebuilt.css` (diálogo, menu e tooltip próprios usam o overlay do CDK).
