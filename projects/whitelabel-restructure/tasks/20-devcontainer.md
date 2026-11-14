+++
card = "TS-5387"
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
# 20 — Devcontainer do front mais leve e confiável

- **TS:** TS-5387 · **Branch:** `chore/TS-5387-devcontainer` (da `origin/master`, com `--no-track`)
- **Status:** **commits feitos, sem push** (15/10)
- **Depende de:** nada. Não depende do épico e pode andar a qualquer momento.

## Por quê

Pedido do Pietro em 15/10. O devcontainer atual:
- demora para subir;
- várias vezes dá erro no Angular;
- não tem as extensões boas para programar em Angular.

A tarefa simplifica e deixa ele mais leve.

## Como está hoje (`origin/master`)

Arquivos: `.devcontainer/` (`devcontainer.json`, `Dockerfile`,
`docker-compose.yml`, `post_start.sh`, `.env`, `codex-config.toml`) e
`.vscode/` (`extensions.json`, `settings.json`, `tasks.json`, `launch.json`).

| Problema | Onde | Efeito |
|---|---|---|
| `npm ci` a cada criação do container | `postCreateCommand` | apaga e reinstala o `node_modules` inteiro, sem cache do npm: minutos a cada rebuild |
| `CHOKIDAR_USEPOLLING=true` | `docker-compose.yml` | o watcher varre os arquivos por polling: CPU alta e recompilação lenta. No WSL, com o código no disco Linux, o inotify nativo funciona |
| `@angular/cli@20.3.9` instalado global | `Dockerfile` | o `ng` global pode divergir do `@angular/cli` do projeto (`^20.3.9`, que sobe sozinho). É fonte de erro difícil de entender |
| `post_start.sh` grava no `~/.gitconfig` (`git config --global --add safe.directory`) | `post_start.sh` + `mounts` | o `~/.gitconfig` está montado **só leitura**, então o comando falha a cada subida |
| Healthcheck `["CMD", "curl", "-f", "http://localhost:4200", "\|\|", "exit", "1"]` | `docker-compose.yml` | na forma `CMD`, o `\|\|` vira argumento do `curl`; e o dev server nem sobe sozinho (`sleep infinity`). O container fica sempre "unhealthy" |
| Porta 4200 publicada duas vezes (`ports` no compose e `forwardPorts`) | compose + `devcontainer.json` | conflito quando a 4200 do host está ocupada |
| Sem Chrome no container | `Dockerfile` | `ng test` (Karma com `ChromeHeadless`) não roda dentro dele |
| `node:20-slim` sem versão fixa | `Dockerfile` | a versão do Node muda sozinha a cada build |
| Trecho do husky em `post_start.sh` | `post_start.sh` | código morto: o projeto não usa husky |

Extensões:
- **Atrapalham:** `ms-vscode.vscode-typescript-next` (TypeScript nightly,
  que briga com o TypeScript 5.9 do projeto e com o Angular Language
  Service) e `charliermarsh.ruff` (é de Python).
- **Ferramentas pessoais de IA no contêiner do projeto:** `openai.chatgpt` e
  o Copilot, além da variável `AZURE_OPENAI_API_KEY` e do
  `codex-config.toml`.
- **Erros no `.vscode/extensions.json`:**
  - recomenda Tailwind, que o projeto não usa;
  - o ESLint está com o id errado (`ms-vscode.vscode-eslint`; o certo é
    `dbaeumer.vscode-eslint`);
  - recomenda Docker e Remote Containers, que são extensões do host, não
    do contêiner.

## Proposta

**Um contêiner só, sem compose.** O `devcontainer.json` aponta direto para
o `Dockerfile`:
- a rede Docker externa compartilhada com o BFF entra por `runArgs`;
- `node_modules` e cache do npm ficam em volumes nomeados (`mounts`);
- o `initializeCommand` continua criando a rede se ela não existir.

**Imagem:**
- Node LTS com versão fixa (ex.: `node:22.x-bookworm-slim`), igual à do
  `.nvmrc` e ao `engines` do `package.json`;
- sem Angular CLI global: só `npx ng` e os scripts do `npm`;
- Chromium e as fontes no próprio `Dockerfile`, com `CHROME_BIN` definido,
  para o `ng test` rodar dentro do contêiner (serve também ao Playwright
  da 16);
- `git config --system --add safe.directory /workspace` no `Dockerfile`
  (não depende do `~/.gitconfig` do host).

**Subida rápida:**
- **`postCreateCommand`:** um script que só roda
  `npm ci --prefer-offline --no-audit --no-fund` quando o hash do
  `package-lock.json` muda, com uma marca guardada no volume do
  `node_modules`. Com o volume do `~/.npm`, até o `ci` reaproveita o cache.
- **Sem polling:** sai o `CHOKIDAR_USEPOLLING`. Se alguém abrir o repo pelo
  disco do Windows (`/mnt/c`), existe a tarefa "ng serve (polling)".
- **Limpeza:**
  - sai o healthcheck e o `restart`;
  - a porta é só o `forwardPorts`;
  - o `post_start.sh` fica só com o que serve (gerar o env, se ainda for
    usado), ou some.

**Extensões do projeto** (no `devcontainer.json` e no
`.vscode/extensions.json`, a mesma lista):
- Angular Language Service (`angular.ng-template`);
- ESLint (`dbaeumer.vscode-eslint`), Prettier (`esbenp.prettier-vscode`) e
  EditorConfig;
- Error Lens (`usernamehw.errorlens`) e Pretty TypeScript Errors
  (`yoavbls.pretty-ts-errors`);
- SCSS IntelliSense (`mrmlnc.vscode-scss`) e Path IntelliSense;
- GitLens e GitHub Pull Requests;
- Playwright (`ms-playwright.playwright`), para a 16.

As ferramentas de IA de cada pessoa ficam no
`dev.containers.defaultExtensions` do VS Code de cada um, e não no
projeto.

**`.vscode/settings.json`:**
- ESLint corrige ao salvar e o Prettier formata ao salvar (`.ts`, `.html`,
  `.scss`);
- o TypeScript usado é o do projeto;
- `files.watcherExclude` e `search.exclude` para `node_modules`,
  `.angular` e `dist`.

**`.vscode/tasks.json` e `launch.json`:** tarefas "ng serve", "ng test" e
"lint", e um debug do Chrome apontando para `localhost:4200`.

**README:** como abrir o projeto, como rodar contra o BFF da sandbox (com
o `bff-sandbox-proxy` do workspace) e como medir os tempos.

## Critério de pronto

- Medir antes e depois, numa máquina com WSL:
  - primeira abertura (build da imagem);
  - "Rebuild Container";
  - reabertura;
  - primeira compilação do `ng serve`;
  - recompilação ao salvar um arquivo.
- O `ng serve`, o `ng test` (ChromeHeadless) e o `ng lint` rodam dentro do
  contêiner sem passo manual.
- Nenhum erro no log de criação e de subida (`safe.directory`,
  healthcheck, porta).
- Formatar e corrigir ao salvar funcionam, e o Angular Language Service
  não reclama da versão do TypeScript.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D20 | Versão do Node | **Decidida em 15/10: (a) 22 LTS** | Conferir se a imagem de produção (`Dockerfile` da raiz) também sobe |
| D21 | Ferramentas de IA no contêiner (Copilot, ChatGPT, Codex, chave do Azure OpenAI) | **Decidida em 15/10: (a) saem do projeto** | — |
| D22 | O BFF entra na mesma tarefa | **Decidida em 15/10: (b), o BFF fica para outra tarefa** | — |

## O que foi feito (15/10/2026)

Branch `chore/TS-5387-devcontainer`, criada da `origin/master`
(`576957c`). São 8 commits, sem push. Só o front entrou (D22).

| Commit | O quê |
|---|---|
| `5c6b615` | cherry-pick do `9bcf7b7` da 01 (A21), para o `ng test` compilar |
| `bb9b878` | imagem `node:22.23.3-bookworm-slim`, igual no `.nvmrc` e no `engines`. Sem CLI global, com o `node_modules/.bin` no PATH. Entram o `chromium-headless-shell` e as fontes, com `CHROME_BIN`, o `safe.directory` no gitconfig do sistema e o `openssh-client` |
| `427236f` | um contêiner só, sem compose. A rede compartilhada com o BFF entra por `runArgs`, com o mesmo `initializeCommand`. `node_modules` num volume por workspace e cache do npm num volume próprio. A porta 4200 só no `forwardPorts`, e `init: true`. Saem o compose, o `.env`, o healthcheck e o `restart` |
| `b4f542e` | saem as ferramentas de IA pessoais (D21) |
| `13de9e1` | `install-dependencies.sh` no `postStartCommand`: o `npm ci --prefer-offline` só roda quando muda o hash do lock mais a versão do Node. Sem mudança, leva menos de 0,2 s. Sai o `post_start.sh` |
| `8313707` | Dockerfile de produção no Node 22.23.3. O build e o `/health` respondem |
| `3a7e22d` | `.vscode/`: ESLint e Prettier ao salvar; tarefas `ng serve`, `ng serve (polling)`, `ng test`, `ng build` e `lint`; debug do Chrome; extensões |
| `b8b9f15` | README do devcontainer. Na revisão, saiu o trecho que citava o proxy da sandbox, que não existe no repo da empresa |

**Tempos** (CLI do Dev Containers, WSL):

| Medida | Antes | Depois |
|---|---|---|
| Primeira criação | 92,6 s | 112,6 s (o Chromium do `ng test` pesa) |
| Recriação ("Rebuild Container") | 39,0 s | **8,1 a 8,8 s** |
| Reabertura | 4,6 s | **1,9 s** |
| Primeira compilação do `ng serve` | 14,9 s | 14,7 s |
| Recompilação ao salvar | 0,53 a 0,55 s | 0,52 a 0,54 s |
| Imagem | 683 MB | 1,25 GB (Chromium) |

- O ganho está na recriação, na reabertura e em não ter erro no log. A
  primeira criação ficou mais lenta por causa do Chromium que o `ng test`
  exige. O `headless-shell` economiza 200 MB e uns 35 s em relação ao
  `chromium` completo.
- O diagnóstico de polling não se confirmou. O Angular 20 vigia os arquivos
  com o watchpack, que não lê o `CHOKIDAR_USEPOLLING`. A variável não tinha
  efeito nenhum.

**Validação dentro do contêiner novo:**
- `ng test`: 250 testes, com as mesmas 96 falhas da master no host;
- `ng lint`: 73/288, igual;
- `ng serve` responde em 4200;
- nenhum erro no log de criação, recriação e reabertura.

**Mudanças visíveis para listar na PR** (só no ambiente de desenvolvimento):
- o `ng test` roda dentro do contêiner;
- some o erro do `.gitconfig` a cada subida;
- o contêiner deixa de ficar "unhealthy";
- a porta 4200 deixa de ser publicada no host;
- as extensões são outras;
- as tarefas do VS Code foram corrigidas (chamavam um `build-env.js` que
  não existe);
- o `ng` passa a ser o do projeto.

**Primeira vez depois do merge:**
1. `Dev Containers: Rebuild Container`.
2. Apagar o contêiner, o volume e as imagens do compose antigo.
3. Ferramentas de IA pessoais vão em `dev.containers.defaultExtensions` e
   nos dotfiles.
4. `THEME_KEY=<marca> npm start` (o `.env` saiu).
5. No host, `nvm use` lê o `.nvmrc`.

**Não exercitado:** só houve CLI, sem VS Code. Ficaram sem testar:
- instalação das extensões e formatar ao salvar;
- Angular Language Service;
- F5 e encaminhamento da porta;
- `/mnt/c` com polling;
- o BFF subido junto.

**Depois da revisão (16/10)**, dois commits a mais (total: 10):

| Commit | O quê |
|---|---|
| `d8cc3d60` | o proxy da sandbox vai para `scripts/bff-sandbox-proxy.mjs` (`npm run bff:sandbox`), com o passo a passo no README. Os comentários estão em inglês, e a URL da sandbox vem do `TARGET`, sem ficar no código |
| `4a3e9bdd` | o `docker-compose.yml` da raiz fica só com o `angular-prod` (imagem de produção, sem profile, com `THEME_KEY` e `API_URL` por variável). Sai o `angular-dev` |

**Conferido:**
- o proxy avisa e sai sem `TARGET`;
- o `/__sessao` grava o cookie e redireciona para o front;
- quando a sandbox não responde, o proxy devolve 502 com a mensagem;
- `docker compose up --build` sobe a imagem: o `/health` responde 200 e o
  `env.js` sai com a API e a marca.

