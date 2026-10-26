# Regressão visual — TS-5358 (estrutura base)

Data: 10/10/2026. Prints da master (`d0bc3de`) e da branch
`refact/TS-5358-estrutura-base-front` (`b38f4c0`), feitos com
[attachments/scripts/smoke.mjs](../attachments/scripts/smoke.mjs):

- build de produção servido localmente, com um BFF falso: sessão válida,
  todas as rotas liberadas e listas vazias;
- Chromium headless, em desktop (1440×900) e celular (390×844);
- 29 rotas, 58 prints de cada lado, comparados pixel a pixel com o
  `pixelmatch` (limiar 0,1).

## Resultado

| Situação | Prints |
|---|---|
| Idênticos | 53 |
| Diferença só no quadro do vídeo animado do robô da Home (o mock redireciona `/login` para `/home`) | 3 (home desktop e celular, login celular; 139–380 px) |
| Diferença de 6–10 px no Orquestrador, provavelmente animação ou tempo relativo (não investigado) | 2 |

- Na primeira rodada, a Home apareceu **desalinhada** na branch: blocos à
  esquerda e no alto, em vez de centralizados. Corrigido no `b38f4c0`
  (achado A12). Depois da correção, é igual à master.
- Navegação interna `/pre-trade` → `/liquidation-batches` (popstate): o
  `<app-shell>` continua sendo o mesmo elemento, e o título troca para
  "Lotes de Liquidação".
- Nenhum erro de JavaScript na página, nas duas builds.
- Na master, a rota `/cerc-reconciliation` no celular travou o print por
  vários minutos (página ocupada), mas na branch não travou. Vale olhar na
  09.

## Fora do alcance deste teste

- Login real no Azure, sessão expirando de verdade e permissões reais: isso
  precisa do BFF, então fica para testar na sandbox.
- Telas com dados. O BFF falso devolve listas vazias, então tabelas cheias,
  diálogos e gráficos não aparecem.

## Observação para as próximas tarefas

No celular (390 px), o portal de hoje **não é responsivo**:
- a sidebar em modo trilho ocupa 64 px fixos;
- o header quebra o nome do usuário em duas linhas;
- o campo da Home é cortado à direita.

É o ponto de partida. O requisito "tudo responsivo" entra na 02 (shell) e
nas tarefas de área.
