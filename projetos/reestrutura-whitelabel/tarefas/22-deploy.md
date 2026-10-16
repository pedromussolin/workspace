# 22 — Deploy da reestruturação

- **TS:** a criar · **Branch:** `release/AAAAMMDD` (front e BFF)
- **Status:** a planejar (pedido de 16/10). É a última tarefa do épico.
- **Depende de:** todas as outras (01 a 21, menos a 16)

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
   - inventário dos **nomes** que o código lê × os que cada ambiente tem.
3. **Normalizar roles e grupos do Azure**, a partir do catálogo do BFF
   (19/21):
   - criar as roles novas (`api-docs:read`, `design-system:read`,
     `access-control:read/write` e as da 21);
   - reatribuir;
   - tirar as que sobram.
4. **Release:** criar a `release/AAAAMMDD`, subir para o ambiente, validar e
   fazer a GMUD de produção (skill `criando-gmud`).

## Segredos: rodar os scripts do Pietro sem ler os valores

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
   leia `$PRIV/env/`, exceto o wrapper.
3. **Gravar:**
   - valor que não é segredo (ex.: `ENVIRONMENT=sandbox`): eu passo para o
     script;
   - segredo: o Pietro digita no próprio terminal (`! comando`) ou num
     arquivo que só ele edita.

## Decisões a tomar

| # | Decisão | Opções | Recomendação |
|---|---|---|---|
| D34 | Ambientes | (a) sandbox, validação com login real e, depois, produção com GMUD; (b) só sandbox agora | (a), em duas etapas |
| D35 | Valores visíveis | (a) nenhum; (b) só a lista aprovada de chaves que não são segredo | (b) |
| D36 | Trava com hook | (a) sim; (b) só o wrapper | (a) |
| D37 | Normalização no Azure | (a) pela tela da 19, se as permissões do Graph (D18) já tiverem saído; (b) pela CLI do Azure, com o login do Pietro | (a), com (b) como plano B |
