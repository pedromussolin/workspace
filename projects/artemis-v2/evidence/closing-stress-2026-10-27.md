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
