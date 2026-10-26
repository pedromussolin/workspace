# TS-5193: ajustes visuais do Orquestrador (21/10, noite)

Pedidos do Pietro depois de ver as telas novas na sandbox. Entram no deploy de produção de hoje, então é
ajuste pontual: nada de redesenho, nada de mudar contrato ou comportamento além do pedido.

## Regras comuns

Valem as do `brief-release-21-10.md` (mesma pasta):
- worktree própria e sem commit;
- comando pesado pelo `ng-slot`;
- rascunho em `~/repos/.reestrutura_whitelabel/agentes/<pacote>/`;
- prints de antes e depois, em claro, escuro e celular, em
  `~/repos/.reestrutura_whitelabel/evidencias/release-21-10/<pacote>/`;
- relatório em PT-BR.

Antes de começar, leia o `CLAUDE.md` e a `.ai/` da worktree. Use o que já existe em `shared/ui` (veja a vitrine
em `/design-system`). Se faltar um padrão, descreva no relatório: não crie nem mude componente de `shared/ui`. Todo
comportamento novo ganha spec.

## Pacote r5193-visual-a (Execuções, `/orchestrator`), portas 4710 a 4719

1. **Resumo por status mais compacto** (`orchestrator/flow-funnel/`).
   - **Hoje:** um cartão por linha ("Todos os flows" e cada subflow, ou cada processo na visão de processos),
     cada um com 5 `app-kpi` grandes. Só esses cartões ocupam boa parte da tela.
   - **Objetivo:** o bloco inteiro com cerca de um terço da altura de hoje.
   - **Sugestão:** a linha "Todos os flows", que filtra a lista, fica como uma faixa de 5 contadores clicáveis,
     compactos e com o estado ativo. Os subflows (ou processos) viram uma tabela compacta: uma linha por subflow,
     uma coluna por status, a contagem com o tom do status quando for maior que zero e o total de execuções.
   - **O que não pode mudar:** os tooltips de hoje, o filtro pelo clique e o texto que diz que o clique filtra
     (decisão de 10/10).
   - **Celular:** a tabela rola por dentro do cartão.
2. **Filtros avançados lado a lado** (`orchestrator/advanced-filters/`).
   - No desktop, "Combinar", os botões "+ Condição de etapa" e "+ Condição de chave de busca" e a linha
     "Resultado" ficam numa linha só, quebrando quando não couber.
   - As condições já adicionadas ficam lado a lado, em grade de 2 colunas a partir de ~1100 px.
   - No celular, uma coluna.

## Pacote r5193-visual-b, portas 4720 a 4729

1. **Funil de processos com mais espaço entre os processos** (`product-view/components/process-funnel/`). As
   linhas de processo dentro de cada etapa ficam um pouco mais altas e mais separadas: hoje estão coladas, com
   cerca de 27 px por linha. Só espaçamento.
2. **Botão de copiar o ID do flow**, ao lado do ID, nos dois lugares em que ele aparece com o ícone `hierarchy`:
   - no cabeçalho do flow na lista de Execuções (`orchestrator/flow-list/`);
   - no cabeçalho do detalhe do flow (`flow-detail/`).

   Como fazer:
   - use `appIconButton` com o ícone `copy`, o rótulo "Copiar ID do flow" e o tooltip;
   - copie pelo `Clipboard` do CDK, como no `population-preview`, e avise com o `ToastService` ("ID copiado");
   - na lista, o cabeçalho do acordeão é um botão: o de copiar fica **fora** dele (botão dentro de botão é
     inválido), e o clique não abre nem fecha o flow.
3. **Headers e Body com o bloco de código das docs** (`components/process-detail/`). Troque o `<pre>` de cada
   JSON pelo `app-code-block` de `shared/ui`, com `language="json"`. Ele já tem o botão de copiar e a cor da
   sintaxe, como em `features/api-docs/components/execute-result/`. Os rótulos "Headers" e "Body" continuam.
