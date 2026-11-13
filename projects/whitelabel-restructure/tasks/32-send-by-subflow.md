+++
card = "TS-5416"
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
# 32 — Enviar agora escolhendo os subfluxos (PR 4 da tarefa 31)

- **TS:** TS-5416 (já existia como "executar rota unitária").
- **Repos:** apl-shared-service, apl-credit-whitelabel-api (BFF) e apl-credit-whitelabel (front).
- **Status (23/10):** implementação local concluída; revisão e smoke pendentes. Diagnóstico em [31](31-visual-adjustments-and-patterns.md), item A14.
- **Branches:** `feature/TS-5416-envio-por-subfluxo` nos três. Shared e BFF saem da `master`; o front
  sai da `feature/TS-5424-ajustes-visuais-e-padroes` (a PR 1 mexe no envio de relatórios). Sempre
  `--no-track` ao criar a partir de outra branch, e `git pull`/`fetch` antes.

## O que o Pietro pediu

Na revisão de 23/10, no diálogo "Enviar agora" de um fluxo com mais de um subfluxo: poder escolher
**um, dois, três... ou todos** os subfluxos. Hoje o envio manual sempre roda o fluxo inteiro.

## Desenho

- **Front (envio de relatórios):**
  - no "Enviar agora" (aba Agendamentos), se o fluxo tem mais de um subfluxo, uma lista "Subfluxos"
    com todos marcados; desmarcar tira da execução; nenhum marcado bloqueia o "Enviar". Fluxo com um
    subfluxo só fica como hoje;
  - "Enviar agora" também na aba Fluxos (A14), com a mesma escolha;
  - texto de tela "subfluxo", nunca "rota" (D115);
  - aviso ao disparar fluxo desativado (A14).
- **BFF:** só repassa a lista ao shared (rota de "Enviar agora", `report-transfer:run`). Contrato
  novo vai junto no front e no BFF.
- **apl-shared-service:**
  - `run_flow` (`src/modules/report_transfer/viewer.py:710`) ganha um parâmetro com os nomes dos
    subfluxos escolhidos; vazio ou ausente = todos (agendamento não muda);
  - `FileFlow.run` (`src/shared/business/file_flow.py:221`, o laço em `definition.routes`) filtra;
    nome que não existe no fluxo é erro de validação, não execução parcial silenciosa;
  - o histórico da execução já grava os subfluxos rodados (`_save_execution_routes`);
  - **trava por fluxo:** lock no Redis pela chave do fluxo enquanto houver execução em andamento;
    disparo manual com o fluxo rodando é recusado com mensagem clara. Motivo (A14): o dedupe é por
    hash dos parâmetros e não pega um manual com parâmetro diferente do agendado, então o mesmo
    subfluxo poderia rodar duas vezes ao mesmo tempo; nomes com `{seq}` gerariam remessas numeradas
    diferente.
  - Confirmar como o "Enviar agora" chega ao `run_flow` (`POST /scheduled-jobs/{key}/run`,
    `trigger_type=MANUAL`, autor no histórico) e por onde o parâmetro novo passa até a task.

## Regras (valem para quem continuar, Claude ou Codex)

- Regras de git do `~/repos/CLAUDE.md` (= `~/repos/AGENTS.md`): commit atômico
  `tipo(TS-5416): mensagem` em PT-BR, até 72 caracteres, **sem Co-authored-by**, nunca na master.
  **Só commitar depois da revisão do Pietro**; não publicar sem ele pedir.
- Front: seguir `AGENTS.md` e `.ai/` do repo (componentes de `shared/ui`, spec de comportamento,
  claro/escuro/celular, `.ai/scripts/validate.sh` no fim).
- Python (shared e BFF): código, comentários, docstrings e **nomes de teste em inglês**; texto de
  tela em PT-BR; log com mensagem fixa em inglês e o que varia no `extra` (sem e-mail/token);
  `ruff` e `black`. Nomes explícitos do processo (ex.: `report_transfer_flow_lock`).
- Testes do BFF: venv em `~/repos/.reestrutura_whitelabel/agentes/t5425/bff/venv`,
  `PYTHONPATH=. <venv>/bin/pytest -q tests/`. Shared: ver o README do repo.
- Validar tudo localmente antes de qualquer ambiente.

## Implementado no Codex (23/10)

- Worktrees: shared `apl-shared-service-wt/32`, BFF `apl-credit-whitelabel-api-wt/32`
  e front `apl-credit-whitelabel-wt/34`, todas na branch TS-5416 indicada acima.
- Diálogo com todos os subfluxos marcados, seleção parcial e bloqueio sem seleção;
  fluxo único conserva o envio sem campo adicional. Botão na aba Fluxos e aviso
  de agendamento desativado. Front e BFF conferem a ação `run`.
- Contrato `payload.route_names`: lista de nomes; vazio/ausente executa todos.
  Nomes desconhecidos são rejeitados antes de transferir. Só as conexões dos
  subfluxos selecionados são abertas.
- `POST /flows/{key}/run` no BFF e no shared. O shared cria um registro ONCE
  inativo para ligar o histórico à execução manual, sem ativar envio automático.
  Os nomes desses registros são únicos para permitir envios repetidos.
- Trava por fluxo no Redis, compartilhada por envios manuais e agendados, com
  renovação durante a execução e liberação por token. Perda da trava cancela
  cooperativamente a transferência. Pedido manual de fluxo em execução recebe 409.
- Texto do CSV e dos erros de validação do shared atualizado para subfluxo.
- Validação: build development, tipos, padrões e lint dos arquivos alterados
  passaram; 38 testes do executor/trava e 5 testes diretos do BFF passaram.
- Limites do ambiente: sem navegador/portas para smoke; o ambiente Python
  disponível não tem todas as dependências do shared, impedindo a suíte completa.
  O modo só-front já não simulava envios manuais e conserva essa limitação.
- Sem commits ou publicação; aguarda revisão.
