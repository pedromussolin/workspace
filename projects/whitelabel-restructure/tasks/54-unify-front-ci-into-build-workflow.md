+++
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
repos = ["apl-credit-whitelabel"]
+++
# 54 — Unificar o CI do front no workflow de build

## Contexto

O front tem dois workflows do GitHub Actions que rodam lado a lado, sem um depender do outro:

- `.github/workflows/ci.yml`: o job `front-ci` (`validate.sh` e smoke), de 8 a 10 min.
- `.github/workflows/workflow.yml`: chama o workflow de build compartilhado, que gera e envia a
  imagem, de 18 a 23 min.

Por isso a imagem é gerada e enviada mesmo com o `front-ci` falhando. Na PR da
`release/20261124-sdbx`, o `front-ci` falhou e o build passou: a PR mostra dois resultados que se
contradizem.

Só o front. O BFF tem a mesma divisão e ganha um card próprio depois desta.

Fora do escopo: no workflow de build compartilhado, o job `build-push` espera só o `setup`, apesar
de o comentário dizer que depende dos testes. Ele fica em outro repositório e é usado por outros
times.

## Desenho combinado

- O `workflow.yml` ganha o job `front-ci`, com os passos de hoje do `ci.yml`, e o `ci.yml` sai.
- O job que chama o build compartilhado ganha `needs: front-ci`: a imagem só é gerada depois do
  `front-ci` aprovado. A execução passa de cerca de 22 para cerca de 30 min.

## A fazer antes de implementar

- Manter o nome do check `🧪 Tests & Smoke (front-ci)`: os rulesets da tarefa 53 podem exigir esse
  nome.
- Push das `release/**`: o build compartilhado envia imagem nessas branches. O job de build pula as
  `release/**`, ou o arquivo deixa de rodar no push delas (a PR já passa pelo CI). Assim continua
  valendo o commit `5ac9ea7c`: imagem só no push das branches de ambiente.
- `concurrency` com `cancel-in-progress` só nas PRs: no push das branches de ambiente, nunca
  interromper um envio de imagem.
- `permissions: contents: read` no job `front-ci`, não no arquivo inteiro: o build compartilhado
  pode precisar de mais.
- O CI de testes previsto na tarefa 16 (adiada) passa a partir deste arquivo único.

## Pronto quando

O front tem um só workflow. Numa PR com o `front-ci` falhando, o job de build não roda. No push da
sandbox, a imagem só é enviada depois do `front-ci` aprovado. O check `🧪 Tests & Smoke (front-ci)`
mantém o nome.
