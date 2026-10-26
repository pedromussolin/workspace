# 30 — Nomes e docstrings dos testes do BFF em inglês

- **TS:** a criar · **Branch:** a criar, da `master` depois do ciclo do deploy de 21/10
- **Status:** aberta (21/10), **depois do deploy**
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
