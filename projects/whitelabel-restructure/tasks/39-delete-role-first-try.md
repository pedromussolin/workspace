# 39 — Apagar role na primeira tentativa

- **TS:** TS-5457 (épico TS-5357) · **Branch:** `fix/TS-5457-apagar-role-na-primeira-tentativa` (BFF), da `master`
- **Status:** **publicada** (28/10): 1 commit (`a65919e`); falta a PR e entrar numa release.

## O que aconteceu

Em produção, em 28/10 entre 16h34 e 16h36, apagar as roles `access-control:read`, `all-pre-trade:bypass` e `admin`
pela aba Permissões falhou na primeira tentativa e passou na segunda:
- o Azure respondeu "Permission (scope or role) cannot be deleted or updated unless disabled first";
- o BFF desabilita a role e já manda a remoção em seguida, e a réplica do Azure ainda não tinha visto o "desabilitar";
- na `admin`, a segunda tentativa leu uma atribuição já removida ("EntitlementGrant ... is not found"); só a terceira
  passou.

## O que mudou

- `src/services/azure/graph.py:211`: o PATCH das app roles repete com espera (1, 2 e 4 s, as mesmas da réplica de
  grupo) enquanto o Azure diz que a role ainda está ativa. Reconhece pelo código
  `CannotDeleteOrUpdateEnabledEntitlement` e, sem ele, pela mensagem. Outro erro falha na hora.
- Remover uma atribuição que o Azure diz não existir (404, ou 400 "not found") conta como já removida, com o mesmo
  texto das outras remoções ("Já estava assim no Azure."), e a role é apagada em seguida.
- O código do erro veio do conhecimento do Graph, não de uma resposta real; os logs só tinham a mensagem, que cobre o
  caso de o código ser outro.

## Validação

7 testes novos (`tests/unit/modules/access_control/test_batch_replication.py`), 4 deles falhando antes da correção;
suíte inteira com 2438 testes passando; ruff e black limpos.
