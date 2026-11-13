+++
card = "TS-5458"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
+++
# 30 — Nomes e docstrings dos testes do BFF em inglês

- **TS:** TS-5458 (épico TS-5357) · **Branch:** `test/TS-5458-testes-do-bff-em-ingles` (BFF), da `master`
- **Status:** **publicada** (28/10): 20 commits, um por módulo, e o último com a regra no README e o teste de
  arquitetura (`test_test_names_are_in_english`, `tests/test_arch.py`). Falta a PR e entrar numa release.
- **Resultado:** 698 nomes, 112 docstrings e 60 comentários traduzidos em 92 arquivos, sem mudar asserção nem `src/`;
  2431 testes antes e 2432 depois (o novo é o de arquitetura), todos passando. `cessao` fica nos nomes, porque é o
  nome do serviço, como no `src`.
- **Depende de:** 24 (deploy de 21/10) fechada

## O que é

O README do BFF diz que o código é em inglês, e nome de teste é código. Na release de 21/10, porém, 515 dos 658
testes novos do BFF têm nome em PT-BR (`test_parceiro_sem_produto_recebe_403`, os do controle de acesso, os da
TS-5193 e os da TS-5129). Alguns módulos já seguem o inglês (`test_owner_renames_the_conversation`). A regra
valia, mas não estava escrita para os testes, e ninguém conferia.

## O que fazer

1. **Regra escrita:** pôr no README do BFF que nomes de teste, docstrings e comentários de teste são em inglês. As
   mensagens que o teste confere continuam no idioma em que o código as produz (PT-BR para a tela, inglês para o
   log).
2. **Renomear:** um commit `test` por módulo, só renomeando, sem mudar o que cada teste confere.
3. **Conferência automática:** um teste de arquitetura (`tests/test_arch.py`) que barra nome de teste com palavra
   comum em português (`nao`, `sem`, `com`, `quando`, `vira`...). Item novo não entra.
4. **Front:** fora desta tarefa. A regra de testes do front escreve as descrições do `it(...)` em PT-BR, porque é
   texto lido por quem revisa, e isso continua.

## Como validar

- Suíte inteira sem falha, com o mesmo número de testes de antes.
- `ruff` e `black` limpos.
- O teste de arquitetura novo falha com um nome em PT-BR de propósito.
