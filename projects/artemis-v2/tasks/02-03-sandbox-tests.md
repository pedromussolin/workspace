# Testes na sandbox: fase 2 do fechamento (TS-5377) e fechamento por remessa (TS-5435)

- **Data:** 28/10/2026. Status: a sandbox está com o código novo; os testes ainda não começaram.
- **Código na sandbox:** cessão `efd1db7`, BFF `20a5d4b` e front `666b080`, que são a cabeça da
  `sandbox` em 27/10. As branches originais estão em:

  | Repo | Fase 2 (`fix/TS-5377-fechamento-lote-fase2`) | TS-5435 (`feature/TS-5435-fechamento-por-proc-id`) |
  |---|---|---|
  | cessão | `9e3d563fe` | `8873832dd` |
  | BFF | `c63b498` | `3bf3e82` |
  | front | `241a8132` | `bf378f60` |

- **Plano:** [02-03-implementation-plan.md](02-03-implementation-plan.md). A TS-5435 foi reescopada
  em 27/10 para só o fluxo novo (`decisions.md`).

## Estado da sandbox, conferido em 28/10 **[C]**

| Repo | PRs mergeadas em 27/10 | Tag no argocd (27/10, 21:01 BRT) | Subida |
|---|---|---|---|
| cessão | #2710, #2711, #2712 | `sand-efd1db7` | migration `c3f81d7a5e24` às 00:17 UTC de 28/10; API, worker e beat reiniciados |
| BFF | #228, #229 | `sand-20a5d4b` | 28/10, entre 00:15 e 00:40 UTC |
| front | #241, #242 | `sand-666b080` | idem |

- **Tags:** as três batem com a cabeça da `sandbox` de cada repo.
- **"Failure" no GitHub Actions:** todos os builds da `sandbox` falham desde 14/10, nos três
  repos.
  - Quem falha são o passo de deploy direto no cluster e a validação depois do deploy ("No
    running pods found").
  - O build e o push da imagem passam, e quem sobe a versão é o argocd.
  - Não bloqueia os testes.
- **Erros desde a subida:** nenhum é do fechamento.
  - O beat caiu uma vez às 00:17 UTC, porque falhou o download da ferramenta que carrega a
    configuração, e voltou sozinho às 00:18. É o mesmo de 20/10 em produção.
  - `GET /titulo/contratos` deu 500 66 vezes entre 06:13 e 11:09 UTC. É de outro domínio.
  - Houve um timeout de API externa na renegociação e uma falha de resolução de nome do RabbitMQ às 05:11.
- **Uso:** nenhum fechamento de lote fake foi exercitado na sandbox até 28/10, ~14:00 UTC.
- **Consulta para repetir:** `kube_namespace:sandbox service:platform-cessao*`, sem os avisos do
  uWSGI e do Celery por rodar como root.

## Preparar a massa

Hoje não temos acesso de leitura ao banco da sandbox. A massa sai da tela ou de quem tiver esse
acesso.

| O que achar na sandbox | Cenários |
|---|---|
| linha `origem:` com pagamentos aptos (produto que fecha por chave) | S1 a S4 |
| produto que acumula, com lote vigente aberto | S5 |
| usuário de parceiro sem acesso a algum produto | S6, S10 |
| linha `proc:` de produto `automatico_por_remessa` (`lote_liquidacao` e `fechar_lote_por_proc_id` ligados), de preferência com 2 originadores | S8, S9 |
| remessa com processo ainda fora de `cadastrado`, `rejeitado` e `errado` | S11 |
| produto com `fechar_lote_por_proc_id` ligado e `lote_liquidacao` desligado, se existir | S14 ([B22](../bugs-found.md)) |

**Onde acompanhar (Datadog):**
- cessão: `kube_namespace:sandbox service:platform-cessao* "Fechamento de lote fake"`. Os eventos
  são solicitado, concluído, falha e descartado. O concluído traz `payments_count` e `batches`.
- BFF: `kube_namespace:sandbox service:apl-credit-whitelabel-api`, rotas de `fake-batches`.

## Roteiro

### Fase 2 (TS-5377)

| # | Cenário | Como | Esperado |
|---|---|---|---|
| S1 | Fechar uma linha `origem:` | Fechar e confirmar | A confirmação mostra "N registros nesta data" e avisa que leva os pendentes de outras datas (D19). Aparece o toast "Fechamento em processamento" e a linha fica "Fechando…". O Excluir fica desabilitado, com a dica "Fechamento em andamento" (R11). No fim aparece "Lote fechado: N pagamentos no lote X." e a lista recarrega sozinha (R24, R26) |
| S2 | Clique repetido | Durante o fechamento, e até 30 s depois, clicar de novo (ou fechar em outra aba) | 409, com "Lote já está em fechamento". Sai um lote só |
| S3 | Pedido sem pagamento apto (R7) | Depois de 31 s, repetir o POST do S1 pelo DevTools (aba Network, repetir a chamada), sem pagamento novo | 400 "Nenhum pagamento apto para fechar.", sem "Fechando…" e sem log "solicitado" |
| S4 | Status falhando (R25) | Durante um fechamento, bloquear a rota de status no DevTools (Network request blocking) e depois desbloquear | As consultas se espaçam em 4, 8, 16, 32 e 60 s. Na 3ª falha aparece, uma vez só, "Não está dando para consultar o status do fechamento; continuamos tentando.". Ao desbloquear, volta a 4 s e conclui |
| S5 | Lote vigente (produto que acumula) | Fechar a linha com o vigente aberto | O vigente fecha e vai para a esteira uma vez só, e o resultado lista o lote. No legado, um despacho duplo ainda é possível (C2, fase 3) |
| S6 | Exclusão fora do escopo (A2) | Com um usuário de parceiro, chamar o `DELETE` de lote fake de um produto que não é dele, direto no BFF | 403, sem chamada à cessão |

Ficam cobertos só pelos testes locais, porque exigem derrubar o Redis ou o worker de uma sandbox
compartilhada:
- R8 (a chave some do status);
- 502 ou 504 no POST;
- o aviso "demorando" depois de 15 min;
- a falha parcial.

### TS-5435 (fechamento por remessa)

| # | Cenário | Como | Esperado |
|---|---|---|---|
| S8 | Fechar uma linha `proc:` | Fechar e confirmar | O título é "Fechar a remessa <proc_id>?" e o texto pergunta se deve "fechar a remessa inteira (N registros)", com "Sai um lote para cada fundo e originador". O POST vai para a rota assíncrona, não para a de consolidate. Sai um lote real por fundo e originador, sem pagamento de outra remessa. A linha `proc:` entra no polling de status |
| S9 | Remessa com 2 originadores | Igual ao S8 | 2 lotes, um por originador |
| S10 | Escopo no status | Usuário de parceiro com linhas `proc:` | O status só traz produtos do parceiro (o filtro é pelo `product_id` do registro) |
| S11 | Remessa em processamento (D23) | Fechar a linha | Toast "A remessa ainda está em processamento.", sem "Fechando…" e sem nada na fila |
| S12 | Modalidade no cadastro | Atualizar a config de um produto sem mexer nas flags; depois mandar `acumula_liquidacoes` e `fechar_lote_por_proc_id` juntos | No primeiro caso as flags ficam iguais e a modalidade é derivada delas. No segundo, 400 "acumula_liquidacoes não combina com fechar_lote_por_proc_id" |
| S13 | O legado continua igual | Remessa nova de um produto por remessa terminando sozinha; `POST /liquidacao/` | Comportamento igual ao da `master`: o portão fecha o lote por proc_id no fim da remessa |
| S14 | Linha `proc:` que a tela não fecha (B22) | Produto só com `fechar_lote_por_proc_id`, se existir | 400 "A chave não corresponde à forma como este produto fecha lote.". Isso confirma o B22 |

Registrar o resultado em `evidence/sandbox-tests-2026-10-28.md`: cenário, horário, trace e
resultado.

## Pendências da TS-5435 (`fechar_lote_por_proc_id`), em 28/10

As pendências do fechamento como um todo (fase 2, worker, fase 3, legado) estão em
[03-post-production-cases.md](03-post-production-cases.md#estado-em-2810).

**Antes da release**
1. **Testes na sandbox:** S8 a S14 deste roteiro. Nenhum foi feito.
2. **B22:** a linha `proc:` aparece com o botão Fechar e a tela não consegue fechá-la. Decidir
   entre as opções (a), (b) e (c) do [B22](../bugs-found.md).
3. **Modalidade × flags:** a modalidade não representa toda combinação das quatro flags.
   - **Combinações perdidas [C, código]:** mandar `modalidade_fechamento_lote` no cadastro
     reescreve as flags pela modalidade (`closing_modality.py:21-25`, `legacy_flags` em
     `enum.py:840-855`, cessão `8873832dd`). Uma combinação que ela não representa se perde no
     legado. Exemplo: `lote_liquidacao` com `baixa_por_agendamento` vira `agendado`, e o
     `lote_liquidacao` é desligado.
   - **Quem manda a modalidade:** ninguém, hoje. O BFF e o fetch-api não mandam o campo, e o
     Atlas não grava a config do produto.
   - **Flag mudada direto no banco [H]:** a modalidade não acompanha, e o fluxo novo passa a ler
     uma regra diferente da do legado.
   - **Antes da GMUD:** rodar a consulta 1 de
     [proc_id_pending_checks.sql](../attachments/sql/proc_id_pending_checks.sql) na réplica.
     Ela mostra quantos produtos têm combinação que a modalidade não representa (e o B22).
4. **Release e GMUD:** `release/<data>` com a fase 2 e a TS-5435 nos três repos.
   - Ordem do deploy: cessão (com worker e migration), depois BFF, depois front (R2).
   - No dia, conferir que a `master` tem uma cabeça de migration só. A original encadeia em
     `7ddf133f1f84`, a cabeça da `master` em 27/10. A `-sdbx` encadeia em `e5a1c7b3d9f2`, que
     só existe na sandbox.
   - A GMUD sai pela skill `change-request`, com a migration e o rollback. O downgrade foi
     testado no estresse local.

**Depois da produção**
5. **Remessas presas (B19):** a remessa cujo último processo termina rejeitado ou errado não
   fecha sozinha e, até a migração, fecha pela tela.
   - A consulta 2 da mesma SQL lista as que estão presas hoje. Serão as primeiras linhas `proc:`
     fechadas pela tela.
   - **[C, Datadog]** De 21/10 a 28/10 não houve nenhum `event=lote_ctrl_sem_registro` nem
     `event=backstop_sem_registro` em produção.
6. **Acompanhar** como na fase 1 (`evidence/async-closing-monitoring.md`), incluindo as
   primeiras linhas `proc:` do 1505 e do 1637.
7. **Rota de consolidate do BFF:** sai depois de 7 dias sem chamada no Datadog, contados a partir
   do front novo em produção.
8. **B20:** a exclusão ainda não confere o `proc_id` por conta própria. **[H]** A cessão filtra
   pelo produto; falta validar.

**Na migração do automático** (reescopo de 27/10)
9. **Portão usando a função nova:** a B2 do plano.
   - **[C, Datadog, 21 a 28/10]** O `_processos_agrupados_por_proc_id` rodou 601 vezes, com 30 s
     no total, p95 de 139 ms e máximo de 572 ms. Em 05/10 eram 88 h em 7 dias.
   - A migração não traz mais ganho de banco, só de regra.
10. **B19 e agendado por remessa:** backstop para produto por remessa sem
    `baixa_por_agendamento`.
11. **Tirar as quatro flags** (D24): depende de o legado ler a modalidade.

**Documentação:** as seções B0 a B4 do plano descrevem o desenho anterior ao reescopo. O
`README.md` e o `CONTINUE.md` (de 26/10) estão desatualizados. Atualizar no próximo checkpoint.
