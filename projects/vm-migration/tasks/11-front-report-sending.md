# 11 — Front da tela Envio de Relatórios

Status: a começar (13/11/2026)

## Objetivo

No portal (`apl-credit-whitelabel`), levar para a tela os cadastros de conexão API e E-mail, a
aba de contatos, o painel da Origem com consulta e prévias, os blocos novos do editor de fluxos e
a agenda por dia útil.

Estimativa: 27,5 dias sem IA, 12,5 com IA.

## Contexto

- O painel de propriedades do bloco tem os campos escritos à mão para cada tipo, e o campo
  "Bucket" só aparece para S3 e GCS (`flow-block-properties.component.ts`, `needsBucket`) [C]. A
  Origem por API segue o mesmo mecanismo, com mais campos, montados a partir do catálogo.
- O `app-select` escolhe um valor só [C]; os destinatários pedem um componente novo.
- O `code-block` de `shared/ui` já destaca SQL [C].
- As regras do repositório estão em `.ai/`: componente novo pela skill `new-component`, lista pela
  `new-page` (gera a tela com specs), `validate.sh` antes da PR.

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| FE1 | Cadastro de conexão API: serviço no lugar de bucket e pasta; teste com o health | 2 | 1 | BF2 |
| FE2 | Seleção múltipla com busca e chips em `shared/ui`, com spec e vitrine | 3 | 1,5 | — |
| FE3 | Cadastro de conexão E-mail: remetente e destinatários to, cc e cco | 2,5 | 1 | FE2, BF2, BF3 |
| FE4 | Aba Contatos, gerada pela `new-page` | 3 | 1 | BF2 |
| FE5 | Painel da Origem com API: consulta e filtros a partir do catálogo; limpa o que deixa de valer ao trocar o tipo da conexão | 4 | 2 | BF1 |
| FE6 | Prévias: primeiras linhas e contagem; SQL recolhível; data de referência e botão de gerar | 2,5 | 1 | FE5 |
| FE7 | Gerar Arquivo e ajustes no editor; paleta conforme a origem; aviso de bloco incompatível | 4 | 2 | FE5 |
| FE8 | Destino com conexão E-mail: assunto, corpo, anexos e condições | 2,5 | 1 | FE7, FE3 |
| FE9 | Agenda por dia útil no diálogo de agendamento | 2 | 1 | SS21 |
| FE10 | Dados fictícios no mock e no smoke; `validate.sh` sem falha nova | 2 | 1 | FE1 a FE9 |

## Cuidados

- Nada de e-mail, CNPJ ou nome de cliente real nos dados do mock, nas specs ou nos prints.
