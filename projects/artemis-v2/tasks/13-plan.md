# Tarefa 13: fechamento de lotes de liquidação — plano de implementação (índice)

> Para quem executa: cada card tem o próprio plano, com tarefas em checkbox. Executar com
> superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans, um card por
> vez, cada um na própria branch `feature/TS-<id>-...`.

**Objetivo:** os lotes de liquidação do Mercato Libero e da Voltis fecham sozinhos, dentro da cessão,
por horário definido por produto, e a VM do Rafael pode ser desligada.

**Desenho:** `13-closing-design.md` (rascunho de 08/11).

**Por que vários planos:** o desenho cobre subsistemas independentes (cessão, shared, front, ETL).
Cada card vira um plano que entrega software testável sozinho; as interfaces entre eles estão nos
blocos "Interfaces" de cada plano.

## Ordem e dependências

```
                ┌─ TS-5583 duas colunas ─┐
TS-5582 vazios ─┤                        ├─ TS-5570 horário por produto ─ auditoria ─ varredura off ─ VM off
                ├─ TS-5567 acúmulo ──────┤                                      (com a TS-5565 feita)
                └─ TS-5569 scheduler ────┘
TS-5584 Excel na shared ─────────────────── TS-5585 resumo diário + aviso (depois de 5569, 5582, D27, D29)
TS-5571 aprovação antes do corte (independente)
TS-5568 POST /liquidacao/ no fluxo novo e TS-5572 automático no fluxo novo (depois da 5570)
Tela de configuração do produto (D30; depois de 5583 e 5569)
```

## Planos

| Card | Plano | Situação | Prazo do card |
|---|---|---|---|
| TS-5582 lotes vazios (guardas, BFF e front) | `13-plan-ts-5582.md` | branches enviadas (10/11), falta abrir as PRs; D26 = `descartado` | 10/11 |
| TS-5596 limpeza dos vazios antigos | Tarefas 6 a 8 de `13-plan-ts-5582.md` | card criado (10/11); depois da TS-5582 em produção; inclui fechar os vigentes dos vazios (ponto 5 da TS-5567) | 18/11 |
| TS-5583 duas colunas | `13-plan-ts-5583.md` | revisado (08/11) | 18/11 |
| TS-5567 acúmulo natural | `13-plan-ts-5567.md` | em replanejamento (10/11): lote aberto para todos (D34), proposta em `13-open-lot-design.md` | 18/11 |
| TS-5569 agendamentos em tabela | `13-plan-ts-5569.md` | reescrito (10/11): cron, histórico, migração das 6 rotinas adiada; 4 decisões novas | 18/11 |
| TS-5584 Excel na shared | `13-plan-ts-5584.md` | revisado (10/11); 2 decisões (teto do arquivo, compressão) | 20/11 |
| TS-5570 horário por produto | `13-plan-ts-5570.md` | revisado (10/11), alinhado à TS-5569 nova; decisões 1 a 6 e 3 novas em aberto | 20/11 |
| TS-5585 resumo diário e aviso | `13-plan-ts-5585.md` | revisado (10/11); 4 decisões (horário do job, dia de referência com o lote aberto, `descartado`, chave do aviso) | 27/11 |
| TS-5571 aprovação antes do corte | `13-plan-ts-5571.md` | revisado (10/11); 2 decisões (corrida com a rotina, `estado_anterior`) | 27/11 |
| Tela de configuração do produto | `13-plan-tela-config-produto.md` | escrito; revisão pausada | card a criar |
| TS-5568 `POST /liquidacao/` no fluxo novo | `13-plan-ts-5568.md` | escrito; revisão pausada | 18/11 |
| TS-5572 automático no fluxo novo | `13-plan-ts-5572.md` | escrito; revisão pausada | 04/12 |

Fora de código: TS-5565 (passagem com o Rafael até 13/11), TS-5566 (documentação), TS-5573
(investigação), mensagens E1 (ETL; perdeu prioridade com a D34) e E2 (negócio; enviada em 10/11, aguardando retorno).

## Ordem, dono de cada trecho e paralelismo

1. **TS-5582** (lotes vazios): independente; primeiro (prazo 10/11). Só as guardas, com BFF e front
   na mesma branch; a limpeza ficou na TS-5596.
2. **TS-5583** (duas colunas): migration, enums, `apply_closing_modality` (com o padrão seguro de
   produto novo), schemas, chave do lote fake pelo agrupamento, criação de lote sem origem e os
   leitores de gatilho e agrupamento. **Não mexe no fechamento de lote vigente.**
3. **TS-5567** (acúmulo natural): parte da TS-5583 mergeada; dona do acúmulo na chegada e dos três
   fechadores de vigente (`refact.py`, `POST /liquidacao/`, task agendada).
4. **TS-5569** (agendamentos em tabela): em paralelo às anteriores; acrescenta enums e modelos próprios
   e o decorator nas tasks (conflitos só textuais com 5582 e 5583).
5. **TS-5584** (Excel na shared): em paralelo, outro repositório; pode começar já.
6. Depois: TS-5570 (com a interface da 5569 aprovada), TS-5585, TS-5571, tela de configuração do
   produto (D30), TS-5568 e TS-5572.

Arquivos que mais de um plano altera (conferir na revisão de cada card): `cessao/tasks/liquidacao_lote.py`
(5582, 5583, 5567, 5569); `refact.py`, `repository.py`, `viewer.py` e `estados_liquidacao.py`
(5583 → 5567); `service.py` e `tasks/conciliacao_liquidacao.py` (5582, 5569); `enum.py` e `models.py`
(5583, 5569).

## Execução (decisão de 08/11)

Um subagente por tarefa e um revisor a cada tarefa, um card por vez. Os subagentes implementam e
testam; o commit sai depois da revisão do Pietro em cada card. Antes de executar, os planos passam
por revisão linha a linha contra o código (revisão de 08/11 no fim de cada plano).

## Limpeza pós-deploy

O que entra provisório na tarefa 13 e tem de sair depois que o novo estiver estável em produção
(lista de 10/11; cada item vira card quando chegar a hora):

- **Interruptor do lote aberto** (D34, decisão 8 da proposta): variável no Parameter Store que
  desliga a entrada no lote aberto. Remover a variável e o código do desvio.
- **Configuração de acúmulo** (`acumula_liquidacoes`): deixa de ter efeito com a D34 (item 6 da
  revisão de 08/11 da TS-5567).
- **Coluna antiga `modalidade_fechamento_lote` e flags legadas** (TS-5583): quando nada mais as ler.
- **Rotinas do beat fixo** (TS-5569, "Fora do escopo"): migrar as 6 para o agendador, inclusive a
  task legada do 1604, e apagar o `beat_schedule` fixo, as leituras do Parameter Store e as rotas
  legadas `/liquidacao/conciliacao/rotina/corte` e `/d0`.

## Decisões que travam algum passo

| Decisão | Trava |
|---|---|
| Arquitetura da TS-5569 (dia útil, disparo duplo) | TS-5569 a partir da Tarefa 2 e a TS-5570 |
| Formato da chave `por_chave_sem_origem` | TS-5583 (chave) e TS-5570 no 1043 |
