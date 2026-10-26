# Estresse do fechamento de lote fake — 20/10/2026

Simulação de pressão maior que a de produção sobre o fechamento novo. Compara
o código em produção (`master` `f19ef2cef`) com a fase 1 de robustez (branch
`fix/TS-5377-robustez-fechamento-lote`, ver
[tarefa 03](../tasks/03-async-closing-and-429.md)). Os dois rodam com
concorrência 16, o padrão desde 20/10.

## Conclusão

- **Sem falha de infraestrutura, as duas versões aguentam igual** a rajada 10×
  a de 20/10, cliques repetidos, produto que acumula e grupos de 1 milhão de
  pagamentos. Nenhuma fechou em dobro, criou lote vazio, quebrou a regra D9 ou
  mandou lote à esteira duas vezes.
- **Com falha, a `master` perde pedidos sem aviso e a branch não perde
  nenhum:**

  | Falha | Pedidos sumidos na `master` | Na branch |
  |---|---|---|
  | Trava externa | 34 de 50 | 0 |
  | Worker parado | 10 de 10 | 0 |
  | Worker morto | 1 de 5 | 0 |

  Na branch, cada pedido termina fechado ou com o motivo na tela.
- **O teste achou um defeito da própria fase 1, já corrigido:** com o Redis
  lento, a trava podia ser gravada depois do timeout do cliente e ficar órfã.
  Agora trava e pedido são gravados num script só.
- **Pontos para decidir:**
  - baixar a espera por trava de 60 s para ~30 s;
  - trocar a mensagem do clique que chega logo depois de um fechamento.

## Como foi feito

- **Ambiente local isolado:**
  - Postgres 13.10, Redis 6.2 e RabbitMQ 3.7;
  - worker Celery real na fila `fake_batch_closing_celery`, com concorrência
    16 e 3 GiB de memória, como o pod;
  - schema criado pelos models da cessão.
- **Massa sintética** de 3,34 milhões de pagamentos:
  - 400 linhas da tela, de 10 a 30 mil pagamentos;
  - 30 linhas de produto que acumula, com vigente aberto;
  - grupos de 100, 300 e 600 mil;
  - 2 milhões já fechados;
  - nas linhas da tela, 8% com cessão não concluída e 2% de contrato
    excluído, para conferir a D9.
- **Simulador:** threads que chamam as mesmas funções da rota
  (`request_fake_batch_closing`) e do status, como usuários na tela. Mede a
  rota, o tempo até o resultado e os pedidos que somem.
- **Conferência no fim de cada cenário:**
  - banco: lotes vazios, D9, lote com mais de uma linha, pagamentos fora das
    linhas pedidas;
  - fila da esteira: cada lote enviado exatamente uma vez;
  - Redis: travas que sobraram.
- **Falhas injetadas** só depois de o simulador avisar que a rajada começou:
  pausar o worker, matar o worker com `kill -9`, pausar o Redis e segurar
  pagamentos em outra transação.
- **Arquivos** em [attachments/stress](../attachments/stress) (`compose.yml`,
  `gen.sql`, `driver.py`, `run.sh`, `summary.py`). Credenciais só de teste
  local.

**Ressalvas:**
- **Velocidade do banco local:** é ~50× maior que a de produção (600 mil em
  ~12 s, contra ~1.000 pagamentos/s medidos em 20/10). Para simular o tempo de
  produção, um cenário roda com o limite de banco reduzido na mesma proporção
  (480 s → 10 s).
- **Carga concorrente:** não há outras cargas (esteira de liquidação,
  varredura, réplica). Contam os comportamentos e as proporções, não os tempos
  absolutos.
- **Índices:** só os declarados nos models; produção pode ter outros.

## Resultados (concorrência 16)

| Cenário | Pressão | Produção hoje (`master`) | Fase 1 (branch) |
|---|---|---|---|
| Rajada | 150 linhas em 30 s (10× 20/10), 154 mil pagamentos | 146 fechados, 4 sem pagamento apto; resultado p50 0,7 s | igual |
| Clique repetido | 20 cliques simultâneos × 10 linhas | 10 fechados, 190 recusados (409) | igual |
| Produto que acumula | 30 linhas com vigente aberto | 30 vigentes + 30 lotes novos, 60 envios únicos | igual |
| Grupos gigantes | 100, 300 e 600 mil | fecha os três | fecha os três |
| Gigantes em escala de produção | limite de banco 10 s (= 480 s) | não tem limite: em produção, 600 mil batem no soft limit (9 min), com "Erro inesperado" ou sem resultado | 100 e 300 mil fecham; 600 mil falham com "O fechamento passou do tempo limite…", sem nada pela metade |
| Trava externa | 20 linhas presas por 400 s (mais que as 16 vagas) no meio de 50 pedidos | 16 vagas presas por 400 s; **34 pedidos sumiram** sem aviso, inclusive as 30 linhas livres | 20 falham em ~60 s com "Os pagamentos desta linha estão em uso…"; 30 livres fecham (p50 47 s); tudo resolvido em 2 min |
| Worker parado | worker congelado por 6 min com 10 pedidos na fila | **10 sumiram** sem aviso | 10 mostram "O fechamento foi interrompido…" aos 5 min; mensagens antigas descartadas sem efeito |
| Worker morto | `kill -9` com um fechamento parado no UPDATE | **o pedido sumiu**; 490 pagamentos sem fechar e sem aviso | a mensagem volta à fila, o worker novo fecha a linha aos 46 s, uma vez só |
| Redis fora por 30 s | 40 pedidos, 25 durante a queda | a rota espera até 30 s (p50 25 s) e depois tudo passa; em produção isso prende processos da API (R13) | a rota falha em 2 s nos 25 pedidos da queda; com a correção, as 25 linhas mostram "interrompido" quando a trava vence, sem trava órfã |
| Status | 50 telas consultando a cada 1 s por 60 s | — | 3.000 consultas, p50 0,44 ms, máx. 24 ms (só a cessão) |

Os invariantes do banco e da esteira ficaram em zero em todos os cenários das
duas versões: nenhum lote vazio, nenhuma quebra da D9, nenhum lote com mais de
uma linha, nenhum envio duplicado ou faltando.

Concorrência 2 contra 16, na mesma rajada e com cache quente: 0,67 s e 0,69 s
(p50) até o resultado. Localmente as duas se equivalem. A primeira rodada com
2 (9,9 s) foi com cache frio, logo depois de gerar a massa, e não serve de
comparação.

## Achados

| # | Achado | Situação |
|---|---|---|
| E1 | **Trava órfã com o Redis lento.** O cliente desiste em 2 s, mas o Redis aplica o `SET` depois; a linha ficava "Fechando…" por 5 min, recusava cliques e voltava calada | **corrigido** na branch: trava e pedido num script Lua só (`_ACQUIRE_LOCK_AND_SAVE_REQUEST_LUA`). Validado em Redis real e no cenário |
| E2 | **Clique logo depois de um fechamento rápido** é aceito como pedido novo e troca "fechado" por "Nenhum pagamento apto" (o dado está certo) | proposta: se a linha foi fechada há pouco, responder "linha já fechada (lote X)" |
| E3 | **Espera por trava de 60 s prende as 16 vagas por 1 min** quando várias linhas estão presas; as livres esperam ~47 s | proposta: `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS` em ~30 s (em 20/10 a espera real foi de 25 s); é variável, sem deploy |
| E4 | **Redis fora:** a branch falha rápido e o usuário tenta de novo; a `master` espera e passa, mas segura processos da API | escolha consciente (decisão de 19/10, timeout curto no cliente Redis) |
| E5 | **Backend órfão depois do kill:** o UPDATE do worker morto continua no Postgres até liberar; a nova tentativa espera e fecha uma vez | comportamento correto; o `lock_timeout` limita a espera |

## Como repetir

```bash
cd attachments/stress   # copiar para fora do repo antes, por causa de results/ e logs/
# compose.yml: CODE_DIR, WW_DIR (westworld da versão do requirements) no .env
docker compose up -d db redis rabbit driver
docker compose exec -T driver sh -c "cd /app && python /estresse/schema.py"
docker compose exec -T db psql -U teste -d platform-cessao -q -f - < gen.sql
MASTER=<cópia da master> BRANCH=<cópia da branch> ./run.sh base-c16 escala-branch \
  trava16-branch trava16-master parado16-branch parado16-master \
  mortotrava-branch mortotrava-master redis16-branch redis16-master
python3 summary.py results
```
