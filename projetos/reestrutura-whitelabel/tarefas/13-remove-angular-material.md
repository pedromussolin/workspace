# 13 — Remove Angular Material

- **TS:** TS-5370 · **Branch:** `chore/TS-5370-remove-angular-material` (da `origin/master`, depois do merge de 01–12)
- **Status:** a iniciar
- **Depende de:** 01–12

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
