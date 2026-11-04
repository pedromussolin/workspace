# 13 — Liquidação do Mercato Libero: absorção pela V2

Status: a mapear (desde 04/11/2026). Por enquanto só o contexto; a implementação não está definida.

## Contexto

O Rafael Frankl está saindo da empresa. Ele roda sozinho, na EC2 de automações (servidor virtual
da AWS dedicado a ele, fora dos repositórios), o fluxo completo da liquidação do Mercato Libero,
o maior cliente: recebe os arquivos do Mercato Libero, transforma para o formato que a cessão
aceita, envia e fecha os lotes, entre outras etapas. O fluxo passa para o Pietro Nett,
possivelmente com apoio de outros devs, e é absorvido pela Artemis V2.

As telas e rotinas que ele fez para o time de operações, na mesma máquina, ficam em outro
projeto: `projects/operations-screens-migration/`. O inventário da máquina é um só e vive lá
(tarefa 01); esta tarefa usa a parte da liquidação.

## Objetivo

O fluxo da liquidação do Mercato Libero passa a ser mantido pelo time, num lugar versionado e
monitorado, sem depender da máquina nem dos acessos do Rafael, e sem parar a liquidação na troca.

## Por que é urgente

- **Sem a varredura, os lotes não fecham [C em 15/10, conferir de novo]:** nos produtos que
  acumulam liquidações (4, 80, 81 e 1406), só o `POST /liquidacao/` da varredura fecha os lotes
  vigentes, porque nenhum deles tem fechamento por agendamento
  ([evidência de 14/10](../evidence/sweep-datadog-2026-10-14.md#produtos-que-acumulam-liquidações-4-80-81-1406)).
  Se a máquina parar, o lote fica aberto e não vai para a ADM.
- **Precedente [C]:** em 14/10, quando a lista da varredura mudou, os produtos 15 e 581 ficaram
  sem fechamento e acumularam 67 mil pagamentos parados num dia
  ([alerta de 15/10](../evidence/sweep-datadog-2026-10-14.md#alerta-1510-produtos-15-e-581-sem-fechamento-desde-a-mudança)).
- **A máquina segue ativa [C]:** chamou a cessão todos os dias de 22/10 a 04/11
  ([evidência de 04/11](../evidence/mercato-libero-ec2-calls-2026-11-04.md)).

## O que já se sabe

Fontes: [respostas do Rafael em 13/10](03-closing-analysis.md#respostas-do-rafael-1310),
[evidência de 14/10](../evidence/sweep-datadog-2026-10-14.md) e
[evidência de 04/11](../evidence/mercato-libero-ec2-calls-2026-11-04.md).

| Etapa | O que se sabe | Status |
|---|---|---|
| Receber os arquivos do Mercato Libero | origem, formato e horário desconhecidos; não passa pela API da cessão | a mapear |
| Transformar para o formato da cessão | script na EC2; a entrada do Mercato Libero é "bem diferente dos outros produtos" (13/10) | a mapear |
| Trocar a configuração do produto | `PATCH /produto/<id>/` grava `padrao_liquidacao = json_padrao` para subir os dados e depois volta (processo legado, 13/10); 466 chamadas em 14 dias | **[C]** existe; detalhe a mapear |
| Enviar as liquidações | **[H]** `POST /operacao/liquidacao/upload` (15 em 14 dias) e/ou gravação direta no banco | a mapear |
| Gravar e ler direto no banco | usuário de banco próprio lê e grava no Postgres da cessão; tabelas em aberto desde 13/10 | a mapear |
| Fechar os lotes | `POST /liquidacao/` com produto, originador, fundo e origem, uma rodada por dia útil às 16h–17h de Brasília; produtos 4, 80, 81, 1406, 581 e 15 | **[C]**; lista de combinações a conferir |
| `PATCH /liquidacao/` | 67 em 14 dias; em 13/10 ele disse ser outro processo (Omnis) | confirmar se entra |
| Exceção: `DELETE /liquidacao/pagamentos` | quando a cessão engasga ou o contrato fica preso; nenhuma em 14 dias | a mapear o procedimento |

## O que levantar no mapeamento

- [ ] Data de saída do Rafael e até quando valem a máquina e os acessos dele.
- [ ] Sessão de passagem: ele roda o fluxo de um dia mostrando cada etapa.
- [ ] Agendamento (crontab) e horários reais de cada etapa, inclusive se há etapa à noite.
- [ ] Código: onde está, se está em algum git, linguagem e dependências.
- [ ] Origem dos arquivos do Mercato Libero, formato, volume e quem envia.
- [ ] Tabelas que o script lê e grava direto, e com que regra (pendência 7d de 13/10).
- [ ] Como ele percebe falha hoje, como reprocessa e o que faz nos casos de exceção.
- [ ] Produtos, originadores, fundos e origens: lista fixa ou descoberta a cada rodada.
- [ ] Quem do negócio depende do fluxo e quem é o contato do lado do Mercato Libero.
- [ ] Plano de contingência se a máquina parar antes da absorção.

Com isso, quebrar em tarefas (14, 15...) e registrar as decisões em `decisions.md`.
