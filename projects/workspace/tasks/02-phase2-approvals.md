Status: decisões pendentes
Data: 30/10/2026
Tags: segurança, aprovação, ws, mcp

# 02 — Fase 2: aprovação no `ws`

## Objetivo

Toda escrita fora da máquina passa a ser do `ws`: alguém prepara (a IA ou o usuário), o `ws` mostra
a prévia em PT-BR com um código, uma pessoa aprova, o `ws` executa com a chave. Funciona igual com
Claude Code, opencode, modelo local ou à mão.

Ponto honesto, já dito ao usuário: sem a caixa da fase 3 o modelo roda como o mesmo usuário e
consegue gravar qualquer arquivo que o painel grave. A fase 2 sozinha traz portabilidade, um jeito
só de aprovar e ferramentas MCP estruturadas; a garantia forte chega com a fase 3, e por isso o
desenho já nasce pensando nela.

## Partes

- **2a**: registro genérico de pedidos pendentes (generalização do registro do card em
  `~/.local/share/workspace/cards/pending/`), painel `ws approvals`, servidor MCP `ws` (JSON-RPC
  sobre stdio), card migrado.
- **2b** (em paralelo): escritas do GitHub pelo `ws` (push de branch de tarefa, PR, comentário) com
  o token do `credentials`; a skill de release (spec em `docs/specs/2026-10-27-release-design.md`)
  nasce em cima disso.
- **2c**: GMUD (portal do Jira Service Management), depois.

Decisões pendentes: P1 a P7 do `decisions.md`.

## Processo (o usuário pediu para acelerar)

1. Uma rodada só de decisões (P1 a P7), com a recomendação de cada uma.
2. Spec curta em `docs/specs/` e o código do contrato comum (formato do pedido, interface de
   executor, canal de aprovação) com testes, no GitHub antes de disparar.
3. Quatro a cinco agentes em paralelo, pastas disjuntas, commit por item; Sonnet na maior parte,
   Opus só no núcleo de aprovação.
4. Uma revisão só no fim (Opus); corrige o grave, o resto vira limite documentado.
5. Sem reiniciar o Claude Code enquanto os agentes rodam.
