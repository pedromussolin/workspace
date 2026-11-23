+++
card = "TS-5873"
type = "improvement"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-23
+++
# 26 — Fechar linha de agrupamento antigo não mistura origens

## Contexto

Achado 7 da revisão da PR da release de 24/11 (cessão), confirmado como caso de borda. Quando um
produto volta de `por_chave_sem_origem` para `por_chave`, pode sobrar a linha sem origem
(`origem:*:<produto>:<originador>:<fundo>`) com lote aberto. Fechar essa linha, pela tela ou pelo
horário, fecha os vigentes abertos de **todas** as origens daquele originador e fundo antes da hora
e junta num lote só os avulsos de todas as origens. **[C]**

Onde, em `cessao/api/liquidacao/refact.py` (release de 24/11):
- `tem_vigente_aberto`: com chave sem origem, não filtra a origem, então qualquer vigente aberto do
  produto, originador e fundo aceita a chave.
- `close_open_accumulating_batches`: com chave sem origem, fecha todos os vigentes sem `proc_id`
  daquele produto, originador e fundo.
- `_close_fake_batch` com `assign_fake_batch_payments`: sem origem, o filtro não olha
  `identificador_extrato`, e os avulsos de todas as origens vão para o primeiro lote aberto.
- `chaves_com_lote_aberto` e `chaves_a_fechar_do_produto`: o horário também pega a linha que
  sobrou, e ela vem primeiro, porque `*` ordena antes de dígitos e letras.

Gravidade média para baixa: mistura origens e fecha antes da hora, sem perda de valor. Não afeta
24/11: ninguém nasce em `por_chave_sem_origem` (migration da TS-5583). O produto 1043 da Voltis vai
para esse agrupamento na TS-5570, e o caso só aparece se ele voltar a `por_chave` com lote `*`
aberto. Detalhe da verificação no relatório privado da revisão (achado 7).

## Desenho combinado

Quando a chave é sem origem e o agrupamento atual do produto já não é `por_chave_sem_origem` (a
linha que sobrou): fechar só o vigente `*` e não juntar avulsos. Em
`close_open_accumulating_batches`, restringir o fechamento à origem `*`
(`CHAVE_LOTE_FAKE_QUALQUER_ORIGEM`); em `_close_fake_batch`, pular o `assign_fake_batch_payments`
nesse caso. O comportamento de `por_chave_sem_origem` em uso não muda (fechar todos os vigentes do
originador e fundo pela linha sem origem foi aprovado na revisão de 08/11 da TS-5567).

## Pronto quando

- Teste `test_fechar_linha_sem_origem_residual_nao_leva_outras_origens`, que falha antes da
  correção: produto `por_chave` com vigentes `*` (lote L*) e `A` (lote LA) abertos e um avulso de
  origem B; ao fechar `origem:*:p:o:f`, só L* fecha, LA continua aberto e o avulso B continua sem
  lote.
- O mesmo cenário pelo fechamento por horário.
- Suíte da cessão verde nos dois modos (local e da CI).
