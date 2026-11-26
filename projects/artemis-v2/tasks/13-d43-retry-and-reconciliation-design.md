# D43: nova tentativa na entrada e conciliação do lote

Status: desenho para aprovação (26/11/2026). Falta validar com o negócio (D43 em `decisions.md`).
Código citado contra a cessão em produção, commit `c6f88ce`. Muda a D42.

## 1. Por que

O lote aberto (TS-5567, em produção desde 24/11) põe cada pagamento no lote da chave quando ele
chega. Quem não consegue entrar fica **solto** (pagamento `cadastrado` sem lote), e hoje todo
fechamento procura os soltos da chave, de qualquer data, para não perdê-los.

- **[C]** Essa procura levou 255 s e 233 s nas rodadas das 16h e 17h de 25/11 do produto 15, com
  limite de 480 s (`evidence/scheduled-closing-production-2026-11-25.md`).
- **[C]** De 24/11 21:46 a 26/11 ~14:00 UTC, ~530 mil entradas no lote aberto e 247 recuos, todos
  por trava: a entrada espera no máximo 2 s pela linha do vigente, e numa rajada da mesma chave quem
  passa disso desiste.
- **[C]** Nenhuma entrada foi barrada pela D9 nesse período (consulta no fim). Nos últimos 60 dias,
  todo pagamento solto na réplica é de contrato com a cessão `cadastrado`: a "D9 tardia" do desenho do
  lote aberto (`13-open-lot-design.md`, 3.5) não acontece, como o usuário esperava ("se o contrato
  ainda não foi cedido para o fundo, como o pagamento já está chegando?").

O usuário, em 25/11: "não quero que eles fiquem soltos, isso de ficar levando os pagamentos soltos eu
acho péssimo, além de prejudicar performance".

## 2. Objetivos

- **Nenhum pagamento solto sem destino.** O recuo por trava, única origem real hoje, é resolvido na
  chegada.
- **Fechamento sem procurar soltos de qualquer data.** Conferir antes de enviar; procurar só quando a
  conferência não bate, e só nos últimos 7 dias.
- **Um pagamento de remessa só no lote da remessa** (um lote por fundo e originador, como hoje).
  Palavras do usuário: "Não pode ficar em outro lote".
- **Rede de segurança como último caso:** o que escapar por erro não se perde e gera alerta.

**Fora do escopo:** a trava da primeira entrada (continua na gravação do `cadastrado`, junto com
ele); o agrupamento das chaves; o schema `live` (tarefa 04, outro chat); o beat parado às 12:00 UTC
(card próprio, evidência de 25/11).

**O que seria fracasso mesmo funcionando:** pagamento de remessa em outro lote; liquidação virando
`errado` por causa da entrada; alerta disparando todo dia por caso esperado.

## 3. Abordagens

| Abordagem | O que troca | Decisão |
| --- | --- | --- |
| **A. Nova tentativa na chegada + conciliação antes do envio e depois do processamento, janela de 7 dias** | o solto vira exceção; o fechamento só procura quando a conta não bate | **escolhida** (D43 1a e 2a, refinada em 26/11) |
| B. Manter a procura no fechamento, com janela de N dias (D43 2b) | simples, mas todo fechamento continua procurando | descartada pelo usuário em 25/11 |
| C. Espera maior pela trava dentro da gravação do `cadastrado` (D43 1b) | menos recuos, mas prende os workers da liquidação nas rajadas | descartada em 25/11 |
| D. Entrada no momento em que o pagamento fica apto (D9 tardia, recompra) | cobre a cessão que termina depois | descartada em 26/11: os dados mostram zero D9 tardia |

## 4. Como funciona hoje [C]

- **Entrada:** `_chama_estado` (`cessao/framework/liquidacao/estados_liquidacao.py:104-107`) chama
  `entrar_no_lote_aberto_da_liquidacao` (`cessao/api/liquidacao/refact.py:4313`) dentro da gravação
  do `cadastrado`. A entrada trava a linha do vigente (`travar_vigente_aberto`, `:1773`) com
  `lock_timeout` de 2 s (`LOTE_ABERTO_LOCK_TIMEOUT_MS`), e a trava dura até o commit do `cadastrado`.
  Falha vira recuo: o aviso `"Pagamento de liquidação ficou sem lote aberto"` e o pagamento solto. A
  liquidação nunca vira `errado` por causa da entrada.
- **D9 em silêncio:** as chaves saem de `chaves_da_liquidacao_para_lote_aberto` (`:1701`), sem a D9;
  a D9 entra só no `UPDATE` (`_vincular_pagamentos_ao_lote_aberto`, `:1852`). Pagamento barrado pela
  D9 fica solto sem aviso: o evento de entrada sai com 0 pagamentos e 0 recuos.
- **Fechamento por chave** (tela, horário): `_close_fake_batch` (`:4069`) fecha o vigente, junta
  **todos** os soltos aptos da chave, de qualquer data (`assign_fake_batch_payments`, `:1687`),
  comita e só então envia à esteira.
- **Rodada por horário:** `chaves_a_fechar_do_produto` une os vigentes abertos às chaves com solto
  apto de qualquer data (`_chaves_com_pagamento_sem_lote_apto_query`, `:2848`): é a consulta de 255 s.
- **Remessa:** fecha quando todos os processos dela terminaram (`:3072`, contra o `total_esperado`).
  `_close_remittance_fake_batch` (`:4167`) leva os soltos da remessa ao lote do mesmo fundo e
  originador (`assign_proc_id_payments_to_batches`, `:1567`). O pagamento que termina depois de a
  remessa fechar pede o fechamento de novo e ganha **outro lote**
  (`_refazer_pedido_do_pagamento_retardatario`, `:3245`): fere a regra do usuário.
- **Índice:** a réplica tem `idx_liquidacao_pag_data_filtrada` (`data_criacao` dos pagamentos sem
  lote). Uma busca de soltos de um dia levou 67 ms na réplica em 26/11
  (`explain-20261126/03`, na pasta privada do projeto).

## 5. O desenho

### 5.1 Na chegada: nova tentativa

1. A primeira entrada continua como hoje, na gravação do `cadastrado`.
2. **Recuo agenda uma nova tentativa,** publicada depois do commit do `cadastrado` (antes dele, a
   tarefa não enxergaria o `cadastrado`). Uma tarefa por liquidação, com o `liquidacao_uuid`.
3. **A tarefa entra no lote aberto numa transação própria e curta,** só com a entrada; a trava dura
   o `UPDATE`, não a gravação inteira. Usa a mesma regra de entrada (vigente travado, lote
   `pendente`, D9, `UPDATE` guardado por `liquidacao_lote_id IS NULL`).
4. **Espera crescente a partir de 30 s, até ~10 min do recuo.** Os intervalos exatos ficam com quem
   constrói, dentro desse limite.
5. **Termina sem erro** quando o pagamento já está num lote (levado por um fechamento ou por uma
   conciliação), quando a liquidação saiu de `cadastrado` ou foi apagada.
6. **Esgotou:** um ERROR por liquidação (`"Pagamento de liquidação não entrou no lote aberto depois
   das novas tentativas"`, `extra` com `liquidacao_uuid`, `produto_id`, `chave`, `tentativas`) e um
   monitor no Datadog. O pagamento fica para as conciliações (5.2 e 5.3).
7. **D9 na entrada vira aviso [minha decisão]:** chave achada e pagamento barrado pela D9 gera um
   WARNING próprio. Hoje isso "deveria ser impossível"; o aviso mostra na hora se acontecer.
8. **Remessa fechada não reabre [minha decisão, pela regra do usuário]:** hoje, uma entrada numa
   chave de remessa cujo vigente está fechado aponta o vigente para um lote novo e o reabre
   (`_apontar_vigente_para_lote_novo`, `:1878`), o que dá um segundo lote à remessa. Na chave de
   remessa, a entrada (a primeira e a nova tentativa) olha antes o estado da remessa:
   - `fechando`: não entra; o fechamento em andamento leva os soltos da remessa;
   - `fechada`: não entra; é o retardatário, que só gera alerta (5.3.3).
9. **A nova tentativa refaz a entrada da liquidação inteira,** pela mesma função: ela já escolhe só
   as chaves com pagamento ainda sem lote (`:1701`). Cumpridas e esgotadas contam por liquidação.
10. **Interruptor e portão valem na hora da tentativa [minha decisão]:** com
    `LIQUIDACAO_LOTE_ABERTO_DESLIGADO` ligado ou o produto fora do lote aberto, a tentativa termina
    sem erro (INFO) e o pagamento fica para a conciliação.

### 5.2 Antes de o lote ir para a administradora: conferir, e só então procurar

1. **Conferir é contar, sem travar nada.**
   - Chave (tela, horário): quantos pagamentos aptos da chave, com `data_criacao` nos últimos 7 dias,
     estão sem lote. Pelo índice dos soltos.
   - Remessa: quantos pagamentos aptos da remessa estão sem lote (pelo `proc_id`, sem janela).
2. **Zero:** fecha só o lote aberto, como está.
3. **Diferente de zero:** procura esses soltos (o mesmo filtro), põe no lote que vai ser enviado, na
   mesma transação do fechamento, e registra um evento com as contagens (`"Conciliação do lote achou
   pagamentos soltos"`).
   - **Alerta só para o que não devia estar solto:** pagamento solto há mais que a janela da nova
     tentativa (~10 min desde que a liquidação virou `cadastrado`). Mais novo que isso é nova
     tentativa em andamento; na remessa é o caso esperado de recuo nos últimos segundos. **[C]** Os
     78 do 1637 recuaram 0,4 s antes do fechamento da remessa e estão nos 2 lotes dela, um por fundo
     e originador, sem nenhum solto (réplica, 26/11).
   - **Medidas [minha decisão]:** a janela de 7 dias usa a `data_criacao` do pagamento, pelo índice.
     A idade para o alerta usa o momento em que a liquidação virou `cadastrado`, lido só para as
     poucas linhas soltas que a contagem achou. Pagamento criado mais de 7 dias antes do
     `cadastrado` cai fora da janela; quem o vê é a conferência diária (5.3.4).
4. **A rodada por horário deixa de usar a consulta sem janela:** as chaves passam a ser os vigentes
   abertos do produto mais as chaves com solto apto dos últimos 7 dias **[minha decisão:** a mesma
   contagem com janela, para o solto de uma chave sem lote aberto não esperar outro dia**]**.

### 5.3 Depois de processar: conferir de novo

1. **Fechamento por chave** (tela, horário, depois do envio): solto apto da chave nos últimos 7 dias
   é sobra de erro. Vai para o lote aberto da chave pela mesma entrada da 5.1, uma liquidação por
   vez, cada uma na sua transação curta, com alerta.
2. **Rodada por horário:** a conferência roda uma vez no fim da rodada, para o produto.
3. **Remessa:** solto apto da remessa depois do fechamento gera **só alerta**, sem lote novo. O
   retardatário (`:3245`) deixa de pedir o fechamento de novo e passa a alertar.
4. **Conferência diária [minha decisão]:** uma vez por dia, pelo agendador do banco, contar por
   produto os soltos aptos com mais de 7 dias. Cobre a chave que fica mais de 7 dias sem fechar, que a
   janela das conferências não vê (o 1505 tinha soltos desde 28/09).
   - Depois da limpeza (5.4): leva esses soltos ao lote aberto da chave, pela entrada da 5.1, com
     alerta; na remessa, só alerta. Assim a tela não precisa de uma ação "incluir os mais antigos".
   - Antes da limpeza: só registra a contagem, sem monitor, para não alertar todo dia sobre os
     soltos antigos já conhecidos.

### 5.4 Uma vez, antes de mudar o fechamento: os soltos antigos

- **[C]** Réplica, 26/11, últimos 60 dias: ~6,2 mil pagamentos aptos e soltos de antes do lote
  aberto, em 1505 (3.748, de 28/09 a 13/11), 1802 (1.676), 1538 (356), 1571 (301), 1145 (45), 1703
  (23) e 1769 (20). Mais antigos que 60 dias: não medido.
- Medir todas as idades por produto e chave, e saber se já foram à administradora por outro caminho,
  antes de decidir o destino (seção 7).
- A mudança do fechamento (5.2) só liga depois dessa limpeza: sem ela, a janela de 7 dias esconderia
  esses pagamentos.

## 6. Ordem sugerida [minha decisão]

1. Nova tentativa, aviso da D9 e eventos (5.1). Só acrescenta; o fechamento segue procurando como
   hoje.
2. Conferência depois de processar e a diária (5.3), primeiro só com alerta, para medir.
3. Medição e limpeza dos soltos antigos (5.4), com o negócio.
4. Fechamento com conferência antes de enviar (5.2), saída da consulta sem janela e o retardatário da
   remessa só com alerta.
5. Monitores no Datadog para os eventos novos; o da conferência diária só depois da limpeza.

Cada passo vira card pelo `task-shaping`, depois da aprovação deste desenho.

**Decisões minhas para o usuário conferir:** D9 vira aviso (5.1.7); remessa fechada não reabre
(5.1.8); interruptor vale na hora da tentativa (5.1.10); medidas da janela e do alerta (5.2.3);
chaves da rodada com a contagem de 7 dias (5.2.4); conferência diária que leva os soltos depois da
limpeza (5.3.4); a ordem acima. Revisão de quem constrói (26/11):
`agents/builder-check-d43.md` da pasta privada do projeto.

## 7. Abertos

- **Destino dos soltos antigos** (5.4): fechar num lote e enviar, ou outro tratamento. Negócio.
- **Pagamento de remessa que só fica apto depois do envio** (retardatário): o alerta avisa, mas o que
  fazer com ele é do negócio, já que não pode ir para outro lote.
- **Validação da D43 com o negócio**, que muda a D42.

## 8. O que fica com quem constrói

- Os intervalos da nova tentativa, dentro de ~10 min.
- A fila da tarefa de nova tentativa: não a do worker de fechamento; fila nova exige a declaração no
  consumer e o argocd (lição da TS-5773).
- Como publicar depois do commit do `cadastrado` (há o padrão "registrado antes da publicação" em
  `cessao/tasks/liquidacao.py:196`).
- Os nomes dos eventos e dos campos, seguindo a regra de log (mensagem fixa, o que varia no `extra`).
- `EXPLAIN` na réplica, às 16h, das contagens com janela da 5.2.
- O efeito na tela "Fechar lotes": a contagem de soltos fora do período
  (`contar_avulsos_fora_da_janela`, `:1171`) e o aviso do diálogo de confirmação mudam com a janela
  de 7 dias.

## Consultas desta análise

- Entradas barradas pela D9 em silêncio (Datadog, de 25/11 00:46 UTC):
  `"Entrada no lote aberto da liquidação concluída" @chaves:>0 @pagamentos_no_lote:0
  @chaves_com_recuo:0`, contagem: 0. Conferência do filtro: com `@chaves_com_recuo:>0`, 247.
- Soltos por estado da cessão (réplica, 60 dias): pagamento com `liquidacao_lote_id IS NULL` e
  `data_criacao` nos últimos 60 dias, liquidação `cadastrado`, juntado a parcela, contrato e
  `contrato_processo`; agrupado por produto, estado da cessão e `data_delete`. Script privado
  `scripts/d43_avulsos_por_cessao.py` da pasta privada do projeto. Sem janela, passa de 90 s.
