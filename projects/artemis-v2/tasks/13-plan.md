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
| TS-5582 lotes vazios | `13-plan-ts-5582.md` | detalhado (08/11); tarefas da D26 marcadas | 10/11 |
| TS-5583 duas colunas | `13-plan-ts-5583.md` | detalhado (08/11) | 18/11 |
| TS-5567 acúmulo natural | `13-plan-ts-5567.md` | detalhado (08/11) | 18/11 |
| TS-5569 scheduler no banco | `13-plan-ts-5569.md` | detalhado (08/11); Tarefa 1 = aprovar a arquitetura | 18/11 |
| TS-5584 Excel na shared | `13-plan-ts-5584.md` | detalhado (08/11); pode começar já | 20/11 |
| TS-5570 horário por produto | a escrever | depende das interfaces da 5569 e da 5583 | 20/11 |
| TS-5585 resumo diário e aviso | a escrever | depende da 5584 e da 5569 | 27/11 |
| TS-5571 aprovação antes do corte | a escrever | independente | 27/11 |
| Tela de configuração do produto | a escrever | depende da D30, 5583 e 5569 | card a criar |
| TS-5568 e TS-5572 | a escrever | depois da 5570 | 18/11 e 04/12 |

Fora de código: TS-5565 (passagem com o Rafael até 13/11), TS-5566 (documentação), TS-5573
(investigação), mensagens E1 (ETL) e E2 (negócio).

## Paralelismo

- Podem andar juntos, em branches separadas: TS-5582, TS-5583, TS-5569 e TS-5584 (repos ou módulos
  diferentes). TS-5567 encosta na TS-5583 (a modalidade `acumulado`): começa depois da migração das
  colunas, ou na mesma janela com a TS-5583 mergeada antes.
- TS-5570 só começa com as interfaces da TS-5569 aprovadas (Tarefa 1 dela).

## Decisões que travam algum passo

| Decisão | Trava |
|---|---|
| D26 destino do lote vazio | tarefas marcadas da TS-5582 e a limpeza |
| D27 destinatários, D29 fila manual no e-mail | ligar a TS-5585 |
| D30 onde fica a tela de configuração do produto | o plano da tela |
| Arquitetura da TS-5569 (dia útil, disparo duplo) | TS-5569 a partir da Tarefa 2 e a TS-5570 |
| Formato da chave `por_chave_sem_origem` | TS-5583 (chave) e TS-5570 no 1043 |
