+++
tracker = false
status = "todo"
+++
Status: a fazer
Data: 24/11/2026
Tags: ws, board, cards, sincronização

# 06 — Sincronização do quadro reconhece em produção o que hoje fica preso

## Contexto

No `/card sincronizar` de 24/11/2026, logo depois do deploy de uma release que ficou inteira em
produção, o `ws board status` deixou 14 dos 17 cards dela fora de "concluído". Os 17 foram movidos
à mão. Foram três casos:

1. **Commit de junção só na cópia da sandbox.** O último commit com o ID do card é a junção das
   migrations feita na branch `release/<data>-sdbx`, com a mensagem "junta as migrations da release
   com as da sandbox". Por regra, a `-sdbx` nunca vai para a `master`, então o card fica preso
   (`held`, `reached: sandbox`) mesmo com o código dele em produção. Foram três cards.
2. **Commit trazido por cherry-pick.** O commit original do card está numa branch de backup e na
   sandbox; o que foi para produção é o cherry-pick dele, com outro hash. O `ws` procura o hash
   original e não o acha na tag. Foi um card.
3. **Serviço com dois ambientes de produção.** O serviço roda em dois realms, cada um com a sua tag
   no repo de deploy. Um subiu para a tag nova e o outro ficou, de propósito, na tag antiga. O `ws`
   só provou até a `master`, e propôs "pronto para deploy" em vez de "concluído" para 9 cards.
   **[H]** O `ws` lê a tag do realm que ficou para trás, ou exige todos os realms; conferir em
   `src/ws/boardproofs.py` e `src/ws/boardconfig.py`.

## Pronto quando

- Commit que só junta branches ou migrations numa branch `-sdbx` não conta como o "último commit" do
  card na prova de produção.
- Um cherry-pick conta como o commit original: comparar também pelo `git patch-id` ou pela linha
  `(cherry picked from commit ...)`, além do hash.
- Para serviço com mais de um ambiente de produção, a config diz qual realm prova o "em produção"
  (ou se basta qualquer um), e o `held` diz qual realm falta.
- Testes com os três casos, em repositórios de exemplo no pytest, e o relato do `held` em PT-BR
  mostra o motivo de cada card.

## Evidência

O `board status` de 24/11, guardado fora do repo:
`~/.local/share/workspace/projects/workspace/evidence/board-status-20261124.json`.
