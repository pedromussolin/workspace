# 12 — Migração em ondas e desligamento dos scripts

Status: a começar (13/11/2026)

## Objetivo

Montar os fluxos na tela, rodar cada onda em paralelo com os scripts da EC2 de automações e, quando
anexos e totais baterem, desligar a linha do script na agenda do orquestrador. Todo fluxo novo
nasce desligado.

Estimativa: 21,5 dias sem IA, 15 com IA. É a parte que a IA menos encurta: validação com dados
reais, paralelo em dias corridos e GMUD.

## Ondas

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| MG1 | URL e token dos serviços no Parameter Store, em homologação e produção; reiniciar a API e o worker do shared-service | 0,5 | 0,5 | SS1 |
| MG2 | Levar as listas da `mv_mail_list` para contatos e conexões de e-mail, direto no ambiente, sem arquivo versionado | 1,5 | 1 | SS13, SS14 |
| MG3 | Onda 1: Cessões diárias, Cessões mensais, Pendura a acrescer, Vencimentos atualizados | 3 | 2,5 | PC6, SS17, SS21, FE10 |
| MG4 | Onda 2: Relação de baixas (Vektor), Valores processados, Liquidações rejeitadas | 3 | 2,5 | MG3, PC6 |
| MG5 | Onda 3: Estoque (VLTS I), Base de operações e estoque (FBRX3) | 2 | 1,5 | DL6, MG3 |
| MG6 | Onda 4: Projeção de valor presente (VLTS I), Renegociações (Equimedix) | 4 | 2,5 | SS12, DL6 |
| MG7 | Valor conciliado e Resultado do processamento: **bloqueado** até a planilha analítica diária sair da pasta local da EC2 para um lugar que o shared-service leia, como um bucket | 4 | 3 | SS12 |
| MG8 | Desativar na `mv_schedule_reports` as linhas de cada onda validada | 1 | 0,5 | MG3 |
| MG9 | GMUDs dos deploys, uma por repositório e entrega | 2,5 | 1 | — |

## Como validar cada onda

- [ ] O fluxo roda desligado da agenda, pelo "rodar agora", com a mesma data do script.
- [ ] Anexo e totais comparados com o que o script mandou, por pelo menos uma semana corrida.
- [ ] Lista de destinatários conferida antes de ligar: a lista 39 é compartilhada entre o
      Vencimentos e um alerta interno [C].
- [ ] Só então o fluxo liga e a linha do script é desativada.

## Cuidados

- Comparações com dado real ficam na pasta local do projeto, fora do repositório.
- A consulta na réplica é só leitura e com trava.
