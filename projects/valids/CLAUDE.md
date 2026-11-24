Status: em andamento
Data: 03/11/2026
Tags: valids, pdd, ecl, controladoria, lake

# valids: regras do projeto

Planejamento e acompanhamento da feature de VALIDs: o dashboard de PDD da controladoria, a tela
"Conciliação de Estoques e VALIDs" (`features/controllership/pdd`) do portal, que reproduz o
protótipo `dashboard_fundos.html`. Aqui ficam as tarefas, as decisões, as evidências e as análises.
O código vive nos repositórios da empresa (ver "Repositórios envolvidos"), não aqui.

Não é tarefa do Artemis: nada daqui vai para `projects/artemis-v2`, e as decisões daqui não usam a
numeração de lá.

As regras comuns (sigilo, mascaramento, commits, idioma e sincronização) estão no `CLAUDE.md` da
raiz do repositório; as regras de trabalho, em `instructions/`. Aqui ficam só as regras específicas
deste projeto.

## Análogos e dados deste projeto

- Administradores pelo **análogo**, o mesmo do `projects/artemis-v2` quando já existe (Genius,
  Dayvale, BGT), inclusive em nomes de arquivo, âncoras e caminhos citados. `INTERNAL` é o rótulo
  da própria tabela e fica como está.
- Fundo pelo administrador e uma letra (`BGT A`, `Genius C`), na ordem do VP em 31/08/2026; nunca o
  CNPJ.
- Totais por fundo e por administrador podem entrar; amostras de linhas não.
- No SQL de `attachments/`, o valor da coluna `source` entra por parâmetro, nunca escrito.

## Valores reais fora do repo

A tabela de nomes reais × análogos e o CNPJ de cada fundo citado por letra ficam no arquivo local
`~/.config/workspace/private/valids.md`, fora do controle de versão. Ler esse arquivo quando um
documento daqui usar um análogo ou uma letra de fundo. Valor sensível novo vai para lá, e aqui
entra só a referência.

## Dados locais fora do repo

As poças fictícia e simulada (`.csv` e o `.js` do mock), as saídas das simulações com dados reais e
os logs ficam em `~/.local/share/workspace/projects/valids/`. Nada dali entra no repo; aqui entra
só o caminho.

## Consultas ao Redshift do lake

- Só SELECT, em transação somente leitura. Nunca INSERT, UPDATE, DELETE ou DDL.
- Sempre filtrar por `data_ref`, a sortkey de todas as tabelas `administradores_*`: um dia, ou no
  máximo um mês. As tabelas são grandes
  (ver [evidência de 21/10](evidence/stock-movement-redshift-2026-10-21.md#tamanho-das-tabelas)).
- Amostras com LIMIT pequeno (até ~20 linhas) e sem colunas de nome ou de CPF/CNPJ de sacado e
  cedente.
- Ferramenta: [attachments/rsq.py](attachments/rsq.py), que recusa tudo o que não for um único
  SELECT/WITH.
- Só as views `plgn.administradores_*` alimentam o dashboard (D1), mais a `plgn.dim_contrato` para
  o produto (D16). A `dim_contrato` não tem `data_ref` nem sortkey (332 mi de linhas): nunca
  consultá-la sozinha sem LIMIT; juntar só a partir de uma foto do estoque filtrada por
  `data_ref`, por igualdade e com `cnpj_classe`.

## Estrutura

| Arquivo | Para que serve |
|---|---|
| `README.md` | visão geral, abas, lista de tarefas e glossário |
| `CONTINUE.md` | onde parei, branches e próximo passo, para um chat novo |
| `decisions.md` | decisões pendentes e tomadas, com dono, data e motivo |
| `concepts.md` | conceitos financeiros (valor presente, taxa, accrual) para quem não é da área |
| `tasks/NN-*.md` | uma tarefa por arquivo (uma aba ou um tema) |
| `evidence/` | números do lake com data e as consultas para medir de novo |
| `data-problems.md` | inconsistências nos dados do lake (P1, P2...), ainda não validadas |
| `later.md` | melhorias adiadas, com o que falta para retomar |
| `attachments/` | SQL e scripts citados nas tarefas |

## Como escrever

- Separar o comprovado da hipótese: **[C]** (visto no código ou numa consulta) e **[H]**
  (hipótese, com o caminho para validar).
- Citar código como `caminho/arquivo:linha` e dizer contra qual commit as linhas valem (tabela no
  README).
- Número do lake sempre com período, fonte e a consulta para repetir.
- Os dados do lake ainda não foram validados (aviso do Heitor, 21/10): toda inconsistência vira
  item em `data-problems.md`, não premissa do desenho.

## Como manter

- **Decisão tomada:** mover de "Pendentes" para "Tomadas" em `decisions.md`, com data, quem
  decidiu e o motivo. Atualizar as tarefas que a citam.
- **Escopo ou status mudou:** atualizar a tarefa (status e "Histórico"), a tabela de tarefas do
  README e o `CONTINUE.md`.
- **Item adiado:** levar para `later.md`, com origem, data e o que falta.
- **Problema de dado:** registrar em `data-problems.md` com onde, efeito, como foi visto e como
  validar.
- Antes de afirmar algo sobre o sistema, conferir no código atual ou no lake.

## Repositórios envolvidos

| Repositório | Papel |
|---|---|
| data-lake-api | API do lake (FastAPI) que lê o Redshift; módulo `valid` (rotas `/valid/ecl`, poça no Postgres, cargas diárias) |
| apl-credit-whitelabel-api | BFF do portal; rotas `controllership/valid/*` |
| apl-credit-whitelabel | front do portal (Angular 20); tela `features/controllership/pdd` |
| platform-cessao | cadastro da régua de PDD (`POST /pdd/regua`) e régua em vigor (`GET /pdd/regua-vigente`, D19) |
| data-lake-api-argocd | deploy do worker `valid` e do agendamento das cargas no beat |

Contrato novo entre front, BFF e data-lake-api muda nas três pontas no mesmo ciclo.
