Status: em andamento
Data: 26/10/2026
Tags: artemis, v2, liquidacao, continuar

# Continuar em outro chat

Leia antes: o `CLAUDE.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisoes.md`. Os valores reais (hosts, usuários de banco, nomes por trás dos análogos) estão no arquivo local `~/.config/workspace/private/artemis-v2.md`.

Este arquivo foi montado em 26/10/2026 a partir do status do `README.md` e do histórico de commits da pasta. O que aqui não está escrito, o README e o histórico não dizem: confira antes de afirmar.

## Onde parei

O desenvolvimento da V2 começou em 05/10/2026. O escopo inicial é a tela de lotes de liquidação da platform-cessao, ou seja, o fechamento e a conciliação dos lotes, com a **performance** como ponto principal. A DBA revisa as queries; a parte de aplicação fica com a gente.

Situação das tarefas, pela tabela do `README.md` (última edição em 20/10):

| Tarefa | Situação |
|---|---|
| 01, réplica de leitura | concluída (PR #2628, 07/10; variável no Parameter Store), TS-5279 |
| 03, fechamento mais rápido e assíncrono | em produção (cessão 19/10, BFF e front 20/10), TS-5377; casos e plano de 20/10 em `tarefas/03-casos-pos-producao.md` |
| 12, lotes reais: buscar os lotes antes dos valores | **prioridade máxima** (14/10); mapeada; depende da D21 |
| 02, dois modos de fechamento (chave ou proc_id) | desenho alinhado |
| 04, 05, 06, 07 | mapeadas (a 04 espera a revisão da DBA; a 06 espera a decisão D4) |
| 08, Genius: reenvio e logs de erro | mapeada (revisada em 13/10); depende das D12 a D16 |
| 09, lote automático da Voltis | aguardando dados (configs do produto) |
| 10, fluxo da Genius para a Dayvale | aguardando descoberta (APIs da Dayvale e TS-5207) |
| 11, fechamento por horário de corte | ideia; depende da 02 e da D8 |

O que o histórico de commits registra depois disso (20 a 22/10):

- **20/10, TS-5383:**
  - a premissa da D21 e o SQL foram validados na réplica;
  - publicada só com código, e depois registrada em produção com as primeiras horas;
  - hotfix do detalhe do lote real pelo `lote_id`.
- **20/10, fase 1 da TS-5377 (robustez do fechamento):** a GMUD seguiu pelas releases de 20/10. Com a fase 1 em produção, a GMUD passou a ser retroativa.
- **21/10:** métricas de produção do fechamento e dos lotes reais.
- **22/10:** a GMUD da TS-5377 de 19/10 virou retroativa; a GMUD da fase 1 recebeu o uso em produção e o rollback; a GMUD da TS-5383 recebeu o hotfix do detalhe pelo `lote_id`; as prioridades das GMUDs e o ambiente da Viva na TS-5383 foram registrados; os testes de 22/10 das GMUDs da TS-5377 e da TS-5383 foram registrados.
- **Último commit da pasta (22/10):** status das GMUDs da TS-5377 sem pendência de teste.

As GMUDs estão em `gmud-ts-5377.md`, `gmud-ts-5377-fase1.md`, `gmud-ts-5383.md` e `gmud-ts-5279.md`.

## Branches e worktrees

O README e o histórico não registram branches nem worktrees. O código da V2 vive nos repositórios da empresa; confira lá a situação de cada branch antes de continuar uma tarefa. Todas as referências `arquivo:linha` do README valem para os commits de `origin/master` de 05/10/2026 listados nele.

## Próximo passo

1. Abrir `decisoes.md` e ver se a D21 já está tomada: a tarefa 12, a de prioridade máxima, depende dela, e a premissa dela foi validada na réplica em 20/10.
2. Ler `tarefas/12-lotes-reais-lotes-antes-dos-valores.md` e seguir a tarefa 12 a partir de "mapeada", sem abrir branch antes de estressar o desenho (é o objetivo desta pasta).
3. Atualizar o `README.md`: ele ainda não registra a TS-5383, as GMUDs nem o que mudou de 20 a 22/10. Fazer isso junto com o primeiro commit do dia, depois de conferir o estado real.
