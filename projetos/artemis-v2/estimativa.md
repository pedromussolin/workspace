# Estimativa de horas — Artemis V2

Quarta versão (13/10/2026). Cada tarefa separa **desenvolvimento** (código e
testes automatizados, inclusive o merge na `-sdbx`) de **validação e
implantação** (testes em ambiente, liberação gradual em produção,
acompanhamento no Datadog, release e deploy). Ficam de fora o code review, a
homologação com a operação e uma folga para imprevistos.

| # | Tarefa | Descrição | Dev | Validação | Total | Impeditivos |
|---|---|---|---|---|---|---|
| 01 | [Réplica de leitura](tarefas/01-replica-de-leitura.md) | Conexão da réplica no init, roteamento de leitura e escrita, decorator nos GETs da tela, nova tentativa no primário em conflito, chave para desligar sem deploy | 16 | 12 | 28 | ID da tarefa; variável da réplica no Parameter Store (infra); D1. Só produção prova o ganho: liberar por endpoint, começando por `lotes/reais` |
| 02 | [Dois modos: chave ou proc_id](tarefas/02-fechar-lote-por-proc-id.md) | Fechamento por proc_id com UPDATE único, rota aceitando proc_id (compatível com o atlas), trava no Redis, validação do acúmulo; BFF e front | 36 | 8 | 44 | Conferir se os geradores de CNAB dependem de uma origem/originador por lote (4 h incluídas); D3 e D7; liberar produto a produto |
| 03 | [Fechamento: mais rápido, sem espera e sem 429](tarefas/03-fechamento-assincrono-e-429.md) | TS-5377. Levantamentos; regra única + UPDATE por grupo, medição; fechamento assíncrono (D10): fila dedicada, marca no Redis, polling na tela, sem 429. Detalhe na [análise](tarefas/03-analise-do-fechamento.md#1-estimativa-revisada) | 48 | 12 | 60 | D9 decidida; combinar o contrato da rota com Rafael Frankl (varredura do Mercato Libero). Índices adiados para [depois-da-v2.md](depois-da-v2.md). Opcionais fora do total: 59 h |
| 04 | [Performance das listagens](tarefas/04-performance-listagens.md) | Lotes irmãos sob demanda, métrica filtrada por `lote_id`, revisão do soft delete, medição | 24 | 8 | 32 | Revisão da DBA em várias rodadas, com `EXPLAIN` antes e depois |
| 05 | [Tipo de baixa](tarefas/05-tipo-de-baixa.md) | Nome do enum nos endpoints da tela, rótulos no front | 6 | 2 | 8 | Conferir o lote da Dots com dados reais |
| 06 | [Nome do CNAB na tela](tarefas/06-nome-do-cnab-na-tela.md) | Exibir o nome do arquivo do parceiro | 8 | 2 | 10 | D4; se for o arquivo enviado à ADM, sobe para ~22 h |
| 07 | [Filtro por contrato](tarefas/07-filtro-identificador-contrato.md) | Filtro nas listagens (cessão, BFF, front) e na coluna do lote real | 12 | 4 | 16 | D5; `EXPLAIN` em dados reais para garantir uso do índice |
| 08 | [Genius: reenvio e logs](tarefas/08-genius-reenvio-e-logs.md) | Logs como evento, checar arquivo existente, separar erro de permissão de erro de conexão, Lambda ignorando `.RET` antigo | 24 | 12 | 36 | Release da lib westworld e bump de versão; deploy da Lambda (infra); SFTP de homologação. Só produção reproduz o arquivo não apagado |
| 09 | [Lote automático da Voltis](tarefas/09-lote-automatico-voltis.md) | Investigar e corrigir o bug | 16 | 8 | 24 | Configs do produto e explicação do bug; provável dependência da 11. Baixa confiança |
| 10 | [Dayvale](tarefas/10-adm-dayvale.md) | Retorno da ADM, conciliação por saldo e extrato, logs; geradores já na branch TS-5207 | 40 | 8 | 48 | Acessos e APIs da Dayvale (Edu e Gus); merge da TS-5207; retorno formal do parceiro. Baixa confiança; pode chegar a ~72 h |
| 11 | [Fechamento por horário de corte](tarefas/11-fechamento-por-horario-de-corte.md) | Modo e horário por produto, rotina periódica, bypass no fechamento e na conciliação; BFF e front | 32 | 12 | 44 | D8; fuso e dia não útil; validar o corte exige esperar um ciclo real de operação |
| B | [Bugs B1–B5](bugs-encontrados.md) | Status múltiplo, paginação sem ordem, cancelamento gravado como liquidação, lote fake que não fecha, permissão no BFF | 15 | 5 | 20 | B3 pode exigir correção de dados antigos |

**Total: 370 horas** (277 de desenvolvimento e 93 de validação e implantação).
Com uma folga de ~10% para imprevistos e review: ~405 horas.

## Esforço x prazo

Capacidade considerada: duas pessoas dedicadas ao projeto, uma em tempo
integral (8 h/dia) e outra em estágio (6 h/dia): 14 h contratadas por dia.
Descontando reuniões, review e troca de contexto (~75% produtivo), são
**~10,5 h/dia**.

370 h ÷ 10,5 h/dia ≈ **35 dias úteis**, 7 semanas só de esforço,
descontando os feriados de 12/10, 02/11 e 20/11.

A espera por terceiros corre em paralelo, mas pode travar tarefas inteiras:

- **Infra:** variável da réplica, deploy da Lambda da Genius.
- **DBA:** revisão das queries, índices, Redis no teto de memória.
- **Parceiros externos:** acessos e APIs da Dayvale, retorno formal.

### Calendário proposto (a partir de 05/10/2026)

| Etapa | Tarefas | Horas | Acumulado | Fim (só esforço) | Depende de terceiros |
|---|---|---|---|---|---|
| 1 | 01, 02, 05, B | 100 | 100 | 20/10 | Infra (variável da réplica) |
| 2 | 03, 11, 04, 07, 06 | 162 | 262 | 09/11 | DBA (04) |
| 3 | 08, 09, 10 | 108 | 370 | 25/11 | Infra (Lambda), Dayvale (acessos e APIs) |

**Prazo realista: 8 a 9 semanas, com conclusão no início de dezembro.** A
tarefa 10 é a que mais pode escorregar: se os acessos não chegarem até o fim
da etapa 2, ela sai do prazo e vira uma entrega à parte.

## O que mudou desde a primeira versão

- 13/10: tarefa 03 vira TS-5377 e segue o `refact.py`; P1, P3 e P4 vão para
  `depois-da-v2.md` (70 h → 60 h; 380 h → 370 h).
- 13/10: P2 da tarefa 03 cortado (76 h → 70 h; 386 h → 380 h).
- 13/10: índices da tarefa 03 adiados para [depois-da-v2.md](depois-da-v2.md);
  03 de 88 h para 76 h (398 h → 386 h).
- 09/10: tarefa 03 de 38 h para 88 h (348 h → 398 h); D10 decidida pelo
  assíncrono (+20 h sobre o cenário síncrono). Entraram a otimização
  do fechamento (consultas, resposta, índices) e a regra única de elegibilidade;
  o estado `excluindo` virou opcional.

- 253 h → 348 h: +103 h, quase todas de validação e liberação em produção
  (só lá chegam operações reais), mais a coordenação com infra, DBA e parceiro.
- Tarefa 10 revisada para baixo em 8 h (de 56 para 48), a pedido do Pietro.
- Capacidade corrigida: de 2 × 6 h para 8 h + 6 h contratadas.
