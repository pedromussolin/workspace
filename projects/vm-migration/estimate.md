# Estimativa de horas — migração da VM até 24/11

Primeira versão (13/11/2026), para a entrega planejada para 24/11/2026. Conta as horas que
**faltam** nos dois épicos da VM (a EC2 de automações) e nos cards da Artemis V2 que travam o épico
da liquidação.

- **Horas com IA.** Os documentos de tarefa dão dias "com IA"; converto a 6 h produtivas por dia (só a conversão da estimativa; a capacidade real de
  cada pessoa está em "Capacidade e calendário").
  Card sem número: estimado pelo escopo, com a base na linha.
- **Pessoas:** o Pietro (dev-ae95329f82) e o outro dev (dev-a0893bc9a2).
- **Fica de fora:** a espera pela aprovação da GMUD (o registro de mudança exigido para subir em
  produção), por infraestrutura e pela DBA, o code review de terceiros e uma folga para imprevistos.
  A tarefa 02 recomenda +25% no envio de relatórios (426 h → ~533 h), fora dos totais abaixo.

## Resumo

| Épico | Pietro | Outro dev | Total |
|---|---|---|---|
| TS-5704 VM TELAS (envio de relatórios) | 0 | 426 | 426 |
| TS-5705 VM LIQUIDAÇÃO ML (desligar os jobs) | 34 | 0 | 34 |
| TS-5278 Artemis V2 (cards que travam a TS-5705) | 154 | 14 | 168 |
| **Total** | **188** | **440** | **628** |
| Capacidade de 16 a 24/11 | 52,8 | 36 | 88,8 |
| **Falta** | **135,2** | **404** | **539,2** |

## TS-5705 — VM LIQUIDAÇÃO ML (8 cards, Pietro)

Cada card tira um job da agenda da VM depois que a cessão passa a fazer o trabalho dele. O esforço é
pequeno; o prazo vem do card da Artemis que bloqueia e da janela de observação.

| Card | O quê | Horas | Depende de | Base |
|---|---|---|---|---|
| TS-5565 | Passagem da VM: agenda, credenciais fora da conta do Rafael, alertas | 6 | — | prazo era 13/11; o CONTINUE da Artemis pede confirmar se a passagem aconteceu. Libera a edição da agenda da VM, usada na TS-5570 |
| TS-5738 | Desligar o fechamento de lotes | 3 | TS-5570, TS-5568, TS-5737 | job fora, Datadog sem chamada da varredura e 5 dias úteis sem lote aberto parado nos produtos 4, 80, 81 e 1406 |
| TS-5750 | Desligar o ajuste de produto (`PATCH /produto`) | 4 | TS-5624 (relacionada) | o PATCH roda no início de cada job de carga, que fica na VM [C, levantamento de 05/11]: tirar a chamada dos scripts depois da tela de configuração subir |
| TS-5751 | Levantar e migrar os alertas do ML | 12 | — (relacionada à TS-5704) | 5 alertas e 8 e-mails no levantamento; supõe destino em monitor do Datadog ou no resumo diário da TS-5585. Se for para a tela de Envio de Relatórios, espera a TS-5704 |
| TS-5752 | Desligar a correção de aptos | 2 | TS-5151 | 0 chamadas do `DELETE` em 14 dias [C, Datadog]: tirar da agenda e do botão do portal |
| TS-5753 | Desligar a autocorreção do upload | 3 | TS-5737 | job fora e 5 dias úteis comparando arquivo e banco. [H] a autocorreção cobre a perda de linha na ingestão (upload assíncrono e parcial com HTTP 200); a TS-5737 cuida da esteira depois do fechamento, e nenhum card cobre essa perda |
| TS-5754 | Desligar a baixa de cancelamentos incompletos | 2 | TS-5748 | job fora e conferência na réplica (cópia somente leitura do banco de produção) |
| TS-5755 | Desligar a baixa de parcelas zeradas | 2 | TS-5749 | idem; hoje são ~65 mil pagamentos de R$ 0 em 30 dias |
| | **Total** | **34** | | |

## Cards da Artemis V2 que travam a TS-5705

Fonte: tabela "Estado por card" do `CONTINUE.md` da Artemis e `tasks/13-plan.md` (13/11). A tarefa
13 sobe numa **release única** (conjunto de branches que vai junto para produção), montada só com
todos os cards prontos e na ordem das migrations: TS-5583 → TS-5569 → TS-5570 → TS-5585 → TS-5567 →
TS-5572. O estado das PRs (pedidos de merge) não foi conferido. Com o código pronto, a IA encurta
pouco o que falta: é revisão, ambiente e acompanhamento.

### Implementados: falta PR, release e ligação (cadeia da TS-5738)

| Card | Falta | Horas | Quem | Depende de | Base |
|---|---|---|---|---|---|
| TS-5582 lotes vazios | PRs na release (cessão, BFF, front) | 1 | Pietro | — | branches enviadas; a TS-5737 depende dela em produção |
| TS-5583 duas colunas | PR; acerto do `down_revision` com a TS-5569 | 1,5 | Pietro | TS-5582 | as duas migrations partem do mesmo ponto |
| TS-5569 agendamentos em tabela | PR; conferências da sequência de deploy (beat e primeira execução) | 2 | Pietro | TS-5583 | 9 commits enviados sobre a TS-5583 |
| TS-5567 acúmulo natural | PRs nos 3 repos; variável de emergência no Parameter Store; Tarefa 18 (avulsos antes, evento de recuo depois, conferência com a operação) | 5 | Pietro | TS-5583 | Fase 1 e Fase 2 publicadas; a Tarefa 24 foi para a TS-5612 |
| TS-5570 horário por produto | PR (1); Tarefa 7: ligar os 6 produtos do ML (6) e os 5 da Voltis (2,5), auditoria e rodadas da VM (2,5) | 12 | Pietro | TS-5569, TS-5567, TS-5565; TS-5537 para o produto 15 | código completo; a ligação é operacional, com consultas na réplica |
| TS-5568 `POST /liquidacao/` | PR do BFF; chamadores no Datadog depois do deploy | 1,5 | Pietro | — | encolhida: a rota legada sai na TS-5612, depois da VM |
| TS-5624 tela de configuração do produto | validar a tela no navegador (3); PRs (1) | 4 | Pietro | TS-5583, TS-5569 | cessão, BFF e front publicados |
| — Release 1 (tarefa 13) | montar a release em cessão, BFF, front e shared (6); sandbox, o ambiente de testes (12); GMUD (2); deploy coordenado e acompanhamento no Datadog (6) | 26 | Pietro | todos acima | uma PR por repositório; Parameter Store antes do deploy |
| | **Subtotal** | **53** | | | |

### Mesma release, fora da cadeia

A release é única, então estes também a seguram.

| Card | Falta | Horas | Quem | Depende de | Base |
|---|---|---|---|---|---|
| TS-5584 Excel na shared | PR; snapshot OpenAPI no BFF | 2 | Pietro | — | 8 commits enviados |
| TS-5585 resumo diário e aviso | PR; definir o horário do job | 1,5 | Pietro | TS-5584 | o job nasce desligado |
| TS-5571 aprovação antes do corte | PR | 0,5 | Pietro | — | cessão e front publicados |
| TS-5572 automático no fluxo novo | PR (1); Tarefa 9: sandbox e ligação por produto (4) | 5 | Pietro | TS-5570 | código completo |
| TS-5596 limpeza dos vazios antigos | revisão da DBA (1); execução do runbook em produção (3) | 4 | Pietro | TS-5582 | script, simulação e runbook publicados |
| | **Subtotal** | **13** | | | |

### Ainda sem código

| Card | O quê | Horas | Quem | Depende de | Base |
|---|---|---|---|---|---|
| TS-5737 reentrega segura | passos 1 a 5 do plano em `14-phase0-design.md` (guarda por estado, teto e rodadas, trava, marca de envio, flags) e `kill -9` no sandbox | 24 | Pietro | TS-5582 em produção; decisões 1, 4 e 8 (D39); versão e `consumer_timeout` do RabbitMQ | 8 passos com testes descritos; comparado às tarefas 03 e 08 da Artemis |
| TS-5737 arquivo em blocos | passos 6 e 7 (iterador e 7 geradores, um commit por gerador); `EXPLAIN` com a DBA | 20 | Pietro | reentrega | o ML usa arquivo vazio (capitalis); o trecho vale para as outras administradoras |
| TS-5748 cancelados | a cessão fecha as parcelas restantes do contrato cancelado: desenho (3), código e testes (8), réplica e sandbox (5) | 16 | Pietro | — | card de 13/11 com uma linha de escopo; equivale ao job de cancelamentos incompletos. Confiança baixa |
| TS-5749 parcelas zeradas | baixa de R$ 0 das parcelas de valor zero, exceto NPL: desenho (4), código (9), validação (5) | 18 | Pietro | TS-5569 em produção | hoje o job lê o Lake; a cessão precisa achar as parcelas no próprio banco [H] e agendar pelo agendador da TS-5569. Confiança baixa |
| TS-5151 reprocessar pagamentos | rota que reprocessa pagamentos presos em `apto` (hoje apagar e reenviar pelo datawall): análise (3), rota e testes (7), sandbox (4) | 14 | outro dev | — | card em análise, sem escopo escrito. Confiança baixa |
| — Release 2 | 2a: a TS-5737 sozinha, como o desenho prevê (4); 2b: TS-5748, TS-5749 e TS-5151 (6). Montagem, sandbox, GMUD, deploy e acompanhamento | 10 | Pietro | cards acima | releases menores que a 1 |
| | **Subtotal** | **102** | | | |

Fora desta conta: TS-5612 (limpeza depois da VM, bloqueada pela TS-5738) e TS-5620 (saída do Atlas,
não da VM).

## TS-5704 — VM TELAS (31 cards, outro dev)

Base: mapa do board (dias com IA por card), que reparte a tabela da tarefa 02 (68 dias) e soma 3 dias
de palpite para o inventário: 71 dias, 426 h. A coluna "Itens" aponta os itens das tarefas 03 a 12.

| Card | O quê | Horas | Depende de | Itens |
|---|---|---|---|---|
| TS-5706 | Inventário da EC2 | 18 | — | palpite do mapa (3 dias); o arquivo não estima |
| TS-5717 | Decisões D5 a D8 | 15 | — | 2,5 dias; a D5 depende de infraestrutura |
| TS-5726 | Especificação do catálogo de consultas | 6 | TS-5717 | tarefa 03 |
| TS-5729 | Rota de contratos na cessão | 21 | TS-5726 | PC1, PC2, PC4, PC5 |
| TS-5730 | Rota de liquidação na cessão | 15 | TS-5726, TS-5729 | PC3 |
| TS-5731 | Validar as rotas contra o SQL dos scripts | 9 | TS-5729, TS-5730 | PC6 |
| TS-5742 | Data lake: lista opcional, VLTS I, prévia SQL | 12 | TS-5726 | DL1, DL2, DL5 |
| TS-5743 | Data lake: ramos Dayvale e FBRX3 | 15 | TS-5742 | DL3, DL4 |
| TS-5732 | Validar a posição de ativos | 6 | TS-5742, TS-5743 | DL6 |
| TS-5707 | Shared: conexão API e cliente HTTP | 15 | TS-5717, TS-5726 | SS1 a SS3 |
| TS-5708 | Shared: catálogo e prévias | 9 | TS-5726, TS-5707 | SS4, SS5 |
| TS-5709 | Shared: calendário e datas relativas | 12 | TS-5717 | SS20, SS8 |
| TS-5710 | Shared: Origem com consulta e Gerar Arquivo | 18 | TS-5707, TS-5708 | SS6, SS7, SS10 |
| TS-5711 | Shared: execução e ajustes de linhas | 18 | TS-5717, TS-5707, TS-5710 | SS9, SS11 |
| TS-5712 | Shared: regras nomeadas | 6 | TS-5711 | SS12 |
| TS-5713 | Shared: agenda por dia útil e aviso de falha | 12 | TS-5709, TS-5711 | SS21, SS22 |
| TS-5714 | Shared: conexão E-mail e contatos | 12 | TS-5717 | SS13, SS14 |
| TS-5715 | Shared: destinatários e envio pelo Graph | 15 | TS-5714 | SS15, SS16 |
| TS-5716 | Shared: destino e-mail no bloco e teste | 12 | TS-5710, TS-5715 | SS17 a SS19 |
| TS-5718 | BFF da tela | 15 | TS-5717, TS-5707, TS-5708, TS-5714 | BF1 a BF4 |
| TS-5719 | Front: conexões e Contatos | 27 | TS-5718 | FE1 a FE4 |
| TS-5720 | Front: Origem e prévias | 18 | TS-5718 | FE5, FE6 |
| TS-5721 | Front: editor, destino e-mail e agenda | 30 | TS-5713, TS-5719, TS-5720 | FE7 a FE10 |
| TS-5722 | URL e token no Parameter Store | 3 | TS-5707 | MG1 |
| TS-5723 | Listas de destinatários para contatos | 6 | TS-5714 | MG2 |
| TS-5724 | Onda 1 e desligamento das linhas | 18 | TS-5731, TS-5713, TS-5716, TS-5721, TS-5722, TS-5723 | MG3, MG8; paralelo de 1 semana ou mais |
| TS-5725 | Onda 2 | 15 | TS-5731, TS-5724 | MG4 |
| TS-5740 | Onda 3 | 9 | TS-5732, TS-5724 | MG5 |
| TS-5741 | Onda 4 | 15 | TS-5732, TS-5712, TS-5724 | MG6 |
| TS-5727 | Grupo bloqueado | 18 | TS-5712; planilha fora da pasta local da EC2 | MG7 |
| TS-5728 | GMUDs dos deploys | 6 | — | MG9 |
| | **Total** | **426** | | |

## Capacidade e calendário

- **Dias úteis de 16 a 24/11:** 16, 17, 18, 19, 23 e 24/11, seis dias. 20/11 é sexta-feira, feriado
  nacional da Consciência Negra.
- **Capacidade por semana:** Pietro, 44 h (segunda a sexta, 8,8 h por dia útil); o outro dev,
  estagiário, 6 h por dia útil (30 h); 74 h na dupla.
- **Capacidade de 16 a 24/11:** Pietro 8,8 h × 6 dias = 52,8 h; outro dev 6 h × 6 dias = 36 h;
  88,8 h na dupla.
- **Premissa:** nada reservado fora da migração, porque os documentos não reservam. Ficam fora
  cards abertos do Pietro sem ligação com a VM (TS-5620, TS-5566, TS-5573, TS-5733 a TS-5736) e a
  reorganização do board; se algum entrar na sprint, sai dessas 52,8 h. Para o outro dev também não
  há nada reservado nos documentos.
- **Depois de 24/11:** feriados de 25/12 e 01/01; sem recesso, férias nem Carnaval.

## Caminho crítico

Caminho crítico é a sequência de dependências que define a data mínima de entrega.

### Liquidação (TS-5705)

Ordem usada para o Pietro: TS-5565 → pré-produção da release 1 (40,5 h) → deploy → TS-5750 →
TS-5737 → release 2a → TS-5748 → TS-5749 → release 2b → TS-5751. Depois do deploy, a ligação dos
produtos e as conferências da release 1 ocupam ~2 h/dia por 9 dias úteis (19,5 h). Os desligamentos
entram quando o bloqueio chega à produção.

| Marco | Mais cedo | Por quê |
|---|---|---|
| TS-5565 | 16/11 | primeiro da fila |
| Release 1 em produção | 25/11 | 46,5 h antes (6 + 40,5), prontas em 24/11 (5,3 dias a 8,8 h); deploy no dia útil seguinte |
| TS-5750 | 26/11 | TS-5624 em produção |
| 6 produtos do ML ligados | 03/12 | um por dia útil a partir de 26/11 (581, 15, 4, 81, 1406, 80); o 15 depende da TS-5537 |
| Auditoria do último produto | 08/12 | 3 dias úteis |
| TS-5737 em produção (release 2a) | 07/12 | TS-5750 (4 h), TS-5737 (44 h) e release 2a (4 h) com 6,8 h/dia livres durante a ligação (8,8 − 2) |
| TS-5753 | 15/12 | job fora em 08/12 + 5 dias úteis de observação |
| TS-5738 | 16/12 | job fora em 09/12 (depois da auditoria) + 5 dias úteis de observação |
| Release 2b (TS-5748, TS-5749, TS-5151) | 14/12 | 40 h depois da 2a |
| TS-5752, TS-5754 e TS-5755 | 15/12 | job fora no dia útil seguinte |
| TS-5751 | 15/12 | sem bloqueio; último da fila |

Li "um produto por vez" (Tarefa 7 da TS-5570) como um por dia útil, com as auditorias sobrepostas. Se
for esperar a auditoria de cada produto antes do próximo, a ligação leva 18 dias úteis (até 21/12) e
a TS-5738 termina em 30/12.

### Relatórios (TS-5704)

O outro dev sozinho, a 6 h/dia (as datas não mudam com a correção de capacidade), com a TS-5151
primeiro (ela trava a TS-5752). O trecho do shared-service até a
Onda 1 é o caminho crítico, como na tarefa 02.

| Marco | Horas acumuladas | Mais cedo |
|---|---|---|
| TS-5151 | 14 | 18/11 |
| Tudo antes da Onda 1 (decisões, catálogo, rotas da cessão, shared, BFF, front, Parameter Store, listas) | 302 | 28/01/2027 |
| Onda 1 montada | 320 | 02/02/2027; desligamento a partir de 09/02/2027 (1 semana de paralelo) |
| Onda 2 | 335 | 04/02/2027, mais o paralelo |
| Data lake e Onda 3 | 377 | 15/02/2027 |
| Onda 4 | 398 | 19/02/2027 |
| Grupo bloqueado | 416 | 24/02/2027, só se a planilha sair da pasta local da EC2 |
| GMUDs e inventário | 440 | 02/03/2027 |

O inventário (TS-5706) não bloqueia nenhum card nos vínculos e vai por último nesta conta; se vier
antes, tudo anda 3 dias.

## Cabe até 24/11?

Não. A demanda é de 628 h e a capacidade, de 88,8 h: faltam 539,2 h (cabe ~14%).

- **Pietro:** 188 h para 52,8 h, faltam 135,2 h (cabe ~28%). Até 24/11 entram a TS-5565 e as 40,5 h
  de pré-produção da release 1 (46,5 h); sobram 6,3 h, sem uso porque os cards seguintes dependem
  da release em produção. A release 1 chega à produção em 25/11, no mais cedo, então nenhum job da
  liquidação sai da VM até 24/11. O primeiro é a TS-5750, em 26/11; o fechamento (TS-5738), em
  16/12; os 8 cards da TS-5705, em 16/12.
- **Outro dev:** 440 h para 36 h, faltam 404 h (cabe ~8%). Até 24/11 entram a TS-5151, a TS-5717
  (decisões D5 a D8) e a TS-5726 (catálogo). Nenhuma onda chega à produção: a Onda 1 desliga a
  partir de 09/02/2027 e o épico termina por volta de 02/03/2027.
- **Prazos que não dependem de horas:** a TS-5738 precisa de pelo menos 15 dias úteis depois da
  release 1 em produção (ligação, auditoria e 5 dias de observação). Com a release em produção já
  em 16/11, o job sairia em 01/12 e o card fecharia em 08/12. Com a capacidade corrigida, o prazo
  da TS-5738 (16/12) passa a ser definido por essa janela, não pelas horas. Cada onda de relatórios
  precisa de pelo menos 1 semana de paralelo com o script.

## O que mudou

- 13/11/2026: primeira versão.
- 13/11/2026: capacidade corrigida (usuário 44 h/semana; outro dev 6 h/dia, estagiário).
