# 12 — Análise do PR de lotes reais (Lukas Freyta)

- **Branch:** `feature/ajuste-rota-liquidacao-lote-real`, commit `79e7c2d`
  (15/10/2026). Sem PR aberto, só o compare. Faz merge limpo com a `master`
  `f19ef2c` (19/10). **[C]**
- **Arquivos:** `cessao/api/liquidacao/repository.py` e o teste dele. Linhas
  abaixo contra `79e7c2d`.
- **Análise:** 20/10/2026. Base: [tarefa 12](12-lotes-reais-lotes-antes-dos-valores.md)
  e [evidência](../evidencias/lotes-reais-datadog-2026-10-14.md) (seção de 20/10).

## Conclusão

Não mergear como está. O PR mexe só na consulta da página, que responde por
**19% dos 500**; a consulta dos lotes irmãos (`lotes_das_remessas`), que
responde por **81%**, fica igual. E, para a página, troca o problema por um
"planejador" na aplicação (contagens prévias e limites fixos) que pode
piorar o caso que hoje funciona. Duas peças pequenas valem aproveitar, com
`EXPLAIN` que comprove.

## O que o PR muda

| # | Mudança | Onde |
|---|---|---|
| 1 | Valores do lote: o `LATERAL` vira uma consulta agrupada com `IN (ids da página)`, juntada em Python | `valores_dos_lotes`, `:772` |
| 2 | `EXISTS` do fundo com o `fundo_id` como valor fixo e `OFFSET 0` | `:824-847` |
| 3 | Na janela de datas, duas contagens antes da página escolhem o filtro do fundo: `EXISTS` por lote ou `IN` a partir das parcelas do fundo | `:853-948` |
| 4 | `lotes_das_remessas` não muda | `:978` |

O ponto 3 em detalhe: conta os pagamentos dos lotes da janela (até 50.000)
e as parcelas do fundo (até 300.000). Se a janela é grande **e** o fundo é
pequeno, monta o conjunto de lotes a partir de **todas** as parcelas do
fundo; em qualquer outro caso, usa o `EXISTS` por lote.

## Onde a rota falha hoje

De 14/10 19h40 a 20/10 18h50 UTC **[C]**:

- `GET /liquidacao/lotes/reais`: 597 chamadas, **124 com 500 (20,8%)**,
  todas por `statement_timeout`. Igual aos 19,5% de antes.
- Das 124: **100 em `lotes_das_remessas`** e **23 na página sem produto**
  (1 em outra consulta).
- Página **com** produto: 265 execuções, **nenhuma** cancelada, p95 16,6 s.

## Pontos a favor

- Mantém o contrato e o critério de fundo, inclusive para lote com mais de
  um fundo: não depende da D11. **[C]**
- Fundo como valor fixo em vez de correlação com `Fundo.id`: equivalente, e
  o Postgres estima o plano com o valor real. **[C]**
- `OFFSET 0` dentro do `EXISTS` é um truque conhecido do Postgres: impede
  que ele vire semi-join (junção que só testa existência) e força o teste
  lote a lote, parando no primeiro pagamento do fundo. Funciona, mas é uma
  dica de plano escondida no código. **[C]** (`simplify_EXISTS_query` no
  código do Postgres recusa subconsulta com `OFFSET`.)

## Problemas

1. **Ataca a parte menor.** Mesmo zerando os cancelamentos da página, ~4 de
   cada 5 erros continuam, porque vêm dos irmãos. **[C]**
2. **As contagens ignoram produto e status.** A escolha olha a janela
   inteira. A chamada com produto (hoje sem cancelamento) passa a pagar a
   contagem e pode cair no caminho pelo fundo, que lê até 300 mil parcelas
   com o soft delete de cada uma, qualquer que seja o filtro. Risco de
   piorar o caso bom. **[H]** Validar com `EXPLAIN` de uma chamada com
   produto e janela de 30 dias.
3. **O pior caso continua no `EXISTS`.** Fundo grande com janela cheia vai
   pelo `EXISTS`, e lote grande de outro fundo continua lido inteiro. O
   ganho ali depende só do `OFFSET 0`. **[C]** no código; ganho **[H]**.
4. **Limites fixos sem medição anexada.** 50.000 e 300.000 não vêm com
   `EXPLAIN` nem número de produção. Com o volume crescendo, um fundo cruza
   o limite e muda de plano sem aviso, e nenhum log diz qual caminho foi
   escolhido. **[C]**
5. **Mais idas ao banco:** de 1 para até 4 consultas por chamada (duas
   contagens, página, valores), mais os irmãos. **[C]**
6. **Testes só de texto do SQL.** Usam sessão falsa: não há teste com dados
   mostrando que os dois caminhos devolvem os mesmos lotes, nem medição.
   **[C]**
7. **Valores (ponto 1):** o PR diz que o `LATERAL` estimava mal, sem
   `EXPLAIN`; no trace de 14/10 página e valores levaram 0,48 s. Neutro até
   prova em contrário. **[H]**
8. **Processo:** branch e commit sem ID de tarefa e em inglês. **[C]**

## Comparação com a tarefa 12

| | PR | Tarefa 12 |
|---|---|---|
| Irmãos (81% dos 500) | não mexe | duas etapas, sem parcela e sem soft delete |
| Fundo da página | escolhe entre dois caminhos por contagem | olha um pagamento por lote |
| Depende da D11 | não | sim |
| Consultas extras | duas contagens | nenhuma |

A raiz é a mesma nos dois: o lote não tem fundo próprio. O PR contorna isso
com heurística; a resposta da D11 decide entre o atalho simples (um
pagamento por lote) e o estrutural (`fundo_id` no lote).

## Recomendação

1. Prioridade continua sendo `lotes_das_remessas` (branch local
   `refact/TS-5383-melhora-consulta-lotes-reais`, sem commits em 20/10).
2. Do PR, aproveitar o fundo como valor fixo e o `OFFSET 0` no `EXISTS`, se
   o `EXPLAIN (ANALYZE, BUFFERS)` na réplica, com os parâmetros de uma
   chamada cancelada sem produto, mostrar ganho. É a parte que pode ajudar
   nos 23 cancelamentos sem esperar a D11.
3. Descartar as contagens, os limites e o caminho pelo fundo, a menos que o
   autor traga `EXPLAIN` provando ganho no fundo grande **e** que não piora
   a chamada com produto.
4. Pedir ao autor os `EXPLAIN` que levaram aos limites: se existem, viram
   evidência aqui.
