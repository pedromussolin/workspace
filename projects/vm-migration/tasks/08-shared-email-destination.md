# 08 — Shared: conexão de e-mail e envio

Status: a começar (13/11/2026)

## Objetivo

Criar o tipo de conexão E-mail, só de destino (T16), com remetente e destinatários escolhidos de
uma lista, e o envio com anexos. O conteúdo do envio (assunto, corpo, anexos e condições) fica no
bloco de destino, porque a mesma lista recebe relatórios diferentes.

Estimativa: 14 dias sem IA, 6,5 com IA.

## Contexto

- O módulo de e-mail que existe manda uma mensagem por pessoa, pelo Microsoft Graph, sem anexo e
  sem cópia [C]. Os scripts mandam uma mensagem só, com to, cc e cco, e anexos [C].
- O cliente do Graph já expande grupos do diretório da empresa (Entra ID) [C].
- Pelo que conheço da API do Graph, anexos acima de cerca de 3 MB pedem sessão de upload [H]:
  validar com um anexo grande em homologação.
- Hoje os destinatários vêm da tabela `mv_mail_list`, por número de relatório [C].

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| SS13 | Tipo E-mail: só destino; remetente e destinatários to, cc e cco numa tabela própria; prefixo opcional neste tipo | 2,5 | 1 | D6 |
| SS14 | Cadastro de contatos externos (nome, e-mail, empresa, ativo), com auditoria | 2 | 1 | D6 |
| SS15 | Resolução de destinatários: contatos, pessoas e grupos do diretório | 1,5 | 0,5 | SS13, SS14 |
| SS16 | Envio pelo Graph: mensagem única com to, cc e cco e anexos, com sessão de upload para os grandes | 3 | 2 | SS15 |
| SS17 | Destino e-mail no bloco: assunto e corpo em template (datas, totais, tabela), anexos; não enviar se vazio ou enviar variante | 2,5 | 1 | SS16, SS10 |
| SS18 | O envio vira item da execução; reenvio não duplica a mensagem | 1,5 | 0,5 | SS17 |
| SS19 | Testar conexão E-mail: remetente, endereços e um teste para quem testa | 1 | 0,5 | SS16 |

## Cuidados

- Endereço de e-mail é dado pessoal: fora de log e do Datadog.
- Cinco relatórios mandam uma variante quando não há dados ou quando há alerta [C]; o bloco de
  destino precisa das duas versões.
