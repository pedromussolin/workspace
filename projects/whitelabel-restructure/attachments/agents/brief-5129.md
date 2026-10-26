# TS-5129: pendências da Conciliação de registros na base nova (21/10)

Um dev fez, na estrutura antiga, a aba de **ativos pendentes** da Conciliação de registros
(`/cerc-reconciliation`): a lista dos ativos sem registro, o status de cada um consultado na
registradora, a busca página a página e a volta para a conciliação. A branch dele é
`origin/feat/TS-5129-visualizacao-de-pendencias`, no front e no BFF, e já foi buscada nos dois repos.

- **Ler um arquivo:** `git show origin/feat/TS-5129-visualizacao-de-pendencias:<caminho>`.
- **Ver o diff:**
  `git diff $(git merge-base origin/feat/TS-5129-visualizacao-de-pendencias origin/sandbox) origin/feat/TS-5129-visualizacao-de-pendencias -- <caminho>`.

**Decisão do Pietro:** é a mesma da TS-5193 ([brief](brief-5193.md)). O desenho e o comportamento
são os do dev, refeitos na base nova. A branch dele não é mergeada.

## Como portar

O porte segue o [roteiro das áreas](../../tasks/area-playbook.md): os passos 4 a 7, a "Regra
de ouro" e o "Pronto quando". Não é só trocar o visual.

- **Lógica:** sai do componente para modelo, regras e visão (`*.view.ts`, funções puras
  testáveis). O componente fica fino:
  - signals, `inject()`, `input()`/`output()`/`viewChild()` e OnPush;
  - `@if`/`@for` com `track`;
  - nenhum `subscribe` sem limpeza.
- **Estados e formatação:** carregando, vazio e erro vêm de `shared/ui`. Valor vazio, datas, moeda e
  percentual vêm de `shared/utils`.
- **Specs:** spec de comportamento em tudo que é novo, cobrindo os casos que o dev cobriu.

## Regras comuns

Valem as do `brief-release-21-10.md` (mesma pasta):
- sem commit;
- limitador `ng-slot` para comando pesado;
- rascunho em `~/repos/.reestrutura_whitelabel/agentes/<pacote>/`;
- prints em `~/repos/.reestrutura_whitelabel/evidencias/release-21-10/<pacote>/`;
- portas da sua faixa;
- relatório em PT-BR.

Leia o `CLAUDE.md` e a `.ai/` (front) ou o `README` (BFF) da worktree antes de começar.

## Pacote r5129-front

- **Worktree:** `~/repos/apl-credit-whitelabel-wt/5129`, branch `feature/TS-5129-pendencias-nova-arquitetura`, a
  partir da release.
- **Portas:** 4700 a 4709.
- **Onde está na release:** a página já foi refeita em `src/app/features/controllership/cerc-reconciliation/`
  (com `pending-registrations/`, `reconciliation-table/` e `cerc-reconciliation.view.ts`), e os dados ficam em
  `features/controllership/data-access/`.
- **Onde o dev mexeu:** na página antiga, `pages/controllership/cerc-reconciliation/`.
- **O que portar:** a aba nova e o comportamento dela, dentro da página da release.
- **`button-toggle`:** o dev mudou o componente antigo para acompanhar o valor externo. Na base nova, use o
  `app-toggle-group`. Se ele não atender, descreva no relatório e não mude o `shared/ui`.
- **Contrato:** é o do BFF do dev (`schemas.py` e `viewer.py` do módulo `cerc_reconciliation` na branch dele).
  O agente do BFF não muda o formato de sucesso. Se mudar, ele avisa.
- **Dados fictícios:** acrescente o necessário em `.ai/scripts/smoke-data/` (e em `MOCK_API_FILES`), para o
  smoke e o `start:mock` abrirem a aba com dados.

## Pacote r5129-bff

- **Worktree:** `~/repos/apl-credit-whitelabel-api-wt/5129`, branch `feature/TS-5129-pendencias-nova-arquitetura`,
  a partir da release.
- **O que portar:**
  - a rota de ativos pendentes e a consulta de status na registradora (serviço novo);
  - a paginação;
  - os nomes curtos dos fundos e a lista de fundos ampliada;
  - o pré-aquecimento do cache.
- **Modelo da release:**
  - **Permissão:** `require`/`require_any` e o catálogo de permissões. O escopo do parceiro (`get_partner_scope`,
    D100) vale onde a rota vizinha usa.
  - **Chamada externa:** pelo `create_outbound_client`.
  - **Erros:** pelo `error_from_response`.
  - **Logs:** em inglês, como eventos, com mensagem fixa e as dimensões no `extra`. Sem f-string e sem corpo de
    resposta no log.
- **Configuração nova (`CFG_CERC_*`):**
  - **Opcional:** o BFF precisa subir sem ela. Sem configuração, a consulta de status responde 503 com uma
    mensagem clara, e o resto da conciliação segue funcionando.
  - **Manifesto:** entra no do Parameter Store (`scripts/parameter-store/`), com o segredo como `SecureString`.
    O `test_parameter_store_manifest` precisa passar.
- **Pré-aquecimento:** o dev fez uma tarefa `asyncio` no `startup` (`on_event`, depreciado) que roda todo dia às
  5h30. Ela roda em cada réplica, e produção tem 3. No porte:
  - mantenha o comportamento;
  - use o `lifespan` (ou o que o app da release usa) no lugar do `on_event`;
  - use uma trava no Redis, para uma réplica só rodar por dia;
  - tire o horário e a ligação da tarefa do código e ponha na configuração, com o padrão do dev.

  Descreva o desenho no relatório: o Pietro decide se fica.
- **Testes:**
  - porte os testes do dev;
  - as 8 falhas conhecidas da suíte são de `controllership/cerc_reconciliation/test_business.py`. Veja se a
    branch do dev mexe nelas e diga no relatório o que as causa;
  - sem commit para corrigi-las.
