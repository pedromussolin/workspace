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
