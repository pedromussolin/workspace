# Chamadas da EC2 de automações à cessão — 22/10 a 04/11/2026

Foto do que a máquina do Rafael Frankl chama na API da cessão, para começar o mapeamento da
[tarefa 13](../tasks/13-mercato-libero-settlement.md). Mostra só o que passa pela API: o que o
script grava direto no banco (usuário de banco próprio) ou busca em outros sistemas não aparece.

- Fonte: Datadog APM (spans indexados), `env:production`, serviço `platform-cessao`,
  `operation_name:flask.request`, IP de origem da EC2 de automações.
- Período: 14 dias, de 22/10 a 04/11/2026 (consulta feita em 04/11, ~23h UTC).
- Horários em UTC; Brasília é UTC−3.

## Resultado

**A máquina segue ativa [C]:** chamou a cessão todos os dias do período, inclusive em 04/11.

| Rota | Chamadas em 14 dias |
|---|---|
| `POST /liquidacao/` (fechar lotes) | 963 |
| `PATCH /produto/<id>/` (trocar a configuração do produto) | 466 |
| `PATCH /liquidacao/` | 67 |
| `POST /operacao/liquidacao/upload` | 15 |
| `GET` com 405 (método não aceito) | 10 |
| `DELETE /liquidacao/pagamentos` | 0 |

| Dia | Chamadas |
|---|---|
| dias úteis | 133 a 169 (253 na sexta, 30/10) |
| sábados, domingos e o feriado de 02/11 | 18 a 24 |

| Hora UTC (Brasília) | Chamadas em 14 dias |
|---|---|
| 11h (8h) | 252 |
| 12h a 18h (9h a 15h) | 132 no total |
| **19h (16h)** | **671** |
| **20h (17h)** | **409** |
| 21h (18h) | 57 |

## Leitura

- **O fechamento roda no fim da tarde, não à noite [C]:** o pico é 19h–20h UTC (16h–17h em
  Brasília), como a rodada única combinada em 13/10 ([evidência de 14/10](sweep-datadog-2026-10-14.md)).
  Se houver etapa noturna, ela não passa pela API: **[H]** leitura dos arquivos ou gravação direta
  no banco. Validar no crontab da máquina.
- **A rodada da manhã [H]:** 252 chamadas às 11h UTC (8h em Brasília), provavelmente a troca de
  configuração do produto (`PATCH /produto`) para subir os dados, a resposta 7a de 13/10. Conferir
  agrupando por rota e hora.
- **`PATCH /liquidacao/` [H]:** em 13/10 o Rafael disse que é outro processo (Omnis). Sai da mesma
  máquina; confirmar se também é dele e se entra na absorção.
- **Fins de semana [C]:** 18–24 chamadas por dia; **[H]** só a troca de configuração, que roda
  todo dia.

## Consultas para medir de novo

- Por rota: `service:platform-cessao env:production operation_name:flask.request
  @http.client_ip:<IP da EC2 de automações>`, COUNT agrupado por `resource_name`.
- Por hora: a mesma consulta, COUNT em série temporal de 1 h, somada por hora do dia (UTC).
- Próximo passo da medição: cruzar rota × hora, e ver no Database Monitoring do Datadog o que o
  usuário de banco próprio executa e quando (**[H]**: se o DBM estiver ligado na cessão).
