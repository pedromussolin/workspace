+++
card = "TS-5735"
type = "improvement"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-13
+++
# 06 — Nome do CNAB na tela

- **Status:** mapeado, aguardando D4.
- **Repos:** platform-cessao, BFF, front.
- **Decisão:** [D4](../decisions.md) — qual nome mostrar.

## Como está hoje

- **Aba de lotes fake:** nenhum nome e nenhum download de CNAB.
- **Aba de lotes reais:** ao abrir a linha, um botão por proc_id ("Baixar
  CNAB" ou "CNAB <8 primeiros caracteres>…")
  (`batch-detail.html:12-31`, `batch-detail.ts:62-79`).
- O nome **existe**, mas só é usado para salvar o arquivo baixado: vem do
  `Content-Disposition`, com fallback `CNAB_<id>.txt`
  (`manual-reconciliation.ts:798-821`).

## De onde vem o nome

TS-5214: `GET /liquidacao/cnab?proc_id=` (`cessao/api/liquidacao/viewer.py:461-474`)
→ `gerar_url_download_cnab` (`service.py:1629-1659`) → documento mais recente
em `liquidacao_processo_docs3` (`models.py:6891-6936`). Devolve
`{proc_id, filename, content_type, download_url, expires_at}`.

Limites:

- Esse documento é o **arquivo que o parceiro enviou**, e só é salvo quando a
  remessa entra por `POST /operacao/liquidacao/upload` com
  `salvar_input_file_liquidacao` no `config_extra` (`operacao/service.py:420-462`).
  Remessa que entra por JSON não tem documento.
- O **CNAB que mandamos à ADM** tem o nome calculado no envio
  (`emissores/liquidacao.py:76-86`) e não é salvo; no máximo aparece no
  `lote_raw` ou em `identificador_adm`.

## Opções (D4)

| Opção | Esforço | Observação |
|---|---|---|
| (a) Nome do arquivo do parceiro | baixo: incluir `filename` na listagem ou no detalhe | uma consulta extra por proc_id; vazio para remessas sem upload |
| (b) Nome do arquivo enviado à ADM | médio: passar a salvar o nome (e o arquivo) no envio | casa com a ata: "salvar o arquivo gerado num bucket S3" |
| (a) + (b) | — | a operação vê o que entrou e o que saiu |

## Pontos para estressar

- Qual nome a operação usa para conversar com a ADM? Provavelmente o de
  saída (b).
- Para a Genius, o nome de saída também é o que o listener usa para achar o
  `.RET` — salvar isso ajuda a [tarefa 08](08-genius-resend-and-logs.md).
- Mostrar no detalhe (ao abrir a linha) evita custo na listagem, que já é o
  gargalo ([tarefa 04](04-listing-performance.md)).

## Validação

- Remessa com upload mostra o nome; remessa sem upload mostra vazio sem erro.
- Se (b): o nome exibido é o mesmo que está no SFTP/S3 da ADM.
