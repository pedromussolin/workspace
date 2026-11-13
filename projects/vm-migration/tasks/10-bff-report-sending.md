+++
card = "TS-5718"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5719", "TS-5720"]
blocked_by = ["TS-5717", "TS-5707", "TS-5708", "TS-5714"]
+++
# 10 — BFF da tela Envio de Relatórios

Status: a começar (13/11/2026)

## Objetivo

Repassar no BFF (`apl-credit-whitelabel-api`, o backend da tela) os contratos novos do
shared-service e criar as permissões. Contrato com o BFF muda no mesmo ciclo do front.

Estimativa: 5 dias sem IA, 2,5 com IA.

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| BF1 | Repasse do catálogo, da prévia de dados e da prévia SQL | 1,5 | 0,5 | SS4, SS5 |
| BF2 | Repasse dos tipos de conexão API e E-mail e do cadastro de contatos | 1,5 | 0,5 | SS1, SS13, SS14 |
| BF3 | Busca no diretório da empresa no escopo desta tela: hoje existe só no Controle de Acesso [C] | 1 | 0,5 | D6 |
| BF4 | Escopos novos no BFF e no Azure: contatos e conexões de e-mail, prévia SQL | 1 | 1 | D6 |

## Cuidados

- Editar contatos e conexões de e-mail tem escopo próprio: é por eles que o dado sai da empresa.
