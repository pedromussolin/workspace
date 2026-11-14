# Handoff 09/11/2026: base do produto (organização, memória, busca, nuvem)

Chat anterior ficou pesado. Leia inteiro antes de agir; com o `CONTINUE.md` e o `decisions.md` do
projeto workspace, basta para retomar.

## Onde estamos

- Sincronização do board concluída e na `main`. Evals passaram 3 de 3: `out-of-sync-card`
  (US$ 0,84) e `daily-detailed` (US$ 0,97), com `scripts/run-evals --case <nome> --ablation none`.
  Correções do caminho: `[tool.uv] link-mode = "copy"` (o `claude plugin eval` recusa hard links,
  e as worktrees em `.claude/worktrees` têm `.venv`), `run-evals` confere hard links também
  nas worktrees, plano com `--case` (`3dbadb5`, `115869c`, `768437c`).
- Config local (fora do repo): um repo da empresa marcado `ignore = true` no `[board.repos]` (o remoto não existe mais).
- Produto: o documento de descoberta foi reescrito em 07/11 (abaixo).
- Tarefa 05 (segredos por adaptador, para depois) registrada (`0cdc5ce`).
- Desenho da base em andamento, pelo caminho arquitetural do `superpowers:brainstorming`: decisões
  D14 a D23 no `decisions.md`; pendentes P14 (três camadas) e P15 (estrutura do espaço).

## Documento de descoberta de produto

https://claude.ai/artifact/NLmKWGPFbZQcyjGez78G5U ("Descoberta de produto: assistente do dev").

- Ids: doc `acd25b27-7cfc-4a1b-8ad4-489338e3fef7`, aba `fc5b68f2-35d8`, corpo `b346c81f-d948`
  (prose), widgets `b461780d-ac0e` (arquitetura hexagonal) e `61a25a71-1e05` (mapa 2x2), enum
  `d23c2b93-8474` (coluna Lançamento da tabela de Frentes). Última rev conhecida: 183.
- Seções: lead, Problema, Público, Frentes, Arquitetura, Concorrentes, Posicionamento, Entrega e
  cobrança, Primeiro lançamento, Validação, Riscos e decisões em aberto, Fontes.
- Antes de editar: carregar a skill `anthropic-skills:docs` (o `guide`), ler com `sinceRev` (o
  usuário edita o doc; em 06/11 ele escreveu no lead), guardas `ifHash` + `ifRev`, nunca `force`.
- Falta no doc: a seção "Base" e a ordem "base antes das frentes" (D16), depois que o desenho
  fechar. A tarefa 05 já aparece na porta Credenciais do desenho (1Password, keyring ou arquivo local).
- Decisões em aberto no doc (P16): frentes do 1º lançamento (proposta: rotina, tarefas e board,
  contexto, organização, segurança; deploy e padrão no 2º), segundo agente (Cursor ou OpenCode,
  que perguntam antes da ferramenta), segundo tracker (Linear ou GitHub Issues), nome, licença,
  merchant of record.

## Desenho da base: decidido (D16 a D22)

Perguntas feitas uma por vez, com a recomendada primeiro; o usuário escolheu a recomendada em todas.

1. A base vem antes das frentes; a primeira prioridade é a organização única.
2. Topo: espaço por contexto (empresa, cliente ou pessoal), fronteira de sigilo e de nuvem.
3. Projeto livre: tarefa = card (1 para 1); projeto agrupa por objetivo e junta épicos; tarefa sem
   projeto vai para a caixa de entrada do espaço (substitui a `sustentacao/` da P9).
4. Sistema como cadastro no espaço (repos, branches de ambiente, conhecimento, releases), não como
   pasta (substitui o "Contexto" da P8 e da tarefa 03).
5. Um repo git por espaço, com remoto próprio.
6. Memória por nível (você, espaço, projeto, tarefa), fonte única; a memória do Claude Code
   (`~/.claude/projects/<pasta do repo>/memory/`, ~60 arquivos) deixa de ser a fonte e é
   importada separada por nível (preferências → perfil; fatos da empresa → espaço).
7. Arquivos como fonte; índice local reconstruível; nuvem = remoto git de cada espaço, serviço
   pago do time depois.

## Em aberto: P15, seção 1 do desenho (estrutura)

Apresentada; o usuário não respondeu a ela, perguntou sobre desempenho (P14).

```text
config por máquina      lista de espaços: nome, caminho, remoto, tracker, cofre, máscara, nuvem
perfil (repo próprio)   suas preferências e regras; vale em todo espaço, sem fato de empresa
<espaço>/               um repo git
  space.toml            tracker, cofre, máscara, nuvem e agentes do espaço
  memory/               regras e fatos do espaço, um por arquivo
  systems/<sistema>/    cadastro (repos, branches de ambiente), conhecimento, releases/
  inbox/items/          tarefas sem projeto: bug, hotfix, avulsa
  projects/<projeto>/
    README.md           objetivo, status, sistemas que toca, épicos
    CONTINUE.md         onde parei
    decisions/          uma decisão por arquivo
    items/              uma tarefa por card: TS-5435-fechar-lote.md
    docs/               atas, estimativas, GMUDs, achados (o tipo fica num campo)
    evidence/  attachments/
fora do git             ~/.local/share/<produto>/<espaço>/ (dados locais), ~/.cache/<produto>/<espaço>/ (índice)
```

Memória por nível: tarefa = o arquivo do item; projeto = `CONTINUE.md` e `decisions/`; espaço =
`memory/` e o conhecimento dos sistemas; você = o repo de perfil. Quadros e índices são gerados.

## Em aberto: P14, base em três camadas (resposta à dúvida "não é performático, sem RAG nem KAG?")

O usuário estava certo em parte: a estrutura é só a fonte; faltava a camada de busca, que entra na
base desde o início (a recomendação "grep primeiro" de 23/10 valia para poucas centenas de arquivos).

1. Fonte: arquivos em git por espaço (durabilidade, diff, aprovação). O agente não varre pastas.
2. Índice por espaço, local, incremental (só o que mudou): grafo cujos nós são espaço, sistema,
   repo, projeto, épico, tarefa, decisão, documento, PR e commit, com arestas vindas dos campos;
   trechos com busca por palavra (BM25, SQLite FTS5) e por significado (vetores, sqlite-vec), cada
   trecho ligado ao seu nó (a ideia de índice mútuo do KAG).
3. Recuperação (porta de busca do núcleo): pacote da sessão (caminha no grafo a partir da tarefa e
   entrega um resumo curto com links, sem IA); busca híbrida filtrada pelo grafo; perguntas em
   vários passos.

Sem KAG ou GraphRAG completos: extrair grafo por IA custa tokens e erra; o domínio já tem estrutura
explícita. Extração por IA fica opcional, depois, só para texto livre (atas). Nuvem do time: outro
adaptador da mesma porta (Postgres + pgvector).

## Próximo passo

1. Pedir o ok de P14 e P15 numa pergunta só.
2. Seguir o desenho, uma seção por vez com o ok dele:
   - 2: tipos de arquivo e campos (front matter TOML entre `+++`, o mesmo do `/card`; tipos de
     item, decisão, documento, memória, sessão; ids; ligações que viram arestas do grafo);
   - 3: memória por nível e como chega a cada agente (AGENTS.md gerado com índice curto, pacote da
     sessão, leitura sob demanda pela CLI ou MCP, importação da memória do Claude Code);
   - 4: índice e busca (atualização por hash, modelo local de embeddings multilíngue a escolher,
     fusão RRF dos rankings, filtros do grafo);
   - 5: nuvem e sigilo (remoto por espaço, máscara só onde o remoto é pessoal, serviço pago depois);
   - 6: migração de `projects/` para espaços (perguntar ao usuário qual projeto vai para qual espaço
     e onde fica o remoto do espaço da empresa; P12 vale);
   - 7: portas do núcleo (armazenamento, índice, busca; credenciais da tarefa 05).
3. Spec em `docs/specs/2026-11-XX-product-base-design.md`, commit e push, revisão do usuário, depois
   `superpowers:writing-plans`.

## Pendências antigas

- Revisão do board sync, item 7: pôr na caixa de aprovação "sobe porque o código está na master;
  aprovar = testado"? Sem resposta.
- Comando que cria arquivo de tarefa para cards e commits feitos fora do agente: já no checklist do
  1º lançamento; entra na spec de início de tarefa.
- Fase 2 dos portões (P1 a P7) fica depois da base (D17 substitui a P13).
- Specs depois da board sync, só com o ok do usuário: campos do card (subtarefas, links neutros,
  story points), início de tarefa (`ws task start`), tracker genérico (tarefa 04).
- Seis worktrees de agente de 03/11 em `~/repos/workspace/.claude/worktrees/` (cinco não
  mergeadas, todas limpas): perguntar se pode remover.

## Pesquisas

Nesta pasta (`attachments/`): `research-20261107-harness-matrix.md`
(o que cada um dos nove agentes oferece: instruções, skills, hooks, MCP, pacotes) e
`research-20261107-multifront-competitors.md`. As pesquisas de 06/11 (sincronização de tracker, tarefas e memória de
agentes, preço e licença) se perderam com a pasta temporária da sessão; o resumo com fontes está no
doc (Concorrentes, Entrega e cobrança, Fontes).

## Como o usuário quis trabalhar neste chat

- Uma pergunta por vez, com opções e a recomendada primeiro (AskUserQuestion): funcionou bem.
- Respostas enxutas; termo técnico explicado; o detalhe vai para o documento.
- Quando o limite do Claude estiver acabando, ele pede para usar o Fable nos agentes: brief
  completo e uma seção do doc por agente; eu reviso no fim.
