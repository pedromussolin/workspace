# Prompts para continuar o épico (16/10)

Os prompts abaixo são para chats novos. Antes de colar, troque os campos
`<…>`. O contexto está no workspace e na memória; os prompts só dizem o que
fazer.

## Chat 1 — 5ª leva: 13 (com a passada de consistência), 18 e 20

```
Continuar o épico de refatoração do front (apl-credit-whitelabel).
Contexto em ~/repos/whitelabel-workspace: README (seção "Situação"),
decisoes.md, tarefas/roteiro-de-area.md (validação com os scripts) e
anexos/agentes/brief-comum.md (instruções dos agentes).

Próxima leva, em paralelo, com agentes Opus 5.5 em xhigh, modo completo:
- 13 Remove Angular Material (TS-5370), junto com a passada de
  consistência listada no README e os ajustes sugeridos pelas áreas
  (app-kpi, app-card, app-code-block, id do tooltip, app-search-field,
  app-switch na 07 e na 08, app-split-button na 08, kpi-grid em shared/ui,
  A14, A15, A18 dos logos no escuro, A19 do spec instável);
- 18 Segurança (<TS da 18>), da origin/master;
- 20 Devcontainer (<TS da 20>), da origin/master.

Base da 13: <"as branches 01–12, 14 e 15 já estão na sandbox: nasce da
origin/sandbox" OU "ainda não juntei: nasce do merge de teste local
(merge-teste.sh)">.

Decisões já tomadas (registre em decisoes.md):
- D13 (ícone more-vertical): <aprovado / outro ícone>;
- A13 (contraste da Dots e da Cerys): <...>;
- D20 (Node): <22 / 20>; D21 (IA fora do contêiner): <sim / não>;
  D22 (BFF entra na 20): <sim / não>.

Fluxo:
1. Antes de disparar, prepare as worktrees, os dados de smoke e tudo o que
   puder adiantar.
2. Na revisão, rode o validar-leva.sh e o merge-teste.sh (FULL=1) e olhe
   os prints.
3. Correção em peça comum fica num commit isolado, que eu levo para as
   outras branches.
4. Commits sem push; me entregue a lista exata de branches para publicar.
5. Documente cada tarefa no workspace (seção "O que foi feito").

Otimize o que puder no fluxo.
```

## Chat 2 — 6ª leva: 17 e 19 (fatia possível)

```
Continuar o épico de refatoração do front (apl-credit-whitelabel).
Contexto em ~/repos/whitelabel-workspace: README (seção "Situação"),
decisoes.md, tarefas/roteiro-de-area.md e anexos/agentes/brief-comum.md.

Próxima leva, com agentes Opus 5.5 em xhigh, modo completo:
- 17 Pasta .ai (<TS da 17>), que fecha depois da 13 (usa as regras de
  lint da 13). Confira no README se a 13 ficou pronta;
- 19 Controle de acesso pelo portal (<TS da 19>), front e BFF: a fatia 1
  (leitura: catálogo, pessoas, grupos e diferença entre código e Azure) e,
  se der, o lote (fatia 2) pronto no código, com o Graph falso nos testes.

Decisões da 19 (registre em decisoes.md):
- D16 (quem usa): <escopo próprio de escrita / admin:read>;
- D17 (atribuir a grupos): <licença P1/P2 confirmada / só pessoas / ainda
  não sei>;
- D18 (permissões de escrita no Graph): <pedidas à infra em DD/MM /
  ainda não>;
- D19 (remover pela tela): <só atribuições e membros / também roles e
  grupos>.

Se a 5ª leva deixou pendência no README, comece por ela.

Mesmo fluxo da leva anterior:
- revisão com o validar-leva.sh, o merge-teste.sh (FULL=1) e os prints;
- commits sem push, com a lista exata de branches para eu publicar;
- tudo documentado no workspace.
```

## Reserva — retomar um chat que acabou no meio

```
Continuar o épico de refatoração do front de onde o chat anterior parou.
Leia ~/repos/whitelabel-workspace (README "Situação", a tarefa em
andamento e roteiro-de-area.md) e confira o estado real antes de agir:
- git log e status das worktrees em ~/repos/apl-credit-whitelabel-wt/ e
  ~/repos/apl-credit-whitelabel-api-wt/;
- os logs em ~/repos/.reestrutura_whitelabel/logs/.
Agente que caiu: dispare um novo (Opus 5.5, xhigh) para terminar o que
ficou no working tree da worktree dele, com o brief comum. Depois siga o
fluxo de revisão, validação e documentação.
```
