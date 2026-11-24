# Guia de migração por produto para o fluxo novo de fechamento

Passo a passo para levar cada produto da liquidação ao fluxo novo à mão, um produto por vez, depois
da release de 24/11/2026. A parte 1 vale para qualquer produto; a parte 2 é o produto 15 (Mercato
Libero), o primeiro, preenchido; a parte 3 mapeia o resto. Complementa o
[guia de ligar](13-post-deploy-switch-on-guide.md) (B1 e B2) e a limpeza da
[TS-5612](22-ts-5612-plan.md).

Consultas na réplica: só leitura, uma por vez, com timeout. Na sandbox, as mesmas consultas valem
para ensaiar.

## Parte 1 — passo a passo de um produto

### Antes de ligar

1. **Deploy conferido:** a cessão subiu com o head `a4f7c2d9e1b6` e o `/deploy-check` passou.
2. **Configuração do produto depois da migration:**
   ```sql
   select produto_id, modalidade_fechamento_lote, gatilho_fechamento_lote_liquidacao,
          agrupamento_lote_liquidacao, liquidacao_baixa_refact
   from produto_config where produto_id = <id>;
   ```
   A migration copia a modalidade antiga: `manual` e `acumulado` viram gatilho `manual`;
   `automatico_*` vira `automatico`; `agendado` vira `agendado`.
3. **Administradora e conciliação dos fundos do produto:**
   ```sql
   select pf.produto_id, f.nome as fundo, f.adm, pf.conciliacao_liquidacao
   from produto_fundo pf join fundo f on f.id = pf.fundo_id
   where pf.produto_id = <id> order by f.nome;
   ```
   - `conciliacao_liquidacao` diferente de `nao_aplica`: o lote para na conciliação antes da
     administradora. Fechado depois do corte (14h) com conciliação automática, vai para a manual,
     e salvar um horário depois do corte dispara o e-mail de aviso.
   - `adm = capitalis`: o arquivo de liquidação sai vazio (`Cnab240SisVazio`); nada vai para
     administradora de fora.
4. **Agendamento do produto** (a migration criou os do Mercato Libero, da Voltis e do 1604,
   desligados):
   ```sql
   select nome, ativo, expressoes_cron, proxima_execucao_em, atualizado_por, configurado_em
   from agendamento
   where modulo = 'liquidacao' and payload @> '{"produto_id": <id>}'::jsonb;
   ```
5. **Quem fecha hoje:** a varredura da VM, a tela (manual), a rotina fixa do beat (só o 1604) ou o
   automático. Fechar pelo horário leva o lote aberto e todos os pagamentos sem lote da chave, de
   qualquer data, como a tela e a VM já fazem. Produto em que a Operações escolhe o que mandar não
   vai para o horário antes da regra dos avulsos.
6. **Agendador validado** (A4 do guia de ligar): dois disparos seguidos, com 30 min ou mais entre
   eles, sem execução `perdida`. Em 24/11, a sandbox ainda não tinha essa prova (ver a parte 2).

### Ligar (tela)

7. "Configuração do produto", aba Liquidação: gatilho `Agendado`, "Salvar fechamento".
8. Horários (já vêm do agendamento criado pela migration; trocar se o negócio pedir), ligado,
   "Salvar horários". A tela só liga com o gatilho agendado salvo. Nunca ligar pelo
   `PATCH /agendamento/<chave>`: ele não confere o gatilho do produto.

### Conferir

9. Logo depois: a consulta do passo 4 mostra `ativo = true` e a `proxima_execucao_em` (UTC).
10. No horário, no Datadog: "Agendamentos despachados" (beat) e "Fechamento de lotes por horário
    concluído" (worker), com `@qtd_fechadas`, `@qtd_falhas`, `@qtd_recusadas` e `@qtd_lotes`.
    Problemas: "Fechamento por horário ignorado: produto fora do gatilho agendado", "Chave recusada
    no fechamento por horário" (`@motivo`), "Execucao de agendamento presa", "Execucao de
    agendamento nao publicada".
11. A execução no banco:
    ```sql
    select e.status, e.previsto_para, e.iniciado_em, e.finalizado_em, e.erro
    from agendamento_execucao e join agendamento a on a.id = e.agendamento_id
    where a.modulo = 'liquidacao' and a.payload @> '{"produto_id": <id>}'::jsonb
    order by e.id desc limit 10;
    ```
    Esperado: `sucesso`. `perdida` com "atrasada em Ns" é disparo que o beat não fez a tempo.
12. Os lotes do dia na tela de lotes reais do produto.

### Desligar o caminho antigo

13. Produto da VM: deixar todas as rodadas da varredura ligadas nos primeiros dias (os dois juntos
    são seguros: cada um fecha só o que está em aberto). Depois de alguns dias sem `perdida`,
    desligar a rodada do primeiro horário; as outras viram conferência (se só recebem "nenhum
    pagamento apto", o horário cobriu tudo); por fim, desligar a varredura do produto (TS-5738).
14. 1604: ligar o agendamento novo e apagar a rotina fixa do beat juntos (TS-5612); os dois
    ligados fecham o produto duas vezes.

### Voltar

15. Na tela: desligar os horários, ou trocar o gatilho para `Manual` (desliga e guarda os
    horários). Religar a rodada da VM, se tiver sido desligada. Sem deploy.

## Parte 2 — produto 15 (Mercato Libero), 24/11/2026

| Passo | Situação |
|---|---|
| 2. Configuração | modalidade `manual` hoje; depois da migration, esperado gatilho `manual`, agrupamento `por_chave`. Conferir depois do deploy. |
| 3. Fundos | 3 fundos, `adm = capitalis`, conciliação `nao_aplica` (réplica, 24/11): sem conciliação e sem aviso de corte. |
| 4. Agendamento | criado pela migration, desligado, com 16h, 17h, 18h e 20h45 em dias úteis (padrão D28, igual às rodadas da VM). |
| 5. Quem fecha | a VM, com a mesma regra: o horário não leva nada que a VM não levaria. |
| 6. Agendador | em 24/11 a sandbox perdeu 3 disparos do backstop, com o beat ainda com `CELERY_CONFIRM_PUBLISH=1`; a variável saiu às 14:33 UTC (`a1b8c3b`, argocd). Conferir os disparos de 15:00 UTC em diante com `scripts/a4_despacho.py` (pasta privada) antes de contar só com o horário. |
| TS-5537 | a correção não está em produção nem nesta release: os 10 contratos presos do 15 seguem em `liberando`, e os pagamentos deles não entram em fechamento nenhum. Decidir sobre eles quando a TS-5537 subir. |
| 13. VM | manter as quatro rodadas ligadas nos primeiros dias. |

## Parte 3 — os outros produtos

| Grupo | Produtos | Depois do deploy | Para o fluxo novo | Depende de |
|---|---|---|---|---|
| Mercato Libero | 581, depois 4, 80, 81 e 1406 | VM | agendado, 16h, 17h, 18h e 20h45 (agendamentos já criados) | A4; drenar os lotes abertos antigos do 4, 80, 81 e 1406 antes (guia de ligar, B1) |
| Voltis | 449, 713, 1044, 746, 1043 | manual, pela tela (a confirmar) | agendado, 13h30 (já criados; 1043 agrupa `por_chave_sem_origem`) | A4; confirmar com a Operações que a Voltis manda tudo no horário |
| 1604 | 1604 | rotina fixa do beat | agendamento novo, 16h | TS-5612 (liga o novo e apaga o legado juntos) |
| Automáticos | 22, 26, 27, 28, 39, 42, 878, 1142, 1472, 1505, 1637 | fluxo novo desde o deploy | nada a configurar; acompanhar o backstop | — |
| Manuais | os demais | manual, pela tela | ficam manuais | regra dos avulsos com o negócio, antes de qualquer horário |
| Esteira de baixa nova | todos, um por dia, do menor volume para o maior | esteira atual | `liquidacao_baixa_refact` ligada (guia de ligar, B2) | TS-5612 para virar a única |

Lista completa por gatilho, para fechar a parte 3 depois do deploy:

```sql
select pc.gatilho_fechamento_lote_liquidacao, pc.agrupamento_lote_liquidacao,
       count(*) as produtos, array_agg(pc.produto_id order by pc.produto_id) as ids
from produto_config pc
group by 1, 2 order by 1, 2;
```
