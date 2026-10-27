# Estresse local da fase 2 do fechamento (TS-5377), 27/10/2026

Ambiente local de estresse (Docker: Postgres 13, Redis 6.2, RabbitMQ), sem tocar em
produção, sandbox ou staging. Código: branch `fix/TS-5377-fechamento-lote-fase2` contra a
`master` `b15aa94` (base). **[C]**

## Vigente com guarda

O fluxo novo e o legado (`get_lote_vigente_and_fecha_lote` + esteira) fecham a mesma chave ao
mesmo tempo, 12 chaves por rodada.

| Modo | Código | Vigentes | Despachados duas vezes | Fluxo novo despachou vigente já fechado | Lote vazio |
|---|---|---|---|---|---|
| natural, 15 rodadas | base | 180 | 7 | 3 | 0 |
| natural, 15 rodadas | fase 2 | 180 | 6 | 0 | 0 |
| forçado, 10 rodadas | base | 120 | 40 | 7 | 0 |
| forçado, 10 rodadas | fase 2 | 120 | 29 | 0 | 0 |

- Na fase 2, todo despacho duplo é o legado fechando depois do fluxo novo (leitura sem
  guarda). Fica para a C2 (fase 3).
- Nenhum pagamento em dois lotes.

## Espera por trava (os 44 s de 21/10)

- `lock_timeout` de 30 s vale **por espera**, não por transação: com duas travas soltas aos 25 s e
  aos 50 s, 4 de 6 fechamentos terminaram em 50,1 a 50,5 s.
- Com a trava presa 40 s, todos falharam em 30,6 a 30,9 s, com o motivo de linha ocupada.

## Clique repetido

- A checagem prévia do R7 ("há pagamento apto?") abria uma janela: um clique atrasado passava
  pela checagem, pegava a trava depois do primeiro job e trocava o `closed` por "nenhum pagamento
  apto". Aconteceu em 7 de 70 chaves; na base, em 0.
- **Correção:** um `closed` gravado há menos de 30 s recusa pedido novo (409) no script da trava.
- Depois da correção: 0 de 70; 202 = 70, 400 = 129, 409 = 1.201. Pedido depois de 31 s com
  pagamento novo fecha normalmente.
- Custo da checagem prévia: a rota passou de ~200 ms para ~450 ms de p50.

## Onde está

Cenários `vigente_concorrente`, `vigente_duplo_fluxo_novo` e `lock_wait` no `driver.py` do
ambiente local de estresse; passos `f2-*` no `run.sh`.

## TS-5435: fechamento por remessa (mesmo dia)

Código: `feature/TS-5435-fechamento-por-proc-id` (sobre a fase 2). Mesmo ambiente local. **[C]**

- **Migration da modalidade:** upgrade, downgrade (coluna e tipo removidos) e upgrade de novo.
  Produto só com `fechar_lote_por_proc_id`, sem `lote_liquidacao`, vira `manual`: a precedência
  exige os dois.
- **Listagem e tela:** remessa com 2 originadores gera 2 linhas `proc:`; fechar a linha de um
  originador cria 1 lote só com os pagamentos dele; a outra linha e outra remessa ficam intactas.
- **Tela × portão na mesma remessa:** 144 corridas. Toda remessa terminou com cada pagamento em
  exatamente 1 lote (2 lotes por remessa), sem lote vazio, sem lote misturando originador, remessa
  ou fundo, e sem despacho duplo. Em 23 casos o portão ganhou depois de a tela aceitar o pedido:
  o job termina `failed: nenhum pagamento apto` com a remessa fechada (sem efeito no dado).
- **Remessa em processamento:** 400 "A remessa ainda está em processamento.", nada enfileirado.
- **Regressão:** `acumula` e `clique_repetido` iguais às rodadas anteriores.
