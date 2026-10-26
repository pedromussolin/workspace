# Artemis V2 — workspace

Planejamento e acompanhamento da V2 do Projeto Artemis: fechamento e
conciliação dos lotes de liquidação da platform-cessao. Aqui ficam as
tarefas, as decisões, as evidências e as análises. O código vive nos
repositórios da empresa (ver "Repositórios"), não aqui.

As regras comuns (sigilo, mascaramento, commits, idioma e sincronização) estão no `CLAUDE.md`
da raiz do repositório, `~/repos/workspace/CLAUDE.md`. Aqui ficam só as regras específicas deste
projeto.

## Análogos deste projeto

Os nomes reais viram análogos, por exemplo "Mercato Libero", "Genius", "Dayvale" e "Rafael
Frankl", inclusive em nomes de arquivo, âncoras e caminhos de código citados. Protótipos próprios
e genéricos em `anexos/` são permitidos, com credenciais só de teste local.

## Valores reais fora do repo

Hosts, IPs, usuários de banco, variáveis do Parameter Store e a tabela de
nomes reais × análogos ficam no arquivo local
`~/.config/workspace/private/artemis-v2.md`, fora do controle de versão. Ler
esse arquivo quando um documento daqui falar em "host da réplica", "EC2 de
automações", "usuário de banco próprio" ou usar um nome análogo. Valor
sensível novo vai para lá, e aqui entra só a referência genérica.

## Estrutura

| Arquivo | Para que serve |
|---|---|
| `README.md` | visão geral, lista de tarefas, fases e glossário |
| `decisoes.md` | decisões pendentes e tomadas, com dono, data e motivo |
| `estimativa.md` | horas por tarefa, capacidade e calendário |
| `tarefas/NN-*.md` | uma tarefa por arquivo; análises longas em `NN-analise-*.md` |
| `evidencias/` | números de produção (Datadog) com data e as consultas para medir de novo |
| `bugs-encontrados.md` | bugs achados que ainda não viraram tarefa (B1, B2...) |
| `depois-da-v2.md` | melhorias adiadas para depois da V2 |
| `anexos/` | SQL e protótipos citados nas tarefas |

## Como escrever

- PT-BR, enxuto: conclusão primeiro, depois o porquê em poucos pontos.
  Explicar todo termo técnico na primeira vez que aparece.
- Separar o comprovado da hipótese: **[C]** (visto no código ou no Datadog) e
  **[H]** (hipótese, com o caminho para validar).
- Citar código como `caminho/arquivo.py:linha` e dizer contra qual commit as
  linhas valem.
- Número de produção sempre com período, fonte e a consulta para repetir a
  medição. Durações do Datadog vêm em nanossegundos.
- Sem número inventado: quando faltar métrica, dizer como obtê-la.

## Como manter

- **Decisão tomada:** mover de "Pendentes" para "Tomadas" em `decisoes.md`,
  com data, quem decidiu e o motivo. Atualizar as tarefas que a citam.
- **Escopo mudou:** atualizar a tarefa, a análise e `estimativa.md` (linha da
  tarefa, totais, calendário e "O que mudou").
- **Item adiado:** levar para `depois-da-v2.md`, com origem, data e o que falta
  para retomar.
- **Bug achado:** registrar em `bugs-encontrados.md` com onde, efeito, como
  foi confirmado, como validar e a correção proposta.
- Antes de afirmar algo sobre o comportamento do sistema, conferir no código
  atual ou no Datadog.

## Repositórios envolvidos

| Repositório | Papel |
|---|---|
| platform-cessao | API, workers Celery e banco da cessão; onde está o fechamento |
| apl-credit-whitelabel-api | BFF do portal (FastAPI) |
| apl-credit-whitelabel | front do portal (Angular) |
| platform-cessao-argocd | deploy (workers, filas, réplicas) |
| atlas / fetch-api | API GraphQL legada que também fecha lote |

As regras de git dos repos da empresa (branch e commit com o ID `TS-…`, sem `Co-Authored-By`,
replicar na branch `-sdbx`) estão no `~/repos/CLAUDE.md` e valem só para eles. Neste repo valem as
regras do `CLAUDE.md` da raiz.

## Diretrizes de desenvolvimento do projeto

- **Código novo da liquidação** vai em `cessao/api/liquidacao/refact.py`
  (`RefactLiquidacaoService`, `RefactLiquidacaoRepository`), usado primeiro
  só pelos fluxos do front (whitelabel), em rotas próprias. Os fluxos
  existentes não mudam até a substituição.
- **Fechamento de lote:** assíncrono (D10), com marca no Redis por linha da
  tela e polling no front; a proteção contra fechar em dobro é o
  `WHERE liquidacao_lote_id IS NULL`. Ver `tarefas/03-*`.
- **Regra para entrar em lote (D9):** exige a cessão do contrato `cadastrado`
  (revisão de 14/10) e usa o produto da liquidação.
- **Logs como eventos:** mensagem fixa, dimensões no `extra`, um INFO por
  execução.
- **Migrations:** nunca alterar uma existente; mudança vai em migration nova.
- **Varredura do Mercato Libero:** chama a mesma rota por fora e grava direto
  no banco. Mudança de regra ou de estado na liquidação deve ser combinada
  com o dono dela.
