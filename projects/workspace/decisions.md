Status: em andamento
Data: 30/10/2026
Tags: ws, skills, hooks, segurança

# Decisões

Uma decisão por linha, com dono e data. Quando uma pendente fechar, ela vai para "Tomadas" com o motivo.

## Pendentes

Em "Quem", quem decide. A coluna "Motivo" traz a recomendação do Claude.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| P16 | Frentes do 1º lançamento, segundo agente (Cursor ou OpenCode perguntam antes da ferramenta) e segundo tracker (Linear ou GitHub Issues) | usuário | 08/11 | Propostas no documento de descoberta de produto |
| P17 | Papéis de agente × motor agêntico da empresa: (a) campo de prova, com os mesmos papéis e documentos, ou (b) inspiração, com os conceitos e os formatos do workspace | usuário | 19/11 | Recomendado (b), com os mesmos nomes de papel onde servirem: o motor ainda muda (primeira versão na entrega 4 de 12) e o formato dele não é o do ADR 0003 |

## Tomadas

Em "Quem", quem decidiu.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| D1 | Prioridade: A (nada grava fora sem o sim), depois C (sigilo), depois B (caixa que se entende) | usuário | 28/10 | Definição do problema |
| D2 | Portão único em fases (1 portão no Claude, 2 aprovação no `ws`, 3 sandbox, 4 outros harnesses) | usuário | 28/10 | Única abordagem em que A não depende de ler texto nem do modelo se comportar |
| D3 | O harness é só interface: regras e escritas no `ws`; aprovação do `ws`, com três canais (terminal, pergunta do servidor MCP, caixa do Claude para ferramentas de terceiros) | usuário | 28/10 | Funcionar com opencode e modelos locais |
| D4 | Modo 100% manual como requisito; toda skill nova tem caminho manual | usuário | 28/10 | Não depender de provedor de IA nem do custo dele |
| D5 | Sandbox próprio, mesmo que trabalhoso: caixa em volta do agente inteiro, aprovação no painel fora da caixa | usuário | 28/10 | Sem dependência externa; vale para qualquer harness |
| D6 | Skills ficam em `skills/`; as pastas de cada harness só têm links | usuário | 28/10 | Uma fonte para todos os provedores |
| D7 | O catálogo MCP lista as leituras; o resto pergunta | usuário | 28/10 | Ferramenta nova pergunta até ser classificada (falha fechada) |
| D8 | As quatro condições do teste do sandbox (fechado por padrão; `.git/hooks`, `.git/config` e `.githooks/` só leitura; git de rede e `gh` fora da caixa; pasta de config própria do harness) | usuário | 29/10 | Achados do teste de viabilidade |
| D9 | Segredos fora do ambiente da sessão: token do GitHub no `credentials`, servidor MCP com `headersHelper`, variáveis vazias no `env` do settings; token trocado | usuário | 29/10 | Qualquer comando lia o token pelo ambiente |
| D10 | `ws setup` avisa servidores MCP fora do catálogo; o portão anota ferramentas desconhecidas; `ws gate catalog pass|ask` classifica | usuário | 29/10 | Configurar o catálogo já no setup |
| D11 | Parar a fase 1 após três revisões e documentar os limites | usuário | 29/10 | Portão que lê texto nunca fecha; quem fecha é tirar as chaves do alcance (fases 2 e 3) |
| D12 | Branches de ambiente `master`, `main`, `sandbox`, `staging`: push só nos repos `*-argocd` e com caixa; merge de PR bloqueado só quando a base é de ambiente | usuário | 29/10 | Fluxo de PR em que o usuário mergeia |
| D13 | Acelerar a fase 2: uma rodada de decisões, contrato no GitHub antes dos agentes, commit por item, uma revisão só no fim, sem reiniciar o Claude com agentes rodando | usuário | 29/10 | A fase 1 demorou |
| D14 | O produto é um assistente do dev em várias frentes (rotina, tarefas e board, contexto e memória, organização de projetos, segurança, entrega e deploy, padrão de código); o board é uma delas | usuário | 07/11 | Revisão do documento de descoberta de produto |
| D15 | Núcleo em arquitetura hexagonal: portas são interfaces (`Protocol`) do núcleo, cada sistema externo entra por adaptador; vale em qualquer agente, pago ou open source | usuário | 07/11 | Trocar agente ou tracker sem mexer no núcleo |
| D16 | A base do produto (organização, memória, busca, nuvem) vem antes das frentes; a organização única é a primeira | usuário | 08/11 | "Antes disso tudo, precisamos melhorar nossa base sólida" |
| D17 | Espaço por contexto no topo (empresa, cliente ou pessoal): fronteira de sigilo e de nuvem, nada cruza sem pedir | usuário | 08/11 | Substitui P11 (`work/`) e P13 (a base vem antes da fase 2) |
| D18 | Projeto livre: tarefa = card (1 para 1); projeto agrupa por objetivo e pode juntar épicos; tarefa sem projeto vai para a caixa de entrada do espaço | usuário | 08/11 | Substitui P9 (`sustentacao/` vira `inbox/`) |
| D19 | Sistema como cadastro no espaço (repos, branches de ambiente, conhecimento, releases), não como pasta acima do projeto | usuário | 08/11 | Substitui P8; projeto que cruza sistemas fica inteiro num lugar |
| D20 | Um repo git por espaço, com remoto próprio | usuário | 08/11 | Sigilo: um vazamento não atinge os outros espaços |
| D21 | Memória por nível (você, espaço, projeto, tarefa), fonte única; a memória do Claude Code deixa de ser a fonte e é importada separada por nível | usuário | 08/11 | Todo agente lê a mesma memória |
| D22 | Arquivos como fonte; índice local reconstruível; nuvem = remoto git de cada espaço, serviço pago do time depois | usuário | 08/11 | Diff e revisão pelo git; perder o índice não perde nada |
| D23 | Segredos por adaptador (1Password, GitHub, chaveiro) com o modelo local de hoje como reserva; mapeada para depois na tarefa 05 | usuário | 08/11 | Pedido do usuário |
| D24 | Onde aprovar na fase 2: painel `ws approvals` numa aba do terminal agora; notificação do Windows depois. O painel é o único canal que continua confiável dentro da caixa da fase 3 | usuário | 17/11 | Recomendação aceita (era P1) |
| D25 | Servidor MCP `ws`: feito por nós, só biblioteca padrão, sem SDK (sem dependência externa) | usuário | 17/11 | Recomendação aceita (era P2) |
| D26 | Processo separado que guarda as chaves (*broker*): só na fase 3, junto com a caixa; na 2a o `ws` e o MCP dividem um registro de pedidos em arquivo | usuário | 17/11 | Recomendação aceita (era P3) |
| D27 | Aprovação dentro do Claude Code: a pergunta do próprio servidor MCP (*elicitation*, que o modelo não responde) ou o painel | usuário | 17/11 | Recomendação aceita (era P4) |
| D28 | Escopo da 2a: registro genérico de pedidos, painel, servidor MCP, card migrado | usuário | 17/11 | Recomendação aceita (era P5) |
| D29 | Escopo da 2b, em paralelo com a 2a: push de branch de tarefa e PR (criar, comentar) pelo `ws`, com o token do `credentials` | usuário | 17/11 | Recomendação aceita (era P6) |
| D30 | GMUD (2c): depois da 2a e da 2b | usuário | 17/11 | Recomendação aceita (era P7) |
| D31 | Itens planos por projeto, com épico, tipo e status como campos (não pastas por épico); nada se move, nenhum link quebra; entra na estrutura da base (D34) | usuário | 17/11 | Recomendação aceita (era P10) |
| D32 | Migração por script (`ws work migrate` com mapa aprovado): workspace primeiro; artemis e whitelabel com os chats parados; vale para a migração para a base | usuário | 17/11 | Recomendação aceita (era P12) |
| D33 | Base em três camadas: fonte (arquivos em git), índice por espaço (grafo vindo dos campos + trechos com busca por palavra e por significado, ligados entre si) e recuperação (pacote da sessão, busca híbrida, perguntas em vários passos). Resposta à dúvida do usuário sobre RAG e KAG: o grafo sai dos campos (card, épico, PR, sistema), sem extração por IA; SQLite FTS5 + sqlite-vec no local, pgvector na nuvem | usuário | 17/11 | Recomendação aceita (era P14) |
| D34 | Estrutura do repo de cada espaço (`space.toml`, `memory/`, `systems/`, `inbox/items/`, `projects/<projeto>/` com `items/`, `decisions/` um arquivo cada, `docs/` tipados) e o repo de perfil; é a seção 1 do desenho da base | usuário | 17/11 | Recomendação aceita (era P15) |
| D35 | Regras do `AGENTS.md` seguem a prática de antes: falso positivo vai para o `.secrets-allow` e a resposta avisa; o Claude aplica o bloco do `ws setup` no `settings.json` só depois do sim | usuário | 17/11 | Revisão da branch de documentos de agentes |
| D36 | O `CLAUDE.md` da raiz carrega sempre as regras de sigilo; as outras convenções são lidas sob demanda | usuário | 17/11 | Revisão da branch de documentos de agentes |
| D37 | A skill `observe` não grava por heredoc quando o Write é negado: para e avisa | usuário | 17/11 | Revisão da branch de documentos de agentes |
| D38 | Réplica de produção: a consulta direta, só leitura, com timeout e uma por vez, continua permitida; `ws observe run` é o caminho das observações, não o único | usuário | 17/11 | Corrige a regra que veio na branch de documentos de agentes e travou outro chat |
| D39 | Papéis de agente: o QA roda o smoke na tela (Playwright, dados fictícios) só quando a mudança tem front; só backend = testes e critérios de aceite. O "tem front" vem da categoria `front` do `ws review pack` | usuário | 19/11 | "apenas quando front, muitas vezes mexo em aplicações full backend" |
| D40 | Papéis de agente: sem agente classificador; o chat principal escolhe o papel pela conversa (descrição de cada agente, tabela situação → papel nas regras de agentes, hook que barra chamada sem papel nem modelo) | usuário | 19/11 | Recomendação aceita; segue o que ficou no backlog em 27/10 |
