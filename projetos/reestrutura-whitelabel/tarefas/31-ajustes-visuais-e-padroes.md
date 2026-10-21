# 31 — Ajustes visuais e padrões de design (pós-deploy)

- **TS:** a criar · **Branch:** a criar, da `master` do front depois do deploy de 21/10
- **Status:** **aberta** (21/10): falta a lista de ajustes do Pietro
- **Depende de:** 24 (deploy de 21/10)

## Por quê

Pedido do Pietro em 21/10, depois do deploy:
- ajustes visuais que ele encontrou em produção;
- regras de design que deixem uma única forma de fazer cada coisa. Hoje há telas que resolvem o mesmo
  problema de jeitos diferentes. O primeiro exemplo dele é o carregando (skeleton).

## Parte A: ajustes apontados pelo Pietro

- (a receber)
- Pendentes da rodada de 21/10 na release ([24](24-deploy.md)):
  - a tabela de agendamentos não cabe a 1440 px com o menu aberto (faltam 195 px);
  - as colunas da visão "Por parceiro" não se alinham entre os grupos.

## Parte B: regras e padrões

**Carregando (21/10, na `master`).** A regra de componentes lista `app-skeleton` e `app-spinner`, mas não
diz quando usar cada um. Em `features/**/*.html`:

| Forma | Arquivos |
|---|---|
| `[loading]` da própria tabela (`app-table`) | 56 |
| `<app-skeleton>` | 43 |
| texto "Carregando" | 17 |
| `<app-spinner>` | 10 |
| skeleton próprio da feature (classe ou componente `*-skeleton`) | 9 |
| `<app-loading>` | 1 |

A fazer:
1. **Levantar** todos os padrões que divergem, não só o carregando: vazio, erro, cabeçalho de página,
   filtros, KPIs, modais, botões de ação e tabelas. Para cada um, as formas que existem e onde.
2. **Decidir** com o Pietro a forma certa de cada caso. Para o carregando, uma proposta:
   - conteúdo que vai aparecer: skeleton no formato final, para a tela não mudar de forma;
   - tabela: o carregando da própria `app-table`;
   - ação em andamento (botão, envio): spinner no próprio botão;
   - texto "Carregando" solto não é usado.
3. **Escrever** a regra no `.ai/rules/components.md` do front (quando usar cada um, não só qual existe) e
   no `design-system.md` daqui, com um exemplo na vitrine (`/design-system`).
4. **Barrar** a forma errada no `check-patterns`, com a lista de legado para o que ainda não foi trocado.
5. **Trocar** as telas, uma área por commit.

## Como validar

- `check-patterns` limpo, sem item novo na lista de legado.
- Prints de antes e depois em claro, escuro e celular.
- Build, lint e testes sem falha nova.
