# B. Automações do Rafael no Mercato Libero (liquidação)

Repo `~/repos/pldr-automations`, branch `master`, HEAD `930c24d` (04/11/2026, "calibragens"). Só leitura de código.
Convenção: **[C]** = visto no código; **[H]** = hipótese, com como validar. Abreviações: `AP` = `Mercato_Libero/Aplicações`, `EM` = `Mercato_Libero/Emails`, `AL` = `Mercato_Libero/Alertas`, `FE` = `Mercato_Libero/Ferramentas`.

## Conclusões (leia isto primeiro)

1. **O código não escreve no Postgres da cessão. Nenhuma vez.** Todo `consulta_cessao` usa o host da **réplica** (somente leitura) via `pd.read_sql_query` (`mv_lib/consultas.py:8-18`). Toda mudança de estado na cessão é por **API**: `PATCH /produto/<id>/`, upload CSV pelo datawall, `POST /liquidacao/`, `DELETE /liquidacao/pagamentos`, `PATCH /liquidacao/`. [C]
   O usuário `processo_mv_operacao` é o `Lake_User` (`orquestrador.py:26`), o mesmo nome serve ao Redshift e à réplica da cessão. A premissa "grava direto no banco" não aparece neste repo. Se existe, é em outro repo/host (ver item 4).
2. **Nenhum script lê as flags de fechamento** (`lote_liquidacao`, `fechar_lote_por_proc_id`, `acumula_liquidacoes`, `baixa_por_agendamento`): grep no repo inteiro dá zero. O "script externo que lê do banco" da migration de 27/10 **não está aqui** [C]. As regras do fechamento estão como constantes dentro do script (produtos, fundos, originadores, "lote pré-criado ou não").
3. **O fechamento é o único job que a Artemis V2 precisa absorver de verdade**; os demais "do sistema em diante" (autocorreção, aptos, zeradas, cancelamentos incompletos) contornam falhas de ingestão e lacunas de dado do cliente (item 5).
4. **A agenda não está no código**: fica na tabela `pldr_mv.mv_schedule_reports` (Redshift). Horários só aparecem em 3 comentários (item 1). Discrepância: o comentário do fechamento diz **4x por dia útil (16h, 17h, 18h, 20h45)**; o pedido fala em "1x/dia". Resolver com a consulta da seção 1.
5. **`PATCH /produto` só grava `json_padrao`, nunca "volta"** [C: `mv_lib/apis.py:79-100`]. Se o PATCH da cessão **substitui** `produto_config` em vez de mesclar, cada chamada (cerca de 6 por job, 466 em 14 dias) apaga as flags de fechamento. **[H] validar já no código da cessão** (é o maior risco para o fechamento automático).

## 1. Agenda (orquestrador)

`orquestrador.py` é um laço único em Python, na VM Windows, `while True` + `time.sleep(60)` (`:739,832`). **[C]**

- **Fonte da agenda:** `select * from pldr_mv.mv_schedule_reports where mvsr_bl_ativo = True` (`:789`), relida a cada 5 min (`CACHE_SCHEDULE_MINUTOS`, `:728,782`). Pontuais: join com `capitalis_science.mv_execucao_pontual` (`:790-794`); depois de disparar, `truncate` na tabela (`:829`).
- **Disparo:** por **igualdade exata** de recorrência + hora + minuto do relógio (`filtrar`, `:631-636`). Recorrências: `diario`, `dia_util`, `primeiro_dia_util_semana`, `primeiro_dia_util_mes`, `quinto_dia_util_mes`, `ultimo_dia_util_mes`, nome do dia da semana, `dia_N` (`:816-825`).
- **Dia útil:** calculado 1x por dia (`:760-778`) com `capitalis_analytics.dom_calendario` (fim de semana, feriado BR ou ANBIMA) no Redshift (`mv_lib/utilitario.py:7-14,84`). Se o Redshift cair nesse momento o laço quebra (`main()` reinicia 60 s depois, `:836-852`).
- **Execução:** `subprocess.Popen(["python", arquivo])`, 1 processo por job, log em arquivo, registro em `scheduler_logs` (Postgres local `mv`) com status `iniciado/ok/erro` (`:385-500,559-582`). Jobs do mesmo minuto rodam em paralelo.
- **Reexecução: não existe.** Falha do script = e-mail do próprio script + log "(Erro)"; ninguém reenfileira. [C]
- **Risco de minuto perdido [C no mecanismo, H na frequência]:** o ciclo é `trabalho + sleep(60)`, sem realinhar ao relógio. O trabalho (consulta ao Redshift a cada 5 min, `colher_jobs`) soma deriva; quando a deriva passa de 60 s, um minuto inteiro é pulado e o job agendado nele **não roda**. Validar: procurar em `scheduler_logs` dias úteis sem execução de um job diário.
- **Portal também dispara à mão** (sem passar pelo orquestrador): `/autocorrecao_mp` (`Projetos/0. Front/main.py:2914`), `/destravar_mp` = Correcao_Aptos (`:2905`), e-mails interno/externo (`:2889,2898`), baixa de contratos (`:3258-3272`, faz `ajuste_produtos_mp` + upload). Liga/desliga o envio ao MeLib mexendo na agenda (`:2923-2950`).

**Horários que o código revela (todos comentários):**

| Job | Horário | Fonte |
|---|---|---|
| `Fechamento_Lotes` | 16h, 17h, 18h, 20h45, dia útil | `AP/App_Liquidacao_Fechamento_Lotes.py:30` (comentário de 27/10) |
| `Zeradas` ("P6") | 16:00, dia útil | `EM/Mail_Valores_Processados.py:341` |
| `Mail_Valores_Diários` (envio ao MeLib) | 11h20 | `Projetos/0. Front/main.py:2923`, `static/modules/tesouraria.html:1219` |

**Para obter a agenda real (o Pietro roda; só leitura):**
```sql
select mvsr_id, mvsr_tx_nome_report, mvsr_tx_recorrencia, mvsr_nr_hora, mvsr_mr_minuto,
       mvsr_tx_caminho_script, mvsr_bl_ativo
from pldr_mv.mv_schedule_reports
where mvsr_tx_caminho_script like '%Mercato_Libero%' order by 4, 5;
```
Duração e falhas reais: view `public.vw_scheduler_execucoes` no Postgres local da VM, ou a tela "Monitor da MV" do portal de Operações.

### Jobs do Mercato Libero

Horário = "banco" quando só a tabela sabe. "Classe": a = chegada dos dados, b = do sistema em diante, c = relatório/alerta (item 5).

| Job (arquivo) | Horário | O que faz | Classe |
|---|---|---|---|
| `AP/App_Liquidacao_Download_Arquivos.py` | banco | Baixa por SFTP os "File4" de D-1 (NP, CITTI, NPL, GS), limpa pastas, e-mail "Confirmação Valores Files 4" | a |
| `AP/App_Liquidacao_Tratamento_Arquivos.py` | banco | xlsx bruto para CSV padrão (regra parcial x total), gera `Analitico_Diario/<data>_Analitico.xlsx` | a |
| `AP/App_Liquidacao_Ordinaria_Total.py` e `_Parcial.py` | banco | `ajuste_produtos_mp` + upload dos CSV `total`/`parcial` de D-1 (3 threads) | a |
| `AP/App_Liquidacao_Cancelamentos.py` | banco | `ajuste_produtos_mp` + upload dos CSV de cancelamento | a |
| `AP/App_Liquidacao_PPV.py` | banco | Baixa do S3 do MeLib o File4 PPV (olha 7 dias), e-mail e upload de cancelamento PPV | a |
| `AP/App_Liquidacao_Zeradas.py` | 16:00 (comentário) | Baixa de parcelas com valor nominal 0, a partir do Lake | b |
| `AP/App_Cancelamentos_Incompletos.py` | banco | Força baixa das parcelas abertas de contratos cancelados no dia | b |
| `AP/App_Liquidacao_Autocorrecao.py` | banco (+ botão no portal) | Compara arquivo x banco e reenvia o que não entrou | b |
| `AP/App_Correcao_Aptos.py` | banco/botão (Datadog: 0 DELETE em 14 dias) | Apaga e reenvia pagamentos presos em `apto` | b |
| `AP/App_Liquidacao_Fechamento_Lotes.py` | 16h/17h/18h/20h45 (comentário) | Fecha lotes (`POST /liquidacao/`) | b |
| `AP/App_Upload_Estoques.py` | banco (mensal) | Estoque do Lake para o S3 do MeLib | c (entrega ao cliente) |
| `EM/*` (8 e-mails), `AL/*` (5 alertas) | banco | Relatórios e checagens (item 5) | c |
| `FE/*` | manual | Baixas pontuais por planilha (`baixa_contabilidade_melib`), versão antiga do Correcao_Aptos, extração trimestral | b/manual |

## 2. Fechamento de lotes (`AP/App_Liquidacao_Fechamento_Lotes.py`, 324 linhas) [C]

**Passo a passo**
1. `checar_credenciais` (`:228`): exige `Lake_User`, `Platform_PWD`, `Token_MP_Operacional`; sem elas, para (não cai no modo cego).
2. Lê da **réplica** dois conjuntos, janela `JANELA_DIAS = 5` (`:36`):
   - `lotes_em_aberto` (`:51-106`): lotes em `liquidacao_lote_processo` com `data_envio_liquidacao is null`, `estado_atual = 'pendente'`, `produto_id in (4,15,80,81,581,1406)`, criados nos últimos 5 dias, **com pelo menos 1 pagamento** (`inner join liquidacao_pagamento`). Para cada lote pega o 1º e o último pagamento (menor/maior id) e deles, via `contrato_parcela` e `contrato`, o **originador** e o **fundo** (`par.fundo_id`). A origem vem de `liquidacao_pagamento.origem_pagamento`.
   - `pagamentos_sem_lote` (`:109-145`): `liquidacao_pagamento` com `liquidacao_lote_id is null` (via `liquidacao_processo`). Existe porque em 15 e 581 **o lote só nasce no POST** (comentário `:113-118`: 67 mil pagamentos ficaram 2 dias parados).
3. Monta combinações `(produto, fundo, origem, originador)`:
   - lote com pontas concordando: 1 combinação (`combinacoes_dos_lotes`, `:155-169`);
   - pontas divergentes ou pagamento sem lote: **varredura** = todos os fundos do produto x 13 originadores fixos (`:13,19-26,148-152`). Originadores `[4,5,6,16,17,19,72,79,80,82,589,1051,1117]`; fundos `{4:[3], 15:[3], 581:[3], 80:[36], 81:[36], 1406:[3,704]}`. Constantes no código: originador ou fundo novo exige edição.
   - banco fora do ar: **modo degradado** (`:172-179,248-252`): 91 chamadas cegas (7 pares produto/fundo x 13), **sem** `origem_pagamento`.
4. Chama, **sequencialmente**, `POST <cessão>/liquidacao/` com `{"produto_id", "originador_id", "fundo_id"[, "origem_pagamento"]}` e header de autorização com o token operacional (`:182-213`). `timeout=1800` s.
5. **Resposta:** só o status. `2xx` = fechado; `400` com o texto "nenhum pagamento apto para liquidar" = sem trabalho; qualquer outro = erro (não retenta). Corpo da resposta de sucesso é descartado. O ID do lote/de proc não é lido. [C]
6. **Tentativas:** 3, só para erro de transporte, espera 2/4 s (`:41,189-201`). Retentar após timeout de 1800 s pode duplicar o POST (a API estaria ainda processando): **[H]** validar se o POST é idempotente.
7. **Rechecagem** (`:277-301`): relê o que estava aberto no início; se sobrou, faz **segunda passada** varrendo todos os originadores; se ainda sobrar, manda e-mail de alerta (destinatários fixos no código, `:47-48`) e **termina com código 0** (o orquestrador registra "ok" mesmo com lote aberto).
8. **Não grava nada no banco** (nem antes nem depois); só POSTs. Falha não prevista: `notificar_falha` e re-raise (`:318-324`).
9. Hora: ver tabela do item 1 (4x/dia útil pelo comentário; o cron real está no banco).

Observação: `mv_lib/apis.py:103-123` ainda tem a versão antiga (`fechar_lote_liquidacao`: sem `fundo_id`, `while` infinito com `except` nu). Nenhum chamador no repo [C].

## 3. Toda escrita na cessão [C]

Nenhum INSERT/UPDATE/DELETE direto na cessão. Escritas por API (tokens por produto vêm de variável de ambiente; `mp_operacional` para PATCH/DELETE/POST de lote):

| # | Escrita | Onde | Estado mexido | Para quê | Quando |
|---|---|---|---|---|---|
| 1 | `PATCH /produto/{4,15,80,81,581,1406}/` `{"produto_config":{"padrao_liquidacao":"json_padrao"}}` | `mv_lib/apis.py:79-100` | **`produto_config.padrao_liquidacao`** (nunca reverte) | Garante o formato de CSV antes de cada upload (**[H]** porque outro fluxo o altera) | Início de Ordinaria Total/Parcial (`:39`), Cancelamentos (`:14`), PPV (`:84`), Autocorrecao (`:426`), Zeradas (`:47`, só se há base), Cancelamentos_Incompletos (`:313`), Tool CTT, baixa de contratos do portal (`main.py:3258`) |
| 2 | `POST datawall /csv/liquidacao` (multipart CSV) | `mv_lib/apis.py:55-76` | Cria `liquidacao_processo` (+ `liquidacao_raw`) de forma **assíncrona**; datawall = borda/WAF na frente da cessão. Equivale ao `POST /operacao/liquidacao/upload` **[H]** (conferir a rota no `platform-cessao`) | Subir baixas (`pag_parcial`, `baixa_sacado`, `cancelamento`) | Todos os jobs classe a e b acima. Devolve só o status HTTP; **200 não prova ingestão** (`Autocorrecao:60-95`) |
| 3 | `POST /liquidacao/` | `AP/...Fechamento_Lotes.py:191` | **`liquidacao_lote_processo.data_envio_liquidacao`**, estado do lote, associa pagamentos a lote (15/581) | Fechar lote | Fechamento (item 2) |
| 4 | `DELETE /liquidacao/pagamentos?produto_id=` `{"motivo":"falha_apto","pagamentos":[uuid...]}` (lotes de 500; `simular=true` é dry run) | `AP/App_Correcao_Aptos.py:44,111`; versão antiga `FE/Tool_Correcao_Aptos.py:9` (1 por uuid, sem o 1406) | **Apaga** `liquidacao_processo` em `apto` (janela: ontem, pulando fim de semana) e reenvia pelo datawall | Destravar pagamentos presos | Manual (portal `/destravar_mp`) ou agenda; 0 chamadas no Datadog em 14 dias |
| 5 | `PATCH /liquidacao/?uuid=` `{"data_envio_liquidacao": ...}` | `Projetos/0. Front/main.py:4917` (portal, "alteração de lotes") | **Data de envio do lote**, com token do Atlas do usuário | Corrigir a data de um lote à mão | Manual, não é o Rafael/orquestrador |
| 6 | Upload de baixa de contratos | `main.py:3258-3272`; `FE/Tool_Arquivos_One_off_CTT.py:77-87`, `_PMT.py` | Cria `liquidacao_processo` com `descricao_extrato = baixa_contabilidade_melib`, valor 0 | Baixa contábil por lista do MeLib | Manual |

- **Cessão de contrato:** não há chamada de cessão/aquisição de contrato nos scripts do ML (só liquidação) [C]. O monitor `AL/Alert_Monitor_Divergencias_Lake.py` apenas **lê** `data_cessao` para conferir.
- **`liquidacao_lote*`, `produto_config`:** mexidos só por #1 (produto_config) e #3 (lote). Flags de fechamento: **não lidas nem escritas** (só `padrao_liquidacao`).
- Escritas em outros bancos (não cessão): `scheduler_logs` no Postgres local (`orquestrador.py:568`); `truncate capitalis_science.mv_execucao_pontual` e UPDATE/INSERT em `pldr_mv.mv_schedule_reports` no Redshift (`orquestrador.py:829`, `main.py:1393-1450`); `executar_ocr` no banco do OCR (`mv_lib/consultas.py:60`), fora do ML.
- Outras pastas que chamam a cessão para gravar: só `Projetos/0. Front/main.py` (itens 5 e 6 e `:4707`, upload do Omnis) [C]. `Origem/`, `OCR/`, `01_monitores_clientes/` só leem a réplica (uma linha, não aprofundado).

## 4. Leituras que importam [C]

- **Flags de fechamento do produto: nenhuma leitura** (item "Conclusões" 2). O código replica a regra por constantes: "lote pré-criado" para 4/80/81/1406 e "lote nasce no POST" para 15/581 (`:113-118`), em vez de ler `lote_liquidacao`/similar. **[H]** essas constantes espelham as flags; validar comparando com `produto_config` desses produtos na réplica.
- **Quem lê as flags então?** **[H]** outro repo ou processo (cessão/Celery, ou job que lê `produto_config` direto do banco). Validar: (a) `grep` por `fechar_lote_por_proc_id` nos repos `platform-cessao`, `apl-shared-service`, `atlas`, `data-lake-api`; (b) Datadog DBM/log de conexão do usuário `processo_mv_operacao` na cessão.
- Leituras de estado de processo que decidem fluxo: `liquidacao_processo.estado_atual` (`apto`, `cadastrado`, `rejeitado`; `pendente` no lote) em Autocorrecao `:373`, Correcao_Aptos `:94`, Mail_Valores_Processados `:366`, Mail_Valores_Diários `:235-258`; `liquidacao_processo_log` (motivo de rejeição); `contrato_parcela.fechada` (Cancelamentos_Incompletos); Lake: `credit_portfolio.metrica` (valor nominal atual) em Zeradas e Estoques.
- Tabelas da cessão lidas: `liquidacao_processo`, `liquidacao_raw`, `liquidacao_pagamento`, `liquidacao_lote_processo`, `liquidacao_processo_log`, `contrato`, `contrato_parcela`, `contrato_processo`, `contrato_lote_processo`. Não lê `produto` nem `produto_config`.

## 5. Classificação e problema que cada job contorna

**(a) Chegada dos dados** (a Artemis V2 não precisa absorver; é a integração com o cliente): Download, Tratamento, Ordinaria Total/Parcial, Cancelamentos, PPV. A lógica de negócio **embutida** no Tratamento é a que mais importa guardar: classifica `baixa_sacado` x `pag_parcial` (PRINCIPAL+INTEREST juntos = baixa total; várias linhas por parcela = a última data é `baixa_sacado`), descarta valor negativo, fatia CSV em 15 mil linhas (`Tratamento:300-370`). Estado local da VM: pastas `C:/Mercato Pago/*` e `Analitico_Diario` (lidas pela Autocorreção e pelo e-mail de processamento), **fora do git**.

**(b) Do sistema em diante** (o que a Artemis V2 absorve ou torna desnecessário):

| Job | Problema da cessão que ele contorna |
|---|---|
| Fechamento de lotes | A cessão não fecha lote sozinha: precisa de POST por (produto, fundo, originador, origem); em 15/581 o lote só nasce no POST; já houve 798 lotes encalhados e 67 mil pagamentos parados 2 dias (`:30-36,113-118,277-281`). |
| Autocorrecao | Ingestão do upload é **assíncrona, em rajadas, e parcial** com HTTP 200 (19/10: 151 mil linhas, entraram 2,8%). O job compara o arquivo com `liquidacao_raw` (chave de 6 campos, multiconjunto), reenvia em lotes de 5.000, espera o banco parar de crescer. Também espera "nenhum `apto`" 10 consultas seguidas antes de começar (`:357-381`). Resolve **perda silenciosa de linha**. |
| Correcao_Aptos | Pagamentos que travam em `apto` (falha do processamento). Apaga e reenvia para reprocessar do zero. Janela "ontem". Destrutivo. Duplicidade só sai à mão (cita `App_Remover_Duplicidades`, que não está no repo). |
| Zeradas (P6, 16h) | ML não manda baixa de parcela de valor zero; ela fica aberta. O job gera baixa `parcelas_nulas` de valor 0 a partir do Lake (D-1 útil), exceto NPL. Cria cerca de 65 mil pagamentos de R$ 0 em 30 dias. |
| Cancelamentos_Incompletos | ML cancela o contrato inteiro mas manda **uma** baixa só; as outras parcelas ficam abertas para sempre. O job envia baixa 0 (`cancelamento_nao_baixado`) para parcelas `fechada = false` dos contratos cancelados **no dia** (`origem_pagamento ilike '%cancelamentos'`). Janela = dia corrente: o que falhar hoje não é retentado amanhã (`:82-86`). |
| `ajuste_produtos_mp` (PATCH) | Garante `json_padrao` antes de subir arquivos (**[H]**: outro fluxo muda o padrão; ver Conclusão 5). |
| Tools one-off | Baixa contábil (`baixa_contabilidade_melib`) por lista do cliente; ignorada nas contagens dos relatórios. |

**(c) Relatório, e-mail e alerta** (não absorver; reavaliar destinatário): `EM/Mail_Valores_Diários` (11h20, "Valor Conciliado", vai ao cliente), `Mail_Valores_Processados` (processamento diário; mostra "ainda não terminou" se há `apto`), `Mail_Reports_Final_do_Dia` (processados + rejeições do dia), `Mail_Valores_Dia_Anterior`, `Mail_Retiradas_BGT/Finvesta/Parcial` (valores a retirar das contas de conciliação por pagamento recusado), `Mail_Valores_Negativos`, `Mail_WO_Mensal`; `AL/Alert_Monitor_Divergencias_Lake` (liquidado e cessão: cessão x Lake x trusted, **por `data_envio_liquidacao` do lote**), `Alert_Impairments`, `Alert_Reprocessamentos`, `Alert_WO_Pendente/Nao_Feito`. Todos leem; nenhum escreve.

## 6. Quando os dados do dia ficam completos [H, a partir da agenda e de comentários]

- Arquivos são de **D-1** (`referencia - 1`, `Download:341`); baixados, tratados e subidos na manhã de D. Rodada de ~8h no Datadog = **[H]** Ordinaria/Cancelamentos (validar com a agenda).
- Marcos: envio ao MeLib **11h20** (usa `liquidacao_processo` em `cadastrado`/`rejeitado`, não lote); **Zeradas 16:00** é o último gerador de pagamento do dia; e-mail "Boa tarde... processados" e "Boa noite... rejeições" depois (`Final_do_Dia:95,101`).
- **Sinal de "completo" que o código já usa:** nenhum `liquidacao_processo` em `apto` por 10 consultas seguidas (Autocorrecao) e `pagamentos esperado = processado` (Analitico x banco). Ingestão pode ter até ~10 min entre rajadas (`Autocorrecao:75-87`).
- **Horário de corte sugerido:** não antes de **16h + tempo de ingestão das zeradas (>= ~16h30)**, e melhor como **condição** (sem `apto`, zeradas feitas) do que só horário; o 20h45 do 4o disparo sugere que a operação aceita fechar tarde para pegar atraso. **[H]** validar com `scheduler_logs`: hora de fim de cada job do dia e se o fechamento das 16h/17h costuma ter lote que só aparece na rodada seguinte.

## 7. Riscos

**Se a varredura de fechamento parar e o resto continuar** [C/H]
- Upload, autocorreção, zeradas continuam; pagamentos viram `cadastrado` mas **lotes ficam abertos** (`data_envio_liquidacao` nula) e, em 15/581, **pagamentos ficam sem lote** (cego para qualquer fila baseada em lote aberto).
- O rodapé do próprio e-mail de cancelamentos diz que **"a baixa só se confirma quando o lote é fechado"** (`App_Cancelamentos_Incompletos.py:270-271`).
- O alerta de "não fechou" mora **dentro** do job parado. Quem sobra é o `Alert_Monitor_Divergencias_Lake`, que compara por `data_envio_liquidacao`: acusa divergência cessão x Lake no dia seguinte **[H]**. Também sobra o status "ok" enganoso (fechamento sai com código 0 mesmo se sobrar lote).
- Acumula passivo além da janela de 5 dias (já havia 798 encalhados, o mais antigo de 2022): depois da janela o job não enxerga mais.

**Se a cessão passar a fechar sozinha com os scripts rodando**
1. **Fechamento do script vira inofensivo, não duplicado:** POST em lote já fechado responde `400 nenhum pagamento apto` e o script conta como "sem pagamento" (`:208-209`) [C]. Sem erro. Mas o alerta passa a não ter o que alertar.
2. **Corrida com ingestão em rajadas:** fechamento automático no meio da ingestão fecha lote parcial; o restante entra em lote novo (mesmo dia ou dia seguinte) **[H]**. Corte tem que esperar o dreno (sem `apto`).
3. **Reenvios depois do corte:** Autocorrecao, Correcao_Aptos (DELETE+reenvio) e Cancelamentos_Incompletos criam pagamentos depois do fechamento; viram lote do dia seguinte. O DELETE de pagamento já em lote fechado: comportamento da API não verificado **[H]**.
4. **Zeradas às 16h:** se o corte automático for antes, os R$ 0 caem no lote seguinte (sem efeito financeiro, mas aparecem como lote aberto).
5. **PATCH de produto vs flags novas:** ver Conclusão 5. Se o PATCH não for mesclado, o script apaga flags que a cessão passe a ler. Mitigação: validar o handler; ou parar o PATCH quando o `padrao_liquidacao` já for `json_padrao`.
6. **Não existe script esperando lote aberto** além do próprio Fechamento [C]; Cancelamentos_Incompletos depende de `fechada = false`/`baixados` do dia, não de lote.
7. **Duas fontes de verdade durante a transição:** manter o Fechamento ligado no início só como **auditor** (alerta se sobrar lote), não como executor, evita corrida e preserva o alerta.

**Handoff do Rafael (13/11)**
- Destinatários fixos no código: `Fechamento_Lotes.py:47-48`, `Autocorrecao` (~`:383,587` e outros), `mv_lib/mail.py:114-119` (`notificar_falha`). Alertas morrem quando a caixa dele sumir. Listas `mail.baixar_destinatarios(id)` vêm de `pldr_mv.mv_mail_list` (ids 2, 3, 10-15, 19, 21, 39, 42).
- Credenciais e tokens por produto (`Token_MP_*`, `Lake_*`, `Platform_PWD`) estão no registro `HKCU\Environment` do usuário da VM; chave SFTP e credencial do S3 do MeLib idem (CLAUDE.md do repo). Ponto único de falha: a VM e o laço único do orquestrador.
- Código só em `master` por cópia manual; a working copy da VM pode diferir do HEAD. Confirmar na VM antes de migrar.
