# 06 — Shared: conexão de API e catálogo

Status: a começar (13/11/2026)

## Objetivo

No apl-shared-service, criar o tipo de conexão API (T12), o cliente HTTP dos microsserviços e o
catálogo fixo de consultas (T13), com as prévias de dados e de SQL que a tela vai mostrar.

Estimativa: 8 dias sem IA, 4 com IA.

## Contexto

- O tipo da conexão está fixo em SFTP, FTP, S3 e GCS
  (`src/modules/report_transfer/schemas/receivables.py:50`) [C].
- Os segredos de cada conexão são lidos por um prefixo de variável de ambiente
  (`src/shared/repository/file_storage.py:137`), e o "testar conexão" já lista as variáveis que
  faltam sem mostrar os valores [C].
- As variáveis vêm do Parameter Store pelo Guardian, só na inicialização do container (`entrypoint.sh`)
  [C]: um token novo só vale depois de reiniciar a API e o worker.
- O shared-service não chama nenhum outro microsserviço hoje [C].

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| SS1 | Tipo API: migration com o tipo e a coluna do serviço; prefixo conforme o tipo; o tipo passa a servir de origem | 2 | 1 | D5 |
| SS2 | Cliente HTTP: URL e token pelo prefixo, timeout, nova tentativa em erro 5xx, páginas; só endpoints do catálogo | 2 | 1 | SS1, 03 |
| SS3 | Testar conexão API: chama o health do serviço | 0,5 | 0,5 | SS2 |
| SS4 | Catálogo fixo: consultas, filtros, tipos de campo e opções por serviço, e o endpoint que a tela usa | 2 | 1 | 03 |
| SS5 | Prévia de dados e de SQL: repasse com data de referência e limite de linhas, só leitura | 1,5 | 0,5 | SS2, SS4 |

## Cuidados

- O usuário nunca digita URL nem caminho: o serviço vem do catálogo, para a tela não virar um
  proxy para qualquer endereço da rede interna.
- Não usar o identificador de acesso de parceiro como token: a conexão precisa de uma credencial
  de serviço própria.
