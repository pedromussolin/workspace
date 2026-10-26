# Protótipo da réplica de leitura

Usado na [tarefa 01](../../tasks/01-read-replica.md). Não é o código
final: a versão do repo vai usar a config da cessão e testes sem banco.

## Como rodar os testes

A réplica é simulada por uma segunda conexão ao mesmo banco com
`default_transaction_read_only=on`, que recusa qualquer escrita.

Rodar a partir desta pasta (`attachments/replica`).

```bash
docker network create rwsplit-net
docker run -d --rm --name rwsplit-pg --network rwsplit-net \
  -e POSTGRES_USER=teste -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=cessao \
  postgres:13.10

docker run --rm --network rwsplit-net \
  -v "$PWD":/proto -w /proto \
  --entrypoint python platform-cessao_devcontainer-web:latest \
  -m pytest -q -p no:cacheprovider test_routing.py

docker rm -f rwsplit-pg && docker network rm rwsplit-net
```

Resultado em 05/10/2026: `15 passed`.
