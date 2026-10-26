# Artemis V2 — Estimativa de esforço e prazo (desenvolvimento x validação)

## Objetivo

Deixar o fechamento e a conciliação dos lotes de pagamento mais rápidos,
confiáveis e automáticos, e preparar a operação com a Dayvale.

## Entregas

Cada entrega separa o tempo de **desenvolvimento** do tempo de **validação e
liberação no ambiente real**. Só no ambiente real chegam as operações do dia a
dia, então é lá que se confirma o ganho, de forma gradual e acompanhada.

| # | Entrega | O que muda para o negócio | Desenvolvimento | Validação e liberação | Total | Depende de |
|---|---|---|---|---|---|---|
| 1 | Tela de lotes mais rápida | Tela carregando sem falhas (hoje ~1 em 5 consultas falha) | 16 | 12 | 28 | Infraestrutura |
| 2 | Fechamento fiel à tela | Fechar o lote fecha exatamente o que aparece na tela | 36 | 8 | 44 | Validação dos arquivos enviados aos administradores |
| 3 | Fechamento sem travas | Fechar e excluir sem erros por clique repetido | 32 | 6 | 38 | Entrega 2 |
| 4 | Consultas mais leves | Tela respondendo em segundos | 24 | 8 | 32 | DBA |
| 5 | Tipo de baixa legível | Tipo de baixa por nome, não por código | 6 | 2 | 8 | — |
| 6 | Nome do arquivo na tela | Saber de qual arquivo veio cada lote | 8 | 2 | 10 | Definição com a operação |
| 7 | Busca por contrato | Encontrar o lote pelo contrato | 12 | 4 | 16 | Definição com a operação |
| 8 | Reenvio para a Genius | Reenvios confiáveis e falhas rastreáveis | 24 | 12 | 36 | Infraestrutura |
| 9 | Lote automático da Voltis | Lotes automáticos fechando corretamente | 16 | 8 | 24 | Informações do produto (estimativa preliminar) |
| 10 | Operação com a Dayvale | Mesmo fluxo da Genius na Dayvale | 40 | 8 | 48 | Acessos e APIs da Dayvale (estimativa preliminar) |
| 11 | Fechamento por horário | Lotes do dia fechados num horário definido, com opção de antecipar | 32 | 12 | 44 | Regras por produto |
| 12 | Correções do levantamento | Filtros, paginação, cancelamentos e permissão corrigidos | 15 | 5 | 20 | — |
| | **Total** | | **261** | **87** | **348** | |

Cerca de 25% do esforço é validação e liberação no ambiente real. Com folga
para imprevistos e revisão, o total fica em torno de 380 horas.

## Prazo

Duas pessoas dedicadas, uma em tempo integral e outra em jornada de 6 h,
somam cerca de 10,5 horas produtivas por dia. O esforço sozinho leva quase
7 semanas. Com a dependência de outras equipes e parceiros, a estimativa é de
**8 a 9 semanas, com conclusão no início de dezembro**.

| Etapa | Entregas | Horas | Conclusão (só esforço) |
|---|---|---|---|
| 1 | 1, 2, 5 e 12 | 100 | 20/10 |
| 2 | 3, 4, 6, 7 e 11 | 140 | 05/11 |
| 3 | 8, 9 e 10 | 108 | 23/11 |

## Riscos

- **Dayvale (entrega 10):** depende de acessos e APIs do parceiro. Se não
  estiverem disponíveis até o fim da etapa 2, a entrega sai deste prazo e
  segue em paralelo, sem atrasar as demais.
- **Infraestrutura e DBA:** parte das entregas depende de configurações e
  revisões dessas equipes.
- **Voltis (entrega 9):** a causa ainda está em investigação; o esforço pode
  mudar.
