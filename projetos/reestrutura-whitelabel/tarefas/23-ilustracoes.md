# 23 — Ilustrações próprias

- **TS:** a criar · **Branch:** `feature/TS-?-ilustracoes` (da 13)
- **Status:** a planejar (pedido de 16/10). Primeiro passo: a proposta visual,
  para escolher a direção.
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
| `general/not-found.svg` | página 404 | troca |
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
   - página não encontrada;
   - acesso negado.

   O Pietro escolhe a direção, como fez com os ícones. Fonte em
   `anexos/ilustracoes/`.
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
4. **Troca nas telas:** 404, acesso negado, erro, estado vazio (o
   `app-empty-state` e as tabelas antigas), upload do chat e o visual do
   login. Os três arquivos sem uso saem, e os assets antigos também, depois
   da troca.
5. **Regra nova na `.ai/`:**
   - ilustração nova nasce no conjunto e no `app-illustration`;
   - nada de imagem de banco;
   - o `check-patterns` acusa `<img src="assets/...svg">` fora dos logos.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D44 | Estado vazio comum | (a) o `app-empty-state` ganha a ilustração no lugar do ícone; (b) a ilustração só nas páginas inteiras (404, acesso negado e erro geral), e o vazio de lista continua com o ícone | (b): lista vazia aparece muito, e o ícone é mais discreto. A ilustração entra onde a tela inteira é o estado |
| D45 | Login | (a) uma composição própria de fundo (formas da marca, sutil); (b) fundo liso com o logo | (a) |
| D46 | Robô do Poli | (a) fica como está; (b) redesenhar no mesmo estilo | (a) nesta tarefa: é a identidade do assistente |
| D47 | Direção visual | escolher na página de comparação | — |
