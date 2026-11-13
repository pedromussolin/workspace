# 09 — Shared: calendário, agenda e aviso de falha

Status: a começar (13/11/2026)

## Objetivo

Dar ao apl-shared-service a noção de dia útil, na data de referência dos filtros e na agenda dos
fluxos, e avisar alguém quando uma execução falha.

Estimativa: 6 dias sem IA, 3 com IA.

## Contexto

- A agenda do shared-service só aceita cron de 5 campos (`src/shared/utils/cron.py`) e a data de
  referência do fluxo só anda em dias corridos [C].
- O orquestrador da EC2 tem recorrências por dia útil: dia útil, primeiro dia útil da semana,
  primeiro, quinto e último dia útil do mês [C]. Os relatórios usam D-1 útil e D-2 útil.
- Hoje, quando um script quebra, ele manda "Falha: <script>" ao responsável técnico [C]. Na tela,
  a falha só aparece na aba de execuções.

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| SS20 | Calendário: feriados por ano; dia útil anterior, N-ésimo e último dia útil do mês | 2 | 1 | D7 |
| SS21 | Agenda além do cron: só em dia útil, N-ésimo e último dia útil do mês | 3 | 1,5 | SS20 |
| SS22 | Aviso de falha: monitor no Datadog sobre as falhas de execução, ou e-mail pela conexão de e-mail | 1 | 0,5 | SS9 |
