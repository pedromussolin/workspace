# Conceitos: valor presente, taxa e accrual de juros

Para quem chega à feature sem formação em finanças. Os exemplos usam números
redondos e inventados; os números reais estão na
[tarefa 01](tasks/01-stock-movement.md) e nas [evidências](evidence/).

## 1. Valor de face e valor presente

Um fundo de crédito compra "promessas de pagamento". Exemplo: um cliente vai
pagar **R$ 1.000 daqui a 12 meses**.

O fundo não paga R$ 1.000 por isso hoje. Ele vai esperar um ano para receber e
corre o risco de o cliente não pagar, então só aceita comprar com desconto.
Digamos que pagou **R$ 800**.

- **Valor de face (nominal):** R$ 1.000, o que o cliente paga no vencimento.
  Coluna `vl_nominal_parcela`.
- **Valor presente (VP):** quanto a promessa vale hoje. No dia da compra,
  R$ 800. Coluna `vl_presente_parcela`.
- **Taxa:** o ganho embutido. Pagar 800 para receber 1.000 em um ano equivale a
  **25% ao ano** (a.a.).
- **Estoque do fundo:** a soma do VP de todas as parcelas que ele tem.

A fórmula que liga as três coisas:

```
VP = nominal ÷ (1 + taxa)^(tempo até o vencimento, em anos)
```

## 2. O VP sobe sozinho: o accrual de juros

Conforme o vencimento se aproxima, a promessa vale cada vez mais, até valer os
R$ 1.000 no último dia:

| Momento | VP da parcela | Quanto subiu no mês |
|---|---|---|
| Dia da compra | R$ 800,00 | — |
| 1 mês depois | R$ 815,02 | **R$ 15,02** |
| 6 meses depois | R$ 894,43 | — |
| 11 meses depois | R$ 981,58 | — |
| Vencimento | R$ 1.000,00 | **R$ 18,42** |

**Essa subida é o accrual de juros:** o quanto o fundo "ganha" só com a
passagem do tempo, sem ninguém pagar nada. Somando os 12 meses dá exatamente os
R$ 200 de desconto. O accrual não vem em coluna nenhuma do lake; ele é
calculado.

## 3. Que taxa é essa

É a porcentagem anual que diz quanto a parcela ganha de valor com o tempo. Nos
dados há duas, por parcela, na view `plgn.administradores_estoque`:

- **Taxa de cessão (`taxa_cessao`):** a taxa embutida no **preço que o fundo
  pagou** ao comprar a parcela de quem originou o crédito (o cedente). No
  exemplo: 800 por 1.000 em um ano = 25% a.a.
- **Taxa do recebível (`taxa_recebivel`):** pelo nome, a taxa do **próprio
  crédito**, a que o cliente paga no contrato. **[H]** Confirmar o significado
  com a controladoria. Se o contrato do cliente cobra 20% a.a., pela taxa do
  contrato a mesma promessa vale R$ 833,33 hoje.

O VP, e portanto o accrual, muda conforme a taxa usada:

| Taxa usada | VP hoje | Accrual no 1º mês |
|---|---|---|
| 25% a.a. (cessão) | R$ 800,00 | R$ 15,02 |
| 20% a.a. (recebível) | R$ 833,33 | R$ 12,76 |

**Regra do dashboard:** usar a mesma taxa que o administrador usou para
calcular o VP. Assim o accrual acompanha a subida real do VP. Nenhuma coluna
diz qual taxa ele usou, então a escolha saiu dos dados. **[C]**:

- Numa amostra, Fydd e Genius calculam o VP pela taxa do recebível.
- No Kanastro, as duas taxas são praticamente iguais.
- Na Dayvale, a taxa que reproduz o VP fica entre as duas.
- Na BGT, a taxa do recebível vem vazia.

Por isso a consulta usa `taxa_recebivel` e cai para `taxa_cessao` quando a
primeira vem vazia. **Isso é inferência, não regra confirmada:** a D14 pede ao
time de dados ou à controladoria a confirmação de qual taxa cada administrador
usa. Detalhes e limites em
[tarefa 01](tasks/01-stock-movement.md#qual-taxa-e-por-quê).

Junto de cada taxa vem o **método** (`metodo_taxa_recebivel`,
`metodo_taxa_cessao`), que diz como contar o tempo (seção 4). E a **unidade**
varia: a BGT manda 75,32 (= 75,32%), os demais mandam 0,2388 (= 23,88%).

Taxa faltando, VP que não bate com a taxa informada e taxas estranhas são
problemas do lake, que o time de dados valida e corrige
([data-problems.md](data-problems.md), P7, P8 e P10). O dashboard
usa as taxas como vêm (D12), e o efeito aparece na conferência (seção 8).

## 4. Juros compostos e contagem de dias

**Juros compostos:** cada período rende sobre o valor já acumulado. Por isso a
subida mensal cresce um pouco a cada mês (R$ 15 no primeiro, R$ 18 no último),
e 25% ao ano **não** é 25 ÷ 12 = 2,08% ao mês, e sim 1,88% ao mês:

```
taxa mensal = (1 + 0,25)^(1/12) − 1 = 1,88%
```

**Contagem de dias:** a fração do ano que passou é contada de um jeito por
administrador, conforme o método:

| Método | Como conta | Um mês típico |
|---|---|---|
| `expb252_aa` | dias úteis ÷ 252 (dias de banco num ano) | 21 ÷ 252 = 1/12 |
| `exp360_aa` | dias corridos ÷ 360 | 30 ÷ 360 = 1/12 |
| `exp365_aa` | dias corridos ÷ 365 | 30 ÷ 365 |

A fórmula do accrual de um período fica:

```
accrual = VP no início × ((1 + taxa)^(dias ÷ base) − 1)
```

Exemplo, a parcela do início num mês de 21 dias úteis:
800 × (1,25^(21/252) − 1) = R$ 15,02.

## 5. Por que a Mov. Estoque precisa do accrual

A aba explica como o estoque foi do **saldo inicial** ao **estoque real** no
fim do período. Só três coisas mexem nele:

1. **Aquisições:** parcelas novas entram (o estoque sobe).
2. **Baixas:** parcelas pagas saem (o estoque desce).
3. **Accrual:** as parcelas que ficaram passam a valer mais (o estoque sobe).

Um fundo de brinquedo, durante um mês:

- **Início do mês:**
  - parcela A, VP de R$ 800 (a do exemplo);
  - parcela B, de R$ 500, que vence no fim do mês e hoje vale R$ 490,79.
- **No mês:**
  - B é paga (R$ 500);
  - o fundo compra C por R$ 300 no último dia.
- **Fim do mês:** A vale R$ 815,02 e C vale R$ 300, total de R$ 1.115,02.

| Etapa | Valor |
|---|---|
| Saldo inicial (800 + 490,79) | 1.290,79 |
| + Aquisições (C) | 300,00 |
| − Baixas (B) | 500,00 |
| + Accrual (A rendeu 15,02; B rendeu 9,21 até vencer) | 24,23 |
| **= Saldo final calculado** | **1.115,02** |
| Estoque real | 1.115,02 |

Sem o accrual, faltariam R$ 24,23 e a conta não fecharia. Aquisições e baixas
vêm prontas das views; o accrual precisa ser calculado.

## 6. Três formas de calcular o accrual

**A. Pela sobra (residual).** Accrual = o que falta para a conta fechar:
1.115,02 − 1.290,79 − 300 + 500 = 24,23. É simples, mas a conta sempre fecha,
então nenhum erro aparece. Se a compra de C não viesse no arquivo de
aquisições, a sobra daria **R$ 324,23 de "accrual"** (25% do fundo num mês) e
ninguém perceberia. **Descartada.**

**B. Pela fórmula (taxa × prazo). Primeira escolha (D4), substituída pela
D15.** Calcula quanto cada
parcela **deveria** ter rendido, pela taxa dela e pelos dias que passaram
(seção 4). Não depende das aquisições e baixas, então o saldo calculado e o
estoque real ficam independentes um do outro. No caso da compra de C sem
registro, o saldo calculado daria R$ 815,02 contra R$ 1.115,02 reais: a
diferença de −R$ 300 acende o alerta. Essa é a **conferência** do protótipo.

**C. Parcela a parcela (roll-forward). Escolhida (D15).** Compara, nos dados,
o VP de cada parcela no início e no fim de um intervalo curto; o que as
parcelas que ficaram subiram é o accrual. Não precisa de taxa, porque mede o
que o administrador de fato apropriou. Em contrapartida, exige juntar ~35
milhões de parcelas de duas fotos, e qualquer mudança de VP das parcelas que
ficaram (não só juros) entra como accrual. A conferência continua funcionando:
a compra de C sem registro apareceria como R$ 300 de parcela nova sem
aquisição. Uma consulta só por intervalo traz saldo, aquisições, baixas,
accrual e estoque ([tarefa 01](tasks/01-stock-movement.md#consulta-única-por-intervalo-d15)).

## 7. A foto de cada dia

O lake guarda uma **foto** do estoque por dia útil (`data_ref`); não há foto
em fim de semana nem em feriado. O accrual é calculado **intervalo a
intervalo** (D15), entre duas fotos seguidas, ou seja, dia a dia (D23).

- Em cada intervalo, o accrual é o quanto subiu o VP das parcelas presentes
  nas duas fotos.
- Qualquer período é a **soma dos dias** dele. Por isso a tela aceita Data
  inicial e Data final livres (D6), e a evolução mensal é a soma por mês.
- A parcela rende só enquanto está no estoque. Se C fosse comprada no dia 15,
  ela apareceria nas fotos a partir dali e renderia ~R$ 2,80 até o fim do mês.
  Uma conta única sobre a foto do início do mês não a enxergaria.
- **Custo:** cada foto tem ~35 milhões de parcelas. O cálculo de cada
  intervalo é feito uma vez e guardado por fundo; a tela só soma (D10).

**Por que não comparar só a primeira e a última foto do período.** "VP no fim
− VP no início" está certo para uma parcela que fica no estoque o período
todo. O problema são as que entram ou saem no meio. Um fundo com 3 parcelas:

| Parcela | O que acontece | VP no início | VP no fim | Rendeu |
|---|---|---|---|---|
| A | fica o período todo | 100 | 110 | 10 |
| B | é paga no meio, por 105 | 100 | — (saiu) | 5 |
| C | é comprada no meio, por 100 | — (não existia) | 105 | 5 |

Saldo inicial 200, aquisições 100, baixas 105, accrual real 20, estoque real
215. O waterfall certo fecha: 200 + 100 − 105 + 20 = 215.

- **Com o VP do estoque inteiro:** 215 − 200 = 15. Isso é aquisição − baixa +
  rendimento (100 − 105 + 20), não só rendimento. No waterfall, aquisições e
  baixas entrariam duas vezes: 200 + 100 − 105 + 15 = 210.
- **Com o VP só das parcelas do início (A e B):** A dá 10. B não tem VP no fim
  e seu rendimento some; se o VP final dela contar como zero, a conta dá −100,
  que é a baixa de novo. C não estava no início e seu rendimento nunca entra.
  Accrual 10, saldo calculado 205.

Aplicando a mesma conta em pedaços curtos (mês a mês ou dia a dia) e somando,
quase toda parcela fica o pedaço inteiro, que é o caso em que a conta
funciona.

Exemplo de um ano, com as parcelas das seções anteriores:

- **1º de janeiro:** o fundo tem só a parcela A (VP R$ 800, vence no fim do
  ano a 25% a.a.).
- **1º de julho:** compra B por R$ 800.
- **Fim do ano:** A é paga (R$ 1.000) e B vale R$ 894,43.

O accrual real é 294,43 (A rendeu 200, B rendeu 94,43). A conta direta dá
**zero**: A não existe no fim e B não existia no início. Encadeando foto a
foto, cada parcela rende enquanto está no estoque e a soma dá os 294,43.
Encadeando por mês, cada parcela perde o mês em que entrou ou saiu: A perde
dezembro (R$ 18,42) e B perde julho (R$ 15,02), e a soma dá 260,99.

## 8. O que sobra na conferência

O saldo final calculado quase nunca bate no centavo com o estoque real. Com o
roll-forward, a diferença se separa em duas partes, as duas calculadas pela
própria consulta:

```
estoque real − saldo calculado = (VP das parcelas que entraram − aquisições)
                               + (pago pelas parcelas que saíram − VP delas)
```

O que entra em cada parte:

1. **Baixa pelo valor pago (D3).** O estoque cai pelo VP da parcela no dia em
   que ela sai, mas a baixa usa o `vl_pago`. Se B tivesse sido paga com R$ 5 de
   multa (R$ 505), o saldo calculado ficaria R$ 5 abaixo do real. Desconto por
   antecipação, multa e perda em renegociação entram aqui.
2. **Salto na entrada.** **[H]** Se o fundo paga a parcela pela taxa de cessão
   (R$ 800 a 25%) e o administrador calcula o VP pela taxa do recebível (20%), a
   parcela já aparece no estoque valendo ~R$ 833. Esses ~R$ 33 não são
   aquisição (que foi R$ 800) nem accrual. Nos dados reais ainda não está
   provado que isso acontece (P10).
3. **Rendimento no dia da entrada e no da saída** de cada parcela, que o
   encadeamento diário não pega (D23).
4. **Erros de dado:** aquisição ou baixa que não veio, fundo que trocou de
   administrador ([data-problems.md](data-problems.md)).

Até ~1% é normal. Acima disso, o protótipo pinta de vermelho, e vale
investigar com a [conferência por parcela](attachments/sql/reconciliation_by_installment.sql).

## 9. PDD: faixa, régua e efeito vagão

**PDD** (provisão para devedores duvidosos) é a parte do VP que o fundo já
reconhece que talvez não receba. Não sai do VP: fica ao lado, e o "VP líquido"
é VP − PDD.

**Como se acha a faixa de um contrato.** O atraso do contrato é o da parcela
vencida **mais antiga ainda não paga**: na foto de 30/09, uma parcela vencida
em 10/09 e não paga dá 20 dias. Contrato sem parcela vencida está em dia. No
lake, é o `dias_atraso` da view por contrato (nulo = em dia).

**Régua.** Tabela que liga a faixa de atraso a um % de PDD. Cada produto tem a
sua. A do produto 713, cadastrada no platform-cessao e aplicada pelo
administrador **[C]**:

| Atraso | Em dia | 1–15 | 16–30 | 31–60 | 61–90 | 91–120 | 121–150 | 151–180 | 181–360 | 361+ |
|---|---|---|---|---|---|---|---|---|---|---|
| % de PDD | 1% | 1,9% | 6% | 15% | 33% | 47% | 66% | 86% | 100% | 100% |

O administrador dá um nome a cada faixa (no Genius: A, B, C … I, `WOP`). Esse
nome é o "rating" da Abertura de Rating.

**Efeito vagão (arrasto).** A parcela atrasada é a locomotiva: o % da faixa
dela vale para o contrato **inteiro**, inclusive as parcelas a vencer, porque
quem atrasou uma parcela tende a atrasar as próximas. Com `prazo_pdd` =
`devedor`, o arrasto vai além: o pior atraso do sacado vale para **todos os
contratos dele** no fundo. Nos dados, os administradores fazem as duas coisas
([evidência](evidence/rating-migration-redshift-2026-10-22.md#efeito-vagão-26102026)).

Exemplo com a régua acima. Contrato de 4 parcelas, R$ 1.000 de VP cada (R$
4.000), a primeira 20 dias atrasada e as outras a vencer:

| Cálculo | Conta | PDD |
|---|---|---|
| Parcela a parcela (sem vagão) | 6% × 1.000 + 1% × 3.000 | R$ 90 |
| Vagão no contrato | 6% × 4.000 | R$ 240 |
| Vagão no devedor (o mesmo sacado tem outro contrato com 70 dias) | 33% × 4.000 | R$ 1.320 |

**[H]** É a prática de mercado herdada da regra dos bancos (Resolução CMN
2.682/1999); cada fundo define a sua no regulamento ou na política de PDD.


## 10. Nominal abaixo da aquisição (Análise Residual)

Mesmo exemplo da seção 1: a parcela vale **R$ 1.000** no vencimento e o fundo
pagou **R$ 800** por ela.

- **Valor nominal:** R$ 1.000, o que o devedor deve. Se ele paga uma parte, o
  nominal cai para o que falta. **[H]** É o que a coluna
  `vl_nominal_parcela` mostra nas parcelas vencidas; falta validar.
- **Valor de aquisição:** R$ 800, o que o fundo pagou ao cedente pela parcela.
  Não muda com o tempo nem com pagamento parcial. Coluna
  `vl_aquisicao_parcela`.
- **Valor presente (VP):** quanto a parcela vale hoje na carteira. Começa em
  R$ 800 e sobe até R$ 1.000 no vencimento (seção 2). Vencida, vale o
  nominal.

O normal é **aquisição < nominal**: o fundo compra com desconto. A Análise
Residual procura o contrário, e há dois jeitos de chegar lá:

1. **A vencer, comprada acima do valor de face:** o fundo pagou R$ 1.050 por
   uma parcela de R$ 1.000 (ágio), ou a aquisição veio errada. Ex.: BGT F
   (P19).
2. **Vencida, paga em parte:** o devedor pagou R$ 600; o nominal caiu para
   R$ 400, abaixo dos R$ 800 da aquisição. Não é perda em si: o fundo já
   recebeu R$ 600. O que sobra a receber é que está abaixo do custo.

**Contrato × parcela.** O contrato soma as parcelas em aberto: nominal do
contrato = soma dos nominais; aquisição do contrato = soma das aquisições.
Contrato de 3 parcelas de R$ 1.000, cada uma comprada por R$ 800; a primeira
vencida e paga em parte, com R$ 500 de nominal:

| Parcela | Nominal | Aquisição | Diferença | Caso por parcela? |
|---|---|---|---|---|
| 1 (vencida) | 500 | 800 | −300 | sim |
| 2 (a vencer) | 1.000 | 800 | +200 | não |
| 3 (a vencer) | 1.000 | 800 | +200 | não |
| **Contrato** | **2.500** | **2.400** | **+100** | **não** |

Por parcela, a parcela 1 aparece. Pelo contrato, não: as sobras das parcelas 2
e 3 **compensam** a falta da parcela 1. O contrato só aparece quando a soma das
faltas passa da soma das sobras, como num contrato de uma parcela só.
