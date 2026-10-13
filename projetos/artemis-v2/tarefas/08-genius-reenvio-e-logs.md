# 08 — Genius: reenvio e logs de erro

- **Status:** mapeado.
- **Repos:** platform-cessao, westworld (envio da liquidação),
  genius-sftp-listener (Lambda do retorno).

## Item original

> Melhorar logs de erro na integração com a Genius (caso onde precisamos
> reprocessar — enviar novamente — e eles não haviam apagado os arquivos do
> SFTP)

O mapeamento mostrou que o problema vai além do log: há um risco de **ler o
retorno errado**.

## Fluxo atual

1. **Envio** (CNAB 500 da Genius via SFTP, paramiko `putfo`):
   - cessão: `ComunicadorGenius._enviar_arquivo`
     (`cessao/administradores/genius/comunicador.py:183-208`);
   - liquidação: `westworld/administrador/genius.py` (versão 1.36.5), chamada
     por `ComunicadorGenius.enviar_liquidacao` (`comunicador.py:699-727`).
   - Diretório: `produto_config.cessao_ftp` (padrão `inbox`).
   - Nome: `{cnpj}_{AAAAMMDD}_R_{NNN}.REM` (cessão) ou `_B_` (liquidação),
     com `NNN` sequencial por fundo por dia.
2. Depois do envio, o arquivo entra num set do Redis como pendente
   (`genius_lote_liquidacao_pendente` / `genius_lote_cessao_pendente`).
3. **Retorno:** a Lambda `genius-sftp-listener` roda a cada 15 min, deriva
   `X.RET` do `X.REM`, faz um `stat` no caminho esperado e, se existir, baixa,
   sobe no S3, publica no RabbitMQ e marca o item como recebido
   (`src/genius_sftp_listener.py:385-402`, `740-762`).
4. Os consumers da cessão processam o retorno (aceita/rejeita pagamentos,
   atualiza `liquidacao_lote_adm`).

## Problemas

### No envio

- **Ninguém verifica se o arquivo já existe** antes do `putfo`. Se o servidor
  aceita sobrescrever, o arquivo antigo some sem log; se recusa, o paramiko
  levanta `PermissionError`/`OSError("Failure")`/`size mismatch`, mensagens
  **sem o nome do arquivo**.
- Esses erros caem em `ERROS_CONEXAO = (SSHException, OSError, EOFError)`
  (`comunicador.py:60`) e são tratados como queda de conexão: 3 tentativas
  com logout/login, e **a última sobe sem log**.
- Os avisos usam f-string na mensagem e `extra.processo = os.getpid()` — o
  PID, não o proc_id. Faltam lote, proc_id, fundo, produto, tipo de envio e se
  é reenvio.
- No fim da esteira o erro vira `log.error("Erro na esteira", exc_info=True)`
  sem `extra`, e o log do banco guarda só `PermissionError: [Errno 13] ...`.
- Na liquidação, a exceção final diz "Erro ao enviar arquivo de
  cessao/pagamento" (`emissores/liquidacao.py:114-118`), mesmo sendo
  liquidação.

### No reenvio

- `POST /liquidacao/liquidar` sempre reenvia; `POST /liquidacao/reenviar` só
  reenvia se nenhum envio anterior teve status 200.
- **Mesmo dia:** o nome é idêntico ao do envio anterior → colide com o
  arquivo que a Genius não apagou.
- **Outro dia:** data nova com o `NNN` antigo, e o contador diário só conta
  linhas de hoje → **outro lote do mesmo fundo pode receber o mesmo `NNN`**.
  Dois lotes com o mesmo nome de arquivo.

### No retorno (o mais grave)

- O item do Redis não tem data de envio, e a Lambda descarta o resultado do
  `stat` (que tem data e tamanho).
- **Se o `.RET` do envio anterior ainda estiver no SFTP, a Lambda o consome
  como resposta do reenvio** e a cessão reaplica decisões antigas ao lote.
- O consumer sempre dá ack e o Redis já foi marcado: retorno que falha ao
  processar não é tentado de novo.

## Evidências (Datadog, 30 dias)

- 68 × `Falha ao enviar arquivo para o SFTP da genius`; 23 delas com
  `size mismatch in put! 0 != N` (08/09) — compatível com o servidor recusando
  sobrescrever.
- 3 × `Falha ao conectar no SFTP da genius: timed out`.
- 4.863 × `Retorno da Genius nao e utf-8 valido; lendo como cp1252` — ruído;
  deveria ser DEBUG.

## Proposta

1. **Logs como evento** (padrão do time): mensagem fixa, sem interpolar;
   `extra` com `lote_id`, `lote_identificador`, `proc_id`, `fundo_id`,
   `produto_id`, `nome_arquivo`, `caminho`, `tentativa`, `reenvio`,
   `tipo_envio`. Uma linha ERROR na falha final. Reaproveitar o helper
   `contexto`/`contexto_esteira` (`cessao/shared/saldo_liquidacao/log.py:12-38`).
2. **Antes do envio:** `stat` no destino; se existir, logar tamanho e data e
   decidir (sobrescrever conscientemente ou falhar com mensagem clara).
3. **Separar erro de permissão/arquivo de erro de conexão** — só o segundo
   merece nova tentativa.
4. **Data de envio no item do Redis** e a Lambda ignorar `.RET` mais antigo
   que o envio, logando quando isso acontecer.
5. **Nome no reenvio:** garantir unicidade (sequencial do lote reservado de
   forma estável, ou sufixo de tentativa se o layout da Genius permitir).
6. Rebaixar o aviso de utf-8 para DEBUG.

## Pontos para estressar

- O layout da Genius aceita outro nome de arquivo no reenvio? A westworld
  valida o padrão `[0-9A-Za-z]{14}_[0-9]{8}_[RB](?:_QI)?_[0-9]{3}\.REM`.
- Combinar com a Genius: eles apagam o `.REM`/`.RET` processado? Em quanto
  tempo?
- As mudanças no envio da liquidação ficam na westworld (versão nova da lib).

## Validação

- Testes para: arquivo já existe, permissão negada, `size mismatch`, `.RET`
  antigo presente no reenvio (hoje só existe teste para `SSHException`,
  `test/administradores/test_genius.py:904-958`).
- No Datadog, a falha final passa a aparecer com `lote_id` e `nome_arquivo`
  filtráveis.
