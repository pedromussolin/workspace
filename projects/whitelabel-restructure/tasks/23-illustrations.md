# 23 — Ilustrações próprias

- **TS:** TS-5393 · **Branch:** `feature/TS-5393-ilustracoes` (da 13)
- **Status:** **commits feitos, sem push** (16/10)
- **Depende de:** 13 (tokens finais, tema claro/escuro e `shared/ui`)

## Por quê

Pedido do Pietro em 16/10:
- ter ilustrações próprias, como já temos ícones e componentes;
- alinhadas ao design atual e "menos infantis".

Hoje as ilustrações são de banco, com personagens e cores fixas. Elas não
seguem a marca nem o esquema escuro: a 13 só clareou a do 404 com filtro.

## Inventário (branch da 13)

| Arquivo | Onde | Fica? |
|---|---|---|
| `general/not-found.svg` | página 404 | **sai**: a 404 fica sem ilustração (D48) |
| `general/unauthorized.svg` | acesso negado | troca |
| `general/error.svg` | `shared/ui/error` (falha ao carregar) | troca |
| `general/empty_state.svg` | estado vazio das tabelas antigas (`config-table`) | troca |
| `general/uploading_files.svg` | área de upload do `textbox` (chat) | troca |
| `general/login-background.svg` | fundo do login | troca |
| `general/no-data.svg`, `general/welcome.svg`, `general/email-sent.png` | sem uso | **apagar** |
| `general/poli.svg` | robô do Poli Chat | fica: é a identidade do assistente (decidir à parte) |
| `general/openai.svg`, `general/microsoft.svg` | logos de terceiros | ficam |

O `app-empty-state` de `shared/ui` usa um ícone num círculo, e não uma
ilustração. A decisão D44 diz se ele ganha a ilustração.

## Proposta

1. **Direção visual:** uma página de comparação com três direções, cada uma
   com as mesmas cenas:
   - lista vazia;
   - busca sem resultado;
   - erro ao carregar;
   - acesso negado.

   A 404 fica de fora (D48).

   O Pietro escolhe a direção, como fez com os ícones. Fonte em
   `anexos/ilustracoes/` (`node build.mjs`).

   Proposta publicada em 16/10: https://claude.ai/artifact/6yYiWAnpGjYuJ5pumuCPZ9.
   Para republicar, publique o `proposta.html` gerado no mesmo artifact.
2. **Regras do conjunto:**
   - **Sem personagens:** nenhuma pessoa, mascote ou rosto.
   - **Formas da interface:** cartões, linhas de tabela, filtros, cadeado,
     sinal, documento, nos mesmos cantos e traço dos ícones (grade, traço
     1,75, pontas redondas).
   - **Cores só por variável CSS**, ligadas aos tokens: marca suave, marca,
     tinta, linha e superfície. Cada ilustração funciona nas quatro marcas e
     nos dois esquemas, sem `filter` e sem cor fixa.
   - **Sem texto dentro do SVG:** o texto fica no componente, traduzível.
   - **Leves:** cada uma com menos de 4 KB e o `viewBox` padronizado.
     Decorativas, com `aria-hidden`.
3. **Componente `app-illustration` em `shared/ui`:**
   - nome da ilustração tipado (como o `app-icon`), SVG inline e tamanho
     por input;
   - spec e página na vitrine (15), com todas as ilustrações nas quatro
     marcas e nos dois esquemas.
4. **Troca nas telas:** acesso negado, erro, estado vazio (o
   `app-empty-state` e as tabelas antigas), upload do chat e o visual do
   login. A 404 vira uma página simples, sem desenho (D48). Os três arquivos sem uso saem, e os assets antigos também, depois
   da troca.
5. **Regra nova na `.ai/`:**
   - ilustração nova nasce no conjunto e no `app-illustration`;
   - nada de imagem de banco;
   - o `check-patterns` acusa `<img src="assets/...svg">` fora dos logos.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D44 | Estado vazio comum | (a) o `app-empty-state` ganha a ilustração no lugar do ícone; (b) a ilustração só nas páginas inteiras (acesso negado e erro geral), e o vazio de lista continua com o ícone | (b): lista vazia aparece muito, e o ícone é mais discreto. A ilustração entra onde a tela inteira é o estado (acesso negado e erro geral) |
| D45 | Login | (a) uma composição própria de fundo (formas da marca, sutil); (b) fundo liso com o logo | (a) |
| D46 | Robô do Poli | (a) fica como está; (b) redesenhar no mesmo estilo | (a) nesta tarefa: é a identidade do assistente |
| D47 | Direção visual | **Decidida em 16/10: A, interface em camadas** | O conjunto final completa a A com as cenas que faltam: upload de arquivos e o visual do login |
| D48 | Página 404 | **Decidida em 16/10:** simples e sem ilustração, só com o código, o título "Página não encontrada", uma frase e o botão "Voltar para a Home" | Pietro: "a página 404 pode ser mais simples e não precisaria usar ilustração" |

## O que foi feito (16/10/2026)

Branch `feature/TS-5393-ilustracoes`, criada da 13 (`fd987f8c`). São 10
commits e 2 merges da 13, sem push:

| Commit | O quê |
|---|---|
| `ced90fe6` | token `--brand-accent`, a cor de destaque da marca (a secundária; na Cerys, a primária), num commit isolado |
| `11eacae5` | o `app-illustration` em `shared/ui/illustration/`: `name` tipado, `size` e `--illustration-size`, SVG inline com `aria-hidden` e as `--illu-*` ligadas aos tokens. Specs do componente e das regras do conjunto |
| `db1cba2c` | acesso negado com a ilustração; a 404 simples (D48) |
| `bb55f3a4` | erro de página inteira com a ilustração |
| `8bd258e1` | as tabelas antigas mostram o vazio no `app-empty-state`, com ícone |
| `668fca97` | upload do chat com a cena de envio de arquivo |
| `9cf19bfa` | login com a composição de fundo própria, nos dois esquemas |
| `6d5abe04` | aba "Ilustrações" na vitrine, nas 4 marcas e nos 2 esquemas |
| `7532528a` | apaga 9 ilustrações de banco sem uso (cerca de 94 KB) |
| `e4a72239` | merge da 13 final: os tokens `--brand-icon` e `--brand-accent` e as abas Formatos e Ilustrações da vitrine juntos |
| `334b78c4` | spec da diretiva de prévia de tema da vitrine (`theme-preview.directive.spec.ts`) |
| `81cda192` | merge da 13 sem o `@angular/animations` (sem conflito) |

O commit da regra no `AGENTS.md` (`7ab840fc`) saiu da branch: a regra vai
para a `.ai/` da 17.

**Cenas:**

| Cena | Tamanho |
|---|---|
| `empty-list` | 1.688 B |
| `search-no-results` | 1.758 B |
| `load-error` | 1.891 B |
| `access-denied` | 1.699 B |
| `file-upload` (nova) | 2.106 B |
| `login-backdrop` (nova, 1440×900) | 2.509 B |

O gerador está em `anexos/ilustracoes/cenas-portal.mjs`.

**Mudanças visíveis para a PR:**
- **Acesso negado:** a cena nas cores da marca, e o título passa a
  "Acesso negado".
- **404:**
  - sem desenho, com o código grande na cor da marca;
  - "Página não encontrada" e uma frase só;
  - o botão "Voltar", que voltava no histórico, vira "Voltar para a Home",
    que vai para `/home`.
- **Erro de página:** a cena de erro e o título menor.
- **Tabelas antigas:** o vazio passa ao `app-empty-state` ("Nenhum
  resultado para sua busca.").
- **Upload do chat:** a cena de envio de arquivo.
- **Login:** composição de fundo própria, nas cores da marca, no claro e no
  escuro.

**Validação:**
- `validar-leva.sh` ok: build ok, lint 20/163, 1.876 testes, sem falha nova
  (o acordeão instável é o A27, que a 13 corrige);
- smoke sem sessão do login, claro e escuro, sem erro;
- prints conferidos nas 4 marcas.

**Para decidir (D57):** o login sempre mostra o logo da Poliedro, mas o fundo
segue a marca do deploy. Num deploy da Dots, o fundo fica laranja atrás do
logo da Poliedro.

**Na junção com a 17:**
- a regra das ilustrações já está na `.ai/` da 17 (`3966e04e`), e o
  `check-patterns` aceita o `bypassSecurityTrustHtml` do `app-illustration`
  (`f18d17f3`);
- o `--brand-accent` e o `--brand-icon` já estão juntos (`e4a72239`).

**Tom suave:** usa o `--tonal-bg` do sistema (12% no claro e 18% no escuro).
A proposta tinha 14% e 20%; ficou o do sistema, para a ilustração casar com
os chips e os destaques das telas.

