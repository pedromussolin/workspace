Status: em andamento
Data: 30/10/2026
Tags: ws, skills, hooks, segurança

# Decisões

Uma decisão por linha, com dono e data. Quando uma pendente fechar, ela vai para "Tomadas" com o motivo.

## Pendentes

Em "Quem", quem decide. A coluna "Motivo" traz a recomendação do Claude.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| P1 | Onde aprovar na fase 2 | usuário | 29/10 | Recomendado: painel `ws approvals` numa aba do terminal agora; notificação do Windows depois. O painel é o único canal que continua confiável dentro da caixa da fase 3 |
| P2 | Servidor MCP `ws` | usuário | 29/10 | Recomendado: feito por nós, só biblioteca padrão, sem SDK (sem dependência externa) |
| P3 | Processo separado que guarda as chaves (*broker*) | usuário | 29/10 | Recomendado: só na fase 3, junto com a caixa; na 2a o `ws` e o MCP dividem um registro de pedidos em arquivo |
| P4 | Aprovação dentro do Claude Code | usuário | 29/10 | Recomendado: a pergunta do próprio servidor MCP (*elicitation*, que o modelo não responde) ou o painel |
| P5 | Escopo da 2a | usuário | 29/10 | Recomendado: registro genérico de pedidos, painel, servidor MCP, card migrado |
| P6 | Escopo da 2b, em paralelo com a 2a | usuário | 29/10 | Recomendado: push de branch de tarefa e PR (criar, comentar) pelo `ws`, com o token do `credentials` |
| P7 | GMUD (2c) | usuário | 29/10 | Recomendado: depois da 2a e da 2b |
| P8 | Contexto = domínio ou sistema (cessão, portal, workspace pessoal, estudos), dono do conhecimento, dos repos e das releases (tarefa 03) | usuário | 30/10 | Recomendado: sim |
| P9 | Todo item pertence a uma iniciativa; cada contexto tem uma `sustentacao/` permanente para bug e hotfix avulsos | usuário | 30/10 | Recomendado: sim (substitui o `standalone`) |
| P10 | Itens planos por iniciativa, com épico, tipo e status como campos (não pastas por épico) | usuário | 30/10 | Recomendado: sim; nada se move, nenhum link quebra |
| P11 | Pasta raiz `work/` no lugar de `projects/` | usuário | 30/10 | Recomendado: sim (o nome cobre contextos); alternativa: manter `projects/` e mudar só o interior |
| P12 | Migração por script (`ws work migrate` com mapa aprovado): workspace primeiro; artemis e whitelabel com os chats parados | usuário | 30/10 | Recomendado: sim |
| P13 | Ordem: a reorganização (tarefa 03) vem antes ou depois da fase 2 dos portões | usuário | 30/10 | Em aberto; o usuário disse que talvez mude o plano |

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
