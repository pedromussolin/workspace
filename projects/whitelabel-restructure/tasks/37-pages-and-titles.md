# 37 — Formalização numa página só, página que abre por outra e títulos

- **TS:** TS-5439 (épico TS-5357) · **Branch:** juntada na `release/20261027` (front e BFF)
- **Status:** **em produção** (27/10). Não passou pela sandbox antes do deploy; validada pelos testes.
- **Decisões:** D134 e D136.

## O que é

- A Formalização vira uma página só no Controle de acesso, com os escopos `whitelists` e `units`.
- Página fora do menu diz de onde abre (`openedFrom`), e a tela avisa: Detalhes do Contrato abre por Lotes de
  Cessão e por Lotes de Liquidação.
- As páginas e os nomes das permissões usam o título do menu e da tela. "Base de Conhecimento - POLI" vira "Base de
  Conhecimento da POLI" também no menu.
- Grupo dentro de grupo fica de fora: o Azure não repassa ao grupo de dentro as roles nem a organização.

## Depois do deploy (com o Pietro)

- Renomear os grupos com o nome antigo da página pelo `renomear-grupos.sh` (pasta privada), primeiro sem `--aplicar`.
- Passado o período de rollback, apagar os grupos de "Formalização (unidades)", depois de passar as permissões
  `units:*` e as pessoas para os grupos da Formalização.
