+++
card = "TS-5712"
type = "feature"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5741", "TS-5727"]
blocked_by = ["TS-5711"]
docs = ["07-shared-query-source-and-file.md"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-25
+++
# 32 — Shared: regras nomeadas em código no catálogo, também sobre arquivos de entrada

## Contexto

Regras que não cabem em blocos, escritas em código e listadas no catálogo: projeção de valor presente, comparação de régua de PDD e semáforo.

As regras também passam a receber um arquivo de entrada (do SFTP ou de download), e não só o resultado de uma consulta:

- esperado do dia do Mercato Pago a partir dos File 4 do SFTP, com a classificação entre baixa total e parcial e o descarte de valores negativos, no lugar da planilha analítica que a VM grava;
- soma dos valores negativos dos File 4 do mês, por fundo (estornos);
- validação dos ganhos semanais da VLTS I contra a cessão, por contrato e parcela;
- filtro do cadastro de fundos da CVM pelos fundos geridos e não cancelados;
- projeção dos contratos que chegam a 360 dias de atraso no fim do mês (write-off mensal).

## Pronto quando

- Regras aparecem no catálogo e têm testes.
- O esperado calculado do File 4 bate com a planilha analítica da VM na mesma data.
