+++
card = "TS-5437"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 36 — Apagar grupo do ambiente criado fora da tela

- **TS:** TS-5437 (épico TS-5357) · **Branch:** juntada na `release/20261027` (front e BFF)
- **Status:** **em produção** (27/10); na sandbox desde 27/10 (BFF `sand-6e92e7d`, front `sand-2c80f33`).
- **Decisão:** D133.

## O que é

O portal apaga qualquer grupo `[FRONT]` do ambiente, criado pela tela ou direto no Azure. Continuam travados o grupo
de instituição (apagá-lo tira a organização das pessoas), o grupo de outro ambiente e o que tem atribuição em outro
app. Usa a permissão `Group.ReadWrite.All` do Graph, que o app já tinha (corrige a D94).

## Segurança da operação

- A prévia do lote pede a confirmação "REMOVER".
- O grupo apagado volta pela lixeira do Azure em até 30 dias.
