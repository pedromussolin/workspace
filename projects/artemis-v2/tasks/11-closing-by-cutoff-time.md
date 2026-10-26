# 11 — Fechamento automático por horário de corte, com bypass

- **Status:** ideia levantada pelo Pietro em 06/10/2026; precisa de desenho.
- **Repos:** platform-cessao (principal), BFF e front (bypass na tela).
- **Decisões:** [D8](../decisions.md).
- **Relacionadas:** [02](02-close-batch-by-proc-id.md),
  [03](03-async-closing-and-429.md),
  [09](09-voltis-automatic-batch.md), [10](10-dayvale-administrator.md).

## Problema

O fechamento automático acontece **em tempo de execução**: cada pagamento que
chega em `cadastrado` tenta fechar o lote da sua remessa
(`cessao/framework/liquidacao/estados_liquidacao.py:342-347`).

Isso não funciona quando o parceiro manda vários pagamentos em remessas
separadas (proc_ids diferentes) que deveriam virar um lote só pela chave
(produto, originador, fundo, origem):

- **Modo por chave (legado):** a primeira remessa que termina fecha a chave
  inteira naquele momento; as que chegam depois viram outro lote. Resultado:
  vários lotes pequenos para a mesma chave no mesmo dia.
- **Modo por proc_id:** por definição, um lote por remessa — também não junta.

## O que já existe de "por horário"

| Rotina | Quando | O que faz |
|---|---|---|
| `fechar_lote_liquidacao_por_agendamento` | beat fixo, 19:00 UTC (16:00 BRT), `cessao/schedule/registro.py` | fecha lotes vigentes (acúmulo), roda o `backstop_por_proc_id` ou `create_by_originador` e envia para a esteira |
| `conciliar_lotes_por_agendamento` | horário de corte da conciliação (`CONCILIACAO_HORARIO_CORTE`, padrão 14:00 BRT) | concilia os lotes da fila contra o saldo da conta |
| `_destino_automatica` | quando o lote chega em `pendente` | depois do corte, manda o lote para `conciliacao_manual` (motivo `pos_horario_corte`), a ser atendido no próximo dia útil (`cessao/framework/liquidacao/baixar.py:53-75`) |

O acúmulo (`acumula_liquidacoes`) já é, na prática, "juntar o dia e fechar
num horário" — mas só para o modo por chave e com horário fixo no beat.

## Proposta

1. **Modo de fechamento automático por produto**, guardado em configuração
   que já existe (`produto_config` ou `produto_fundo.config_extra`, sem
   tabela nova):
   - `por_remessa`: o comportamento atual, em tempo de execução;
   - `por_horario_de_corte`: nada fecha em tempo de execução; no horário do
     produto, fecha tudo o que está apto, pelo modo do produto (chave ou
     proc_id, tarefa 02);
   - `manual`: só pela tela.
2. **Horário configurável por produto (ou produto + fundo)**, não fixo no
   código. Como o beat da cessão tem horários fixos, uma rotina curta (ex.: a
   cada 15 min) fecha os produtos cujo corte já passou e ainda não fecharam no
   dia. É o mesmo princípio do scheduler da shared: o horário mora no banco.
3. **Bypass no fechamento manual:** com o produto em `por_horario_de_corte`,
   o operador pode fechar antes do horário pela tela. A rota registra quem
   forçou e por quê (log do lote, `liquidacao_lote_log`, que já existe).
4. **Bypass na conciliação (aprovar antes do corte):** um lote em
   `aguarda_conciliacao`, esperando o horário de corte, pode ser aprovado na
   hora pelo operador, sem esperar a rotina do corte. Lote que chega depois do
   corte continua indo para a fila manual, como hoje.
   - Hoje o "aprovar" só aceita lote em `conciliacao_manual`
     (`_validar_conciliacao_manual`, `cessao/api/liquidacao/service.py:379-384`),
     e a máquina só tem `aprovar_revisao` de `conciliacao_manual` → `pendente`
     (`cessao/states/liquidacao.py:69`).
   - Mudança: aceitar também `aguarda_conciliacao` (nova transição
     `aguarda_conciliacao` → `pendente`) e reaproveitar o resto do
     `aprovar_revisao_conta`: log com autor e observação, compromisso manual
     registrado **sob o lock da conta** e envio para a esteira.
   - Por que o compromisso importa aqui: a rotina do corte desconta cada
     aprovação do saldo da próxima. Com o compromisso registrado na aprovação
     antecipada, quando o corte rodar ele já enxerga esse valor como saído da
     conta e não aprova outro lote contra o mesmo saldo.
   - Ponto para estressar: a aprovação antecipada fura a fila (a rotina do
     corte ordena os lotes, com pagamentos parciais primeiro). Aceitável por ser
     ação consciente do operador, como já é o "aprovar" da fila manual.

## Tarefas afetadas

- **02:** o modo (chave/proc_id) define *o que* fecha; esta tarefa define
  *quando*.
- **03:** o fechamento manual ganha a opção de bypass do corte.
- **09 (Voltis):** forte candidata — o bug do lote automático pode ser
  exatamente pagamentos em remessas separadas fechando cedo demais.
- **10 (Dayvale):** a ata prevê "fechamento automático de lotes" com
  integração Voltis; nasce já com este modo.

## Pontos para estressar

- Fuso: o beat interpreta UTC; a conciliação já converte de Brasília
  (`cessao/shared/saldo_liquidacao/corte.py`). O horário por produto deve
  seguir o mesmo padrão.
- Dia não útil: fecha no próximo dia útil ou não fecha?
- Ordem com a conciliação: o corte de fechamento precisa vir antes do corte
  da conciliação, senão todo lote cai em `conciliacao_manual`.
- Remessa com pagamento ainda em processamento no horário do corte: fecha o
  que está apto e o resto fica para o próximo corte?

## Validação

- Produto `por_horario_de_corte`: três remessas da mesma chave no dia viram um
  lote só no horário configurado.
- Bypass: fechamento manual antes do corte funciona e fica registrado no log
  do lote.
- Produto `por_remessa` segue igual ao de hoje.
