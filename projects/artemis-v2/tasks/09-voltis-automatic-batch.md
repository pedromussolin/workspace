# 09 — Lote de liquidação automático da Voltis

- **Status:** aguardando as configs do produto e a explicação do bug.
- **Repos:** platform-cessao.
- **Relacionada:** [11](11-fechamento-por-horario-de-corte.md) — hipótese: pagamentos em remessas separadas fechando cedo demais no fechamento em tempo de execução.

## Contexto

Um dos fluxos da Genius que deu errado foi o fechamento automático do lote de
liquidação da Voltis. A ata cita: "Fechamento automático de lotes: requer
validação da entrada do request (recebimento pagamento a pagamento) +
integração com Voltis".

## O que precisamos levantar

Rodar as consultas com o `produto_id` e o `fundo_id` da Voltis:

- [anexos/sql/configs_produto_fundo.sql](../anexos/sql/configs_produto_fundo.sql)
  — um JSON com produto, `produto_config`, `produto_fundo`, fundo, contas,
  regras de liquidação e lotes vigentes.
- [anexos/sql/remessas_recentes.sql](../anexos/sql/remessas_recentes.sql) —
  remessas dos últimos dias, quantos pagamentos ficaram sem lote e em quais
  lotes foram parar. Filtra por colunas com índice, mas rodar na réplica ou
  em horário calmo.

Flags que decidem o caminho (`produto_config`):

| Flag | Efeito |
|---|---|
| `lote_liquidacao` | liga o fechamento automático a cada pagamento cadastrado |
| `fechar_lote_por_proc_id` | caminho por proc_id com portão no Redis × caminho legado |
| `liquidacao_automatico` | envia o lote para a esteira de baixa logo após fechar |
| `acumula_liquidacoes` | usa lote vigente (acumula até fechar) |
| `baixa_por_agendamento` | fechamento pelo beat das 19:00 |

E em `produto_fundo.conciliacao_liquidacao`: modo de conciliação
(`nao_aplica`, `automatica`, `manual`).

## O que já sabemos

- No caminho por proc_id, o fechamento automático só acontece se a entrada da
  remessa registrou o "total esperado" no Redis (`lote_controle.registrar_total`,
  `cessao/api/operacao/viewer.py:769` e `840`). Sem registro, a remessa espera
  o fechamento manual (`cessao/database/models.py:5519-5525`).
- **Mas** não há nenhum aviso `lote_ctrl_sem_registro` nem
  `backstop_sem_registro` nos últimos 30 dias. Então, se a Voltis usa o caminho
  por proc_id, o problema não é a falta desse registro.
- O caminho legado tenta fechar a cada pagamento quando todos os estados são
  terminais; daí os 3.939 avisos de corrida (ver [tarefa 02](02-fechar-lote-por-proc-id.md)).

## Hipóteses a testar quando os dados chegarem

1. A Voltis manda pagamento a pagamento por uma entrada que não registra o
   total da remessa (cada chamada vira um proc_id?).
2. A flag está desligada e o caminho legado fecha cedo ou fecha misturando
   remessas.
3. O lote fecha, mas trava na conciliação (`conciliacao_manual`) ou no
   retorno da Genius ([tarefa 08](08-genius-reenvio-e-logs.md)).

## Próximo passo

Pietro roda as consultas e descreve o sintoma (o que esperava × o que
aconteceu, com um proc_id ou lote de exemplo).
