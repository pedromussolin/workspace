# 20 — Devcontainer do front mais leve e confiável

- **TS:** a criar · **Branch:** `chore/TS-?-devcontainer` (da `origin/master`, com `--no-track`)
- **Status:** a planejar (pedido de 15/10)
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
| D20 | Versão do Node | (a) 22 LTS; (b) continuar na 20 | (a). O Angular 20 suporta a 22, que tem suporte por mais tempo. Conferir se a imagem de produção (`Dockerfile` da raiz) também sobe |
| D21 | Ferramentas de IA no contêiner (Copilot, ChatGPT, Codex, chave do Azure OpenAI) | (a) saem do projeto e cada um configura as suas; (b) ficam como opcionais | (a). Deixa o contêiner menor e não força ferramenta nem chave em ninguém |
| D22 | O BFF entra na mesma tarefa | (a) sim, no mesmo padrão (ele tem os mesmos arquivos e o mesmo `safe.directory`); (b) depois | (a), numa branch própria no BFF, porque o padrão é o mesmo |
