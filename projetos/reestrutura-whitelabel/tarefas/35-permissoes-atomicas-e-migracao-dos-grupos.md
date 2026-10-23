# 35 — Permissões atômicas por ação, perfis por página e migração dos grupos

- **TS:** TS-5431 (épico TS-5357).
- **Repos:** BFF (catálogo de permissões e de perfis, rotas, migração) e front (ações, "Novo grupo", tela da
  migração).
- **Status (23/10):** desenho combinado com o Pietro (D125 a D127). **Antes de implementar, falta o
  levantamento de todas as telas** (não feito ainda, a pedido dele).
- Fora da `release/20261026`.

## Por quê

O acesso passa a ser só por grupo (D124): grupos de página `[FRONT] <página> - <perfil>` e grupos de
instituição `[FRONT] <NOME>`. Na subida em produção, o Pietro quer recriar todos os grupos no padrão novo
e reatribuir as pessoas, sem se prender aos grupos de hoje, e depois atualizar a variável dos grupos de
instituição com os ids novos.

Hoje uma permissão às vezes cobre funções que o negócio quer separar: no Envio de relatórios,
`report-transfer:update` edita fluxos **e** agendamentos, então não dá para o time de produtos editar só o
agendamento.

## Desenho

1. **Permissões atômicas (D125):** toda ação na tela tem uma permissão própria. Uma página pode ter vários
   escopos, um por área, como o Envio de relatórios já faz com as conexões (`report-transfer-manage`). Ex.:
   Fluxos (`report-transfer`), Agendamentos (`report-transfer-schedules`, novo) e Conexões.
   - Cada separação mexe no catálogo do BFF, na proteção das rotas, nas ações do front e nas app roles do
     App Registration.
   - Ninguém perde acesso na troca: quem tem a permissão antiga ganha as novas pela migração de permissões
     que a tela já tem.
2. **Catálogo de perfis por página (D126):** no BFF, ao lado do catálogo de permissões. Cada página declara
   perfis com nome, descrição e as permissões exatas (ex.: Leitura, Agendamentos, Fluxos, Conexões, Admin).
   - Perfis se somam: uma pessoa pode estar em mais de um perfil da mesma página.
   - Página sem perfis próprios ganha Leitura e Admin.
   - No "Novo grupo" de página, o perfil vem do catálogo com as permissões dele; "Perfil próprio" fica para
     exceções. Grupo de página só recebe permissões da página dele.
3. **Migração no deploy (D127, perfis padrão com exceções):**
   - para cada pessoa e página, a combinação de perfis do catálogo que cabe inteira no acesso efetivo dela
     (permissões diretas e de grupos);
   - o que sobra vira atribuição direta, visível como exceção na aba Pessoas;
   - sobra que se repete em várias pessoas vira sugestão de perfil novo (ex.: aprovações do Pré-Trade por
     área);
   - pela tela, como plano com prévia (quem vai para cada grupo, o que ganha ou perde) e aplicação pelo lote,
     com auditoria;
   - **fase 1** cria os grupos, põe as pessoas e dá as permissões, sem tirar nada; **fase 2**, depois de
     conferir, tira as permissões dos grupos antigos e as atribuições diretas que viraram grupo;
   - grupos de instituição: a fase 2 só depois que a infraestrutura trocar as claims (`org_type` e
     `internal_client_id`) para os grupos novos, senão a pessoa perde a organização e não entra;
   - no fim, a tela gera o valor de `CFG_ACCESS_CONTROL_INSTITUTION_GROUPS` com os ids novos, numa linha só;
   - os grupos `[PLGN AI]` ficam (o código usa os nomes para os departamentos da POLI).

## A fazer antes de implementar

- **Levantamento de todas as telas:** as ações de cada uma, a permissão que protege cada ação e onde uma
  permissão cobre mais de uma função. Com ele, o Pietro decide o que separar e os perfis de cada página.

## Pronto quando

- Toda ação de tela com permissão própria, sem perda de acesso para ninguém na troca.
- Catálogo de perfis por página no BFF, usado pelo "Novo grupo".
- Migração pela tela, em duas fases, ensaiada na sandbox, com a variável gerada no fim.

## Regras

As da [32](32-envio-por-subfluxo.md): git do `~/repos/CLAUDE.md`, commit só depois da revisão do
Pietro, Python em inglês, log com mensagem fixa e dimensões no `extra`, `.ai/` do front, validar local
antes.
