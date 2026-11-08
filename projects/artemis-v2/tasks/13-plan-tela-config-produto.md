# TS-XXXX: tela de configuração do produto (Cessão e Liquidação) — plano de implementação

> Para quem executa: usar superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans, tarefa por tarefa. Passos com checkbox (`- [ ]`).
> Card ainda sem número: trocar `TS-XXXX` pelo ID quando o card existir (branches, commits, listas
> `PENDING`/`INTERNAL_ONLY` do BFF).

**Objetivo:** uma página nova do portal, "Configuração do produto", com as abas Cessão e Liquidação
(cada uma com escopo próprio), que lê e grava no `produto_config` da cessão, nos horários de
fechamento do produto (jobs do scheduler) e no modo de conciliação por fundo, sem mão no banco.

**Arquitetura:** o front (Angular) chama um módulo novo do BFF (`src/modules/product_settings`, FastAPI),
que traduz para as rotas da cessão (`GET /cadastro/produto?id=`, `PATCH /produto/<id>/` e as rotas de
horário de fechamento do módulo da liquidação, por cima do scheduler da TS-5569). O front só pergunta
ao BFF as ações do escopo (`GET /iam/actions?scope=`); papéis ficam no BFF e no Azure. Toda regra de
negócio (par gatilho × agrupamento, aviso de horário depois do corte) fica na cessão; o BFF mapeia
nomes e o front exibe.

**Stack:** platform-cessao (Flask + flask-restx, SQLAlchemy 1.3, Python 3.8, PT-BR);
apl-credit-whitelabel-api (FastAPI 0.133, pydantic 2.12, pytest; inglês; `test_arch*`);
apl-credit-whitelabel (Angular com signals, componentes próprios em `shared/ui`, Karma/Jasmine;
inglês).
**Desenho:** ~/repos/.artemis_v2/agentes/ts13-spec/spec-fechamento-lotes.md (seção 4.14; também
4.3, 4.5, 4.6)
**Branches** (uma por repo, da master, `git switch --no-track -c ...`):
`feature/TS-XXXX-config-produto-api` (cessão), `feature/TS-XXXX-product-settings-bff` (BFF),
`feature/TS-XXXX-product-settings-page` (front). Uma PR por repo.
**Depende de:** TS-5583 (colunas `gatilho_fechamento_lote_liquidacao` e `agrupamento_lote_liquidacao`
nos schemas) e TS-5569 (scheduler em tabela) mergeadas; TS-5570 (rota de horários, ver D2).

Linhas de código abaixo valem para `origin/master`: platform-cessao `6c152445d`, BFF `f0511cb`,
front `8e3699ad`.

## Decisões em aberto

- **D30 — onde fica a tela.** (a) uma aba "Configurações" na tela de lotes de liquidação e outra na
  de lotes de cessão; (b) página nova `/product-settings` com as abas Cessão e Liquidação.
  **O plano segue (b)** (recomendação do desenho). Se o Pietro escolher (a), muda:
  - BFF: os escopos novos não existem; as rotas entram sob `/operations/liquidation/settings` e
    `/operations/assignment/settings`, com `require("liquidation-real-batches", Policies.UPDATE)` e
    um escopo novo `assignment-batches` `UPDATE` (hoje só tem `READ`); nada de `Page` nova nem de
    `FRONTEND_ROUTE_PERMISSIONS`; a lista `URL_PREFIXES_OF_PAGES` já cobre as URLs.
  - Front: sem rota, menu e `product-settings.permissions.ts`; cada aba vira mais um `app-toggle`
    em `liquidation-batches.page.html:5-14` e em `assignment-batches.page`, lendo `update` do escopo
    da própria tela; o seletor de produto reaproveita o filtro de produto da barra de filtros.
  - O que não muda: Tarefas 2 e 3 (cessão), schemas e business do BFF, os componentes
    `app-liquidation-settings` e `app-assignment-settings` do front.
- **D1 — quais campos do `produto_config` são "configuração de cessão".** O `produto_config` tem 52
  colunas (`models.py:1277-1540`) misturando cessão, liquidação, cálculo, renegociação e cobrança.
  Opções: (i) só os campos do fluxo de cessão (20, lista na Tarefa 5); (ii) tudo que não é
  liquidação. **Recomendação: (i)**; cálculo (`base_dias`, `tipo_juros_vp`, `calcular_vp_curva`,
  `tipo_calculo`, `calcula_valor_aberto`, `taxa_fixa`, `calcular_taxa_operacao`, `discount_tax`),
  renegociação (`aceita_renegociacao`, `padrao_renegociacao`, `padrao_aditamento`) e cobrança
  (`emissor_boleto`, `tipo_cobranca`, `bucket`, `carencia_retencao_dias`, `originador_as_recebedor`)
  ficam para a área administrativa, por rota até lá.
- **D2 — quem entrega a rota de horários de fechamento por produto.** O desenho (4.5 e 4.6) coloca
  o serviço "por cima do scheduler" no módulo da liquidação, que é a TS-5570 (plano ainda não
  escrito). **Recomendação:** a TS-5570 entrega a rota com o contrato fixado na Tarefa 3 deste plano;
  a Tarefa 3 só é executada aqui se a TS-5570 ainda não a tiver entregue quando este card começar.
  O e-mail do aviso (4.6) fica fora dos dois: é da integração com a shared (4.8, D27).
- **D3 — valores dos enums no contrato do BFF.** (i) manter os valores da cessão (`agendado`,
  `por_chave_sem_origem`, `automatica`), com rótulo PT-BR vindo do BFF; (ii) traduzir para inglês
  (`scheduled`) e destraduzir ao gravar. **Recomendação: (i)**, como o BFF já faz com os status de
  lote (`liquidation_batches/schemas.py:65-73`: valor cru + `status_label`); um valor novo na cessão
  não derruba a resposta, e o nome do campo é em inglês.
- **D4 — de onde vem a lista de produtos do seletor.** (i) da cessão (`GET /cadastro/produto`:
  `id`, `nome`); (ii) do product-manager (`GET products/lookup`, já usado pelo front). **Recomendação:
  (i)**: os ids que a tela grava são os da cessão; o product-manager tem outro id.
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
  padrão 14:00; depois da TS-5569 Tarefa 10, lê o job `liquidacao.conciliacao_corte`).
- Aviso de horário depois do corte: **salva e avisa** (nunca recusa); código `horario_apos_corte` na
  cessão, `after_reconciliation_cutoff` no BFF.
- Horário removido na tela vira job `ativo=False` (o `DELETE /agendamento/<chave>` devolve 409 quando
  há histórico; TS-5569 Tarefa 9). Horário recolocado reativa o mesmo job.
- Nome do job: `liquidacao.fechamento_produto_<produto_id>_<HHMM>`; tarefa
  `liquidacao.fechar_lotes_do_produto_por_horario`; `somente_dia_util=True`; `dias_semana=[0,1,2,3,4]`;
  `payload={"produto_id": <id>}` (interface da TS-5569, seção "Interface para o primeiro consumidor").
- BFF: escopos `product-settings-assignment` e `product-settings-liquidation`, ações `read` e
  `update` (nunca `write`, `.ai/rules/permissions.md:22-25`); página `CONFIGURACAO-DO-PRODUTO`,
  prefixo `product-settings`; rotas só da organização interna (`internal_only`).
- BFF: nomes de teste em inglês sem as palavras de `PORTUGUESE_TEST_WORDS` (`tests/test_arch.py:220-251`);
  `HTTPException` só no viewer; log com mensagem fixa e `extra`.
- Front: HTTP só em `data-access/`; interfaces em snake_case iguais ao BFF, sem mapeador; cor só por
  token; `data-scheme` para o escuro; cabe em 390 px sem rolagem lateral; `aria-label` no
  `app-toggle-group`; `.page.spec.ts` com `expectNoAccessLock`/`expectActionButtonsLocked` e
  `writesOnlyFor(...)` (check `pagina-sem-trava-de-permissao`).
- Commits `feat|fix|test|chore(TS-XXXX): ...` (PT-BR, até 72 caracteres, sem Co-Authored-By);
  **todo commit sai só depois da revisão do usuário do card** (os passos dizem "Preparar o commit").
- Roles no Azure (`product-settings-assignment:read|update`, `product-settings-liquidation:read|update`)
  criadas antes do deploy do BFF (`.ai/rules/permissions.md:158-169` do BFF).

## Foco de revisão

1. **Forma real do `GET /cadastro/produto`.** `schema_config_prod` (`cadastro/schema.py:199-270`)
   marshala `tipo_registro`, `tipo_lastro`, `tipo_cobranca` e `tipo_juros_vp` sem
   `attribute=".value"`: a resposta sai `"EnumTipoRegistro.nao_aplica"`, não `"nao_aplica"`. O fake
   do BFF copia a cessão real; se copiar o bug, o contrato passa e a tela quebra. Teste na Tarefa 2
   (`test_campos_enum_da_config_saem_pelo_valor`) e no contrato da Tarefa 7
   (`test_assignment_settings_enum_fields_are_plain_values`).
2. **`PATCH /produto/<id>/` devolve texto e 400 genérico** (`produto/viewer.py:109-119`:
   `raise BadRequest(str(e))`). O BFF relê o produto depois de gravar e repassa o 400 com a mensagem
   (400 está em `STATUSES_PASSED_TO_CLIENT`); o front mostra `apiErrorMessage(err, fallback)`. Teste
   na Tarefa 6 (`test_closing_update_passes_cessao_400_message_through`).
3. **Aviso não é erro.** Horário depois do corte grava e volta 200 com `warnings`; o front mostra
   `toast.success` e um `app-notice tone="warning"` persistente na aba, não `toast.error`. Teste na
   Tarefa 10 (`shows the cutoff warning after a successful save`).
4. **"Ver como" e parceiro.** Durante a simulação o BFF recusa escrita com 403 (`users.py:337-354`) e
   devolve só `read`; parceiro com `admin:*` recebe 403 pelo `internal_only`. O front esconde o
   "Salvar" sem `update` e mostra o motivo. Testes na Tarefa 6 (`test_partner_session_is_refused`) e
   na Tarefa 9 (`expectActionButtonsLocked`).
5. **Fundo sem par `produto_fundo`.** `_create_or_update_produto_fundos` (`produto/sevice.py:111-131`)
   **cria** o vínculo se o CNPJ não estiver ligado ao produto. O BFF só aceita `fund_id` que veio no
   `GET` do mesmo produto (404 `FundNotLinkedError` caso contrário). Teste na Tarefa 5
   (`test_reconciliation_update_refuses_a_fund_not_linked_to_the_product`).

## Mapa de arquivos

**platform-cessao** (`~/repos/platform-cessao`)
- Modificar `cessao/api/cadastro/schema.py:199-270` (`schema_config_prod`: campos que faltam,
  `attribute=".value"`), `:312-338` (`fundoProduto`: `fundo_id`, `nome_fundo`).
- Modificar `cessao/api/produto/schema.py:33-96` (`schema_produto_config`: campos que faltam).
- Modificar `cessao/api/produto/viewer.py` (rota `GET /produto/config/opcoes`), `sevice.py`
  (`ProdutoService.opcoes_config()`).
- Criar `cessao/api/liquidacao/horario_fechamento.py` (serviço por cima do scheduler) e as rotas em
  `cessao/api/liquidacao/viewer.py` (Tarefa 3, condicional à D2).
- Testes: `test/cadastro/test_schema.py`, `test/api/produto/test_viewer.py`,
  `test/api/liquidacao/test_horario_fechamento.py`, `test/api/liquidacao/test_viewer_horario_fechamento.py`.

**apl-credit-whitelabel-api** (`~/repos/apl-credit-whitelabel-api`)
- Criar `src/modules/product_settings/{__init__.py,viewer.py,business.py,repository.py,schemas.py}`
  (`./create_module.sh`).
- Modificar `src/services/platform_cessao/__init__.py` (`_patch`, 5 métodos novos),
  `src/shared/utils/permissions.py:133-742` (2 escopos), `src/modules/access_control/business/pages.py:44-196`
  (1 página), `src/shared/utils/constants.py:29-191` (1 tela), `src/delivery/api/__init__.py:38-64`
  (router), `tests/test_arch_partner_scope.py:80` (`INTERNAL_ONLY_ROUTES`),
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
  `src/app/core/config/page.constants.ts`, `src/app/core/http/mock-api/mock-api.reply.ts:23-56` e
  `:198-199`, `src/app/mock-api.fake-data.ts:35-80`.

---

### Tarefa 1: apresentar e aprovar a arquitetura

**Arquivos:** nenhum (proposta no chat, a partir deste plano)
**Interfaces:** Produz: as decisões que as Tarefas 2–12 assumem (D30, D1–D6) e os contratos abaixo.

Levar ao Pietro, em uma mensagem:
1. D30 (b) e o que muda em (a); D1–D6 com a recomendação de cada uma.
2. Contrato BFF ↔ front (uma tabela):

   | Rota do BFF | Escopo/ação | Cessão por trás |
   |---|---|---|
   | `GET /product-settings/products` | `read` de qualquer um dos dois escopos | `GET /cadastro/produto` |
   | `GET /product-settings/{product_id}/liquidation` | `product-settings-liquidation:read` | `GET /cadastro/produto?id=` + `GET /liquidacao/produto/<id>/horarios-fechamento` |
   | `PUT /product-settings/{product_id}/liquidation/closing` | `product-settings-liquidation:update` | `PATCH /produto/<id>/` (`produto_config` com o par) e releitura |
   | `PUT /product-settings/{product_id}/liquidation/closing-schedules` | `product-settings-liquidation:update` | `PUT /liquidacao/produto/<id>/horarios-fechamento` |
   | `PUT /product-settings/{product_id}/liquidation/funds/{fund_id}` | `product-settings-liquidation:update` | `PATCH /produto/<id>/` (`produto_fundo`) e releitura |
   | `GET /product-settings/{product_id}/assignment` | `product-settings-assignment:read` | `GET /cadastro/produto?id=` + `GET /produto/config/opcoes` |
   | `PUT /product-settings/{product_id}/assignment` | `product-settings-assignment:update` | `PATCH /produto/<id>/` (`produto_config`) e releitura |

   Todas internas (`internal_only`), sem `get_partner_scope`.
3. Contrato cessão de horários (Tarefa 3) para alinhar com a TS-5570.
4. Camadas do BFF (viewer → business → repository → `PlatformCessaoManager`), escopos e página.

- [ ] Passo 1: enviar a proposta; registrar as respostas na seção "Decisões em aberto" deste
      arquivo (riscar a decisão e escrever a escolha).
- [ ] Passo 2: se a TS-5570 for a dona da rota de horários (D2), mandar o contrato da Tarefa 3 para o
      plano dela (`~/repos/.artemis_v2/agentes/ts13-plans/TS-5570.md`, seção Interfaces) e marcar a
      Tarefa 3 aqui como "só conferir".
- [ ] Passo 3: só então começar a Tarefa 2.

---

## platform-cessao

### Tarefa 2: schemas do produto completos para a tela e opções dos enums

**Arquivos:** Modificar `cessao/api/cadastro/schema.py:199-270` e `:312-338`,
`cessao/api/produto/schema.py:33-96`, `cessao/api/produto/viewer.py` (rota nova),
`cessao/api/produto/sevice.py` (método novo) / Teste `test/cadastro/test_schema.py`,
`test/api/produto/test_viewer.py`
**Interfaces:** Consome: TS-5583 Tarefa 4 (par já nos dois schemas). Produz:
- `GET /cadastro/produto?id=<id>` devolve, em `produto_config`, também `compra_npl`,
  `calcular_taxa_operacao`, `endosso_contrato`, `lote_contrato_individual`,
  `tipo_processamento_externo_cessao`, `tipo_acao_fim_esteira`, `limite_contratos_por_envio`,
  `padrao_estorno`, `tipo_calculo`, `padrao_escrituracao`; **todo campo enum sai pelo `.value`**
  (`fields.String(enum=E.to_values(), attribute="<coluna>.value")`), inclusive `tipo_registro`,
  `tipo_lastro`, `tipo_cobranca`, `tipo_juros_vp`, `certificadora` (hoje `to_names()` sem
  `attribute`); em `fundos[]`, `fundo_id` (`fields.Integer(attribute="fundo.id", readonly=True)`) e
  `nome_fundo` (`fields.String(attribute="fundo.nome", readonly=True)`).
- `PATCH /produto/<id>/` aceita, em `produto_config`, os mesmos 10 campos (`fields.Boolean`/
  `fields.Integer`/`fields.String(enum=E.to_names(), required=False)`); `limite_contratos_por_envio`
  aceita `null` (sem limite, `models.py:1535`).
- `GET /produto/config/opcoes` → `{"<campo>": ["valor", ...]}` para os campos enum do
  `produto_config` (os 10 acima que são enum mais `padrao_originador`, `certificadora`,
  `tipo_registro`, `tipo_lastro`, `gatilho_fechamento_lote_liquidacao`, `agrupamento_lote_liquidacao`)
  e `"conciliacao_liquidacao"` (`EnumConciliacaoLiquidacao`). `ProdutoService.opcoes_config() -> dict`
  monta a partir de `ProdutoConfig.__table__.c[<campo>].type.enum_class.to_values()`.

- [ ] Passo 1: testes que falham:
  ```python
  # test/cadastro/test_schema.py (helper marshal como em :15-19)
  def test_campos_enum_da_config_saem_pelo_valor():
      config = ProdutoConfig(tipo_registro=EnumTipoRegistro.nao_aplica,
                             endosso_contrato=EnumEndossoContrato.nao_aplica,
                             tipo_acao_fim_esteira=EnumTipoAcaoFimEsteiraCessao.nao_aplica)
      response = marshal(config, schema_config_prod)
      assert response["tipo_registro"] == "nao_aplica"          # hoje "EnumTipoRegistro.nao_aplica"
      assert response["endosso_contrato"] == "nao_aplica"       # hoje ausente
      assert response["tipo_acao_fim_esteira"] == "nao_aplica"
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
  def test_get_opcoes_config_lista_valores_dos_enums(test_client):
      res = test_client.get("/produto/config/opcoes", headers={"Authorization": FAKE_AUTH_UUID})
      assert res.status_code == 200
      assert res.json["gatilho_fechamento_lote_liquidacao"] == ["manual", "agendado", "automatico"]
      assert res.json["conciliacao_liquidacao"] == ["nao_aplica", "automatica", "manual"]
      assert "nao_aplica" in res.json["tipo_registro"]
  ```
- [ ] Passo 2: rodar (comando do BRIEF) `test/cadastro/test_schema.py test/api/produto/test_viewer.py`
      e ver falhar (`KeyError`, valor `"EnumTipoRegistro.nao_aplica"`, 404 na rota).
- [ ] Passo 3: implementar. Rota `@ns.route("/config/opcoes")` **antes** de qualquer rota com
      `<int:produto_id>` no mesmo caminho (não há conflito: `/<int:produto_id>/` exige inteiro).
      `readonly=True` nos campos novos de `fundos[]` para o `POST /cadastro/produto` (validate=True)
      não exigi-los.
- [ ] Passo 4: rodar e ver passar; rodar também `test/cadastro/` e `test/api/produto/` inteiros.
- [ ] Passo 5: preparar os commits `feat(TS-XXXX): schemas do produto expõem campos de cessão pelo valor`
      e `feat(TS-XXXX): rota de opções dos enums do produto_config` (saem depois da revisão do
      usuário do card).

### Tarefa 3: rotas de horário de fechamento por produto (condicional à D2)

> Executar só se a TS-5570 não entregar esta rota; se entregar, conferir o contrato abaixo contra o
> código dela e pular para a Tarefa 4.

**Arquivos:** Criar `cessao/api/liquidacao/horario_fechamento.py` / Modificar
`cessao/api/liquidacao/viewer.py` (rotas no fim), `cessao/api/liquidacao/schema.py` (models) /
Teste `test/api/liquidacao/test_horario_fechamento.py`, `test/api/liquidacao/test_viewer_horario_fechamento.py`
**Interfaces:** Consome: `ServicoAgendamento.{listar, criar, alterar}` (TS-5569 Tarefas 6 e 9;
`listar(modulo, tarefa, payload_contem)`), `horario_corte()` (`corte.py:58`),
`ProdutoFundo.conciliacao_liquidacao`. Produz:

```python
# cessao/api/liquidacao/horario_fechamento.py
NOME_TAREFA_FECHAMENTO_POR_HORARIO = "liquidacao.fechar_lotes_do_produto_por_horario"
CODIGO_AVISO_HORARIO_APOS_CORTE = "horario_apos_corte"

class ServicoHorarioFechamentoProduto:
    @staticmethod
    def nome_job(produto_id: int, horario: time) -> str  # "liquidacao.fechamento_produto_713_1330"
    @classmethod
    def listar(cls, produto_id: int) -> dict
    # {"produto_id", "horario_corte": "14:00",
    #  "horarios": [{"chave", "horario": "13:30", "ativo", "somente_dia_util", "ultima_execucao"}]}
    # ordenado por horario; inclui inativos
    @classmethod
    def substituir(cls, produto_id: int, horarios: List[dict], solicitado_por: str) -> dict
    # horarios = [{"horario": "HH:MM", "ativo": bool}]; conjunto-alvo: cria o que falta,
    # altera `ativo` do que existe, desativa o que não veio; devolve listar() + "avisos"
    @classmethod
    def avisos_horario_apos_corte(cls, produto: Produto, horarios_ativos: List[time]) -> List[dict]
    # [] se nenhum produto_fundo do produto está em `automatica`; senão um aviso por horário
    # >= horario_corte(): {"codigo": "horario_apos_corte", "horario": "16:00",
    #   "horario_corte": "14:00", "fundos": ["<cnpj>", ...]}
```
Rotas (`ns` de `cessao/api/liquidacao/viewer.py`, parser com `Authorization`):
- `GET /liquidacao/produto/<int:produto_id>/horarios-fechamento` → `listar`; 404 se produto não existe.
- `PUT /liquidacao/produto/<int:produto_id>/horarios-fechamento`, corpo
  `{"horarios": [{"horario": "HH:MM", "ativo": true}], "solicitado_por": "<e-mail>"}` →
  `substituir`; 200 com `avisos` (lista vazia quando não há aviso); 422 horário fora de `HH:MM` ou
  repetido; 404 produto.

- [ ] Passo 1: testes que falham:
  ```python
  # test/api/liquidacao/test_horario_fechamento.py (ServicoAgendamento e Produto mockados)
  def test_nome_do_job_tem_produto_e_horario():
      assert ServicoHorarioFechamentoProduto.nome_job(713, time(13, 30)) == "liquidacao.fechamento_produto_713_1330"
  def test_substituir_cria_altera_e_desativa():
      # existentes: 13:30 ativo, 16:00 ativo; alvo: 13:30 ativo, 17:00 ativo
      # → criar(17:00, payload={"produto_id": 713}, somente_dia_util=True, dias_semana=[0,1,2,3,4]);
      #   alterar(chave_16, {"ativo": False, "solicitado_por": ...}); 13:30 intocado
  def test_aviso_so_com_fundo_em_automatica_e_horario_no_corte_ou_depois(mocker):
      mocker.patch("cessao.api.liquidacao.horario_fechamento.horario_corte", return_value=time(14, 0))
      # fundos: um automatica, um nao_aplica; horários 13:30 e 14:00
      # → um aviso: horario "14:00", horario_corte "14:00", fundos == [cnpj do automatica]
  def test_sem_fundo_em_automatica_nao_avisa(): ...
  # test/api/liquidacao/test_viewer_horario_fechamento.py (padrão de test_viewer_conciliacao_rotina.py)
  def test_put_horarios_devolve_200_com_avisos(test_client, mocker): ...
  def test_put_horario_invalido_devolve_422(test_client): # {"horarios": [{"horario": "25:00"}]}
  def test_put_horario_repetido_devolve_422(test_client): ...
  ```
- [ ] Passo 2: rodar e ver falhar (`ImportError`, 404).
- [ ] Passo 3: implementar. `substituir` chama `avisos_horario_apos_corte` **depois** de gravar
      (salva e avisa). Um `log.info("Horarios de fechamento do produto substituidos", extra={"produto_id", "criados", "desativados", "avisos"})`.
- [ ] Passo 4: rodar e ver passar; `test/api/liquidacao/` inteiro continua verde.
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): rotas de horário de fechamento por produto`.

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
- `PlatformCessaoManager._patch(endpoint, body=None) -> dict | str` (2xx; a cessão devolve texto no
  PATCH do produto: devolver `resp.json()` se `Content-Type` JSON, senão `resp.text`) e:
  ```python
  async def list_products(self) -> list[dict]                       # GET /cadastro/produto
  async def get_product(self, product_id: int) -> dict | None        # GET /cadastro/produto?id=; lista vazia → None (o business levanta NotFoundError)
  async def get_product_config_options(self) -> dict                 # GET /produto/config/opcoes
  async def update_product(self, product_id: int, body: dict) -> None  # PATCH /produto/{id}/
  async def list_product_closing_schedules(self, product_id: int) -> dict        # GET /liquidacao/produto/{id}/horarios-fechamento
  async def replace_product_closing_schedules(self, product_id: int, body: dict) -> dict  # PUT ...
  ```
  (`_put(endpoint, body)` igual ao `_patch`.)

- [ ] Passo 1: testes que falham (`httpx.MockTransport`, como `tests/unit/services/test_platform_cessao_fake_batches.py`):
  ```python
  async def test_get_product_filters_by_id_and_unwraps_the_single_item()   # GET /cadastro/produto?id=713 → [ {...} ] → dict
  async def test_get_product_returns_none_when_the_list_is_empty()
  async def test_update_product_accepts_a_text_body()                      # PATCH → 200 "Dados atualizados com sucesso"
  async def test_replace_closing_schedules_sends_the_put_body()
  ```
  E em `test_pages.py`/`test_permissions.py`: o catálogo e a página novos já são cobertos pelos
  testes genéricos (todo escopo em exatamente uma página; prefixo da página); só rodar.
- [ ] Passo 2: rodar `PYTHONPATH=. pytest -q tests/unit/services/test_platform_cessao_product_settings.py tests/unit/shared/utils/test_permissions.py tests/unit/modules/access_control` e ver falhar (`AttributeError`).
- [ ] Passo 3: implementar; `__all__` do serviço inalterado (classe e fábrica já exportadas).
- [ ] Passo 4: rodar e ver passar; `PYTHONPATH=. pytest -q tests/test_arch*.py` (o
      `test_arch_route_permissions` ainda não muda: sem rotas).
- [ ] Passo 5: preparar os commits `feat(TS-XXXX): escopos e página da configuração do produto` e
      `feat(TS-XXXX): cliente da cessão lê e grava a configuração do produto`.

### Tarefa 5: schemas e business do módulo `product_settings`

**Arquivos:** Criar `src/modules/product_settings/__init__.py` (vazio), `schemas.py`,
`business.py`, `repository.py` / Teste `tests/unit/modules/product_settings/test_schemas.py`,
`test_business.py`
**Interfaces:** Consome: Tarefa 4. Produz (`schemas.py`, pydantic v2, atributo em inglês, `alias`
com o nome da cessão, `populate_by_name=True`, resposta com `model_dump(by_alias=False)`):

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

class ProductOption(BaseModel): id: int; name: str = Field(alias="nome")
class ClosingSettings(BaseModel):
    trigger: ClosingTrigger = Field(alias="gatilho_fechamento_lote_liquidacao")
    grouping: ClosingGrouping = Field(alias="agrupamento_lote_liquidacao")
class ClosingSchedule(BaseModel):
    key: UUID | None = Field(default=None, alias="chave"); time: str = Field(alias="horario")
    active: bool = Field(alias="ativo"); last_execution: dict | None = Field(default=None, alias="ultima_execucao")
class FundReconciliation(BaseModel):
    fund_id: int; cnpj: str = Field(alias="cnpj_fundo"); name: str = Field(alias="nome_fundo")
    reconciliation_mode: ReconciliationMode = Field(alias="conciliacao_liquidacao")
class CutoffWarning(BaseModel):
    code: Literal["after_reconciliation_cutoff"] = "after_reconciliation_cutoff"
    time: str; cutoff_time: str; funds: list[str]
class LiquidationSettings(BaseModel):
    product: ProductOption; closing: ClosingSettings; schedules: list[ClosingSchedule]
    cutoff_time: str; funds: list[FundReconciliation]
class ClosingSchedulesResponse(BaseModel): schedules: list[ClosingSchedule]; cutoff_time: str; warnings: list[CutoffWarning]
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
class ScheduleInput(BaseModel): time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$"); active: bool = True
class ClosingSchedulesRequest(BaseModel): schedules: list[ScheduleInput] = Field(max_length=12)
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
`fund_id` não está em `fundos[]`; `InvalidInputError("Horários repetidos.")` em `ScheduleInput`
duplicado. `repository.py`: um método por chamada do manager, `@require_attr("_platform_cessao_manager")`.

- [ ] Passo 1: testes que falham:
  ```python
  # test_schemas.py
  def test_liquidation_settings_is_built_from_the_cessao_names()   # dict com alias → atributos em inglês; dump sem alias
  def test_closing_trigger_keeps_the_cessao_values_and_labels()     # ClosingTrigger("agendado").label == "Agendado (horários do produto)"
  def test_schedule_input_rejects_a_bad_clock_time()                # "25:00" → ValidationError
  def test_assignment_request_refuses_unknown_fields()
  # test_business.py (repository AsyncMock; GET do produto com fixture `cessao_product()` que copia a forma real da Tarefa 2)
  async def test_update_closing_sends_only_the_pair_and_rereads()   # update_product(713, {"produto_config": {"gatilho_fechamento_lote_liquidacao": "agendado", "agrupamento_lote_liquidacao": "por_chave_sem_origem"}}); depois get_product
  async def test_reconciliation_update_refuses_a_fund_not_linked_to_the_product()  # NotFoundError; update_product não chamado
  async def test_reconciliation_update_sends_the_fund_cnpj()        # {"produto_fundo": [{"cnpj_fundo": "...", "conciliacao_liquidacao": "automatica"}]}
  async def test_replace_schedules_maps_the_cutoff_warning()        # avisos[0].codigo "horario_apos_corte" → warnings[0].code "after_reconciliation_cutoff", requested_by vira solicitado_por
  async def test_assignment_update_translates_names_and_drops_unset_fields()  # {"max_contracts_per_send": None, "buys_npl_contracts": True} → {"produto_config": {"limite_contratos_por_envio": None, "compra_npl": True}}
  async def test_missing_product_raises_not_found()
  ```
- [ ] Passo 2: `PYTHONPATH=. pytest -q tests/unit/modules/product_settings` → `ModuleNotFoundError`.
- [ ] Passo 3: `./create_module.sh product_settings` e implementar; `options` da aba Cessão vem de
      `get_product_config_options()` filtrado pelos campos enum do schema e renomeado pelo alias.
- [ ] Passo 4: rodar e ver passar; `PYTHONPATH=. pytest -q tests/test_arch.py` (camadas, nomes em
      inglês, sem divisores).
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): schemas e regras do módulo product_settings`.

### Tarefa 6: viewer, rotas internas e foto de permissões

**Arquivos:** Criar `src/modules/product_settings/viewer.py` / Modificar
`src/delivery/api/__init__.py:38-64`, `tests/test_arch_partner_scope.py:80` (`INTERNAL_ONLY_ROUTES`),
`tests/snapshots/route_permissions.json` / Teste `tests/unit/modules/product_settings/test_viewer.py`
**Interfaces:** Consome: Tarefa 5. Produz: `router = APIRouter(prefix="/product-settings",
tags=[Tags.OPERATIONS], dependencies=[Depends(internal_only)])`;
`@contextmanager def get_product_settings_business()`; as 7 rotas da Tarefa 1 (tabela), com
`require("product-settings-liquidation", Policies.READ|UPDATE)`, `require("product-settings-assignment", ...)`
e `require_any(("product-settings-assignment", READ), ("product-settings-liquidation", READ))` em
`GET /products`. `INTERNAL_ONLY_DETAIL = "A configuração do produto é só da organização interna."`
`requested_by` = e-mail da sessão (`request.state.user`; conferir o nome do campo em
`src/shared/schemas/users.py:55-62`).

- [ ] Passo 1: testes que falham (app próprio por teste e `route_access`, como
      `tests/unit/modules/operations/liquidation_batches/test_viewer_close.py:51-105`):
  ```python
  def test_each_route_requires_its_role()        # parametrizado: 7 rotas × role certa abre, role da outra aba nega, admin abre
  def test_partner_session_is_refused()          # OrgType parceiro com admin:update → 403
  def test_closing_update_passes_cessao_400_message_through()   # business levanta RemoteServiceError(400, "acumula_liquidacoes só combina com gatilho manual") → 400 com o detail
  def test_schedules_response_carries_warnings()
  def test_products_list_opens_with_either_read()
  ```
- [ ] Passo 2: rodar e ver falhar (404/`ImportError`).
- [ ] Passo 3: implementar; incluir `router.include_router(product_settings_router)` no delivery;
      acrescentar as 7 rotas em `INTERNAL_ONLY_ROUTES` com a razão
      `"configuração do produto: só a organização interna (TS-XXXX)"`;
      `UPDATE_ROUTE_PERMISSIONS=1 PYTHONPATH=. pytest tests/test_arch_route_permissions.py`.
- [ ] Passo 4: `PYTHONPATH=. pytest -q tests/unit/modules/product_settings tests/test_arch*.py`
      verde (inclui `test_arch_internal_routes`, que chama cada rota interna como parceiro e exige
      403, e `test_arch_route_scopes`: URL `/product-settings` é o `/{prefix}` da página).
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): rotas internas da configuração do produto`.

### Tarefa 7: fake da cessão e contratos

**Arquivos:** Modificar `local/upstreams/platform_cessao.py` (rotas `GET /cadastro/produto`,
`PATCH /produto/{id}/`, `GET /produto/config/opcoes`, `GET|PUT /liquidacao/produto/{id}/horarios-fechamento`),
`local/seed/cessao.py` (produto_config completo e `fundos` com `conciliacao_liquidacao`),
`.ai/rules/local.md:40-53` / Criar `tests/contract/test_product_settings.py`
**Interfaces:** Consome: Tarefas 2, 3 (forma real da cessão), 6. Produz: o fake responde **com a
forma real** (enum pelo valor, PATCH devolvendo texto, aviso quando horário ≥ `14:00` e algum fundo
`automatica`).

- [ ] Passo 1: testes que falham (`bff`, `login("admin")`, como `tests/contract/test_cessao.py`):
  ```python
  def test_liquidation_settings_round_trip()                 # GET → PUT closing (agendado/por_chave) → GET reflete
  def test_schedules_after_the_cutoff_are_saved_with_a_warning()   # PUT 16:00 → 200, warnings[0].code, GET lista 16:00 ativo
  def test_assignment_settings_enum_fields_are_plain_values()      # registration_type in options["registration_type"]
  def test_partner_login_gets_403()                           # login("parceiro-dots")
  def test_read_only_role_cannot_update()                    # login("x", roles="product-settings-liquidation:read") → 403 no PUT
  ```
- [ ] Passo 2: `PYTHONPATH=. pytest -q tests/contract/test_product_settings.py` → 404 do fake.
- [ ] Passo 3: implementar o fake copiando a cessão em `origin/master` (depois da Tarefa 2/3).
- [ ] Passo 4: `PYTHONPATH=. pytest -q tests/unit/local tests/contract tests/test_arch_local.py` verde;
      atualizar a tabela do `local.md`.
- [ ] Passo 5: preparar o commit `test(TS-XXXX): fake da cessão e contratos da configuração do produto`.

---

## apl-credit-whitelabel (front)

### Tarefa 8: permissões, data-access, mock e rota

**Arquivos:** Criar `src/app/features/product-settings/product-settings.permissions.ts`,
`data-access/product-settings.interface.ts`, `data-access/product-settings.service.ts` (+`.spec.ts`),
`testing/product-settings.fake.ts`, `src/app/core/http/mock-api/mock-api.product-settings.ts`
(+`.spec.ts`), `product-settings.routes.ts` / Modificar `src/app/app.routes.ts:62-69`,
`src/app/layouts/app-shell/navigation.ts:61-71`, `src/app/core/config/page.constants.ts`,
`src/app/core/http/mock-api/mock-api.reply.ts:23-56` e `:198-199`, `src/app/mock-api.fake-data.ts:35-80`
**Interfaces:** Produz:
```ts
// product-settings.permissions.ts
export const PRODUCT_SETTINGS_ASSIGNMENT_SCOPE = 'product-settings-assignment';
export const PRODUCT_SETTINGS_LIQUIDATION_SCOPE = 'product-settings-liquidation';
// product-settings.interface.ts — snake_case igual ao BFF (Tarefa 5)
export interface ProductOption { id: number; name: string }
export interface ClosingSettings { trigger: ClosingTrigger; grouping: ClosingGrouping }
export type ClosingTrigger = 'manual' | 'agendado' | 'automatico';
export type ClosingGrouping = 'por_chave' | 'por_chave_sem_origem' | 'por_remessa';
export type ReconciliationMode = 'nao_aplica' | 'automatica' | 'manual';
export interface ClosingSchedule { key: string | null; time: string; active: boolean; last_execution: unknown | null }
export interface FundReconciliation { fund_id: number; cnpj: string; name: string; reconciliation_mode: ReconciliationMode }
export interface CutoffWarning { code: 'after_reconciliation_cutoff'; time: string; cutoff_time: string; funds: string[] }
export interface LiquidationSettings { product: ProductOption; closing: ClosingSettings; schedules: ClosingSchedule[]; cutoff_time: string; funds: FundReconciliation[] }
export interface ClosingSchedulesResponse { schedules: ClosingSchedule[]; cutoff_time: string; warnings: CutoffWarning[] }
export interface AssignmentSettings { product: ProductOption; /* 20 campos da Tarefa 5 */ options: Record<string, string[]> }
export type AssignmentSettingsPatch = Partial<Omit<AssignmentSettings, 'product' | 'options'>>;
// product-settings.service.ts (BaseApiService; BASE = 'product-settings')
listProducts(): Observable<ProductOption[]>
getLiquidationSettings(productId: number): Observable<LiquidationSettings>
updateClosing(productId: number, body: ClosingSettings): Observable<LiquidationSettings>
replaceClosingSchedules(productId: number, body: { schedules: { time: string; active: boolean }[] }): Observable<ClosingSchedulesResponse>
updateFundReconciliation(productId: number, fundId: number, body: { reconciliation_mode: ReconciliationMode }): Observable<LiquidationSettings>
getAssignmentSettings(productId: number): Observable<AssignmentSettings>
updateAssignment(productId: number, body: AssignmentSettingsPatch): Observable<AssignmentSettings>
```
Mock: `productSettingsFakeRoutes(fake): MockApiData` com `product-settings/products`,
`product-settings/<id>/liquidation` e `.../assignment` (3 produtos, um com fundo `automatica`);
`productSettingsWrite` em `mock-api.product-settings.ts` responde os `PUT` (o de horários devolve
`warnings` quando `time >= '14:00'` e há fundo `automatica`), chamado em `mock-api.reply.ts:198-199`
antes do genérico. Rota: `{ path: 'product-settings', canActivate: [iamGuard], loadChildren: ... }`;
`PAGE_TITLES.PRODUCT_SETTINGS = 'Configuração do produto'`; item `{ name: PAGE_TITLES.PRODUCT_SETTINGS,
icon: 'sliders', route: '/product-settings' }` no grupo "Operações" (D6); `/product-settings` em
`MOCK_API_PATHS`.

- [ ] Passo 1: specs que falham: `product-settings.service.spec.ts` (`HttpTestingController`, como
      `batches.service.spec.ts:7-31`): `calls PUT product-settings/713/liquidation/closing-schedules with the schedules`,
      `calls PUT .../funds/9 with the reconciliation mode`; `mock-api.product-settings.spec.ts`:
      `answers a schedule after the cutoff with a warning`, `answers a schedule before the cutoff without warnings`;
      `src/app/app.routes.spec.ts` e `navigation-mock-api.spec.ts` já existentes passam a exigir a rota.
- [ ] Passo 2: `npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/product-settings/**/*.spec.ts' --include='src/app/core/http/mock-api/mock-api.product-settings.spec.ts'` → falha de compilação.
- [ ] Passo 3: implementar; `node .ai/scripts/check-patterns.mjs` sem `escopo-fora-do-permissions`,
      `http-fora-do-data-access`, `leitura-sem-mock`.
- [ ] Passo 4: rodar e ver passar (incluir `src/app/app.routes.spec.ts` e
      `src/app/layouts/app-shell/**/*.spec.ts`).
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): rota, data-access e mock da configuração do produto`.

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
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): página de configuração do produto com abas`.

### Tarefa 10: aba Liquidação

**Arquivos:** Criar `liquidation-settings/liquidation-settings.{ts,html,scss,spec.ts}`,
`liquidation-settings/closing-schedules-editor/closing-schedules-editor.{ts,html,scss,spec.ts}`
**Interfaces:** Consome: Tarefas 8 e 9. Produz: `app-liquidation-settings`
(`productId = input.required<number>()`, `canUpdate = input.required<boolean>()`) com três cartões
(`app-card`): **Fechamento** (dois `app-select` — gatilho e agrupamento — com rótulos fixos no
front: `CLOSING_TRIGGER_LABELS`, `CLOSING_GROUPING_LABELS`; botão "Salvar fechamento"), **Horários de
fechamento** (`app-closing-schedules-editor`: `schedules = model<ScheduleDraft[]>`, `cutoffTime = input<string>()`,
`disabled`; linha = `input[appInput] type="time" step="60"` + `app-switch` "Ativo" + `app-icon-action`
remover; botão "Adicionar horário"; `app-notice tone="warning"` na linha quando `time >= cutoffTime`
**antes** de salvar, com o texto "Depois do corte da conciliação (HH:MM): o lote vai para a fila
manual"; botão "Salvar horários"), **Conciliação por fundo** (tabela `app-pill` por modo + `app-select`
por linha; grava por linha ao mudar, `updateFundReconciliation`). Depois de cada gravação o componente
**substitui** o estado pelo retorno (sem otimismo); `warnings` do retorno viram um `app-notice
tone="warning"` persistente acima do editor, um item por aviso (`"16:00 fica depois do corte (14:00);
lotes dos fundos X, Y vão para a fila manual"`), e `toast.success('Horários salvos')`.

- [ ] Passo 1: specs que falham (`provideHttpClient(), provideHttpClientTesting()`; serviço dublado):
  ```ts
  it('renders trigger and grouping from the settings')
  it('saves the closing pair and replaces the state with the response')
  it('shows the cutoff warning after a successful save')       // resposta com warnings → app-notice[tone=warning] visível e toast.success chamado, toast.error não
  it('flags a schedule at or after the cutoff before saving')  // 14:00 com cutoff 14:00 → notice na linha
  it('refuses a duplicated time before calling the api')
  it('disables every control without update')                  // canUpdate=false → selects/inputs disabled, sem botões Salvar
  it('saves the fund reconciliation mode per row')
  it('shows the api message when the save fails')              // 400 "acumula_liquidacoes só combina com gatilho manual" → toast.error com o texto
  ```
- [ ] Passo 2: rodar e ver falhar.
- [ ] Passo 3: implementar; `prefers-reduced-motion` no `.scss` de qualquer transição; em 600 px a
      tabela de fundos vira lista de cartões (`.ai/rules/responsive.md`).
- [ ] Passo 4: rodar e ver passar; `npm run start:mock` e conferir em 390 px sem rolagem lateral.
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): aba Liquidação da configuração do produto`.

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
coluna, `models.py:1277-1540`, encurtado).

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
- [ ] Passo 5: preparar o commit `feat(TS-XXXX): aba Cessão da configuração do produto`.

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
- Modalidade antiga e flags legadas (`modalidade_fechamento_lote`, `lote_liquidacao`,
  `fechar_lote_por_proc_id`, `acumula_liquidacoes`, `baixa_por_agendamento`): derivadas pela cessão
  (`apply_closing_modality`), nunca exibidas nem gravadas pela tela.
- Disparar "fechar agora" pela tela (`POST /agendamento/<chave>/executar`): depois da TS-5570.
- Cache de permissões no front (`authorizeActions` sem cache): comportamento atual do portal.

## Não confirmado

- Se `GET /cadastro/produto?id=` com id inexistente devolve `[]` (inferido de `Consulta.filter`,
  `cadastro/service.py:226-236`) e se `ns.doc(validate=True)` recusa campo desconhecido no nested
  `produto_config` (o plano da TS-5583 supõe que sim; se não recusar, a Tarefa 2 continua necessária
  para a leitura).
- Se o campo do e-mail do usuário na sessão do BFF se chama `email` (`src/shared/schemas/users.py:55-62`).
- Se o `test_arch_route_scopes` aceita `/product-settings` sem entrada em `URL_PREFIXES_OF_PAGES`
  só por ser `/{prefix}` da página (o agente leu que sim; conferir no Passo 4 da Tarefa 6).
- Interface final da TS-5569 (`ServicoAgendamento.listar(modulo, tarefa, payload_contem)` e o 409
  do `DELETE`): o plano dela está em revisão; a Tarefa 3 lê o que for aprovado.
- Aparência do `input type="time"` nativo nos três navegadores com o tema escuro (D5).
- Linhas do front citadas valem para `origin/master` `8e3699ad`; a working tree local pode diferir.

## Revisão de 08/11

### Corrigido
(a preencher na revisão linha a linha contra o código)

### Conferido sem mudança
(a preencher)

### Para decisão do Pietro
- D30 (a)/(b), D1–D6 (acima, com recomendação).

### Ainda não confirmado
- Ver "Não confirmado".
