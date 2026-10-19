# 26 — Controle de acesso: organização e UX/UI

- **TS:** TS-5405 · **Branch:** `feature/TS-5405-controle-de-acesso-ux` (front e BFF)
- **Status:** spec aprovada (19/10); [plano de implementação](26-controle-de-acesso-ux-plano.md) em revisão
- **Depende de:**
  - **front:** os commits da 25 (TS-5395). A branch nasce da `refact/TS-5395-refinamento-visual` depois
    deles, porque usa a barra de filtros, a grade de campos e a tabela do refinamento;
  - **BFF:** `release/20261016`, onde o módulo `access_control` já existe (não está na master);
  - **infraestrutura** (entra na 24): atributo e grupo dinâmico no Azure, licença Entra ID P1 e a
    variável nova nos values da sandbox e do staging.

## Por quê

Pedido do Pietro em 19/10, revisando a tela `/access-control` (tarefas 19 e 21):

- inconsistências de design e de estilo entre as abas;
- falta organização e uma UX/UI melhor, em **todas as abas**;
- pedidos por aba:
  - **Permissões:** manter lista, cruzamento código × Azure, criar no Azure, criar e excluir;
    acrescentar **os grupos e as pessoas que têm cada permissão**;
  - **Pessoas:** manter as funções, mas listar **todo mundo que tem acesso ao portal** (com ou sem
    grupo e permissão), a partir de um **grupo dinâmico do Azure** montado por uma flag booleana do
    usuário;
  - **Grupos:** manter as funções; membros e permissões num **modal com alternância entre os dois e
    paginação**;
  - **Em lote e Migração:** só organização e UX/UI.

## Como está hoje (19/10, branch da 25)

- **Toda escrita passa pelo lote.** As abas só põem operações no lote
  (`access-control.store.ts`, `addToBatch`), aplicadas na aba Em lote ou na Migração, com prévia e
  confirmação.
- **Permissões:** catálogo com o cruzamento (`inAzure`, `usedInCode`), KPIs filtráveis, criar no
  Azure e apagar pelo lote. **Só contagens** de pessoas e grupos; não existe lista de quem tem.
- **Pessoas:** busca no diretório inteiro (`GET users` com `$search`), no mínimo 2 letras, até 25,
  sem paginação. Não filtra quem tem acesso ao portal.
- **Grupos:** lista dos grupos do app; com busca, grupos de segurança do diretório (até 50). O
  detalhe abre na linha, com membros e permissões lado a lado.
- **Inconsistências** (conferidas contra a `.ai/` do front):
  - busca num `div` próprio, fora do `app-filter-bar`;
  - ações da linha com formas diferentes por aba (botão de texto, ícone, lixeira, `minus-circle`), e
    nenhuma com `app-table__destructive-action`;
  - listas principais sem paginador; só Permissões ordena;
  - KPIs com larguras diferentes (140, 160 e 240 px);
  - diálogos montados de jeitos diferentes (template em arquivo × inline);
  - o aviso "vale no próximo login" em 4 lugares;
  - sem `write`, os botões somem sem explicar a falta (`permissions.md`).

## Decisões (19/10, Pietro)

| # | Decisão |
|---|---|
| D60 | **Pessoas vêm de um grupo dinâmico do Azure.** A infraestrutura cria o atributo booleano, a regra do grupo e liga a flag de cada pessoa. O BFF só lê os membros (`GroupMember.Read.All`, que já tem). Dar ou tirar acesso ao portal fica fora da tela |
| D61 | **Ações diretas com confirmação.** Cada ação pontual abre um diálogo com a prévia do BFF e aplica ali. A aba Em lote fica só para operações em massa. Mesmo motor de prévia e aplicação, sem endpoint novo de escrita |
| D62 | **Lista e modal de detalhe, iguais nas três abas.** Permissão (Pessoas, Grupos, No código), Grupo (Membros, Permissões) e Pessoa (Permissões, Grupos) |
| D63 | **O BFF nunca tem banco de dados.** A cópia temporária do que vem do Graph fica no Redis que o BFF já usa como cache (Lotes, Pré-Trade), com validade de 5 min, apagada a cada mudança aplicada pela tela. Com o Redis fora, o BFF lê o Graph direto |

## Desenho

### Página

- Título "Controle de acesso" e as abas no mesmo segmentado: Permissões, Pessoas, Grupos, Em lote,
  Migração (as duas últimas só com `write`, como hoje).
- **Sai o aviso fixo das 3 regras.** Cada regra aparece uma vez, onde vale:
  - "vale no próximo login": na confirmação de atribuir;
  - "os membros herdam": ao atribuir a grupo;
  - "recuperável por 30 dias": ao excluir grupo.
- **Sem `write`:** um aviso curto no topo, "Você pode consultar. Para alterar, é preciso a permissão
  `access-control:write`."; os botões de escrita não aparecem.

### Padrão das abas Permissões, Pessoas e Grupos

- KPIs no topo, todos com a mesma largura mínima (240 px, a do padrão).
- `app-filter-bar` com a busca e o filtro de situação. KPI que filtra liga o mesmo filtro.
- Tabela com ordenação e paginação (10 por página).
- **Ações da linha:** ícone com tooltip, mesma forma em todas as abas; "Ver" por último; "Excluir"
  isolado na ponta direita (`app-table__destructive-action`), desabilitado com o motivo quando não dá.
- Clicar na linha abre o modal de detalhe.
- Ação principal da aba ao lado do título ("Nova permissão", "Novo grupo").

### Modal de detalhe (componente da feature, um só)

- **Topo:** nome, código ou e-mail, pílulas e as ações do item; "Excluir" à direita, separado.
- **Corpo:** segmentado entre as listas, com contador; cada lista com busca e paginação de 5
  (`NESTED_TABLE_PAGE_SIZE`).
- **URL:** `?tab=…&role=<value>`, `&group=<id>` ou `&person=<id>`. Recarregar reabre; fechar tira.
- No celular, tela cheia.

### Diálogo de mudança (componente da feature, um só)

- Recebe as operações e o nível de cuidado; chama `batch/preview`, mostra o que vai acontecer,
  aplica com `batch/apply` e mostra o resultado no próprio diálogo. Reaproveita a prévia e o
  resultado do Em lote.
- **Níveis:**
  - **atribuir / adicionar:** confirmação simples;
  - **remover membro ou permissão:** confirmação em vermelho;
  - **excluir permissão ou grupo:** digitar o nome do item.
- Remoção e exclusão mandam `confirm: "REMOVER"` depois da confirmação na tela (o BFF continua
  exigindo).
- Sucesso: toast e a lista atualiza. Falha parcial: item e motivo no diálogo, com "Tentar de novo"
  só do que falhou.

### Permissões

- **KPIs:** Permissões, Faltando no Azure, Sem uso no código.
- **Filtros:** busca (código, nome, descrição, onde o código usa); Situação (Todas, Faltando no
  Azure, Sem uso no código, Desabilitada, Sem ninguém).
- **Tabela:** Permissão (código mono e nome), Situação (pílulas), Pessoas (quem tem, direto ou por
  grupo, sem repetir), Grupos, Ações ("Criar no Azure" quando falta, "Ver", "Excluir").
- **"Nova permissão":** diálogo (valor `escopo:ação`, nome, descrição) → aplica → abre o modal dela.
- **Modal:**
  - topo: código, nome, descrição, pílulas; "Atribuir" (pessoas e grupos), "Criar no Azure" (se
    falta; "Atribuir" fica desabilitado com o motivo até lá) e "Excluir";
  - **Pessoas · N:** uma linha por pessoa: nome, e-mail, origens ("Direta", "Pelo grupo X"); remover só a direta; a
    herdada fica desabilitada com "vem do grupo X: tire a pessoa do grupo ou a permissão do grupo";
  - **Grupos · N:** grupo, membros, remover;
  - **No código · N:** onde o código exige (tela ou rota).

### Pessoas

- **Fonte:** membros do grupo dinâmico (`CFG_ACCESS_CONTROL_PORTAL_USERS_GROUP_ID`), sem as contas
  desabilitadas.
  - Sem a variável: a busca no diretório de hoje, com um aviso de que o grupo não está configurado.
  - Variável com um grupo que não existe: aviso de erro dizendo isso, sem cair na busca no
    diretório.
- **KPIs:** Com acesso ao portal, Sem permissão (filtra).
- **Filtros:** busca (nome, e-mail); Situação (Todas, Com permissão, Sem permissão).
- **Tabela:** Nome, E-mail, Permissões (direto ou por grupo), Grupos (os do portal, como no filtro da aba Grupos), Ações
  ("Atribuir permissão", "Ver"). Paginação, ordenação, busca e filtro no BFF.
- **Modal:**
  - topo: nome, e-mail, pílula "Sem permissão" quando vale; "Atribuir permissão" e "Adicionar a
    grupo";
  - **Permissões · N:** permissão e origem; remover só a direta;
  - **Grupos · N:** grupo e quantas permissões ele dá; "Tirar do grupo" só em grupo criado pela
    tela (regra do Azure); nos outros, desabilitado com o motivo.
- **Escolher pessoas** em qualquer lugar da tela (grupo, atribuição, lote): só da lista de quem tem
  acesso ao portal. Colar e-mails no lote continua.

### Grupos

- **KPIs:** Grupos, Criados pela tela, Sem permissão.
- **Filtros:** busca (nome, descrição, permissão); Origem:
  - **Do portal** (padrão): os que têm permissão do app ou foram criados pela tela;
  - **Todo o diretório:** com 2 letras ou mais, grupos de segurança do Azure (até 50), para achar
    um grupo corporativo e dar permissão a ele.
- **Tabela:** Grupo (nome e descrição), Membros, Permissões (contagem), Origem (pílula), Ações
  ("Ver", "Excluir" desabilitado com o motivo quando o grupo não é da tela ou tem permissão em outro
  app).
- **"Novo grupo":** nome, descrição e, opcionais, os primeiros membros e permissões, aplicados
  juntos → abre o modal dele.
- **Modal:**
  - topo: nome, descrição, origem; "Adicionar membros", "Atribuir permissão" e "Excluir", cada um
    desabilitado com o motivo quando o Azure não deixa (grupo de fora; atribuição a grupo desligada
    até a licença);
  - **Membros · N:** nome, e-mail, "Tirar do grupo";
  - **Permissões · N:** código e nome, "Remover do grupo".

### Em lote

- Só operações em massa. Passos sempre visíveis: **1 Montar → 2 Prévia → 3 Resultado**; da Prévia
  volta para Montar sem perder nada.
- **Montar:** Operação (Atribuir permissões, Remover permissões, Adicionar membros, Tirar membros);
  na grade de campos, Pessoas (de quem tem acesso), Colar e-mails, Grupos e Permissões; "Adicionar
  ao lote" → tabela "Operações do lote" (tipo, operação, tirar), com paginação; "Limpar" e "Ver a
  prévia" no cabeçalho dela.
- **Saem do lote:** "Nova permissão" e "Novo grupo" (criados direto nas abas) e o aviso "N operações
  esperam no lote" nas outras abas.
- **Prévia:** resumo por tipo, bloqueados com o motivo, agrupado por ação (como hoje); "Aplicar";
  com remoção, digitar REMOVER; "Voltar e editar".
- **Resultado:** KPIs (Feitos, Pulados, Falharam, Bloqueados), tabela item a item com paginação,
  "Tentar de novo as que falharam" e "Novo lote".

### Migração

- Uma frase no topo: copia as pessoas e os grupos da permissão antiga para a nova, sem tirar a
  antiga.
- Passos **1 Plano → 2 Prévia → 3 Resultado**: o plano com os KPIs e a tabela (antiga, nova, quantos
  têm a antiga, o que vai na prévia); Prévia e Resultado com as mesmas peças do Em lote.
- Sem nada a migrar: estado vazio "Nada a migrar".
- Mesmo tamanho de KPI e colunas no centro (a "Operação" e o "Item" de hoje estão à esquerda sem
  ser texto longo).

## BFF (módulo `access_control`)

| Rota | Mudança |
|---|---|
| `GET access-control/settings` | `+ portalUsersGroup`: `not-configured`, `ok` ou `not-found` (o BFF confere se o grupo existe) |
| `GET access-control/roles` | `+ peopleCount` por permissão (direto ou por grupo, sem repetir) |
| `GET access-control/roles/{value}/holders` | **nova:** `{ people: [{ id, displayName, mail, origins: [{ via, groupId, groupName, assignmentId }] }], groups: [{ id, displayName, memberCount, assignmentId }] }`, uma linha por pessoa com todas as origens |
| `GET access-control/people` | com o grupo configurado: membros do grupo dinâmico, `search`, `status` (`all`, `with-roles`, `without-roles`), `sort`, `page`, `perPage`; cada pessoa com `roleCount` e `groupCount`; resposta com o total. Sem o grupo: a busca de hoje |
| `GET access-control/people/{id}` | `+ groups` (os do portal de que a pessoa é membro direto, com quantas permissões cada um dá) |
| `POST access-control/batch/apply` | apaga o cache do controle de acesso no fim |

- **Variável nova:** `CFG_ACCESS_CONTROL_PORTAL_USERS_GROUP_ID` (vazia por padrão).
- **Graph:** membros do grupo com `$select` e `$top=999`, seguindo o `nextLink`; nenhuma permissão
  nova.
- **Cache (D63):** membros do grupo dinâmico, atribuições do app e membros de cada grupo com
  permissão, no Redis existente, com validade de 5 min. Apagado no fim de cada `apply`. Redis fora
  ou com erro: lê o Graph direto e registra um WARNING (padrão de logs como eventos).
- O motor do lote não muda.

## Front (`features/access-control`)

- **Peças novas da feature:** modal de detalhe, diálogo de mudança, seletores de pessoas (da lista
  de quem tem acesso), grupos e permissões, e o cabeçalho de passos do Em lote e da Migração.
- **Store:** deixa de girar em torno do lote; cada aba cuida dos seus dados; o modal aberto fica na
  URL.
- **Data-access:** `holders`, os parâmetros novos de `people` e os campos novos de `settings`,
  `roles` e `people/{id}`.
- Só peças de `shared/ui`; nada novo em `shared/ui` sem passar por mim. Regras de alinhamento,
  ações, paginação e filtros da 25.
- `.ai/` muda junto (padrão da tela de controle de acesso, se virar referência).

## Testes

- **BFF** (Graph falso `tests/unit/services/fake_graph.py`):
  - lista de pessoas do grupo: paginação, busca, situação, ordenação e contagens;
  - `holders`: direta, por grupo, sem repetir;
  - cache: acerto, falta, apagado depois do `apply`, Redis fora;
  - sem a variável (busca de hoje) e com grupo inexistente (erro);
  - `settings`, `roles.peopleCount` e `people/{id}.groups`.
- **Front:**
  - cada aba: filtros, KPIs que filtram, tabela, ações e o aviso sem `write`;
  - modal: segmentado, busca, paginação e a URL;
  - diálogo de mudança: os três níveis, falha parcial e "Tentar de novo";
  - passos do Em lote e da Migração;
  - smoke de `/access-control` em claro, escuro e celular, com dados fictícios para as rotas novas
    no BFF falso.

## Fora do escopo

- Dar ou tirar a flag de acesso ao portal pela tela (D60).
- Banco de dados no BFF (D63).
- Mudar o motor do lote ou as regras de bloqueio (dono do grupo, uso no código, licença).

## Execução

- Agentes Sonnet com pastas disjuntas e o brief da rodada:
  1. BFF e as peças comuns do front (modal, diálogo de mudança, seletores, store e data-access), em
     paralelo;
  2. as abas em paralelo (Permissões, Pessoas, Grupos, Em lote + Migração);
  3. revisão, validação (`validar-leva.sh` e smoke) e plano de commits para o Pietro aprovar.
- Commits só depois da revisão, em PT-BR, `tipo(TS-5405): …`, sem `Co-Authored-By`.
