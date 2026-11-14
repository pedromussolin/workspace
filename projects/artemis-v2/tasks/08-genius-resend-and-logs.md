+++
card = "TS-5379"
type = "improvement"
epic = "TS-5278"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"

[tracker]
status = "todo"
priority = "Medium"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 08 — Genius: reenvio e logs de erro

- **Status:** mapeado; problemas revisados no código em 13/10/2026.
- **Repos:** platform-cessao, westworld (envio da liquidação),
  genius-sftp-listener (Lambda do retorno).
- **Fluxo completo, com tabelas:** [08-analise-fluxo-genius.md](08-analise-fluxo-genius.md).
- **Linhas citadas valem para:** platform-cessao `9ddb97f`, westworld
  `195e01e` (versão 1.36.5, a que a cessão usa em `requirements.txt:47`),
  genius-sftp-listener `9b3b19c`.

## Item original

> Melhorar logs de erro na integração com a Genius (caso onde precisamos
> reprocessar — enviar novamente — e eles não haviam apagado os arquivos do
> SFTP)

## Resumo

O problema vai além do log. No reenvio, **o lote pode receber o retorno de
outro envio, ou de outro lote**, e a cadeia toda segue como sucesso. Um
retorno que falha ao processar também não é tentado de novo. Os logs ruins
são o sintoma visível; a correção precisa mexer no nome do arquivo, no item do
Redis e na Lambda, além dos logs.

## Fluxo atual

Termos usados abaixo:

- **`putfo`:** método do paramiko (lib de SFTP) que envia um arquivo aberto
  para um caminho remoto. Abre o destino em modo `wb` (cria ou **trunca** o
  que existir), copia os bytes e, por padrão, faz `stat` no remoto e compara
  o tamanho; se diferir, levanta `size mismatch in put! {remoto} != {enviado}`.
- **consumer do RabbitMQ:** processo que roda em segundo plano em cada pod do
  worker Celery (`entrypoint.sh:16`, `cessao/consumer/start.py`), com pika, e
  escuta as filas de retorno. Não é o worker Celery (outro processo no mesmo
  pod) nem o `busconsumer` (que consome SQS).
- **ack:** confirmação ao RabbitMQ de que a mensagem foi tratada; depois dela
  a mensagem some da fila.

### 1. Envio

| | Cessão (`_R_`) | Liquidação (`_B_`) |
|---|---|---|
| Quem chama | Celery `esteira_desembolso` → `EmissorCessao.enviar_esteira_desembolso` | `POST /liquidacao/liquidar`, `/reenviar` ou esteira de baixa → `EmissorLiquidacao.enviar_esteira_baixa` (`emissores/liquidacao.py:103`) |
| Quem faz o `putfo` | `ComunicadorGenius._enviar_arquivo` (`cessao/administradores/genius/comunicador.py:183`) | westworld `_putfo_com_tentativas` (`westworld/administrador/genius.py:104`), chamada por `ComunicadorGenius.enviar_liquidacao` (`comunicador.py:699-727`) |
| Nome | `{cnpj}_{AAAAMMDD}_R_{NNN}.REM`, gerado ou repassado (abaixo) | `{cnpj}_{AAAAMMDD}_B_{NNN}.REM`, gerado ou repassado; a westworld extrai o padrão por regex (`genius.py:38-45`) |
| Diretório | `produto_config.cessao_ftp` (padrão `inbox`) | o mesmo |
| Tentativas | 3, com logout/login, para `ERROS_CONEXAO = (SSHException, OSError, EOFError)` (`comunicador.py:60`) | as mesmas (`genius.py:25`, `:104-137`) |
| Resposta 400 | só `SSHException` (`comunicador.py:280`) | só `SSHException` (`genius.py:204`), ou sem vaga no controle de conexões |

#### O que dispara o envio

O envio acontece num ponto só de cada esteira (máquina de estados do lote).
Quase todos os gatilhos só "empurram a esteira": o arquivo sai apenas se o
lote estiver naquele estado **e** não houver resposta 200 anterior
(`ja_enviado_ok`). As exceções são as rotas que enviam direto e **sempre
enviam**. [C]

| | Cessão | Liquidação |
|---|---|---|
| Ponto do envio | `EstadoAssinado` → transição `pagar`, emissor `pagamento` (`framework/cessao/estados_desembolso.py:140-152`) | `EstadoPendente` → transição `liquidar`, emissor `liquidacao` (`framework/liquidacao/estados_baixa.py:204-216`) |
| **Envio direto (sempre envia)** | `POST /cessao/cessionar` → `cessionar_task` (`tasks/cessao_lote.py:21-28`); `POST /cessao/automatica` → `cessao_automatica` → `ServiceCessao.cessionar` (`api/cessao/services/cessao.py:121-142`, `:401-413`) | `POST /liquidacao/liquidar` → `liquidar_task` (`tasks/liquidacao_lote.py:30-41`) |
| Esteira, automático | fim da esteira de cessão, se `cessao_automatico` (`framework/cessao/estados_cessao.py:548-554`) | fechamento agendado às 19h (beat `liquidacao_fecha_lote_task`, `tasks/liquidacao_lote.py:240`); fechamento ao cadastrar pagamento, se `liquidacao_automatico` (`framework/liquidacao/estados_liquidacao.py:335-340`); rotina de conciliação no corte, que leva o lote aprovado a `pendente` (`tasks/conciliacao_liquidacao.py:157-175`, escalonado) |
| Esteira, por evento | callback de endosso da certificadora (`api/callback/service.py:228`) leva o lote a `assinado`; outros callbacks retomam a esteira (registro, pagamento) | — |
| Esteira, manual | `/endossar`, `/registrar`, `/cobrar`, `/consolidar`, `/callback` terminam em `enviar_para_esteira` (`api/cessao/services/cessao.py:387-471`); `/etapa` com `enviar_para_esteira` | fechamento `POST /liquidacao/` (tela via BFF e varredura do Mercato Libero, `api/liquidacao/viewer.py:400`); `POST /liquidacao/reenviar` (`tasks/liquidacao_lote.py:51-60`); aprovação manual da conciliação (`api/liquidacao/service.py:457-485`); rotina de corte disparada à mão (`POST /liquidacao/conciliacao/rotina/corte`) |
| Retomam depois do envio (não reenviam) | retorno da Genius (`consumer/callbacks/cessao.py:260`) | retorno da Genius (`consumer/callbacks/liquidacao.py:163`); baixa do registro (`:75`); callback HTTP de ADM (`api/callback/service.py:663`) |

- `/cessao/etapa` com a etapa `pagar` grava uma resposta manual como feita:
  a esteira passa a considerar o envio feito e não envia.
- Para esta tarefa, **os caminhos de reenvio são as rotas de envio direto**
  (`/cessionar`, `/automatica`, `/liquidar`) e o `/reenviar`, que só envia sem
  200 anterior. Excluir o lote e fechar de novo cria lote novo (N6).
- **[H]** O atlas (API legada) também fecha lote. Conferir se passa pela mesma
  esteira.

#### O que vai no CNAB

O CNAB é **gerado de novo a cada envio**, no `gerar_output` do emissor, com o
estado do banco naquele momento. Um reenvio pode, portanto, sair com conteúdo
diferente e o mesmo nome (A1.3). [C]

| | Cessão (`_R_`) | Liquidação (`_B_`) |
|---|---|---|
| O que descreve | os **contratos e parcelas** cedidos (aquisição, ocorrência `01` por padrão) | os **pagamentos** do lote |
| Modo gerado | header, uma linha por parcela de cada contrato do lote, trailer (`geradores/remessa_genius.py:205-258`, `:283-350`) | header, uma linha por pagamento (ou por contrato, com `contratos_problematicos_n_problematicos`), trailer (`geradores/cnab_500_liquidacao_genius.py:818-832`). Cada linha leva contrato e parcela, valor e data do pagamento, multa, juros, vencimento e a ocorrência: `03` liquidação, `13` antecipada, `14` parcial, `71` cancelamento, `10` sem financeiro (`:418-468`) |
| Modo repasse | o CNAB do parceiro anexado ao **primeiro contrato** do lote, filtrado para as linhas dos contratos do lote e renumerado (`remessa_genius.py:51-80`, `:95-135`) | o CNAB que o parceiro mandou para o proc_id do **primeiro pagamento**, enviado como veio (CNAB 520 vira 500 no seguro prestamista) (`cnab_500_liquidacao_genius.py:63-77`, `:132-175`) |
| Renegociação | contratos novos (ocorrência `12`) e os pagamentos do proc_id (ocorrência `10`) no mesmo arquivo | não gera arquivo: a westworld responde 200 sem enviar (`cnab_500_liquidacao_genius.py:105-115`) |

No repasse, o nome e o conteúdo são os do parceiro, então um reenvio sai
idêntico. Ver B13 em [bugs-found.md](../bugs-found.md) para o risco
de usar só o primeiro arquivo.

#### Como o nome é formado

Há dois modos, escolhidos pela configuração do produto. [C]

| Modo | Cessão | Liquidação | Data e `NNN` |
|---|---|---|---|
| **Gerado** (CNAB montado a partir do banco) | `padrao_originador` `json_padrao` ou um padrão de CNAB de parceiro (`geradores/remessa_genius.py:83-93`, nome em `:246-248`) | `padrao_liquidacao` `csv_padrao`/`json_padrao`, ou `gerar_cnab` no `config_extra` do produto-fundo (`geradores/cnab_500_liquidacao_genius.py:179-188`) | data de hoje; `NNN` reservado para o lote |
| **Repasse** (arquivo do parceiro) | os demais: nome do CNAB do contrato no S3 (`remessa_genius.py:60-80`). A renegociação gerada também usa o nome do documento (`:241-242`) | os demais: nome do CNAB do proc_id no S3 (`cnab_500_liquidacao_genius.py:63-77`) | os do arquivo do parceiro |

Reserva do `NNN` no modo gerado:

1. Na primeira geração do lote, não há registro em `liquidacao_lote_arquivo`
   (ou `cessao_lote_arquivo`). `criar_novo_arquivo` trava a linha do fundo
   (`SELECT ... FOR UPDATE`, para dois lotes do mesmo fundo não pegarem o
   mesmo número ao mesmo tempo), pega o maior `numero` do fundo com
   `data_criacao` de hoje, soma 1 e grava (`database/models.py:7143-7191`;
   cessão em `:7219-7256`).
2. Nas gerações seguintes do mesmo lote, como num reenvio, o registro já
   existe e o número é reaproveitado. A data do nome continua sendo a de hoje.
   "Mesmo lote" é a mesma linha: a API e as tasks recebem o `identificador`
   (UUID) do lote, carregam a linha **existente**
   (`get_lote_by_liquidacao_lote_id`, `api/liquidacao/repository.py:61-71`),
   e o gerador busca o número pelo `id` inteiro dela (`liquidacao_lote_processo.id`; na cessão,
   `contrato_lote_processo.id`). Nada compara conteúdo: se os pagamentos do
   lote mudarem antes do reenvio, o CNAB muda e o nome fica. O reenvio não
   cria lote: o `identificador` só é gerado quando a linha é inserida
   (`database/models.py:5724-5726`; `uuid` é um apelido dele, `:5779-5785`).
   UUID e `NNN` novos só existem se nascer outro lote, por exemplo se a
   operação excluir o lote e fechar de novo (N6).
3. O número ocupa 3 posições; acima de 999 é truncado (`_adjust_info`,
   `cnab_500_liquidacao_genius.py:302`). Com a contagem por dia, isso exige
   mais de 999 arquivos de um fundo no mesmo dia.

Exemplo, fundo F:

| Dia | Evento | Nome |
|---|---|---|
| 10 | lote A gera; nenhum registro do dia → 001 | `F_20261010_B_001.REM` |
| 10 | lote B gera → 002 | `F_20261010_B_002.REM` |
| 10 | reenvio de A: reaproveita 001 | `F_20261010_B_001.REM` (igual ao 1º envio) |
| 11 | lote C gera; nenhum registro **criado** no dia 11 → 001 | `F_20261011_B_001.REM` |
| 11 | reenvio de A: reaproveita 001, data de hoje | `F_20261011_B_001.REM` (igual ao de C) |

Reenvio do mesmo lote **em outro dia**, modo gerado (no repasse, tudo é
reaproveitado do arquivo do parceiro): [C]

| Parte | No reenvio | Origem |
|---|---|---|
| CNPJ no nome | igual | fundo do lote |
| Data no nome | muda para hoje | gerada no envio |
| `NNN` no nome | reaproveitado | registro do lote em `liquidacao_lote_arquivo`, não alterado |
| Header: data de gravação | muda para hoje | `cnab_500_liquidacao_genius.py:352` |
| Header: número do arquivo | reaproveitado (o `NNN`, com 7 posições) | `:354` |
| Header da cessão: data da cessão | igual | data de criação do lote (`remessa_genius.py:268`) |
| Corpo | regerado do banco; pode mudar | estado atual do lote |
| Item no Redis | novo, com o nome novo e o mesmo UUID | envio OK |

Como o nome muda, a Lambda não acha o `.RET` antigo (sem A1.2), mas o nome
pode coincidir com o de um lote novo do mesmo fundo criado nesse dia (A2).

### 2. Registro no Redis

Depois de um envio OK, o comunicador adiciona um JSON `{nome_arquivo, id,
status: pendente}` a um set. O id é o `identificador` (UUID) do lote
(`emissores/liquidacao.py:112`, `comunicador.py:261`). O set é um `RedisSet`
do pottery: cada JSON diferente é um membro, então itens que só diferem no
status convivem.

- cessão: `genius_lote_cessao_pendente`, com `cessao_id` (`comunicador.py:395-427`);
- liquidação: `genius_lote_liquidacao_pendente`, com `liquidacao_lote_id`
  (`comunicador.py:362-393`).

### 3. Retorno (Lambda)

A cada 15 min, a Lambda lê os itens `pendente` (`genius_sftp_listener.py:614`),
deriva `X.RET` de `X.REM` (`:697`), faz um `stat` no caminho esperado
(`:385-402`) e, se o arquivo existir, baixa, sobe no S3, publica `{id,
path_s3}` no RabbitMQ e troca o item para `arquivo_recebido` (`:717-760`,
`:628`). A pasta sai do prefixo de CNPJ do nome (`SFTP_ROUTES`, `:372-383`).

**O id do lote não entra na busca; só vai na mensagem.** O vínculo entre um
`.RET` e um lote é só o nome do arquivo. Dois envios com o mesmo nome são
indistinguíveis para a Lambda, e essa é a raiz de A1 e A2.

### 4. Processamento (consumer do RabbitMQ)

- **Cessão:** `listener_cessao_retorno_adm` (`consumer/callbacks/cessao.py:234`)
  → `processar_retorno_cessao` (`comunicador.py:597`). O comunicador separa
  contratos aceitos e rejeitados, atualiza o lote e remove o item do Redis
  (`:453-473`). Se o lote seguir `pagando`, a esteira de desembolso roda de
  novo.
- **Liquidação:** `listener_liquidacao_retorno_adm`
  (`consumer/callbacks/liquidacao.py:112`) → `processar_retorno_liquidacao`
  (`comunicador.py:729`), que só separa aprovadas (`A`) e rejeitadas (`N`).
  Quem decide o estado é o consumer: só rejeitadas → `errado`; senão, esteira
  de baixa até `concluido`. Atualiza `liquidacao_lote_adm`.

### Regra do reenvio

- `POST /liquidacao/liquidar` sempre envia (`api/liquidacao/service.py:278`).
- `POST /liquidacao/reenviar` volta o lote para `pendente` e roda a esteira
  (`tasks/liquidacao_lote.py:51-66`). A esteira só envia de novo se nenhuma
  resposta anterior teve 200 (`framework/liquidacao/estados_baixa.py:61`,
  `emissores/base.py:13-18`).

## Problemas

Ordenados pelo efeito: dado errado no lote, informação perdida, envio sem
visibilidade e logs.

| ID | Problema | Efeito | Status |
|---|---|---|---|
| A1.1 | `.RET` reemitido pela Genius sem reenvio nosso não é lido | correção da Genius perdida | [C] mecanismo; [H] se acontece |
| A1.2 | reenvio com o `.RET` antigo ainda no SFTP: a Lambda lê o antigo | decisão antiga aplicada; resposta do reenvio perdida | [C] |
| A1.3 | reenvio antes do primeiro retorno: o primeiro `.RET` que aparece vira resposta | o mesmo, se o conteúdo mudou entre os envios | [C] |
| A2 | reenvio em outro dia repete o nome de outro lote | um lote recebe o retorno de outro | [C] (código e Datadog) |
| A3 | retorno reprocessado em laço quando a conexão do consumer cai antes do ack | recusas e reversões de parcela reaplicadas; até 4.160 processamentos de um lote | [C] laço; [H] efeito no banco |
| B1 | retorno que falha ao processar não é tentado de novo | lote parado, sem alarme | [C] |
| B2 | `putfo` sobrescreve sem log | `.REM` anterior some | [C] |
| B3 | `size mismatch 0 != N` | `.REM` vazio no SFTP; causa provável: envios simultâneos do mesmo nome | [C] no Datadog |
| B4 | `.RET` vai para o S3 com o mesmo nome | prova do primeiro retorno some | [C] |
| B5 | itens do Redis não são limpos | acúmulo e itens duplicados | [C] |
| B6 | `data_envio_liquidacao` gravada mesmo com falha | data de envio não confiável | [C] |
| C1 | erro de permissão tratado como queda de conexão | 3 tentativas inúteis | [C] |
| C2 | última tentativa sobe sem log | falha sem rastro | [C] |
| C3 | só `SSHException` vira 400 | exceção sem contexto; mensagem de "cessao/pagamento" na liquidação | [C] |
| D1–D4 | logs sem contexto, com f-string; ruído de utf-8 | falha não filtrável no Datadog | [C] |

### A. Dado errado no lote

**A1. O `.RET` tratado como resposta pode não ser o do envio.** A Lambda não
varre o SFTP: só procura `.RET` de item `pendente`
(`genius_sftp_listener.py:614-626`). Depois do primeiro retorno, o item vira
`arquivo_recebido` (liquidação) ou é removido (cessão). Três casos:

**A1.1 — A Genius reenvia o `.RET` sem reenvio nosso.** [C] no mecanismo; [H]
se a Genius faz isso e com qual nome
- Não há item `pendente`, então a Lambda nem faz `stat`. O lote fica com a
  decisão do primeiro retorno, e a correção da Genius passa despercebida.
- Diferente dos outros casos, aqui o efeito é **perda**, não leitura errada.

**A1.2 — Reenviamos o CNAB e o `.RET` antigo continua no SFTP.** [C] no
mecanismo; [H] na frequência
- O reenvio que dá certo grava um item **novo** `pendente`, com o mesmo
  `nome_arquivo` e o mesmo id (`liquidacao_lote_id` ou `cessao_id`, os dois com
  o UUID do lote). O JSON antigo só difere no status, então o set guarda os
  dois (`comunicador.py:362-427`; `genius_sftp_listener.py:614-633`).
- Na rodada seguinte, a Lambda faz `stat` no mesmo `X.RET`. Se a Genius não
  apagou o anterior, ele já está lá e é publicado, em até 15 min, antes de a
  Genius processar o reenvio. A data e o tamanho do `stat` são descartados
  (`:395-402`), e o item não tem data de envio para comparar.
- O item volta a `arquivo_recebido`. O `.RET` verdadeiro do reenvio, quando
  chegar com o mesmo nome, não é lido por ninguém.
- Quando acontece: reenvio com o mesmo nome (mesmo dia no modo gerado; qualquer
  dia no modo repasse) **e** `putfo` aceito. Se o servidor recusar
  sobrescrever, o envio falha, não há item novo e o problema é o do grupo C.
- Efeito: a cessão aplica as decisões antigas ao lote e perde a resposta do
  reenvio.

**A1.3 — Reenviamos antes de o primeiro retorno chegar.** [C] no mecanismo
- O item ainda está `pendente`, e o JSON do reenvio é idêntico ao que já está
  no set: o `SADD` não muda nada.
- O primeiro `.RET` que aparecer é tomado como resposta, mesmo que seja do
  envio anterior. O do reenvio chega depois, com o mesmo nome, e ninguém lê.
- Só pesa se o conteúdo mudou entre os envios (pagamento removido, por
  exemplo). É o caso menos provável: exige reenviar enquanto a Genius ainda
  processa o primeiro. `/reenviar` não reenvia depois de um envio OK;
  `/liquidar` reenvia.

```
10:00  envio 1 do lote A (P1, P2, P3) → X.REM; Redis {X, A, pendente}
10:20  Genius pega o X.REM do envio 1
10:30  /liquidar de novo, P3 removido → envio 2 (P1, P2), mesmo X.REM; SADD não muda o set
11:00  Genius grava X.RET do envio 1 (P1, P2, P3)
11:15  Lambda publica esse X.RET para A → arquivo_recebido
12:00  Genius grava o X.RET do envio 2 por cima → ninguém lê
```

**A2. Dois lotes diferentes podem ter o mesmo nome, e o retorno de um vai
para o outro.** [C]. Ver "Como o nome é formado".
- Acontece no modo gerado, quando um lote é reenviado **em outro dia**. O
  `NNN` é reservado uma vez por lote (`liquidacao_lote_id` é único em
  `database/models.py:7117`; `_get_file_number` em
  `geradores/cnab_500_liquidacao_genius.py:319-332`), e a data do nome é a de
  hoje (`:859-865`): o nome sai com a data nova e o `NNN` antigo. Como o
  contador só conta registros criados hoje (`models.py:7143`), um lote novo
  do mesmo fundo pode receber o mesmo `NNN` nesse dia. A cessão repete o
  desenho (`models.py:7193-7256`;
  `geradores/cnab/genius/cnab_500_base.py:12-34`, `:243-249`).
- O reenvio no mesmo dia não cai aqui: o nome repete, mas é do mesmo lote
  (A1).
- No modo repasse, depende de o parceiro repetir nomes entre arquivos. [H]
- Efeito: o `.REM` de um lote sobrescreve o do outro no SFTP. O Redis fica com
  dois itens de mesmo nome e **ids diferentes**, os dois apontando para o
  mesmo `.RET`; um lote recebe o retorno do outro.
- O processamento **não confere se as linhas são do lote**. Na cessão, o lote
  vira `pago` se houver qualquer contrato aceito no arquivo
  (`comunicador.py:475-493`, `:620-650`). Na liquidação, o consumer decide o
  estado pela contagem de aprovadas e rejeitadas do arquivo inteiro; só as
  rejeições são casadas com os itens do lote, por contrato e parcela
  (`comunicador_base.py:85-115`). Um `.RET` de outro lote com aprovações leva
  o lote a `concluido`.
- Outra origem do mesmo problema: a rota de download do CNAB
  (`/liquidacao/<produto_id>/<liquidacao_id>/arquivo`, `api/liquidacao/viewer.py:436-460`)
  chama o mesmo gerador e **reserva o `NNN` sem enviar**. Se o primeiro envio
  for em outro dia, o nome sai com a data do envio e um número reservado no
  dia do download.

```
DIA 10  lote A reserva 001                       → F_20261010_B_001.REM
DIA 11  lote C, novo: nenhuma reserva do dia 11 → 001
                                                 → F_20261011_B_001.REM  Redis {..._001, C, pendente}
        reenvio de A: 001 (reservado no dia 10) + data de hoje
                                                 → F_20261011_B_001.REM  Redis {..._001, A, pendente}
        Genius processa o .REM que está lá (o de A, que sobrescreveu o de C) → ..._001.RET
        Lambda: item C → acha ..._001.RET → publica para C   (C recebe a resposta de A)
                item A → acha ..._001.RET → publica para A
```

  Se a Genius já tinha processado o `.REM` de C, o contrário: A recebe o
  `.RET` de C. A premissa do contador ("o nome já carrega a data, então
  reiniciar por dia mantém o nome único", docstring de
  `get_numero_proximo_arquivo_by_fundo`) quebra porque a data do nome é a do
  envio, e o número é do dia da reserva.
- O `NNN` também vai no header do CNAB de liquidação
  (`cnab_500_liquidacao_genius.py:354`).

**A3. Retorno reprocessado em laço.** [C] no código e no Datadog; [H] no
efeito sobre as parcelas. Detalhe na [evidência de 15/10](../evidence/genius-resend-datadog-2026-10-15.md).
- O consumer do RabbitMQ processa o `.RET` inteiro dentro do callback e só dá
  ack no fim (`consumer/__init__.py:54-65`). Com `pika.BlockingConnection`
  (`consumer/messaging/consumer.py:9-12`), a conexão não troca heartbeat
  durante o callback; o intervalo efetivo é de 60 s. Retorno grande passa
  disso (p99 de 16 min, máximo de 40 min), o broker derruba a conexão, a
  mensagem volta para a fila e outro pod processa de novo.
- Produção: um lote processado 4.160 vezes em 7 dias, por 215 pods
  diferentes; outros quatro lotes, de 7 a 42 vezes. Num deles, 7 passadas
  aplicaram 49.616 recusas para 7.101 linhas recusadas.
- **[H]** Passadas concorrentes revertem a mesma parcela mais de uma vez.
  Validar `contrato_parcela.valor_aberto` dos pagamentos recusados desses
  lotes.

### B. Informação perdida sem aviso

**B1. Um retorno que falha ao processar não é tentado de novo.** [C]
- `ask_consumer` dá ack depois do callback (`consumer/__init__.py:54-65`), e
  os dois listeners capturam qualquer exceção (`callbacks/cessao.py:262-263`,
  `callbacks/liquidacao.py:172`). A Lambda já marcou `arquivo_recebido`.
- Efeito: o lote fica parado em `pagando`/`pendente`, sem fila de erro nem
  alarme.
- Pelo mesmo motivo do A1.1 (item já fora de `pendente`), um `.RET`
  reemitido depois da falha também não é lido.

**B2. Reenviar sobrescreve o arquivo sem log.** [C]
- Ninguém faz `stat` antes do `putfo`, que trunca o destino. Os docstrings de
  `_enviar_arquivo` (`comunicador.py:183-187`) e de `_putfo_com_tentativas`
  (`genius.py:107-111`) chamam isso de "idempotente", assumindo que o servidor
  aceita sobrescrever.

**B3. `size mismatch 0 != N` pode deixar um `.REM` vazio no SFTP.** [C] no
Datadog: o único caso em 30 dias foi num arquivo enviado por 5 lotes ao
mesmo tempo (B13, repasse); um `putfo` truncou o arquivo enquanto outro
conferia o tamanho ([evidência de 15/10](../evidence/genius-resend-datadog-2026-10-15.md)).
- O 0 é o tamanho remoto depois da escrita: abertura e escrita foram aceitas,
  mas o arquivo ficou vazio. Isso não bate com "servidor recusa sobrescrever",
  que falharia na abertura. Causas possíveis: o servidor trunca e descarta a
  escrita, ou algo do lado da Genius mexe no arquivo entre a escrita e o `stat`.
- Risco: a Genius processar um `.REM` vazio, e a próxima tentativa já o
  encontrar no destino.
- Validar: `stat` antes e depois do envio (proposta 2).

**B4. O `.RET` vai para o S3 com o mesmo nome.** [C]
- A chave é o prefixo mais o nome do `.RET` (`genius_sftp_listener.py:749`).
  Um reenvio com o mesmo nome sobrescreve o retorno anterior no S3, e some a
  prova do que chegou da primeira vez.

**B5. Redis: itens da liquidação nunca saem; na cessão sai só o primeiro.** [C]
- Só existe remoção para a chave da cessão (`comunicador.py:453-473`), e ela
  remove só o primeiro item do `cessao_id`. Depois de um reenvio pode haver
  dois. Na liquidação os itens `arquivo_recebido` se acumulam.

**B6. `data_envio_liquidacao` é gravada mesmo quando o envio falha.** [C]
- `emissores/liquidacao.py:116`, antes de checar o status. Não serve como data
  de envio confiável para filtrar o `.RET` (proposta 4).

### C. Envio: erro tratado do jeito errado

**C1. Erro de arquivo ou permissão é tratado como queda de conexão.** [C]
- `PermissionError` é subclasse de `OSError`, que está em `ERROS_CONEXAO`.
  Resultado: 3 tentativas com logout, espera e login que não resolvem nada.

**C2. A última tentativa sobe sem log.** [C]
- O laço só faz `raise`.

**C3. Só `SSHException` vira resposta 400.** [C]
- `OSError` escapa como exceção para a esteira, sem nome do arquivo nem lote.
  Na liquidação a resposta 400 vira a exceção "Erro ao enviar arquivo de
  cessao/pagamento" (`emissores/liquidacao.py:118`), mesmo sendo liquidação.

### D. Logs

- **D1.** Os avisos de tentativa interpolam a mensagem com f-string e põem
  `os.getpid()` em `processo` (`comunicador.py:195-205`, `genius.py:123-131`).
  Faltam `lote_id`, `lote_identificador`, `proc_id`, `fundo_id`, `produto_id`,
  `tipo_envio` e `reenvio`. [C]
- **D2.** A esteira loga `Erro na esteira` com f-string e sem `extra`
  (`emissores/liquidacao.py:100`); o log do banco guarda só
  `PermissionError: [Errno 13] ...`. [C]
- **D3.** Os consumers logam `Consumer ..._retorno_adm error` com f-string,
  sem lote nem arquivo (`callbacks/cessao.py:263`, `callbacks/liquidacao.py:172`). [C]
- **D4.** O aviso de utf-8 (`comunicador.py:89`) é ruído. [C]

## Evidências (Datadog, 30 dias)

- 68 × `Falha ao enviar arquivo para o SFTP da genius`; 23 delas com
  `size mismatch in put! 0 != N` (08/09). Ver B3 para a leitura do número.
- 3 × `Falha ao conectar no SFTP da genius: timed out`.
- 4.863 × `Retorno da Genius nao e utf-8 valido; lendo como cp1252`.
- Fonte e consultas: [baseline-datadog-2026-10-05.md](../evidence/baseline-datadog-2026-10-05.md).

**15/10/2026, 30 dias (logs desde 16/09)**, na [evidência de 15/10](../evidence/genius-resend-datadog-2026-10-15.md):

- A2 confirmado: 31 nomes de arquivo usados por mais de um lote (66 lotes),
  por três mecanismos: reenvio de outro dia (7 nomes), dois lotes novos no
  mesmo dia com o mesmo número (21; causa ainda [H]) e repasse do mesmo
  arquivo do parceiro (3; B13).
- A1: 38 lotes enviados mais de uma vez; 26 com mais de um retorno
  processado. Não dá para saber, pelos logs, se o `.RET` lido depois do
  reenvio foi o antigo: a Genius responde em menos de 5 min em ~5% dos lotes.
  Correção: D15 (I2), com um só `pendente` por lote.
- A3: o laço de reprocessamento acima.
- 18.281 avisos `Liquidação rejeitada sem pagamento correspondente no lote`.
- 426 de 1.425 lotes de liquidação sem retorno processado; os 11 enviados com
  nome sem `_B_` estão todos nessa conta.
- 65 avisos de falha de envio, todos com a mensagem vazia.
- A Lambda não manda logs para o Datadog.

## Proposta

| # | Proposta | Resolve | Onde |
|---|---|---|---|
| 1 | **Logs como evento:** mensagem fixa; `extra` com `lote_id`, `lote_identificador`, `proc_id`, `fundo_id`, `produto_id`, `nome_arquivo`, `caminho`, `tentativa`, `reenvio`, `tipo_envio`. Uma linha ERROR na falha final. Reaproveitar `contexto`/`contexto_esteira` (`cessao/shared/saldo_liquidacao/log.py:12-38`) | C2, D1–D3 | cessão, westworld |
| 2 | **`stat` antes e depois do envio:** logar tamanho e data do que já existe e decidir conforme a D12 | B2, B3 | cessão, westworld |
| 3 | **Separar erro de arquivo/permissão de erro de conexão:** só o segundo merece nova tentativa | C1, C3 | cessão, westworld |
| 4 | **Descartar `.RET` antigo:** data de envio no item do Redis, e a Lambda ignorar (e logar) `.RET` mais antigo que o envio. Decidido na D15 (filtro por data; implementação I2). Não cobre A1.3: o `.RET` do envio anterior chega depois do reenvio e passa no filtro de data | A1.2 | cessão, listener |
| 5 | **Nome único no reenvio**, conforme a D13 | A1.2, A1.3, A2, B4 | cessão, westworld |
| 6 | Rebaixar o aviso de utf-8 para DEBUG | D4 | cessão |
| 7 | **Novo:** retorno que falha ao processar não pode sumir, conforme a D14 | B1 | cessão, listener |
| 8 | **Novo:** limpar o item do Redis da liquidação depois do processamento e remover todos os itens do id na cessão | B5 | cessão |
| 9 | **Novo:** detectar `.RET` alterado depois de lido: ao marcar recebido, guardar data e tamanho do arquivo no item e, por alguns dias, alertar se mudarem. Sem reprocessar sozinho: uma correção da Genius precisa de alguém olhando. Depende de a Genius reemitir com o mesmo nome. Alternativa levantada em 14/10, voltar todos os itens para `pendente` e varrer o SFTP: **não recomendada**, porque a Lambda não distingue o `.RET` reemitido do já lido (não guarda data nem tamanho) e republicaria todos os retornos, reaplicando decisões a lotes já concluídos; na cessão o item já foi apagado | A1.1 | listener |

A estimativa (36 h em [estimate.md](../estimate.md)) não cobre as
propostas 7, 8 e 9 nem a mudança de modelo que a D13 pode exigir. Revisar quando
as decisões fecharem.

### Desenho da correção de A1 e A2 (proposta, 14/10/2026)

A raiz é que o `.RET` se liga ao lote só pelo nome, o nome se repete e nada no
caminho confere tempo ou conteúdo. A correção vai em camadas:

| # | Implementação | Onde | Cobre | Depende de |
|---|---|---|---|---|
| I1 | **Conferir o retorno contra o lote antes de aplicar.** Casar cada linha com os itens do lote (cessão: contrato; liquidação: contrato e parcela, a mesma chave da rejeição). Linha que não é do lote, ou item sem linha: não aplicar, logar ERROR com lote, arquivo e divergência, e deixar o lote para revisão (D16) | cessão (comunicador e consumers) | A2 em todos os modos; A1.2 e A1.3 quando o conteúdo mudou | — |
| I2 | **Decidido (D15).** **Data do envio no item do Redis, e a Lambda comparar com o `.RET`.** Usar a hora do próprio servidor SFTP: o `putfo` com `confirm=True` devolve os atributos do arquivo enviado, com `st_mtime` (hoje a westworld descarta). A Lambda guarda o `stat` do `.RET`; se for mais antigo que o envio, não publica, loga e mantém `pendente`. Publica e guarda data e tamanho do `.RET` lido (base da proposta 9). Item sem data segue como hoje. No reenvio, o comunicador troca o item `pendente` anterior do lote pelo novo (um `pendente` por lote, com a data do último envio); senão o item antigo ainda aceita um `.RET` tardio do primeiro envio. Logar uma vez quando ignorar um `.RET`. Se a Genius não gerar `.RET` novo, o item fica `pendente` para sempre: precisa de alarme de "sem retorno há X horas" (N10). Não cobre A1.3, A2 nem `.RET` antigo reemitido depois do reenvio: todos são mais novos que o envio | cessão, westworld, listener | A1.2 em todos os modos | deploy da Lambda; G8, N10 |
| I3 | **Número novo a cada envio (modo gerado).** Tabela nova de envios (migration nova): lote, fundo, número, nome, data do envio. O número é reservado **uma vez por envio, no emissor**, e passado ao gerador para o header e o nome. Hoje o gerador busca o número duas vezes por geração (header, `cnab_500_liquidacao_genius.py:354`; nome, `:863`) e a rota de download também reserva | cessão, westworld (regex segue valendo) | A1.2, A1.3 e A2 no modo gerado | G4, N2, N3 |
| I4 | **Checar o destino antes do envio.** `stat` no `.REM` e no `.RET` com o nome que vai ser usado. Se existir: com I3, pular para o próximo número e logar; sem I3 ou no repasse, falhar com erro claro (lote, nome, data e tamanho do que existe), sem nova tentativa | cessão, westworld | detecta A1.2 e A2 quando o arquivo antigo ainda está no SFTP; B2, B3 | D12 |
| I5 | **Bloquear reenvio enquanto o lote espera retorno** nas rotas que enviam direto (`/liquidar`, `/cessionar`, `/automatica`): erro com a data do envio pendente | cessão | A1.3 em todos os modos | N4; muda rota existente, combinar com o Pietro (diretriz do `CLAUDE.md`) |
| I6 | **Arquivar o `.RET` depois de lido:** a Lambda move para uma pasta de processados, com data no nome, e a chave do S3 ganha a data (B4) | listener | A1.2 em todos os modos, sem depender de relógio; com a proposta 9, torna o A1.1 detectável | G5 |
| I7 | **Decidido (D17).** **Retorno direto no worker do Celery:** a Lambda publica a mensagem no formato de task do Celery numa fila do Celery, e o worker processa num processo filho, que não segura a conexão. O consumer pika deixa de atender o retorno. Junto, trava por lote no Redis e registro do arquivo já processado (caminho e ETag no `*_lote_raw`), para que repetir não reaplique recusas. Detalhe em "I7 em detalhe" | cessão (tasks novas), listener (formato da mensagem) | A3; B1 com a D14 | deploy da Lambda; `acks_late` × `consumer_timeout` |

Cobertura:

| | A1.1 | A1.2 | A1.3 | A2 |
|---|---|---|---|---|
| I1 | — | se o conteúdo mudou | se o conteúdo mudou | sim |
| I2 | base para detectar | sim | — | — |
| I3 (gerado) | — | sim | sim | sim |
| I4 | — | detecta | — | detecta |
| I5 | — | — | sim | — |
| I6 | com a proposta 9 | sim | — | — |
| I7 | — | evita reaplicar se o arquivo for o mesmo | — | — |

Ordem sugerida:

0. **Antes de tudo:** I7 (decidido na D17), que tira o laço de
   reprocessamento (A3), o problema de maior impacto medido em produção.
1. **Primeiro, sem depender da Genius nem de migration:** I1, I4 e I2, junto
   com os logs (proposta 1). Já impede aplicar retorno de outro lote e ler o
   `.RET` antigo, nos dois modos.
2. **Depois das respostas G4, N2 e N3:** I3, que corrige a raiz no modo gerado.
3. **Se a N4 for "sim":** I5, que é barata.
4. **Se a G5 permitir:** I6, junto com o I2 (decidido na D15).

No modo repasse, I3 não se aplica: a proteção fica com I1, I2/I6 e I5, e
renomear o arquivo depende da N12.

#### I7 em detalhe — retorno direto no worker do Celery (D17, 15/10/2026)

Hoje a Lambda publica um JSON simples numa fila lida pelo consumer pika, que
processa o arquivo dentro do callback. Com a D17:

```
Lambda ──mensagem no formato de task do Celery──► fila do Celery (ex.: liquidacao_lote_celery)
                                                      │
                          worker Celery: o processo principal mantém a conexão e o heartbeat
                                                      │
                          um processo filho executa processar_retorno_liquidacao(...)
```

O worker do Celery só aceita mensagens no protocolo de task dele: uma
mensagem sem o cabeçalho `task` é descartada (`Received and deleted unknown
message`). Por isso a Lambda precisa publicar neste formato (protocolo v2 do
Celery 5.2.2, a versão da cessão):

| Parte | Conteúdo |
|---|---|
| Exchange e routing key | exchange padrão (`''`) e routing key igual ao nome da fila, como a Lambda já faz com `RABBITMQ_EXCHANGE_*` vazio |
| Propriedades | `content_type = application/json`, `content_encoding = utf-8`, `correlation_id` = id da task, `delivery_mode = 2` (persistente) |
| Headers | `lang = py`, `task` = nome registrado da task, `id` = UUID novo, `root_id` = o mesmo id, `retries = 0`, `origin = genius-sftp-listener` |
| Corpo | `[[], {"liquidacao_lote_id": …, "path_s3": …, "etag": …, "ret_mtime": …, "ret_tamanho": …}, {"callbacks": null, "errbacks": null, "chain": null, "chord": null}]` |

`etag`, `ret_mtime` e `ret_tamanho` são novos. A Lambda já tem a resposta do
upload no S3 e o `stat` do SFTP; levar esses dados serve à idempotência e ao
filtro por data (D15).

Mudanças por repositório:

| Repositório | Mudança |
|---|---|
| platform-cessao | tasks novas para o retorno da liquidação e da cessão (nomes a definir), com a lógica que hoje está em `listener_*_retorno_adm`; trava por lote no Redis (`SET NX` com prazo acima da maior duração medida, 40 min); registro do arquivo processado (`path_s3` e `etag`) no `*_lote_raw`, para ignorar repetição com log; rota das tasks em `task_routes` |
| genius-sftp-listener | publicar no formato de task do Celery, por fluxo, controlado por variável (formato `json` ou `celery`, nome da task e fila), para trocar e voltar sem deploy de código |
| platform-cessao-argocd | só se a fila for dedicada: incluir a fila nos workers (`-Q` / `CELERY_WORKER_QUEUES`) |

Ordem de implantação:

1. Deploy da platform-cessao com as tasks registradas, ainda sem ninguém
   publicando nelas.
2. Ligar o formato `celery` na Lambda para a liquidação e acompanhar no
   Datadog.
3. Repetir para a cessão.
4. Com as filas `*_retorno_adm` vazias, tirar os dois listeners de retorno do
   consumer pika (`consumer/start.py`). Os outros 10 listeners continuam.

Volta: trocar a variável da Lambda para `json`. Os listeners antigos seguem
ativos até o passo 4.

O que não muda: a Lambda continua marcando o item como `arquivo_recebido` só
depois de publicar. A1 (ler o `.RET` antigo) e A2 (nome repetido) continuam e
dependem de I1–I6.

A definir:

- **`acks_late`.** Com ele, a mensagem só é confirmada no fim e volta se o
  worker morrer, o que é bom se a task for idempotente. Só que o RabbitMQ
  fecha entregas sem confirmação depois do `consumer_timeout` (30 min por
  padrão nas versões recentes), e o maior processamento medido levou 40 min.
  Conferir a versão e o `consumer_timeout` do broker; se preciso, aumentar
  para essa fila. Sem `acks_late`, a mensagem é confirmada ao chegar, e um
  worker que morre no meio perde o retorno (B1); a saída seria nova tentativa
  da própria task e alarme (D14).
- **Fila:** `liquidacao_lote_celery`, já consumida pelos workers e sem mudança
  no argocd, ou uma dedicada, que isola tasks de até 40 min das outras.
- **Nome das tasks** e se a cessão entra junto ou depois da liquidação.
- **Plano B:** se a mudança na Lambda travar, o repasse pelo consumer (o
  consumer cria a task e dá ack), que só muda a platform-cessao.

## Decisões

### Pendentes

Registradas em [decisions.md](../decisions.md).

- **D12 — Arquivo já existe no destino antes do envio:** (a) falhar com erro
  claro; (b) sobrescrever e logar o que existia; (c) apagar antes de enviar.
  Recomendação: (a), junto com a D13, para o reenvio nunca cair no mesmo nome.
  Depende de: N5, N7, G1, G3.
- **D13 — Nome do arquivo no reenvio:** (a) `NNN` novo a cada envio, tirado
  do mesmo contador do fundo e dia; (b) manter nome e data do primeiro envio;
  (c) sufixo de tentativa. Recomendação: (a). Exige migration nova
  (`liquidacao_lote_id` deixa de ser único, ou uma tabela de envios) e a
  Genius aceitar número novo para o mesmo lote. (c) depende do layout: a regex
  da westworld e os parsers da cessão só aceitam `_NNN.REM`. No modo repasse
  o nome vem do parceiro: trocar o `NNN` é renomear o arquivo repassado, e o
  `NNN` também vai no header quando o CNAB é gerado (`cnab_500_liquidacao_genius.py:354`).
  Depende de: N2, N3, N4, N12, G4.
- **D14 — Retorno que falha ao processar:** (a) fila de erro (DLQ) com
  alarme; (b) devolver o item ao Redis como `pendente`; (c) só alarme no
  Datadog e tratamento manual. Recomendação: (a); (b) entra em laço se o erro
  for permanente. Depende de: N11.
- **D16 — Retorno com linhas que não são do lote (I1):** (a) não aplicar nada
  e mandar o lote para revisão; (b) aplicar só as linhas que casam e logar o
  resto. Recomendação: (a). Linha de outro lote é sinal de colisão de nome, e
  aplicar parte esconde o problema. Depende de: N8.

### Tomadas

- **D17 — Retorno direto no worker do Celery (15/10/2026, Heitor):** para o
  A3, a Lambda publica a mensagem do retorno no formato de task do Celery,
  numa fila do Celery, e o worker processa. O consumer pika deixa de atender
  esse fluxo. Preferida ao repasse pelo consumer, que fica como plano B se a
  mudança na Lambda travar. Mantém a trava por lote e o registro do arquivo
  processado. Implementação: I7.
- **D15 — Filtro por data na Lambda (14/10/2026, Heitor):** opção (a). O item
  do Redis leva a data do envio (de preferência a hora do servidor SFTP,
  devolvida pelo `putfo`); a Lambda só publica `.RET` com data igual ou
  posterior ao envio, ignora e loga o mais antigo e mantém o item `pendente`.
  Junto, alarme de "sem retorno" (prazo da N10). Resolve o A1.2 nos dois
  modos; A1.3 e A2 ficam com I1, I3 e I5. (c) fica como complemento se a G5
  permitir. Premissa a confirmar: G8. Implementação: I2. Complemento
  (15/10/2026): o reenvio troca o item `pendente` anterior do lote pelo novo,
  para haver um só `pendente` por lote. Cobre o item 3 do Datadog (A1.2); não
  cobre A1.3, A2 nem A3.

## Perguntas de negócio

Para negócio e operação. Cada resposta fecha ou simplifica uma decisão; as
marcadas com ★ são as que mais mudam a implementação.

**Reenvio**

| # | Pergunta | Como a resposta muda a implementação | Destrava |
|---|---|---|---|
| N1 | Por que um lote é reenviado hoje: falha no envio, recusa da Genius, correção de conteúdo, retorno que não chegou? | Define quais casos o desenho precisa cobrir. Se for só falha de envio, quase nunca há `.RET` anterior (A1.2 fica raro) | escopo |
| N2 ★ | O reenvio pode ser feito em outro dia? Até quantos dias depois? | Se não: bloquear reenvio em outro dia elimina A2 sem migration. Se sim: nome único (D13) é obrigatório | D13 |
| N3 ★ | No reenvio, o conteúdo do lote pode mudar (pagamentos entram ou saem), ou é sempre o mesmo arquivo? | Se pode mudar, o reenvio é uma remessa nova: precisa de nome novo (A1.3) e talvez de lote novo | D13 |
| N4 ★ | Podemos bloquear o reenvio enquanto o lote espera o retorno do envio anterior? | Se sim, A1.3 some com uma regra na rota. Se não, só o nome único resolve | D13 |
| N5 | Para a Genius e para a operação, o reenvio **substitui** o envio anterior (o anterior deve ser ignorado) ou o complementa? | Se substitui: o `.REM`/`.RET` antigos podem ser descartados sem análise. Se complementa: os dois retornos precisam ser aplicados | D12, D15 |
| N6 | Quem dispara o reenvio e por qual caminho: tela, suporte, `/liquidar`, `/reenviar`, ou excluir o lote e fechar de novo? Deve existir um só? | Hoje `/liquidar` sempre reenvia e `/reenviar` só sem 200 anterior, os dois no **mesmo** lote (mesmo UUID e `NNN`). Excluir e fechar de novo cria lote novo, com UUID e `NNN` novos | escopo |
| N7 | Um envio pode falhar e esperar ação manual quando já existe arquivo com o mesmo nome no SFTP, ou nunca pode travar? | Se pode travar: D12 (a), falhar com erro claro. Se não: D12 (b), sobrescrever e logar | D12 |

**Retorno**

| # | Pergunta | Como a resposta muda a implementação | Destrava |
|---|---|---|---|
| N8 | Se chegarem dois retornos diferentes para o mesmo lote, qual vale: o primeiro, o último, ou alguém revisa? | Regra da Lambda ao ver um `.RET` novo ou alterado (A1.1, proposta 9) | D15, prop. 9 |
| N9 | Um lote já concluído pode ter a decisão alterada por um retorno posterior? | Se não: retorno tardio só gera alerta. Se sim: precisa de fluxo de estorno, fora do escopo atual | prop. 9 |
| N10 | Em quanto tempo a Genius deve devolver o retorno, e o que fazer quando ele não chega? | Prazo do alarme de "sem retorno" e de quando o reenvio é permitido | D14, N4 |
| N11 | Quando um retorno falha ao processar, quem precisa saber e em quanto tempo? Pode reprocessar sozinho? | DLQ com alarme ou reprocessamento automático | D14 |

**Nome do arquivo**

| # | Pergunta | Como a resposta muda a implementação | Destrava |
|---|---|---|---|
| N12 ★ | Nos produtos em que repassamos o arquivo do parceiro, podemos renomear o arquivo antes de enviar à Genius? O nome original é usado pelo parceiro, pela Genius ou pela operação (conciliação, tela da [tarefa 06](06-cnab-name-on-screen.md))? | Se não pode renomear, o modo repasse não tem nome único: o reenvio precisa ser bloqueado ou tratado à parte | D13, D4 |
| N13 | As mesmas regras valem para cessão e liquidação? A cessão é reenviada na prática? | Se a cessão não é reenviada, a correção começa pela liquidação | escopo |

## Perguntas para a Genius

| # | Pergunta | Destrava |
|---|---|---|
| G1 | Vocês apagam o `.REM` e o `.RET` depois de processar? Em quanto tempo? Apagam só o `.REM`? | D12, D15 |
| G2 | Vocês reemitem um `.RET` (correção) sem novo `.REM` nosso? Com o mesmo nome? Avisam por outro canal? | prop. 9, N8 |
| G3 | O servidor deixa sobrescrever um `.REM` existente? O que acontece com um `.REM` vazio ou incompleto? | D12, B3 |
| G4 | Aceitam um `NNN` novo para reenviar o mesmo lote? E um sufixo no nome? | D13 |
| G5 | Temos permissão para mover ou renomear o `.RET` depois de baixar? | I6 (complemento da D15) |
| G6 | O `.RET` é gravado de forma atômica (com outro nome e renomeado no fim), ou pode ser lido pela metade? | Lambda |
| G7 | O `.RET` repete algo do `.REM`, como a data de gravação ou o número do arquivo no header? | I1 (conferir também o envio, não só o lote) |
| G8 | A data de modificação do `.RET` no SFTP é a hora em que vocês o gravaram, ou pode vir preservada de outro lugar? | I2 (filtro por data) |

## Pontos para estressar

- As mudanças no envio da liquidação ficam na westworld (versão nova da lib e
  bump na cessão).
- **[H]** O diretório da rota da Lambda (`SFTP_ROUTES`) aceita `{yyyymmdd}`
  (`genius_sftp_listener.py:297-299`). Se a rota da Genius usar data, a busca
  só olha o diretório do dia, o que muda quais `.RET` antigos ela vê. Conferir
  a configuração da Lambda.
- Quantos produtos com fundo Genius usam cada modo (gerado ou repasse)?
  Define onde a D13 pesa mais. Medir por `produto_config.padrao_originador`,
  `produto_config.padrao_liquidacao` e `config_cnab_liquidacao_genius.gerar_cnab`
  no `config_extra` do produto-fundo.
- **[H]** No repasse da liquidação, o arquivo vem do proc_id do primeiro
  pagamento (`cnab_500_liquidacao_genius.py:66-67`). Se um proc_id virar mais
  de um lote (ver D3), os lotes podem repassar o mesmo arquivo com o mesmo
  nome.

- **[H]** Envio que falha do nosso lado com o arquivo já entregue (por
  exemplo, `timeout` depois da escrita): sem resposta 200 não há item no
  Redis, e o `.RET` que a Genius gerar não é lido. Um reenvio depois cai no
  A1.2.
- **[H]** A Lambda pode ler um `.RET` ainda sendo gravado pela Genius, se a
  gravação não for atômica (G6).

- **[H]** Os 12 listeners do consumer pika de cada pod usam a mesma conexão
  e o mesmo canal, sem `basic_qos`. Enquanto um retorno grande é processado,
  o pod deixa de atender as outras filas, e na queda da conexão as mensagens
  não confirmadas delas também voltam. Medir duplicidade em
  `callback_liquidacao` antes de concluir. A D17 tira o retorno desse canal.

## Validação

- Testes para: arquivo já existe, permissão negada, `size mismatch`, `.RET`
  antigo presente no reenvio, dois lotes do mesmo fundo com o mesmo `NNN`,
  retorno que falha ao processar. Hoje só existe teste para `SSHException`
  (`test/administradores/test_genius.py:904-958`).
- No Datadog, a falha final passa a aparecer com `lote_id` e `nome_arquivo`
  filtráveis.
- I7 (D17): testes para mensagem no formato do Celery com os argumentos
  esperados, mensagem repetida (a segunda é ignorada pelo registro do
  arquivo), duas tasks do mesmo lote ao mesmo tempo (a trava segura a
  segunda) e retorno com mais de 60 s de processamento sem reentrega. Em
  produção: `Retorno de liquidação Genius processado` uma vez por lote e por
  arquivo, e nenhum `Consumer Erro: Stream connection lost` ligado ao
  retorno.
- Medir o tamanho do problema antes de mudar: lotes com mais de um
  `processar_retorno_*` no raw, e itens `arquivo_recebido` acumulados no
  Redis da liquidação.

## Histórico

- 13/10/2026: problemas revisados no código. Confirmado o `NNN` repetido em
  outro dia (A2) e achada a entrega do retorno de um lote a outro. Entraram
  B1, B3–B6 e as propostas 7 e 8; decisões D12–D15 abertas.
- 13/10/2026: mapeados os dois modos de formar o nome (gerado e repasse) e a
  reserva do `NNN`. No repasse, todo reenvio repete o nome em qualquer dia.
- 13/10/2026: A1 e A2 separados (revisão do Heitor). A1 é o mesmo lote: o
  reenvio grava um `pendente` novo e reabre a busca do `.RET`. A2 é só entre
  lotes diferentes, no reenvio em outro dia.
- 14/10/2026: A1 dividido em três casos (proposta do Heitor): A1.1 `.RET`
  reemitido pela Genius sem reenvio nosso (não detectado), A1.2 reenvio com
  `.RET` antigo no SFTP, A1.3 reenvio antes do primeiro retorno. Entrou a
  proposta 9 para o A1.1.
- 14/10/2026: explicado no fluxo que o vínculo `.RET`↔lote é só o nome;
  linhas do tempo de A1.3 e A2; a nota sobre retorno com falha saiu do A1.1
  e foi para o B1.
- 14/10/2026: índice dos problemas; perguntas de negócio (N1–N13) e para a
  Genius (G1–G5), ligadas às decisões D12–D15.
- 14/10/2026: confirmado que o reenvio não cria lote (mesmo UUID, mesmo
  `NNN`); o caminho "excluir e fechar de novo" entrou na N6.
- 14/10/2026: mapeados os gatilhos do envio (rotas, agendamentos, callbacks)
  nos dois fluxos.
- 14/10/2026: mapeado o conteúdo do CNAB nos dois fluxos e modos; hipótese
  B13 registrada em bugs-found.md.
- 14/10/2026: revisado o mapeamento de casos do Heitor; a alternativa "voltar
  todos para pendente" foi registrada como não recomendada na proposta 9;
  entraram duas hipóteses (envio com falha aparente, `.RET` lido pela metade)
  e a pergunta G6.
- 14/10/2026: tabela do que muda e do que é reaproveitado no reenvio em outro
  dia (nome, header, corpo, Redis).
- 14/10/2026: desenho da correção de A1 e A2 (I1–I6) com cobertura e ordem;
  confirmado que o processamento não confere se as linhas são do lote (efeito
  do A2 passa a [C]); achada a reserva do `NNN` pela rota de download; D16 e
  G7 abertas.
- 14/10/2026: avaliado o filtro por data para o A1.2: resolve, com a data do
  envio no item (preferir a hora do servidor SFTP), a data do `.RET` confiável
  (G8) e alarme de "sem retorno" (N10). Não cobre A1.3 nem A2.
- 14/10/2026: D15 decidida pelo filtro por data (I2); movida para "Tomadas"
  aqui e em decisions.md.
- 15/10/2026: mapa do fluxo completo (cessão e liquidação, com as tabelas de
  cada etapa) em [08-analise-fluxo-genius.md](08-analise-fluxo-genius.md),
  base para avaliar o refactor.
- 15/10/2026: conflito do stash com o trabalho do Pietro resolvido; itens
  renumerados (B9 desta tarefa virou B13; D11–D15 viraram D12–D16).
- 15/10/2026: achados do Datadog na evidência de 15/10. Entraram o A3 (laço de
  reprocessamento por queda da conexão do consumer) e o I7; B3 confirmado
  como envio simultâneo do mesmo nome; corrigido o nome do consumer do
  RabbitMQ (roda no pod do worker, não no `busconsumer`).
- 15/10/2026: D17 tomada (Heitor): retorno direto no worker do Celery, com a
  Lambda publicando no formato de task. I7 refeito com o desenho, a ordem de
  implantação e o que falta definir.
- 15/10/2026: o filtro por data (D15) passa a cobrir o item 3 do Datadog
  (A1.2), com o complemento de manter um só item `pendente` por lote no
  reenvio.
