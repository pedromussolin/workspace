# 24 — Deploy da reestruturação

- **TS:** TS-5394 · **Branch:** `release/AAAAMMDD` (front e BFF)
- **Status:** a iniciar quando 13 e 21 a 23 estiverem prontas (D40 a D43 decididas em 16/10). É a última tarefa do épico.
- **Depende de:** todas as outras (01 a 23, menos a 16)

## O que é

1. **Atualizar tudo com a master.** Juntar as branches do épico com o que
   tiver entrado na `master` até o dia. O que chegou nesse meio-tempo é
   levado para o padrão novo, como a 08 fez com o `e4e13a5`. Os conflitos
   conhecidos usam os scripts de `$PRIV/resolucoes/`.
2. **Normalizar as variáveis de ambiente**, nos repos de deploy (argocd) e
   nos segredos:
   - **front:** `ENVIRONMENT` (14), `API_URL`/`API_UPSTREAM` (a CSP da 18 tira
     a origem do BFF do `API_URL`) e `THEME_KEY`;
   - **BFF:** a configuração da atribuição a grupo (19) e as do Graph, se a
     escrita entrar;
   - **observabilidade (22):** as chaves do RUM no `env.js` do front
     (aplicação, client token, `env`, versão e amostragem);
   - inventário dos **nomes** que o código lê × os que cada ambiente tem.
3. **Liberar as permissões do Graph para o app do BFF** (D18). A lista e o
   porquê de cada uma estão na tarefa 19, em "O que foi feito: BFF".
   - Pedir à infraestrutura:
     - `Application.ReadWrite.OwnedBy`, `AppRoleAssignment.ReadWrite.All`,
       `Group.Create` e `GroupMember.ReadWrite.All`, com consentimento de
       admin;
     - pôr o service principal do BFF como dono do próprio app
       registration.
   - Proteger a credencial do app, de preferência com um certificado,
     porque a `AppRoleAssignment.ReadWrite.All` deixa o app dar privilégio
     a si mesmo.
   - Testar na sandbox, com o lote da 19:
     - as buscas;
     - criar role e grupo;
     - atribuir e remover;
     - apagar grupo do app sem a `Group.ReadWrite.All`. Se não der, decidir
       entre pedir essa permissão ou apagar grupo pelo portal do Azure.
   - Ligar a `CFG_ACCESS_CONTROL_GROUP_ASSIGNMENT_ENABLED` só depois de a
     infraestrutura confirmar a licença Entra ID P1/P2 (D17).
4. **Normalizar roles e grupos do Azure**, a partir do catálogo do BFF
   (19/21):
   - criar as roles novas (`api-docs:read`, `design-system:read`,
     `access-control:read/write` e as da 21);
   - reatribuir;
   - tirar as que sobram.
5. **Release:** criar a `release/AAAAMMDD`, subir para o ambiente, validar e
   fazer a GMUD de produção (skill `criando-gmud`).

## Segredos: rodar os scripts do Pietro sem ler os valores

**Onde estão:** em `~/bashes`. As variáveis ficam no AWS Systems Manager
Parameter Store:
- `list-parameter-store`, `diff-parameter-store`, `create-parameter-store`
  e `delete-parameter-store`;
- `params`, um arquivo de dados que deve ter parâmetros e valores. **Ninguém
  abre esse arquivo**, e ele entra na trava;
- fora do escopo: `generate-codeartifact-token`, `rot-crypt`,
  `clear-docker` e `hello-pietro`.

Em 16/10 só os nomes foram listados, sem abrir nem executar nada. O formato
da saída (para o wrapper) sai do código dos scripts `list` e `diff`, lido
depois de a trava estar ligada. Se o código tiver algum valor embutido, a
leitura passa por uma máscara.


Os scripts do Pietro leem e gravam variáveis de verdade. Para eu usá-los sem
ver valor nenhum:

1. **Wrapper próprio** (`anexos/scripts/env-sem-valor.sh`):
   - roda o script do Pietro com a saída inteira redirecionada para
     `$PRIV/env/<repo>-<ambiente>.raw` (permissão 600), sem passar pela
     tela;
   - imprime só o nome de cada variável, se está presente ou vazia, e se o
     valor é **igual ou diferente** entre ambientes, por classe (A, B, C…);
   - nem hash do valor aparece;
   - o valor só aparece para as chaves de uma lista aprovada pelo Pietro,
     que não são segredo (ex.: `THEME_KEY`, `ENVIRONMENT`, `PRODUCTION`).
2. **Trava:** um hook `PreToolUse` no Claude Code nega qualquer comando que
   leia `$PRIV/env/` ou o `~/bashes/params`, exceto o wrapper.
3. **Gravar:**
   - valor que não é segredo (ex.: `ENVIRONMENT=sandbox`): eu passo para o
     script;
   - segredo: o Pietro digita no próprio terminal (`! comando`) ou num
     arquivo que só ele edita.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D40 | Ambientes | (a) sandbox, validação com login real e, depois, produção com GMUD; (b) só sandbox agora | (a), em duas etapas |
| D41 | Valores visíveis | (a) nenhum; (b) só a lista aprovada de chaves que não são segredo | (b) |
| D42 | Trava com hook | (a) sim; (b) só o wrapper | (a) |
| D43 | Normalização no Azure | (a) pela tela da 19, depois do passo 3, que libera as permissões do Graph; (b) pela CLI do Azure, com o login do Pietro | (a), com (b) como plano B, se o consentimento atrasar |

## O que foi feito: release (16/10/2026)

Decisão do Pietro em 16/10: juntar tudo numa release agora, criar o
refinamento visual (25) a partir dela e subir no ambiente. A master não
andou desde a base do épico (front `576957c`, BFF `946dce3`).

**Front: `release/20261016`**, da `origin/master`, com um merge por tarefa,
sem push:

| Merge | Tarefa |
|---|---|
| `21bbe3c5` | 13 (com as áreas 01 a 15) |
| `78265657` | 17 |
| `a5d19b60` | 23 |
| `40deaff0` | 19 |
| `5a6f36dc` | 21 |
| `0005b5eb` | 18 (script de resolução) |
| `5bb1d0e9` | 20 (script) |
| `9f08ddb2` | 22 (script) |

- A árvore é igual à da junção validada (`f32dce27`). Só muda uma linha:
  o spec do erro sai da lista de legado do `check-patterns`.
- A validação completa da junção vale para ela: 2.213 testes, audit 0 e
  smoke em 9 rotas.
- `check-patterns` limpo e `tsc` 0.

**BFF: `release/20261016`**, da `origin/master`, sem push:

| Merge | Tarefa |
|---|---|
| `0368282` | 14 |
| `9f827bc` | 15 |
| `6669c9e` | 19 (script) |
| `f62ed98` | fix da 21 |
| `082f47d` | 21: a 14 e a 15 entram no catálogo |
| `65d07de` | 22 |

O que a junção do BFF pediu além do conflito de texto (scripts
`bff_feature_TS-5391-…` e `bff_feature_TS-5392-…` em `$PRIV/resolucoes/`):
- **21 × 14 e 15:**
  - a 21 tirou o `check_authorized_roles`, que a rota do OpenAPI da 14 usa,
    e ela quebraria na importação. Passou ao `require("api-docs", read)`;
  - os escopos `api-docs` e `design-system` entraram no catálogo, e as
    telas `/api-docs` e `/design-system` entraram na lista de rotas da 21;
  - os testes do fix da 21 ganharam a configuração que o `require` lê.
- **22 × 21 e fix:**
  - imports dos dois lados;
  - a indexação na Base de Conhecimento fica com a medição da 22 e o
    usuário que o fix passa;
  - o log de sucesso do PATCH sai;
  - os testes do fix trocam o transport observado da 22.
- **Resultado:** 955 testes, com as mesmas 8 falhas da base; ruff igual à
  master (9 avisos antigos).

**Refinamento:** `refact/TS-5395-refinamento-visual`, criada da release do
front.

**Subir na sandbox (só depois da validação local, D58):** pelo fluxo da empresa, uma cópia da release junta a
`origin/sandbox`. O teste (16/10) mostrou:
- **front:** conflito em 5 arquivos do fechamento de lotes. É a TS-5377
  (fechamento assíncrono do lote fake, 2 commits) e a TS-5211 (1 commit),
  que estão na sandbox e não na master. Elas foram escritas na estrutura
  antiga e precisam ser levadas à `features/liquidation-batches`, como a 08
  fez com o `e4e13a5`;
- **BFF:** conflito em 2 arquivos (`exceptions_handlers.py` e o viewer do
  pré-trade), da TS-5377 e da TS-5228.

## Migração das permissões (D59, 16/10)

Sem a transição, a ordem no deploy é:
1. sobe a release;
2. logo em seguida, alguém com `access-control:write` abre a aba Migração da
   tela da 19 e aplica o plano: cria as roles novas e copia as atribuições;
3. quem recebeu entra de novo no portal para a role chegar à sessão;
4. as roles antigas aparecem como "sem uso no código" na aba Permissões e
   são apagadas pela tela.

**Antes do deploy:**
- as permissões do Graph (passo 3), para a tela gravar;
- a **D56** (admins): sem a transição, quem só tem `admin:update` perde o
  dry run e o "Enviar agora", e quem tem `admin:read` perde o re-executar
  do orquestrador. A migração precisa dar `admin:test`, `admin:run`,
  `admin:approve` e `admin:reprocess` a quem for decidido;
- avisar as áreas da janela sem acesso entre os passos 1 e 3.
