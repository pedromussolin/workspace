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
| TS-5582 lotes vazios | `13-plan-ts-5582.md` | revisado (08/11); tarefas da D26 marcadas | 10/11 |
| TS-5583 duas colunas | `13-plan-ts-5583.md` | revisado (08/11) | 18/11 |
| TS-5567 acúmulo natural | `13-plan-ts-5567.md` | revisado (08/11) | 18/11 |
| TS-5569 agendamentos em tabela | `13-plan-ts-5569.md` | revisado (08/11); Tarefa 1 = aprovar a arquitetura | 18/11 |
| TS-5584 Excel na shared | `13-plan-ts-5584.md` | escrito; revisão pausada | 20/11 |
| TS-5570 horário por produto | `13-plan-ts-5570.md` | escrito; revisão pausada (alinhar a `horarios`, lista) | 20/11 |
| TS-5585 resumo diário e aviso | `13-plan-ts-5585.md` | escrito; revisão pausada | 27/11 |
| TS-5571 aprovação antes do corte | `13-plan-ts-5571.md` | escrito; revisão pausada | 27/11 |
| Tela de configuração do produto | `13-plan-tela-config-produto.md` | escrito; revisão pausada | card a criar |
| TS-5568 `POST /liquidacao/` no fluxo novo | `13-plan-ts-5568.md` | escrito; revisão pausada | 18/11 |
| TS-5572 automático no fluxo novo | `13-plan-ts-5572.md` | escrito; revisão pausada | 04/12 |

Fora de código: TS-5565 (passagem com o Rafael até 13/11), TS-5566 (documentação), TS-5573
(investigação), mensagens E1 (ETL) e E2 (negócio).

## Ordem, dono de cada trecho e paralelismo

1. **TS-5582** (lotes vazios): independente; primeiro (prazo 10/11). As tarefas da D26 esperam a
   decisão.
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

## Decisões que travam algum passo

| Decisão | Trava |
|---|---|
| D26 destino do lote vazio | tarefas marcadas da TS-5582 e a limpeza |
| D27 destinatários, D29 fila manual no e-mail | ligar a TS-5585 |
| D30 onde fica a tela de configuração do produto | o plano da tela |
| Arquitetura da TS-5569 (dia útil, disparo duplo) | TS-5569 a partir da Tarefa 2 e a TS-5570 |
| Formato da chave `por_chave_sem_origem` | TS-5583 (chave) e TS-5570 no 1043 |
