+++
card = "TS-5624"
type = "feature"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# TS-5624: tela de configuração do produto (Cessão e Liquidação) — plano de implementação

> Para quem executa: usar superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Passos com checkbox (`- [ ]`).
> Card ainda sem número: trocar `TS-5624` pelo ID quando o card existir (branches, commits, listas
> `PENDING`/`INTERNAL_ONLY` do BFF).

**Objetivo:** uma página nova do portal, "Configuração do produto", com as abas Cessão e Liquidação
(cada uma com escopo próprio), que lê e grava no `produto_config` da cessão, nos horários de
fechamento do produto (jobs do scheduler) e no modo de conciliação por fundo, sem mão no banco.

**Arquitetura:** o front (Angular) chama um módulo novo do BFF (`src/modules/product_settings`, FastAPI),
que traduz para as rotas da cessão (`GET /fundo/produtos`, `GET /cadastro/produto?id=`,
`PATCH /produto/<id>/` e `GET`/`PUT /liquidacao/fechamento-por-horario/<produto_id>`, da TS-5570, por
cima do scheduler da TS-5569). O front só pergunta ao BFF as ações do escopo
(`GET /iam/actions?scope=`); papéis ficam no BFF e no Azure. Toda regra de negócio (ligar horário só
com gatilho `agendado`, aviso de horário depois do corte) fica na cessão; o BFF mapeia nomes e o front
exibe. **Não há regra de combinação entre gatilho e agrupamento (D36, 10/11):** qualquer par é aceito
e o acúmulo (lote aberto) vale em qualquer caso, então a tela **não** oferece "acumula sim/não"
(`acumula_liquidacoes` e `modalidade_fechamento_lote` não são lidos nem gravados; a Fase 1 da TS-5567
guarda `acumula_liquidacoes` só como portão de transição, e a TS-5612 o apaga).

**Stack:** platform-cessao (Flask + flask-restx, SQLAlchemy 1.3, Python 3.8, PT-BR);
apl-credit-whitelabel-api (FastAPI 0.133, pydantic 2.12, pytest; inglês; `test_arch*`);
apl-credit-whitelabel (Angular com signals, componentes próprios em `shared/ui`, Karma/Jasmine;
inglês).
**Desenho:** ~/repos/.artemis_v2/agentes/ts13-spec/spec-fechamento-lotes.md (seção 4.14; também
4.3, 4.5, 4.6)
**Branches** (uma por repo, da master, `git switch --no-track -c ...`):
`feature/TS-5624-config-produto-api` (cessão), `feature/TS-5624-product-settings-bff` (BFF),
`feature/TS-5624-product-settings-page` (front). Uma PR por repo.
**Depende de:** TS-5583 (colunas `gatilho_fechamento_lote_liquidacao` e `agrupamento_lote_liquidacao`
nos schemas, branch `feature/TS-5583-gatilho-agrupamento-lote-liquidacao`) e TS-5569 (scheduler em
tabela, branch `feature/TS-5569-scheduler-em-tabela`) mergeadas; **TS-5570** (rotas
`GET`/`PUT /liquidacao/fechamento-por-horario/<produto_id>`, plano `tasks/13-plan-ts-5570.md`,
Tarefas 3 e 4) mergeada, com o pedido da D2 (campo `horario_corte` na resposta).

Linhas de código abaixo valem para `origin/master`: platform-cessao `c041122eb` (o plano dizia
`6c152445d`; conferido em 10/11), BFF `6472fb1` (era `f0511cb`), front `8e3699ad`. Os arquivos que as
TS-5583, TS-5569 e TS-5570 tocam mudam de linha: localizar pelo nome.

## Decisões em aberto

- **D30 — onde fica a tela (decidida em 10/11, Pietro).** Página nova `/product-settings`, com as
  abas Cessão e Liquidação, cada uma com o seu escopo; as telas de lotes não crescem. A alternativa
  "aba em cada tela de lotes" foi descartada e saiu do plano.
- **D1 — quais campos do `produto_config` são "configuração de cessão".** O `produto_config` tem 54
  colunas (`models.py:1283-1560`, contadas em `c041122eb`) misturando cessão, liquidação, cálculo, renegociação e cobrança.
  Opções: (i) só os campos do fluxo de cessão (20, lista na Tarefa 5); (ii) tudo que não é
  liquidação. **Recomendação: (i)**; cálculo (`base_dias`, `tipo_juros_vp`, `calcular_vp_curva`,
  `tipo_calculo`, `calcula_valor_aberto`, `taxa_fixa`, `calcular_taxa_operacao`, `discount_tax`),
  renegociação (`aceita_renegociacao`, `padrao_renegociacao`, `padrao_aditamento`) e cobrança
  (`emissor_boleto`, `tipo_cobranca`, `bucket`, `carencia_retencao_dias`, `originador_as_recebedor`)
  ficam para a área administrativa, por rota até lá.
- **D2 — quem entrega a rota de horários de fechamento por produto (resolvida pelo plano da
  TS-5570).** A TS-5570 entrega `GET`/`PUT /liquidacao/fechamento-por-horario/<produto_id>`
  (`tasks/13-plan-ts-5570.md`, Tarefas 3 e 4): **um agendamento por produto**
  (`liquidacao.fechamento_lote_produto_<produto_id>`) com vários horários, `ativo` único, `avisos` em
  texto e `solicitado_por` obrigatório (oid do Azure). O contrato que este plano tinha (um job por
  horário, `ativo` por horário, aviso estruturado) **não vale mais**; a Tarefa 3 virou conferência e
  o BFF e o front seguem o contrato da TS-5570. **Pedido à TS-5570** (cabe nela, uma linha no
  serviço e na rota): `horario_corte` (`"HH:MM"`, de `horario_corte()`) em `GET` e `PUT`; sem ele o
  front não avisa antes de salvar e o aviso pós-gravação não diz o corte (ver "Para decisão" 2).
  O e-mail do aviso (4.6) fica fora dos dois: é da TS-5585 (D27).
- **D3 — valores dos enums no contrato do BFF.** (i) manter os valores da cessão (`agendado`,
  `por_chave_sem_origem`, `automatica`), com rótulo PT-BR vindo do BFF; (ii) traduzir para inglês
  (`scheduled`) e destraduzir ao gravar. **Recomendação: (i)**, como o BFF já faz com os status de
  lote (`liquidation_batches/schemas.py:65-73`: `str` cru na resposta); um valor novo na cessão não
  derruba a resposta, e o nome do campo é em inglês. **O rótulo PT-BR fica no front**
  (`CLOSING_TRIGGER_LABELS` etc., conjuntos fechados): o BFF não manda `*_label`. O `LabeledEnum`
  só valida o pedido e documenta (`x-enum-labels`).
- **D4 — de onde vem a lista de produtos do seletor.** (i) `GET /cadastro/produto` sem `id`
  (`cadastro/viewer.py:41-55`): devolve **todos** os produtos já com config, acessos, emissores e
  originadores aninhados (`schema_cadastro_prod`), pesado para um seletor; (ii) o product-manager
  (`GET products/lookup`, BFF `modules/products/viewer.py:103`, `ProductLookupItem` do front): o id é
  do product-manager, não o da cessão que a tela grava; (iii) `GET /fundo/produtos` da cessão
  (`api/fundo/viewer.py:51`, já usado pelos lotes por `get_funds`, `src/services/platform_cessao/__init__.py:103`):
  fundos com a lista de `produtos`, ids da cessão, sem config. **Recomendação: (iii)**, achatando e
  deduplicando por `id` no business (`schema_produto_simple` já traz `id` e `nome`, `fundo/schema.py:4-13`).
  Limite: produto sem fundo vinculado não aparece; se isso importar, cai para (i). Mais de ~15
  produtos pedem `app-select` com busca (combobox).
- **D5 — campo de horário no front.** Não existe componente de hora (só `app-date-picker` e texto
  cron). (i) `input[appInput] type="time"` nativo; (ii) componente novo `app-time-input`.
  **Recomendação: (i)** (Chrome, Edge e Safari atuais rendem o controle nativo; `step="60"`), com
  validação `HH:MM` em função pura; o componente próprio entra se o nativo ficar feio na vitrine.
- **D6 — posição no menu.** Grupo "Operações", abaixo de "Lotes de Liquidação"
  (`navigation.ts:61-71`), ou grupo de administração junto de "Produtos" (`navigation.ts:119`).
  **Recomendação:** "Operações" agora (quem configura é quem opera os lotes); muda de grupo quando a
  área administrativa nascer.

## Restrições globais

- Produto novo nasce seguro (decisão de 08/11, TS-5583): gatilho `manual`, agrupamento `por_chave`; a
  tela não tem "padrão" próprio, exibe o que a cessão devolve.
- Valores aceitos: gatilho `manual | agendado | automatico`; agrupamento
  `por_chave | por_chave_sem_origem | por_remessa`; conciliação `nao_aplica | automatica | manual`.
- Horário em Brasília, `"HH:MM"`, no banco e no contrato; conversão para UTC só no scheduler.
- Corte da conciliação lido de `horario_corte()` (`cessao/shared/saldo_liquidacao/corte.py:58`;
  padrão 14:00, do Parameter Store; a TS-5570 não muda isso, o agendamento do corte é de um card
  futuro).
- Aviso de horário depois do corte: **salva e avisa** (nunca recusa). A cessão devolve `avisos` como
  **lista de textos** (TS-5570, Tarefa 3, `AVISO_HORARIO_DEPOIS_DO_CORTE`); o BFF repassa como
  `warnings: list[str]`, sem código nem estrutura.
- Um agendamento por produto, `liquidacao.fechamento_lote_produto_<produto_id>`, com vários horários
  e um `ativo` só; tarefa `liquidacao.fechar_lotes_do_produto_por_horario`; `somente_dia_util=True`;
  `payload={"produto_id": <id>}` (TS-5570, "Restrições globais"). **A tela não cria nem apaga job:**
  grava a lista de horários e o `ativo`; o agendador nunca exclui, só desativa. Lista vazia é recusada
  pela cessão ("Informe ao menos um horário"): para desligar, `ativo=false` com os horários.
- **Ligar horários (`ativo=true`) exige o gatilho `agendado` já gravado** (TS-5570, decisão 3a; 400
  "Produto não está no gatilho agendado"). A tela segue a ordem: salvar o fechamento (gatilho) antes
  de ligar os horários; o switch "Ativo" fica desabilitado enquanto o gatilho **gravado** não é
  `agendado`. Gravar com `ativo=false` vale em qualquer gatilho.
- Quem pede vai como **oid do Azure** (`request.state.user.azure_id`, opcional na sessão: sem ele o
  BFF recusa a gravação com 403 e o motivo), nunca e-mail: o histórico da cessão e os logs não levam
  dado pessoal (mesma regra do fechar lote, `liquidation_batches/business.py:340-343`).
- **Sem acúmulo na tela (D34/D36):** nenhum controle, rótulo ou campo de `acumula_liquidacoes` nem
  de `modalidade_fechamento_lote`; o pedido de gravação manda só o par gatilho/agrupamento (a cessão
  da TS-5583 preserva o `acumula_liquidacoes` gravado, `closing_modality.py:68-100`). Não confundir
  com `acumula_contratos` (acumula contratos na mesma remessa, `proc_id`), que é campo de cessão e
  fica na aba Cessão.
- Enum de produto: o identificador que a tela lê e grava é o **nome** do membro (`.name`,
  `to_names()`): é o que o `PATCH /produto/<id>/` valida (`enum=...to_names()`). Onde valor e nome
  diferem (`certificadora`, `tipo_lastro`, `padrao_originador`) o `.value` não volta no PATCH.
- BFF: escopos `product-settings-assignment` e `product-settings-liquidation`, ações `read` e
  `update` (nunca `write`, `.ai/rules/permissions.md:22-25`); página `CONFIGURACAO-DO-PRODUTO`,
  prefixo `product-settings`; rotas só da organização interna (`internal_only`).
- BFF: nomes de teste em inglês sem as palavras de `PORTUGUESE_TEST_WORDS` (`tests/test_arch.py:220-251`);
  `HTTPException` só no viewer; log com mensagem fixa e `extra`. Rota interna: cada viewer define o
  próprio `internal_only(request)` com `require_internal_organization(user, INTERNAL_ONLY_DETAIL)`
  (`src/shared/business/internal_only.py`), como `collateral_checks/viewer.py:105`.
- Front: dado pessoal nunca na URL (LGPD): o link leva só `product` (id) e `tab`, nada digitado;
  formulários em cartões empilhados de largura total (se virarem grade, altura igual); tabela de
  fundos com os 10 primeiros e "ver mais" quando houver mais; HTTP só em `data-access/`; interfaces em snake_case iguais ao BFF, sem mapeador; cor só por
  token; `data-scheme` para o escuro; cabe em 390 px sem rolagem lateral; `aria-label` no
  `app-toggle-group`; `.page.spec.ts` com `expectNoAccessLock`/`expectActionButtonsLocked` e
  `writesOnlyFor(...)` (check `pagina-sem-trava-de-permissao`).
- Commits `feat|fix|test|chore(TS-5624): ...` (PT-BR, até 72 caracteres, sem Co-Authored-By);
  **todo commit sai só depois da revisão do usuário do card** (os passos dizem "Preparar o commit").
- Roles no Azure (`product-settings-assignment:read|update`, `product-settings-liquidation:read|update`)
  criadas antes do deploy do BFF (`.ai/rules/permissions.md:158-169` do BFF).

## Foco de revisão

1. **Forma real do `GET /cadastro/produto`.** `schema_config_prod` (`cadastro/schema.py:199-272`)
   marshala `tipo_registro`, `tipo_lastro`, `tipo_cobranca` e `tipo_juros_vp` sem `attribute`: a
   resposta sai `"EnumTipoRegistro.nao_aplica"`, não `"nao_aplica"`. **E o `.value` que os outros
   campos já usam não volta no PATCH** onde valor e nome diferem: `certificadora` sai
   `"ID Trust Certificadora Digital"` e o PATCH só aceita `idtrust`; `tipo_lastro` (o
   `EnumLastroValidacao` é definido duas vezes em `database/enum.py`, vale a segunda, linha 717) sai
   `"NAO_APLICA"` e o PATCH só aceita `nao_aplica`; `padrao_originador` idem para `mpmerchant`.
   Por isso a tela lê e grava o **nome** (`.name`) e as opções saem de `to_names()` (Tarefa 2; "Para
   decisão" 1). O fake do BFF copia a cessão real; se copiar o bug, o contrato passa e a tela quebra.
   Teste na Tarefa 2 (`test_campos_enum_da_config_saem_pelo_nome`) e no contrato da Tarefa 7
   (`test_assignment_settings_enum_fields_round_trip`).
2. **`PATCH /produto/<id>/` devolve JSON string e 400 genérico** (`produto/viewer.py:103-114`:
   `return "Dados atualizados com sucesso"`, `raise BadRequest(str(e))`). O BFF relê o produto depois
   de gravar e repassa o 400 com a mensagem (400 está em `STATUSES_PASSED_TO_CLIENT`,
   `shared/utils/errors.py:88`; `_extract_detail` lê `message`); o front mostra
   `apiErrorMessage(err, fallback)`. Teste na Tarefa 6 (`test_closing_update_passes_cessao_400_message_through`).
3. **Aviso não é erro.** Horário depois do corte grava e volta 200 com `warnings`; o front mostra
   `toast.success` e um `app-notice tone="warning"` persistente na aba, não `toast.error`. Teste na
   Tarefa 10 (`shows the cutoff warning after a successful save`).
4. **"Ver como" e parceiro.** Durante a simulação o BFF recusa escrita com 403 (`users.py:337-354`) e
   devolve só `read`; parceiro com `admin:*` recebe 403 pelo `internal_only`. O front esconde o
   "Salvar" sem `update` e mostra o motivo. Testes na Tarefa 6 (`test_partner_session_is_refused`) e
   na Tarefa 9 (`expectActionButtonsLocked`).
5. **Fundo sem par `produto_fundo`.** `_create_or_update_produto_fundos` (`produto/sevice.py:92-112`)
   **cria** o vínculo se o CNPJ não estiver ligado ao produto. O BFF só aceita `fund_id` que veio no
   `GET` do mesmo produto (404 `FundNotLinkedError` caso contrário). Teste na Tarefa 5
   (`test_reconciliation_update_refuses_a_fund_not_linked_to_the_product`).

## Mapa de arquivos

**platform-cessao** (`~/repos/platform-cessao`)
- Modificar `cessao/api/cadastro/schema.py:199-272` (`schema_config_prod`: 6 campos que faltam,
  `attribute=".name"` nos enums), `:316-338` (`fundoProduto`: `fundo_id`, `nome_fundo`).
- Modificar `cessao/api/produto/schema.py:33-98` (`schema_produto_config`: os mesmos 6 campos).
- Modificar `cessao/api/produto/viewer.py` (rota `GET /produto/config/opcoes`), `sevice.py`
  (`ProdutoService.opcoes_config()`).
- Horários de fechamento: **nada a criar aqui**; é da TS-5570 (`cessao/api/liquidacao/fechamento_por_horario.py`
  e as rotas em `viewer.py`). Este card só pede `horario_corte` na resposta (D2).
- Testes: `test/cadastro/test_schema.py`, `test/api/produto/test_viewer.py`.

**apl-credit-whitelabel-api** (`~/repos/apl-credit-whitelabel-api`)
- Criar `src/modules/product_settings/{__init__.py,viewer.py,business.py,repository.py,schemas.py}`
  (`./create_module.sh`).
- Modificar `src/services/platform_cessao/__init__.py` (`_put`, `_patch` e 5 métodos novos; a lista de produtos reaproveita `get_funds`),
  `src/shared/utils/permissions.py:133-742` (2 escopos), `src/modules/access_control/business/pages.py:44-196`
  (1 página), `src/shared/utils/constants.py:29-191` (1 tela), `src/delivery/api/__init__.py:36-66`
  (router; `_register_domain_routes`), `tests/test_arch_partner_scope.py:80` (`INTERNAL_ONLY_ROUTES`),
  `tests/snapshots/route_permissions.json` (foto), `local/upstreams/platform_cessao.py` e
  `local/seed/cessao.py` (fake), `.ai/rules/local.md:40-53` (tabela do fake).
- Testes: `tests/unit/modules/product_settings/test_{schemas,business,viewer}.py`,
  `tests/unit/services/test_platform_cessao_product_settings.py`,
  `tests/contract/test_product_settings.py`.

**apl-credit-whitelabel** (`~/repos/apl-credit-whitelabel`)
- Criar `src/app/features/product-settings/` (`product-settings.routes.ts`, `.page.{ts,html,scss,spec.ts}`,
  `.view.{ts,spec.ts}`, `product-settings.permissions.ts`,
  `data-access/product-settings.{service.ts,service.spec.ts,interface.ts}`,
  `liquidation-settings/` (`app-liquidation-settings` + `closing-schedules-editor/`),
  `assignment-settings/` (`app-assignment-settings`), `testing/product-settings.fake.ts`).
- Criar `src/app/core/http/mock-api/mock-api.product-settings.{ts,spec.ts}`.
- Modificar `src/app/app.routes.ts:62-69`, `src/app/layouts/app-shell/navigation.ts:61-71`,
  `src/app/core/config/page.constants.ts` (`PAGE_TITLES:9` e as descrições, `:42`), `src/app/core/http/mock-api/mock-api.reply.ts:23-56` e
  `:198-199`, `src/app/mock-api.fake-data.ts:35-80`.

---

### Tarefa 1: apresentar e aprovar a arquitetura

**Arquivos:** nenhum (proposta no chat, a partir deste plano)
**Interfaces:** Produz: as decisões que as Tarefas 2–12 assumem (D30 decidida; D1, D3–D6 e os itens de "Para
decisão do Pietro") e os contratos abaixo.

Levar ao Pietro, em uma mensagem:
1. D1, D3–D6 e os itens de "Para decisão do Pietro" (Revisão de 10/11), com a recomendação de cada um.
2. Contrato BFF ↔ front (uma tabela):

   | Rota do BFF | Escopo/ação | Cessão por trás |
   |---|---|---|
   | `GET /product-settings/products` | `read` de qualquer um dos dois escopos | `GET /fundo/produtos` (D4) |
   | `GET /product-settings/{product_id}/liquidation` | `product-settings-liquidation:read` | `GET /cadastro/produto?id=` + `GET /liquidacao/fechamento-por-horario/<id>` |
   | `PUT /product-settings/{product_id}/liquidation/closing` | `product-settings-liquidation:update` | `PATCH /produto/<id>/` (`produto_config` com o par) e releitura |
   | `PUT /product-settings/{product_id}/liquidation/closing-schedules` | `product-settings-liquidation:update` | `PUT /liquidacao/fechamento-por-horario/<id>` (corpo `horarios`, `ativo`, `solicitado_por`) |
   | `PUT /product-settings/{product_id}/liquidation/funds/{fund_id}` | `product-settings-liquidation:update` | `PATCH /produto/<id>/` (`produto_fundo`) e releitura |
   | `GET /product-settings/{product_id}/assignment` | `product-settings-assignment:read` | `GET /cadastro/produto?id=` + `GET /produto/config/opcoes` |
   | `PUT /product-settings/{product_id}/assignment` | `product-settings-assignment:update` | `PATCH /produto/<id>/` (`produto_config`) e releitura |

   Todas internas (`internal_only`), sem `get_partner_scope`.
3. Contrato de horários da TS-5570 (Tarefa 3, só conferência) e o pedido do `horario_corte`.
4. Camadas do BFF (viewer → business → repository → `PlatformCessaoManager`), escopos e página.

- [ ] Passo 1: enviar a proposta; registrar as respostas na seção "Decisões em aberto" deste
      arquivo (riscar a decisão e escrever a escolha).
- [ ] Passo 2: levar o pedido do `horario_corte` (D2) para o plano da TS-5570
      (`tasks/13-plan-ts-5570.md`, Tarefas 3 e 4) e conferir o resto do contrato na Tarefa 3 daqui.
- [ ] Passo 3: só então começar a Tarefa 2.

---

## platform-cessao

### Tarefa 2: schemas do produto completos para a tela e opções dos enums

**Arquivos:** Modificar `cessao/api/cadastro/schema.py:199-272` e `:316-338`,
`cessao/api/produto/schema.py:33-98`, `cessao/api/fields.py` (campo novo), `cessao/api/produto/viewer.py`
(rota nova), `cessao/api/produto/sevice.py` (método novo) / Teste `test/cadastro/test_schema.py`,
`test/api/produto/test_viewer.py`
**Interfaces:** Consome: TS-5583 Tarefa 4 (par já nos dois schemas: `cadastro/schema.py` e
`produto/schema.py` da branch). Produz:
- `GET /cadastro/produto?id=<id>` devolve, em `produto_config`, também os **6** campos da tela que
  hoje faltam: `compra_npl`, `endosso_contrato`, `lote_contrato_individual`,
  `tipo_processamento_externo_cessao`, `tipo_acao_fim_esteira`, `limite_contratos_por_envio`
  (`models.py:1379, 1489, 1524, 1530, 1535, 1548`). Os outros 4 que o plano antigo listava
  (`calcular_taxa_operacao`, `padrao_estorno`, `tipo_calculo`, `padrao_escrituracao`) **não entram**:
  não estão nos 20 campos da D1 e dois deles são de cálculo.
- **Todo campo enum dos 20 sai pelo nome** (`fields.String(enum=E.to_names(), attribute="<coluna>.name")`):
  os 5 novos enums, `tipo_registro`, `tipo_lastro` (hoje sem `attribute`: sai `"EnumTipoRegistro.x"`),
  e, se o Pietro aprovar ("Para decisão" 1), `certificadora` e `padrao_originador` (hoje `.value`,
  que não volta no PATCH). `tipo_cobranca` e `tipo_juros_vp` **não mudam** (cobrança e cálculo,
  fora da D1: não alterar contrato sem consumidor na tela). Em `fundos[]`: `fundo_id`
  (`fields.Integer(attribute="fundo.id", readonly=True)`) e `nome_fundo`
  (`fields.String(attribute="fundo.nome", readonly=True)`); `conciliacao_liquidacao` já sai
  (`cadastro/schema.py:329-332`).
- `PATCH /produto/<id>/` aceita, em `produto_config`, os mesmos 6 campos (`fields.Boolean`,
  `fields.String(enum=E.to_names(), required=False)`); `limite_contratos_por_envio` aceita `null`
  (sem limite) com um campo novo `NullableInteger` (`__schema_type__ = ["integer", "null"]`) em
  `cessao/api/fields.py`, no molde do `NullableString` que já existe lá: o `fields.Integer` puro
  recusa `null` em `validate=True` [H: conferir no Passo 2].
- `GET /produto/config/opcoes` → `{"<campo>": ["nome", ...]}` (**nomes**, `to_names()`) para os campos
  enum da tela (`endosso_contrato`, `tipo_processamento_externo_cessao`, `tipo_acao_fim_esteira`,
  `padrao_originador`, `certificadora`, `tipo_registro`, `tipo_lastro`) e para
  `gatilho_fechamento_lote_liquidacao`, `agrupamento_lote_liquidacao` e `conciliacao_liquidacao`
  (`EnumConciliacaoLiquidacao`). `ProdutoService.opcoes_config() -> dict` monta a partir de
  `ProdutoConfig.__table__.c[<campo>].type.enum_class.to_names()`; `conciliacao_liquidacao` vem de
  `ProdutoFundo.__table__`.

- [ ] Passo 1: testes que falham:
  ```python
  # test/cadastro/test_schema.py (helper marshal como em :15-19)
  def test_campos_enum_da_config_saem_pelo_nome():
      config = ProdutoConfig(tipo_registro=EnumTipoRegistro.nao_aplica,
                             endosso_contrato=EnumEndossoContrato.nao_aplica,
                             tipo_acao_fim_esteira=EnumTipoAcaoFimEsteiraCessao.nao_aplica,
                             tipo_lastro=EnumLastroValidacao.nao_aplica)
      response = marshal(config, schema_config_prod)
      assert response["tipo_registro"] == "nao_aplica"          # hoje "EnumTipoRegistro.nao_aplica"
      assert response["endosso_contrato"] == "nao_aplica"       # hoje ausente
      assert response["tipo_lastro"] == "nao_aplica"            # o valor seria "NAO_APLICA", que o PATCH recusa
      assert response["limite_contratos_por_envio"] is None
  def test_fundo_do_produto_sai_com_id_e_nome():
      fundo = Fundo(nome="FIDC TESTE", _cnpj="35820740000159"); fundo.id = 9
      response = marshal(ProdutoFundo(fundo=fundo), schema_cadastro_prod["fundos"].container.model)
      assert response["fundo_id"] == 9 and response["nome_fundo"] == "FIDC TESTE"
  # test/api/produto/test_viewer.py (padrão de :580-597: ProdutoService mockado)
  def test_patch_produto_aceita_campos_de_cessao_novos(mocker, test_client):
      # PATCH /produto/1/ {"produto_config": {"endosso_contrato": "nao_aplica",
      #   "limite_contratos_por_envio": None, "lote_contrato_individual": True}} → 200;
      # update_dados_produto chamado com o mesmo produto_config
  def test_patch_produto_recusa_enum_fora_dos_nomes(test_client):
      # {"produto_config": {"tipo_lastro": "NAO_APLICA"}} → 400 (o valor do enum não é nome)
  def test_get_opcoes_config_lista_nomes_dos_enums(test_client):
      res = test_client.get("/produto/config/opcoes", headers={"Authorization": FAKE_AUTH_UUID})
      assert res.status_code == 200
      assert res.json["gatilho_fechamento_lote_liquidacao"] == ["manual", "agendado", "automatico"]
      assert res.json["conciliacao_liquidacao"] == ["nao_aplica", "automatica", "manual"]
      assert "nao_aplica" in res.json["tipo_registro"] and "NAO_APLICA" not in res.json["tipo_lastro"]
  ```
- [ ] Passo 2: rodar (comando do BRIEF) `test/cadastro/test_schema.py test/api/produto/test_viewer.py`
      e ver falhar (`KeyError`, valor `"EnumTipoRegistro.nao_aplica"`, 404 na rota). Conferir também
      se `validate=True` recusa campo desconhecido dentro de `produto_config` (o restx não fecha
      `additionalProperties`; sem o schema novo o campo passaria sem validar o enum).
- [ ] Passo 3: implementar. Rota `@ns.route("/config/opcoes")` no mesmo `ns` (não há conflito com
      `/<int:produto_id>/`, que exige inteiro). `readonly=True` nos campos novos de `fundos[]` para o
      `POST /cadastro/produto` (validate=True) não exigi-los.
- [ ] Passo 4: rodar e ver passar; rodar também `test/cadastro/` e `test/api/produto/` inteiros.
- [ ] Passo 5: preparar os commits `feat(TS-5624): schemas do produto expõem campos de cessão pelo nome`
      e `feat(TS-5624): rota de opções dos enums do produto_config` (saem depois da revisão do
      usuário do card).

### Tarefa 3: conferir as rotas de horário de fechamento da TS-5570 (sem código novo aqui)

> A TS-5570 entrega a rota (D2). Esta tarefa só confere o contrato abaixo contra o código dela e leva
> o pedido do `horario_corte`; se divergir, o BFF (Tarefas 4 e 5) e o front (Tarefa 8) se ajustam, a
> cessão não ganha rota paralela.

**Arquivos:** nenhum (leitura de `cessao/api/liquidacao/fechamento_por_horario.py` e do `viewer.py`
da branch da TS-5570)
**Interfaces:** Consome (contrato da TS-5570, Tarefas 3 e 4 do plano dela):
- `GET /liquidacao/fechamento-por-horario/<int:produto_id>` → 200
  `{"produto_id", "gatilho", "agrupamento", "ativo", "chave", "expressoes_cron", "horarios": ["HH:MM"],
  "proxima_execucao_em", "ultima_execucao"}`; produto sem agendamento: `ativo false`, listas vazias,
  `chave null`; 404 produto inexistente.
- `PUT` mesma rota, corpo `{"horarios": ["HH:MM"], "ativo": bool, "solicitado_por": "<oid>"}` → 200
  com o mesmo formato mais `"avisos": [texto]`; 400 horário inválido, repetido, lista vazia ou
  `ativo` sem gatilho `agendado`; 404 produto; 409 conflito do agendador.
- **Pedido à TS-5570 (D2):** `horario_corte: "HH:MM"` (de `horario_corte()`) em `GET` e `PUT`. O
  `GET`/`PUT` só tem `horarios` (um conjunto por produto, `ativo` único): a tela mostra a lista e um
  switch, não "ativo por linha".

- [ ] Passo 1: abrir os dois arquivos da branch da TS-5570 (quando existir) e comparar campo a campo
      com a lista acima; registrar a divergência na seção "Revisão" e nos schemas da Tarefa 5.
- [ ] Passo 2: sem a TS-5570 mergeada, as Tarefas 4 a 11 seguem contra o fake (Tarefa 7), que copia
      este contrato; a Tarefa 12 só fecha depois da conferência com a rota real.

---

## apl-credit-whitelabel-api (BFF)

### Tarefa 4: escopos, página, tela e cliente da cessão

**Arquivos:** Modificar `src/shared/utils/permissions.py:133-742`,
`src/modules/access_control/business/pages.py:44-196`, `src/shared/utils/constants.py:29-191`,
`src/services/platform_cessao/__init__.py` / Teste `tests/unit/shared/utils/test_permissions.py`
(já existente, cobre catálogo e telas), `tests/unit/modules/access_control/test_pages.py`,
`tests/unit/services/test_platform_cessao_product_settings.py`
**Interfaces:** Produz:
- Catálogo: `PermissionScope("product-settings-assignment", "Configuração do produto (Cessão)",
  (ScopeAction(Policies.READ, "Vê a configuração de cessão do produto."),
  ScopeAction(Policies.UPDATE, "Altera a configuração de cessão do produto.")))` e
  `PermissionScope("product-settings-liquidation", "Configuração do produto (Liquidação)",
  (READ "Vê gatilho, agrupamento, horários de fechamento e conciliação por fundo.",
  UPDATE "Altera gatilho, agrupamento, horários de fechamento e conciliação por fundo."))`.
- `Page("CONFIGURACAO-DO-PRODUTO", "Configuração do produto",
  ("product-settings-assignment", "product-settings-liquidation"), prefix="product-settings")`.
- `_page("Configuração do produto", "/product-settings", "product-settings-assignment",
  "product-settings-liquidation")` em `FRONTEND_ROUTE_PERMISSIONS`.
- `PlatformCessaoManager._patch(endpoint, body=None)` e `_put(endpoint, body=None)`, iguais ao
  `_post` (`src/services/platform_cessao/__init__.py:67-92`: qualquer 2xx é sucesso e `resp.json()`;
  o PATCH do produto devolve uma string JSON, `"Dados atualizados com sucesso"`, que o `resp.json()`
  já lê) e:
  ```python
  async def get_product(self, product_id: int) -> dict | None        # GET /cadastro/produto?id=; lista vazia → None (o business levanta NotFoundError)
  async def get_product_config_options(self) -> dict                 # GET /produto/config/opcoes
  async def update_product(self, product_id: int, body: dict) -> None  # PATCH /produto/{id}/
  async def get_product_closing_schedules(self, product_id: int) -> dict         # GET /liquidacao/fechamento-por-horario/{id}
  async def replace_product_closing_schedules(self, product_id: int, body: dict) -> dict  # PUT ...
  ```
  A lista de produtos usa o `get_funds()` que já existe (`GET /fundo/produtos`, D4).

- [ ] Passo 1: testes que falham (`httpx.MockTransport`, como `tests/unit/services/test_platform_cessao_fake_batches.py`):
  ```python
  async def test_get_product_filters_by_id_and_unwraps_the_single_item()   # GET /cadastro/produto?id=713 → [ {...} ] → dict
  async def test_get_product_returns_none_when_the_list_is_empty()
  async def test_update_product_accepts_a_json_string_body()               # PATCH → 200 "Dados atualizados com sucesso"
  async def test_replace_closing_schedules_sends_the_put_body()
  ```
  E em `test_pages.py`/`test_permissions.py`: o catálogo e a página novos já são cobertos pelos
  testes genéricos (todo escopo em exatamente uma página; prefixo da página); só rodar.
- [ ] Passo 2: rodar `PYTHONPATH=. pytest -q tests/unit/services/test_platform_cessao_product_settings.py tests/unit/shared/utils/test_permissions.py tests/unit/modules/access_control` e ver falhar (`AttributeError`).
- [ ] Passo 3: implementar; `__all__` do serviço inalterado (classe e fábrica já exportadas).
- [ ] Passo 4: rodar e ver passar; `PYTHONPATH=. pytest -q tests/test_arch*.py` (o
      `test_arch_route_permissions` ainda não muda: sem rotas).
- [ ] Passo 5: preparar os commits `feat(TS-5624): escopos e página da configuração do produto` e
      `feat(TS-5624): cliente da cessão lê e grava a configuração do produto`.

### Tarefa 5: schemas e business do módulo `product_settings`

**Arquivos:** Criar `src/modules/product_settings/__init__.py` (vazio), `schemas.py`,
`business.py`, `repository.py` / Teste `tests/unit/modules/product_settings/test_schemas.py`,
`test_business.py`
**Interfaces:** Consome: Tarefa 4. Produz (`schemas.py`, pydantic v2, atributo em inglês, `alias`
com o nome da cessão, `populate_by_name=True`, resposta com `model_dump(by_alias=False)`; o enum `LabeledEnum` só nos
pedidos, `str` nas respostas):

```python
class ClosingTrigger(LabeledEnum):      # valores da cessão (D3)
    MANUAL = "manual", "Manual"
    SCHEDULED = "agendado", "Agendado (horários do produto)"
    AUTOMATIC = "automatico", "Automático (na chegada)"
class ClosingGrouping(LabeledEnum):
    BY_KEY = "por_chave", "Por chave (origem, produto, originador e fundo)"
    BY_KEY_WITHOUT_ORIGIN = "por_chave_sem_origem", "Por chave sem origem"
    BY_REMITTANCE = "por_remessa", "Por remessa (proc_id)"
class ReconciliationMode(LabeledEnum):
    NOT_APPLICABLE = "nao_aplica", "Não aplica"
    AUTOMATIC = "automatica", "Automática (corte)"
    MANUAL = "manual", "Manual"

class ProductOption(BaseModel): id: int; name: str = Field(alias="nome")   # de /fundo/produtos (D4)
class ClosingSettings(BaseModel):       # `str` na resposta (D3: valor novo da cessão não derruba a tela)
    trigger: str = Field(alias="gatilho_fechamento_lote_liquidacao")
    grouping: str = Field(alias="agrupamento_lote_liquidacao")
class ClosingSchedules(BaseModel):      # um agendamento por produto (TS-5570): vários horários, um `ativo`
    key: UUID | None = Field(default=None, alias="chave")
    times: list[str] = Field(default_factory=list, alias="horarios")
    active: bool = Field(default=False, alias="ativo")
    next_run_at: str | None = Field(default=None, alias="proxima_execucao_em")
    last_execution: dict | None = Field(default=None, alias="ultima_execucao")
class FundReconciliation(BaseModel):
    fund_id: int = Field(alias="fundo_id"); cnpj: str = Field(alias="cnpj_fundo"); name: str = Field(alias="nome_fundo")
    reconciliation_mode: str = Field(alias="conciliacao_liquidacao")
class LiquidationSettings(BaseModel):
    product: ProductOption; closing: ClosingSettings; schedules: ClosingSchedules
    cutoff_time: str | None = Field(default=None, alias="horario_corte")   # None até a TS-5570 entregar (D2)
    funds: list[FundReconciliation]
class ClosingSchedulesResponse(BaseModel):
    schedules: ClosingSchedules; cutoff_time: str | None = Field(default=None, alias="horario_corte")
    warnings: list[str] = Field(default_factory=list, alias="avisos")   # texto pronto da cessão
class AssignmentSettings(BaseModel):    # D1 (i): 20 campos; atributo → alias
    product: ProductOption
    assignment_batch_auto_close: bool = Field(alias="lote_cessao")
    assignment_file_auto_send: bool = Field(alias="cessao_automatico")
    accumulate_contracts_in_remittance: bool = Field(alias="acumula_contratos")
    single_contract_batch: bool = Field(alias="lote_contrato_individual")
    max_contracts_per_send: int | None = Field(alias="limite_contratos_por_envio")
    assignment_ftp_folder: str = Field(alias="cessao_ftp")
    business_day_due_dates: bool = Field(alias="vencimento_ajustado")
    buys_overdue_contracts: bool = Field(alias="compra_vencidos")
    buys_npl_contracts: bool = Field(alias="compra_npl")
    rejects_duplicate_contracts: bool = Field(alias="contratos_duplicados")
    manual_assignor_registration: bool = Field(alias="cadastro_cedente_manual")
    contract_endorsement: str = Field(alias="endosso_contrato")
    certifier: str | None = Field(alias="certificadora")
    registration_type: str = Field(alias="tipo_registro")
    auto_registration_settlement: bool = Field(alias="registro_baixa")
    collateral_validation: str = Field(alias="tipo_lastro")
    external_disbursement: bool = Field(alias="desembolso_externo")
    external_assignment_processing: str = Field(alias="tipo_processamento_externo_cessao")
    pipeline_end_action: str = Field(alias="tipo_acao_fim_esteira")
    originator_file_format: str = Field(alias="padrao_originador")
    options: dict[str, list[str]]       # só os campos enum acima, chave = atributo em inglês
# requests
class ClosingSettingsRequest(BaseModel): trigger: ClosingTrigger; grouping: ClosingGrouping
ClockTime = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
class ClosingSchedulesRequest(BaseModel): times: list[ClockTime] = Field(min_length=1, max_length=12); active: bool
class FundReconciliationRequest(BaseModel): reconciliation_mode: ReconciliationMode
class AssignmentSettingsRequest(BaseModel): # os 20 campos, todos Optional = None; model_config extra="forbid"
```
`business.py`:
```python
class ProductSettingsBusiness:
    def __init__(self, settings, repository: ProductSettingsRepository)
    async def list_products(self) -> list[ProductOption]
    async def get_liquidation_settings(self, product_id: int) -> LiquidationSettings
    async def update_closing(self, product_id: int, request: ClosingSettingsRequest) -> LiquidationSettings
    async def replace_closing_schedules(self, product_id: int, request: ClosingSchedulesRequest, requested_by: str) -> ClosingSchedulesResponse
    async def update_fund_reconciliation(self, product_id: int, fund_id: int, request: FundReconciliationRequest) -> LiquidationSettings
    async def get_assignment_settings(self, product_id: int) -> AssignmentSettings
    async def update_assignment(self, product_id: int, request: AssignmentSettingsRequest) -> AssignmentSettings
ASSIGNMENT_FIELD_ALIASES: dict[str, str]  # atributo → nome da cessão, derivado de AssignmentSettings.model_fields
```
Erros de domínio (`src/shared/utils/domain_errors.py`): `NotFoundError("Produto não encontrado.")`
quando `get_product` devolve `None`; `NotFoundError("Fundo não vinculado ao produto.")` quando o
`fund_id` não está em `fundos[]`. Horário repetido, lista vazia e `ativo` sem gatilho `agendado` são
da cessão (400 repassado, sem regra duplicada no BFF; o `min_length=1` do pedido só poupa a ida).
`repository.py`: um método por chamada do manager, `@require_attr("_platform_cessao_manager")`;
`list_products` do business monta a lista de `get_funds()` achatando `fundos[].produtos` por `id`.

- [ ] Passo 1: testes que falham:
  ```python
  # test_schemas.py
  def test_liquidation_settings_is_built_from_the_cessao_names()   # dict com alias → atributos em inglês; dump sem alias
  def test_closing_trigger_keeps_the_cessao_values_and_labels()     # ClosingTrigger("agendado").label == "Agendado (horários do produto)"
  def test_schedules_request_rejects_a_bad_clock_time()             # ["25:00"] → ValidationError
  def test_schedules_request_refuses_an_empty_list()
  def test_assignment_request_refuses_unknown_fields()
  # test_business.py (repository AsyncMock; GET do produto com fixture `cessao_product()` que copia a forma real da Tarefa 2)
  async def test_update_closing_sends_only_the_pair_and_rereads()   # update_product(713, {"produto_config": {"gatilho_fechamento_lote_liquidacao": "agendado", "agrupamento_lote_liquidacao": "por_chave_sem_origem"}}); depois get_product
  async def test_reconciliation_update_refuses_a_fund_not_linked_to_the_product()  # NotFoundError; update_product não chamado
  async def test_reconciliation_update_sends_the_fund_cnpj()        # {"produto_fundo": [{"cnpj_fundo": "...", "conciliacao_liquidacao": "automatica"}]}
  async def test_replace_schedules_passes_the_warning_texts()       # avisos ["Horário 16:00 fica ..."] → warnings igual; corpo da cessão {"horarios", "ativo", "solicitado_por"}
  async def test_replace_schedules_sends_the_oid_as_requester()     # requested_by (oid) vira solicitado_por
  async def test_assignment_update_translates_names_and_drops_unset_fields()  # {"max_contracts_per_send": None, "buys_npl_contracts": True} → {"produto_config": {"limite_contratos_por_envio": None, "compra_npl": True}}
  async def test_missing_product_raises_not_found()
  ```
- [ ] Passo 2: `PYTHONPATH=. pytest -q tests/unit/modules/product_settings` → `ModuleNotFoundError`.
- [ ] Passo 3: `./create_module.sh product_settings` e implementar; `options` da aba Cessão vem de
      `get_product_config_options()` filtrado pelos campos enum do schema e renomeado pelo alias.
- [ ] Passo 4: rodar e ver passar; `PYTHONPATH=. pytest -q tests/test_arch.py` (camadas, nomes em
      inglês, sem divisores).
- [ ] Passo 5: preparar o commit `feat(TS-5624): schemas e regras do módulo product_settings`.

### Tarefa 6: viewer, rotas internas e foto de permissões

**Arquivos:** Criar `src/modules/product_settings/viewer.py` / Modificar
`src/delivery/api/__init__.py:36-66`, `tests/test_arch_partner_scope.py:80` (`INTERNAL_ONLY_ROUTES`),
`tests/snapshots/route_permissions.json` / Teste `tests/unit/modules/product_settings/test_viewer.py`
**Interfaces:** Consome: Tarefa 5. Produz: `router = APIRouter(prefix="/product-settings",
tags=[Tags.OPERATIONS], dependencies=[Depends(internal_only)])`;
`@contextmanager def get_product_settings_business()`; `internal_only(request)` e `INTERNAL_ONLY_DETAIL`
próprios do viewer (usam `require_internal_organization`, ver "Restrições globais"); as 7 rotas da
Tarefa 1 (tabela), com
`require("product-settings-liquidation", Policies.READ|UPDATE)`, `require("product-settings-assignment", ...)`
e `require_any(("product-settings-assignment", READ), ("product-settings-liquidation", READ))` em
`GET /products`. `INTERNAL_ONLY_DETAIL = "A configuração do produto é só da organização interna."`
`requested_by` = `request.state.user.azure_id` (oid; `src/shared/schemas/users.py:44-53`, opcional),
como o fechar lote (`liquidation_batches/viewer.py:397`); sem `azure_id`, a rota de horários levanta
`HTTPException(403)` no viewer com o motivo (sessão antiga: entrar de novo).

- [ ] Passo 1: testes que falham (app próprio por teste e `route_access`, como
      `tests/unit/modules/operations/liquidation_batches/test_viewer_close.py:51-105`):
  ```python
  def test_each_route_requires_its_role()        # parametrizado: 7 rotas × role certa abre, role da outra aba nega, admin abre
  def test_partner_session_is_refused()          # OrgType parceiro com admin:update → 403
  def test_closing_update_passes_cessao_400_message_through()   # business levanta RemoteServiceError(400, "gatilho_fechamento_lote_liquidacao inválido, use um de [...]") → 400 com o detail
  def test_schedules_without_azure_id_are_refused()              # sessão sem azure_id → 403, cessão não chamada
  def test_schedules_response_carries_warnings()
  def test_products_list_opens_with_either_read()
  ```
- [ ] Passo 2: rodar e ver falhar (404/`ImportError`).
- [ ] Passo 3: implementar; incluir `router.include_router(product_settings_router)` no delivery;
      acrescentar as 7 rotas em `INTERNAL_ONLY_ROUTES` com a razão
      `"configuração do produto: só a organização interna (TS-5624)"`;
      `UPDATE_ROUTE_PERMISSIONS=1 PYTHONPATH=. pytest tests/test_arch_route_permissions.py`.
- [ ] Passo 4: `PYTHONPATH=. pytest -q tests/unit/modules/product_settings tests/test_arch*.py`
      verde (inclui `test_arch_internal_routes`, que chama cada rota interna como parceiro e exige
      403, e `test_arch_route_scopes`: URL `/product-settings` é o `/{prefix}` da página).
- [ ] Passo 5: preparar o commit `feat(TS-5624): rotas internas da configuração do produto`.

### Tarefa 7: fake da cessão e contratos

**Arquivos:** Modificar `local/upstreams/platform_cessao.py` (rotas `GET /cadastro/produto`,
`PATCH /produto/{id}/`, `GET /produto/config/opcoes`, `GET|PUT /liquidacao/fechamento-por-horario/{id}`, `GET /fundo/produtos`),
`local/seed/cessao.py` (produto_config completo e `fundos` com `conciliacao_liquidacao`),
`.ai/rules/local.md:40-53` / Criar `tests/contract/test_product_settings.py`
**Interfaces:** Consome: Tarefas 2, 3 (forma real da cessão), 6. Produz: o fake responde **com a
forma real** (enum pelo nome, PATCH devolvendo uma string JSON, horários como um conjunto por produto
com `ativo` único, 400 ao ligar sem gatilho `agendado`, `avisos` em texto quando algum horário ≥ `14:00`
e algum fundo `automatica`, `horario_corte` na resposta).

- [ ] Passo 1: testes que falham (`bff`, `login("admin")`, como `tests/contract/test_cessao.py`):
  ```python
  def test_liquidation_settings_round_trip()                 # GET → PUT closing (agendado/por_chave) → GET reflete
  def test_schedules_after_the_cutoff_are_saved_with_a_warning()   # PUT ["16:00"] ativo → 200, warnings[0] texto, GET lista 16:00 ativo
  def test_schedules_refuse_active_without_the_scheduled_trigger() # produto em manual + active=true → 400 com a mensagem da cessão
  def test_assignment_settings_enum_fields_round_trip()            # registration_type e collateral_validation em options[...], e o valor lido volta no PUT
  def test_partner_login_gets_403()                           # login("parceiro-dots")
  def test_read_only_role_cannot_update()                    # login("x", roles="product-settings-liquidation:read") → 403 no PUT
  ```
- [ ] Passo 2: `PYTHONPATH=. pytest -q tests/contract/test_product_settings.py` → 404 do fake.
- [ ] Passo 3: implementar o fake copiando a cessão em `origin/master` (depois da Tarefa 2/3).
- [ ] Passo 4: `PYTHONPATH=. pytest -q tests/unit/local tests/contract tests/test_arch_local.py` verde;
      atualizar a tabela do `local.md`.
- [ ] Passo 5: preparar o commit `test(TS-5624): fake da cessão e contratos da configuração do produto`.

---

## apl-credit-whitelabel (front)

### Tarefa 8: permissões, data-access, mock e rota

**Arquivos:** Criar `src/app/features/product-settings/product-settings.permissions.ts`,
`data-access/product-settings.interface.ts`, `data-access/product-settings.service.ts` (+`.spec.ts`),
`testing/product-settings.fake.ts`, `src/app/core/http/mock-api/mock-api.product-settings.ts`
(+`.spec.ts`), `product-settings.routes.ts` / Modificar `src/app/app.routes.ts:62-69`,
`src/app/layouts/app-shell/navigation.ts:61-71`, `src/app/core/config/page.constants.ts` (`PAGE_TITLES` e a
descrição da página), `src/app/core/http/mock-api/mock-api.reply.ts:23-56` e `:198-199`, `src/app/mock-api.fake-data.ts:35-80`
**Interfaces:** Produz:
```ts
// product-settings.permissions.ts
export const PRODUCT_SETTINGS_ASSIGNMENT_SCOPE = 'product-settings-assignment';
export const PRODUCT_SETTINGS_LIQUIDATION_SCOPE = 'product-settings-liquidation';
// product-settings.interface.ts — snake_case igual ao BFF (Tarefa 5)
export interface ProductOption { id: number; name: string }
export interface ClosingSettings { trigger: ClosingTrigger; grouping: ClosingGrouping }  // o BFF manda `string`; o front estreita
export type ClosingTrigger = 'manual' | 'agendado' | 'automatico';
export type ClosingGrouping = 'por_chave' | 'por_chave_sem_origem' | 'por_remessa';
export type ReconciliationMode = 'nao_aplica' | 'automatica' | 'manual';
export interface ClosingSchedules { key: string | null; times: string[]; active: boolean; next_run_at: string | null; last_execution: unknown | null }
export interface FundReconciliation { fund_id: number; cnpj: string; name: string; reconciliation_mode: ReconciliationMode }
export interface LiquidationSettings { product: ProductOption; closing: ClosingSettings; schedules: ClosingSchedules; cutoff_time: string | null; funds: FundReconciliation[] }
export interface ClosingSchedulesResponse { schedules: ClosingSchedules; cutoff_time: string | null; warnings: string[] }
export interface AssignmentSettings { product: ProductOption; /* 20 campos da Tarefa 5 */ options: Record<string, string[]> }
export type AssignmentSettingsPatch = Partial<Omit<AssignmentSettings, 'product' | 'options'>>;
// product-settings.service.ts (BaseApiService; BASE = 'product-settings')
listProducts(): Observable<ProductOption[]>
getLiquidationSettings(productId: number): Observable<LiquidationSettings>
updateClosing(productId: number, body: ClosingSettings): Observable<LiquidationSettings>
replaceClosingSchedules(productId: number, body: { times: string[]; active: boolean }): Observable<ClosingSchedulesResponse>
updateFundReconciliation(productId: number, fundId: number, body: { reconciliation_mode: ReconciliationMode }): Observable<LiquidationSettings>
getAssignmentSettings(productId: number): Observable<AssignmentSettings>
updateAssignment(productId: number, body: AssignmentSettingsPatch): Observable<AssignmentSettings>
```
Mock: `productSettingsFakeRoutes(fake): MockApiData` com `product-settings/products`,
`product-settings/<id>/liquidation` e `.../assignment` (3 produtos, um com fundo `automatica`, um com gatilho `manual`);
`productSettingsWrite` em `mock-api.product-settings.ts` responde os `PUT` (o de horários devolve
`warnings` em texto quando algum horário é `>= '14:00'` e há fundo `automatica`, e responde 400 ao
ligar `active` com o gatilho gravado diferente de `agendado`), chamado em `mock-api.reply.ts:198-199`
antes do genérico. Rota: `{ path: 'product-settings', canActivate: [iamGuard], loadChildren: ... }`;
`PAGE_TITLES.PRODUCT_SETTINGS = 'Configuração do produto'`; item `{ name: PAGE_TITLES.PRODUCT_SETTINGS,
icon: 'sliders', route: '/product-settings' }` no grupo "Operações" (D6); `/product-settings` em
`MOCK_API_PATHS`.

- [ ] Passo 1: specs que falham: `product-settings.service.spec.ts` (`HttpTestingController`, como
      `batches.service.spec.ts:7-31`): `calls PUT product-settings/713/liquidation/closing-schedules with the times and the active flag`,
      `calls PUT .../funds/9 with the reconciliation mode`; `mock-api.product-settings.spec.ts`:
      `answers a schedule after the cutoff with a warning`, `answers a schedule before the cutoff without warnings`;
      `src/app/app.routes.spec.ts` e `navigation-mock-api.spec.ts` já existentes passam a exigir a rota.
- [ ] Passo 2: `npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/product-settings/**/*.spec.ts' --include='src/app/core/http/mock-api/mock-api.product-settings.spec.ts'` → falha de compilação.
- [ ] Passo 3: implementar; `node .ai/scripts/check-patterns.mjs` sem `escopo-fora-do-permissions`,
      `http-fora-do-data-access`, `leitura-sem-mock`.
- [ ] Passo 4: rodar e ver passar (incluir `src/app/app.routes.spec.ts` e
      `src/app/layouts/app-shell/**/*.spec.ts`).
- [ ] Passo 5: preparar o commit `feat(TS-5624): rota, data-access e mock da configuração do produto`.

### Tarefa 9: página com seletor de produto, abas e trava de permissão

**Arquivos:** Criar `product-settings.page.{ts,html,scss,spec.ts}`, `product-settings.view.{ts,spec.ts}`
**Interfaces:** Consome: Tarefa 8; `IAMService.authorizeActions`, `app-toggle-group`/`app-toggle`,
`app-select`, `app-page-header`, `app-no-access`, `app-skeleton`. Produz:
```ts
// product-settings.view.ts (funções puras)
export type ProductSettingsTab = 'liquidation' | 'assignment';
export const TAB_KEYS: readonly ProductSettingsTab[] = ['liquidation', 'assignment'];
export function resolveActiveTab(requested: string | null, visible: readonly ProductSettingsTab[]): { active: ProductSettingsTab | null; closed: ProductSettingsTab | null }
export function humanizeOption(value: string): string      // 'nao_aplica' → 'Não aplica'; 'por_chave_sem_origem' → 'Por chave sem origem'
export function isClockTime(value: string): boolean        // /^([01]\d|2[0-3]):[0-5]\d$/
export function sortSchedules<T extends { time: string }>(items: T[]): T[]
// product-settings.page.ts
selector 'app-product-settings-page'; URL: ?product=<id>&tab=liquidation|assignment (bindFiltersToUrl, como report-transfer.page.ts:100)
permissions = signal<{ liquidation: TabPermissions; assignment: TabPermissions }>  // { read: boolean; update: boolean } por aba, via authorizeActions dos dois escopos (forkJoin)
visibleTabs = computed(...)  // só abas com read; sem nenhuma → <app-no-access page="Configuração do produto">
product = signal<ProductOption | null>; products via listProducts()
```
Template: `app-page-header` (título, descrição) → `app-toggle-group aria-label="Aba"` solto (regra
"Seletor de visão") → `app-select` do produto (`clearable`, `placeholder="Escolha o produto"`) →
`@switch (activeTab())` com `<app-liquidation-settings [productId] [canUpdate]>` e
`<app-assignment-settings [productId] [canUpdate]>`; sem produto escolhido, `app-empty-state`.

- [ ] Passo 1: specs que falham (setup como `liquidation-batches.page.spec.ts:170-215`, dublando
      `IAMService` e `ProductSettingsService`):
  ```ts
  it('shows only the tabs the session can read')            // só liquidation:read → um app-toggle
  it('locks the page without any read')                      // expectNoAccessLock(root) com writesOnlyFor(...) e sem ações
  it('hides the save actions without update')                // expectActionButtonsLocked(root, { actionButtons: ['Salvar'] })
  it('keeps the product and the tab in the url')             // navigateByUrl('/?product=713&tab=assignment') → select e aba certos
  it('resolveActiveTab falls back to the first visible tab') // view.spec
  it('humanizeOption capitalizes and accents the known words')
  ```
- [ ] Passo 2: rodar o `--include` da feature e ver falhar.
- [ ] Passo 3: implementar; `.scss` só layout (`display: grid; gap: var(--space-4)`), tokens para
      cor; em `max-width: 600px` o `app-toggle-group` já vira folha sozinho.
- [ ] Passo 4: rodar e ver passar; `check-patterns.mjs` sem `pagina-sem-trava-de-permissao` nem
      `visao-na-barra`.
- [ ] Passo 5: preparar o commit `feat(TS-5624): página de configuração do produto com abas`.

### Tarefa 10: aba Liquidação

**Arquivos:** Criar `liquidation-settings/liquidation-settings.{ts,html,scss,spec.ts}`,
`liquidation-settings/closing-schedules-editor/closing-schedules-editor.{ts,html,scss,spec.ts}`
**Interfaces:** Consome: Tarefas 8 e 9. Produz: `app-liquidation-settings`
(`productId = input.required<number>()`, `canUpdate = input.required<boolean>()`) com três cartões
(`app-card`, empilhados em largura total): **Fechamento** (dois `app-select` — gatilho e agrupamento —
com rótulos fixos no front: `CLOSING_TRIGGER_LABELS`, `CLOSING_GROUPING_LABELS`; **nenhum controle de
acúmulo**, D36; botão "Salvar fechamento"), **Horários de fechamento**
(`app-closing-schedules-editor`: `times = model<string[]>`, `active = model<boolean>`,
`cutoffTime = input<string | null>()`, `triggerIsScheduled = input<boolean>()`, `disabled`; linha =
`input[appInput] type="time" step="60"` + `app-icon-action` remover; botão "Adicionar horário"; **um**
`app-switch` "Ativo" para o produto todo, desabilitado e com a dica "Salve o gatilho Agendado
antes de ligar os horários" enquanto o gatilho **gravado** não for `agendado`; sem horário na lista,
"Salvar horários" fica desabilitado e o switch desligado (a cessão recusa lista vazia);
`app-notice tone="warning"` na linha quando `time >= cutoffTime` **antes** de salvar, só se
`cutoffTime` veio na resposta (D2), com o texto "Depois do corte da conciliação (HH:MM): o lote vai
para a fila manual"; botão "Salvar horários"), **Conciliação por fundo** (tabela `app-pill` por modo +
`app-select` por linha; grava por linha ao mudar, `updateFundReconciliation`; mais de 10 fundos:
10 primeiros e "ver mais"). Depois de cada gravação o componente **substitui** o estado pelo
retorno (sem otimismo); os `warnings` do retorno (textos prontos da cessão) viram um
`app-notice tone="warning"` persistente acima do editor, um item por texto, e
`toast.success('Horários salvos')`. Em 600 px o editor empilha linha a linha.

- [ ] Passo 1: specs que falham (`provideHttpClient(), provideHttpClientTesting()`; serviço dublado):
  ```ts
  it('renders trigger and grouping from the settings')
  it('saves the closing pair and replaces the state with the response')
  it('shows the cutoff warning after a successful save')       // resposta com warnings → app-notice[tone=warning] visível e toast.success chamado, toast.error não
  it('flags a schedule at or after the cutoff before saving')  // 14:00 com cutoff 14:00 → notice na linha
  it('does not flag before saving when the response has no cutoff')  // cutoff_time null → sem notice por linha
  it('locks the active switch while the saved trigger is not scheduled')
  it('keeps save schedules disabled with an empty list')
  it('refuses a duplicated time before calling the api')
  it('disables every control without update')                  // canUpdate=false → selects/inputs disabled, sem botões Salvar
  it('saves the fund reconciliation mode per row')
  it('shows the api message when the save fails')              // 400 "Produto não está no gatilho agendado" → toast.error com o texto
  it('offers no accumulation control')                          // nenhum texto/controle de acúmulo (D36)
  ```
- [ ] Passo 2: rodar e ver falhar.
- [ ] Passo 3: implementar; `prefers-reduced-motion` no `.scss` de qualquer transição; em 600 px a
      tabela de fundos vira lista de cartões (`.ai/rules/responsive.md`).
- [ ] Passo 4: rodar e ver passar; `npm run start:mock` e conferir em 390 px sem rolagem lateral.
- [ ] Passo 5: preparar o commit `feat(TS-5624): aba Liquidação da configuração do produto`.

### Tarefa 11: aba Cessão

**Arquivos:** Criar `assignment-settings/assignment-settings.{ts,html,scss,spec.ts}`
**Interfaces:** Consome: Tarefas 8 e 9. Produz: `app-assignment-settings` (`productId`,
`canUpdate`): `app-field-grid` com os 20 campos (booleanos em `app-switch`; enums em `app-select`
com `options[campo].map(v => ({ value: v, label: humanizeOption(v) }))`; `max_contracts_per_send`
`input type="number" min="1"` com `clearable` → `null` = "sem limite"; `assignment_ftp_folder` texto),
agrupados em três cartões: "Lote e envio" (`assignment_batch_auto_close`, `assignment_file_auto_send`,
`accumulate_contracts_in_remittance`, `single_contract_batch`, `max_contracts_per_send`,
`assignment_ftp_folder`, `external_assignment_processing`, `pipeline_end_action`, `external_disbursement`),
"Elegibilidade" (`buys_overdue_contracts`, `buys_npl_contracts`, `rejects_duplicate_contracts`,
`business_day_due_dates`, `collateral_validation`, `originator_file_format`), "Registro e endosso"
(`contract_endorsement`, `certifier`, `registration_type`, `auto_registration_settlement`,
`manual_assignor_registration`). Um botão "Salvar" que manda **só os campos alterados**
(`diffAssignmentSettings(original, draft): AssignmentSettingsPatch` em `product-settings.view.ts`).
Rótulos PT-BR dos 20 campos em `ASSIGNMENT_FIELD_LABELS` no `.view.ts` (texto do `comment` da
coluna, `models.py:1283-1560`, encurtado). `accumulate_contracts_in_remittance` (`acumula_contratos`)
é "Acumular contratos na mesma remessa" e **não** é o acúmulo de lote de liquidação (D34/D36), que
não aparece na tela. Opções de nome técnico (`idtrust`, `qidtvm`, `mpmerchant`) têm rótulo no mapa
`OPTION_LABELS`; `humanizeOption` é só o fallback.

- [ ] Passo 1: specs que falham:
  ```ts
  it('sends only the changed fields')                     // view.spec: diff de {buys_npl_contracts: false→true} → { buys_npl_contracts: true }
  it('renders the enum options from the settings')        // options.registration_type → app-select com as opções
  it('clears the max contracts to null')                  // "sem limite"
  it('disables every control without update')
  it('replaces the draft with the saved response')
  ```
- [ ] Passo 2: rodar e ver falhar.
- [ ] Passo 3: implementar.
- [ ] Passo 4: rodar e ver passar; feature inteira verde:
      `npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/product-settings/**/*.spec.ts'`.
- [ ] Passo 5: preparar o commit `feat(TS-5624): aba Cessão da configuração do produto`.

### Tarefa 12: varredura final dos três repositórios

**Arquivos:** nenhum novo
**Interfaces:** —

- [ ] Passo 1: cessão — suíte completa pelo comando do BRIEF (`test/`), `tail` com `passed|failed`.
- [ ] Passo 2: BFF — `PYTHONPATH=. pytest -q tests`, `ruff check src tests local`,
      `black --check src tests local`.
- [ ] Passo 3: front — `npx tsc -p tsconfig.spec.json --noEmit`, `npx ng test --watch=false --browsers=ChromeHeadless`,
      `node .ai/scripts/check-patterns.mjs`, `npm run lint` (se existir no `package.json`).
- [ ] Passo 4: `npm run start:mock` e percorrer: sem produto → escolher produto → aba Liquidação
      (salvar 16:00 e ver o aviso) → aba Cessão → "ver como" leitor (botões somem) → 390 px.
- [ ] Passo 5: abrir as três PRs (uma por repo) com os links para o usuário mergear; ordem de deploy:
      cessão → roles no Azure → BFF → front.

## Fora do escopo (registrado para não perder)

- Horários globais (corte da conciliação, verificação D0): área administrativa.
- E-mail do aviso de horário depois do corte (4.6 + 4.8, D27): TS-5585.
- Campos de cálculo, renegociação e cobrança do `produto_config` (D1).
- **Acúmulo do lote de liquidação (D34/D36):** vale em qualquer caso e não é escolha do usuário; a
  tela não o mostra. Na Fase 1 da TS-5567 o `acumula_liquidacoes` é só o portão de transição; a
  TS-5612 o apaga.
- Modalidade antiga e flags legadas (`modalidade_fechamento_lote`, `lote_liquidacao`,
  `fechar_lote_por_proc_id`, `acumula_liquidacoes`, `baixa_por_agendamento`): derivadas pela cessão
  (`apply_closing_modality`, `closing_modality.py` da TS-5583), nunca exibidas nem gravadas pela tela.
- Disparar "fechar agora" pela tela (`POST /agendamento/<chave>/executar`): depois da TS-5570.
- Cache de permissões no front (`authorizeActions` sem cache): comportamento atual do portal.

## Não confirmado

- Se `ns.doc(validate=True)` recusa campo desconhecido dentro de `produto_config`: pelo código o
  flask-restx não fecha `additionalProperties`, então provavelmente não recusa (o plano da TS-5583
  supõe que recusa). Conferir no Passo 2 da Tarefa 2; sem o schema novo o campo passaria sem validar
  o enum.
- Se `NullableInteger` (`__schema_type__ = ["integer", "null"]`) é aceito pelo `validate=True` do
  flask-restx 1.1.0 como o `NullableString` já é (`cessao/api/fields.py`): conferir na Tarefa 2.
- Quais outros consumidores leem `certificadora` e `padrao_originador` do `GET /cadastro/produto`
  (BFF e front não leem; Atlas e scripts não foram verificados): "Para decisão" 1.
- Contrato final das rotas da TS-5570 (a branch ainda não existe; vale o plano dela, `13-plan-ts-5570.md`,
  Tarefas 3 e 4) e se ela aceita o `horario_corte` ("Para decisão" 2).
- Aparência do `input type="time"` nativo nos três navegadores com o tema escuro (D5).
- Quantos produtos o `/fundo/produtos` devolve (tamanho do seletor, D4) e se há produto sem fundo.
- Linhas do front citadas valem para `origin/master` `8e3699ad`; a working tree local pode diferir.

## Revisão de 10/11

Revisão linha a linha contra `origin/master` das três bases (cessão `c041122eb`, BFF `6472fb1`, front
`8e3699ad`), contra as branches `feature/TS-5583-gatilho-agrupamento-lote-liquidacao` e
`feature/TS-5569-scheduler-em-tabela`, contra o plano da TS-5570 e contra as decisões D30, D34 e D36
de 10/11. Nada foi executado; só leitura.

### Corrigido

- **D30 decidida:** virou "(b) página nova"; a alternativa (a) e tudo que dependia dela saíram.
- **Acúmulo (D34/D36):** a tela não oferece "acumula sim/não". Regra escrita em "Arquitetura",
  "Restrições globais", Tarefa 10 (teste `offers no accumulation control`) e "Fora do escopo". Apagadas
  a "regra de combinação gatilho × agrupamento" e a mensagem de exemplo "acumula_liquidacoes só
  combina com gatilho manual" (Tarefas 6 e 10): na TS-5583 o par é aceito em qualquer combinação
  (`closing_modality.py:68-100`) e só a `modalidade_fechamento_lote` divergente é recusada.
- **Horários vs TS-5570 (D2):** o contrato do plano (um job por horário, `ativo` por horário, aviso
  estruturado com código, `PUT /liquidacao/produto/<id>/horarios-fechamento`) não era o da TS-5570
  (um agendamento por produto, `horarios` em `"HH:MM"`, um `ativo`, `avisos` em texto, rota
  `/liquidacao/fechamento-por-horario/<id>`, `solicitado_por` obrigatório). A Tarefa 3 virou
  conferência; BFF (Tarefas 4 a 7), fake e front (Tarefas 8 e 10) seguem o contrato dela. Saíram o
  nome de job por horário, o "horário removido vira job inativo" e o 409 do `DELETE`.
- **Ordem gatilho antes dos horários:** ligar horários exige o gatilho `agendado` já gravado (400 da
  TS-5570); a tela desabilita o switch e explica.
- **Corte para o front:** a resposta da TS-5570 não traz o corte; pedido de `horario_corte` (D2) e
  o pré-aviso na linha só aparece quando ele vier. O texto do aviso pós-gravação já vem pronto.
- **Solicitante:** `azure_id` (oid), não e-mail (`liquidation_batches/viewer.py:397`; o e-mail iria
  para o histórico e os logs da cessão); o campo da sessão não era "a confirmar", é `azure_id`
  (`schemas/users.py:44-53`, opcional).
- **Enum nome × valor (Foco 1, Tarefa 2):** o plano mandava `.value` e `options` por `to_values()`,
  mas o PATCH valida por `to_names()` (`produto/schema.py:33-98`) e `certificadora`,
  `tipo_lastro` (enum definido duas vezes, vale a de `enum.py:717`) e `padrao_originador` têm valor
  diferente do nome: o dado lido não voltaria. Agora tudo pelo nome. `certificadora` não "saía sem
  `attribute`" (já saía `.value`).
- **Tarefa 2 enxuta:** faltam **6** campos no schema, não 10 (os outros 4 eram de cálculo, fora da D1);
  `tipo_cobranca` e `tipo_juros_vp` saíram da correção (fora da D1, não alterar contrato sem uso);
  `limite_contratos_por_envio` nulo precisa de campo próprio (`NullableInteger`, molde do
  `NullableString`).
- **Lista de produtos (D4):** `GET /cadastro/produto` sem `id` devolve todos os produtos com config e
  aninhados; recomendado `GET /fundo/produtos` (já usado pelos lotes, ids da cessão).
- **BFF:** `_patch`/`_put` não existem (só `_get`, `_post`, `_delete`) e o PATCH do produto devolve
  string JSON, o que o `resp.json()` já lê (sem ramo para texto); 5 métodos novos (não 5+6);
  `internal_only` é função própria de cada viewer (não há compartilhada); respostas com `str` e rótulo
  no front (a D3 e a Tarefa 5 se contradiziam: enum tipado na resposta derruba a tela com valor novo);
  `fund_id` vem de `fundo_id`; `FundReconciliation`, `ClosingSchedules` e `warnings` ajustados.
- **Linhas e hashes:** cessão `6c152445d` para `c041122eb`, BFF `f0511cb` para `6472fb1`;
  `models.py` 52 colunas e `:1277-1540` para 54 e `:1283-1560`; `produto/sevice.py:111-131` para
  `:92-112`; `produto/viewer.py:109-119` para `:103-114`; `cadastro/schema.py:312-338` para
  `:316-338`; `delivery/api/__init__.py:38-64` para `:36-66`; caminho do plano da TS-5570.
- **Front:** `page.constants.ts` tem também as descrições; `app-switch` leva o rótulo como conteúdo
  projetado (`<ng-content>`), conforme a Tarefa 10 já supunha; regras de desenho acrescentadas (sem dado digitado na URL, cartões em largura
  total, "ver mais" nos fundos, combobox para muitos produtos).

### Conferido sem mudança

- Escopos `product-settings-assignment` e `product-settings-liquidation`, ações `read` e `update`
  (`Policies.UPDATE` existe; `write` não entra em escopo novo, `.ai/rules/permissions.md:22-25`);
  `Page(..., prefix="product-settings")` e `_page(descrição, caminho, *escopos)`
  (`pages.py:22-33`, `constants.py:17`).
- `/product-settings` não precisa de `URL_PREFIXES_OF_PAGES` (`test_arch_route_scopes.py:27`: página
  com URL `/{prefix}` não entra) e `INTERNAL_ONLY_ROUTES` existe em `test_arch_partner_scope.py:80`.
- `require`/`require_any` (`shared/business/users.py:55-67`); 400 repassado
  (`STATUSES_PASSED_TO_CLIENT`, `errors.py:88`); "ver como" só leitura (`users.py:337`); `create_module.sh`.
- Cessão: `GET /cadastro/produto?id=` devolve lista (`Consulta` com `filter_by`, id inexistente vira
  `[]`); `PATCH /produto/<id>/` cria o vínculo `produto_fundo` se faltar (Foco 5) e `val2enum` aceita
  nome ou valor (o problema é só a validação do schema); `conciliacao_liquidacao` já sai em `fundos[]`;
  `horario_corte()` em `corte.py:58`; `ServicoAgendamento.listar(modulo, ativo, tarefa, payload_contem)`
  na branch da TS-5569.
- O par `gatilho`/`agrupamento` já está nos dois schemas da branch da TS-5583 e o produto novo nasce
  `manual`/`por_chave`; valores aceitos conferem com os enums.
- `acumula_contratos` é campo de cessão, distinto do acúmulo de liquidação: fica na aba Cessão.
- Front: `app-toggle-group`, `app-select` (`clearable`), `app-notice` (`tone`), `app-switch`,
  `app-card`, `app-pill`, `app-icon-action`, `app-field-grid`, `app-empty-state`, `app-skeleton`,
  `app-no-access`, `app-page-header`, `input[appInput]`, `ToastService.success/error`, ícone `sliders`,
  `BaseApiService`, `iamGuard`, `IAMService.authorizeActions`, `bindFiltersToUrl`,
  `expectNoAccessLock`/`expectActionButtonsLocked`/`writesOnlyFor`, as regras do `check-patterns.mjs`,
  `npm run start:mock`; linhas de `app.routes.ts:63`, `navigation.ts:62-71` e `:119`,
  `mock-api.reply.ts:198`, `mock-api.fake-data.ts`; D5 e D6.
- Sem Angular Material, URL só com ids, tela responsiva a 390 px, testes de componente: mantidos.

### Para decisão do Pietro

**Respostas de 11/11 (Pietro):** card **TS-5624**. 1 = sim, certificadora e padrão do originador pelo nome, depois de conferir que nada externo lê o formato atual; 2 = sim, a TS-5570 devolve o horário do corte; 3 = (b), ao sair de `agendado` a cessão desliga o agendamento do produto e mantém os horários gravados; ao voltar para `agendado`, a tela oferece religar com os mesmos horários (regra na cessão); 4 = 403 sem `azure_id`; 5 = módulo `product_settings` do BFF aprovado.

1. **Enum pelo nome em `certificadora` e `padrao_originador` (muda um contrato da cessão).** Hoje o
   `GET /cadastro/produto` os devolve pelo valor (`"ID Trust Certificadora Digital"`), que o PATCH
   recusa. Opções: (a) trocar para o nome (`idtrust`), como os campos novos; (b) deixar esses dois
   fora da tela agora; (c) fazer o PATCH aceitar o valor também. **Recomendação: (a)**, depois de
   confirmar que Atlas e scripts não os leem (BFF e front não leem).
2. **Corte da conciliação na resposta da TS-5570.** Opções: (a) a TS-5570 devolve `horario_corte` em
   `GET` e `PUT`; (b) o BFF busca o corte em outra rota (não existe hoje); (c) sem pré-aviso na tela,
   só o texto depois de salvar. **Recomendação: (a)**: uma linha na TS-5570, e o aviso na linha antes
   de salvar é o que a opção C pede.
3. **Trocar o gatilho para fora de `agendado` com horários ativos.** A TS-5570 mantém o agendamento
   ativo e a task só confere o gatilho antes de fechar (não fecha). Opções: (a) a tela deixa e avisa
   "horários ativos não disparam com este gatilho"; (b) o BFF desativa o agendamento ao salvar o
   gatilho (regra nova no BFF, duas chamadas); (c) a cessão desativa ao receber o PATCH do gatilho.
   **Recomendação: (a)** agora; (c) se a operação estranhar.
4. **Sessão sem `azure_id`** (gravada antes do campo existir): (a) recusar gravar horários com 403 e
   pedir novo login; (b) gravar com um solicitante genérico. **Recomendação: (a)**: o histórico do
   agendador exige quem alterou.
5. **Arquitetura do BFF (aprovação, Tarefa 1):** módulo novo `product_settings` (viewer, business,
   repository, schemas) no molde de `collateral_checks`, dois escopos, uma página, rotas internas com
   `internal_only` próprio do viewer, lista de produtos reaproveitando `get_funds`. Nada fora do
   molde existente. **Recomendação: aprovar como está.**
6. D1, D3, D4 (recomendação mudou para `/fundo/produtos`), D5 e D6 seguem em "Decisões em aberto",
   cada uma com a sua recomendação.

### Ainda não confirmado

- Ver "Não confirmado" acima: validação do `produto_config` com campo desconhecido, `NullableInteger`,
  outros consumidores de `certificadora`/`padrao_originador`, contrato final da TS-5570, tamanho da
  lista de produtos e o `input type="time"` no tema escuro.
- **O que impede executar:** (1) a aprovação da arquitetura e das decisões acima (Tarefa 1); (2) a
  TS-5570, que ainda não tem código (só o plano) e precisa devolver o `horario_corte`; (3) as TS-5583
  e TS-5569 mergeadas na master; (4) o número do card (`TS-5624`).
