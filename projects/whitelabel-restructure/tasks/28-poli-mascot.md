+++
card = "TS-5406"
type = "task"
epic = "TS-5357"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
docs = ["28-poli-mascot-plan.md"]

[tracker]
status = "done"
priority = "Low"
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-13
+++
# 28 — POLI dentro do portal, com mascotes animados

- **TS:** TS-5406 · **Branch:** `feature/TS-5406-poli-mascote` (só front)
- **Status:** **publicada** (20/10), 8 commits sobre a `6303b2e5`, ponta `91b75672`. Plano em
  [28-poli-mascot-plan.md](28-poli-mascot-plan.md)
- **Depende de:** a 26 (TS-5405). A branch nasce da `feature/TS-5405-controle-de-acesso-ux`
  (`6303b2e5`), na worktree `apl-credit-whitelabel-wt/28`. Quando a R59 da 25 for publicada, entra
  por merge a `refact/TS-5395-refinamento-visual` (ela mexe no shell e na sidebar).
- **Faixa de decisões:** D80–D89. A 27 corre em paralelo e usa a sequência a partir da D69.

## Por quê

Pedido do Pietro em 19/10:

- o conteúdo do chat vazio (vídeo do robô, saudação e texto sobre a POLI) não agrada; deveria ser
  algo como "Escreva algo para iniciar um chat";
- a POLI é a única página com cabeçalho próprio, e não deveria ter;
- quer mascotes animados (Poli, Cofre, Moeda e Nota) andando em cima da barra de digitar e fazendo
  as ações; clicar no mascote faz ele interagir, sem balão de mensagem;
- a troca de mascote só existe na página da POLI.

Fonte dos mascotes: o pacote `poli-mascote.zip` (só a Poli; guardado em
`$PRIV/poli-mascote-original/`) e o quadro "Poli em ação" do artefato
https://claude.ai/artifact/6S5AR8hXRvYp2bRE12EGyq (`project/Palco.dc.html`), que tem os quatro.

## Como está hoje

- **Rotas:** as 11 rotas da POLI (`/poli-chat` e os 10 `*-poli-chat`) ficam fora do shell
  (`src/app/app.routes.ts:12-17`, `features/poli-chat/poli-chat.routes.ts:10`), por causa do
  cabeçalho próprio.
- **Cabeçalho:** `features/poli-chat/poli-header/` tem voltar, robô (`assets/general/poli.svg`),
  título do departamento, usuário e sair. O shell já tem usuário e sair no rodapé da sidebar.
- **Chat vazio:** `components/chat/chat.component.html:3-20` mostra o vídeo
  `assets/general/poli-animation.webm`, a saudação e o texto sobre a POLI (`chat.component.ts:85-88`).
- **Home (organização interna):** `features/general/home/home.page.html:1-31` tem o mesmo vídeo, a
  mesma saudação, a caixa de digitar que abre a POLI com a pergunta, o aviso do modelo e o rodapé.
- **Reduced motion:** é o pedido do sistema operacional para reduzir animações. O Windows do Pietro
  está com ele ligado, e o README do pacote manda deixar o mascote parado nesse caso.

## Decisões

| # | Decisão | Quem / motivo |
|---|---|---|
| D80 | A POLI entra no shell, com as mesmas URLs, guards e `data.department`. O cabeçalho próprio sai: usuário e sair ficam na sidebar do portal; o título do departamento vai para o topo da coluna de histórico; o voltar some | Pietro, 19/10: opção recomendada |
| D81 | O chat vazio mostra só a frase "Escreva algo para iniciar um chat", sem sugestões | Pietro, 19/10 |
| D82 | O mascote aparece na POLI e na Home. Na Home ele substitui o vídeo e a saudação; a troca de mascote só existe na POLI | Pietro, 19/10 |
| D83 | A animação segue o sistema por padrão. Junto da troca de mascote há "Animação: ligada/desligada", salva no navegador, que vale por cima do sistema | Pietro, 19/10: acessibilidade por padrão, com escolha da pessoa |
| D84 | Os mascotes são portados para TypeScript em `shared/ui/mascot/`, desenhados em SVG por código, sem imagem. As matrizes e as fases das ações ficam idênticas às do artefato | Pietro, 19/10: abordagem recomendada |
| D85 | O vídeo do robô e o `poli.svg` saem do repositório. Revoga a D46 (o robô ficava como identidade do assistente) | consequência da D80 e da D82 |
| D86 | As cores fixas do pixel art ficam num arquivo só, `shared/ui/mascot/mascot-palettes.ts`, que entra no `ALLOWED` da regra `cor-fora-do-scss` do `check-patterns`. O Cofre e os destaques seguem a cor da marca por token | Pietro, 19/10: aprovou a exceção, que é arte fixa, como as cores das marcas em `themes.ts` |
| D87 | Mascotes menores e do mesmo tamanho: cada pixel do desenho vale 2 px de tela no Cofre, na Moeda e na Nota (44 px de altura) e 1,5 px na Poli, cujo desenho é maior (51 px), em todas as telas | Pietro, 20/10: "tem que ser menores, para não atrapalharem" e "o boneco da POLI tá maior que os outros"; escolhida a opção C de uma comparação lado a lado |
| D88 | A troca de mascote vira um botão de configuração (engrenagem) ao lado do título da coluna, com um menu (os quatro com miniatura e o "Animação"); na coluna recolhida, o mesmo botão. Sai a lista do rodapé | Pietro, 20/10: "é só um adereço da página, então devia ser uma config", sem ocupar a listagem |
| D89 | Com anexos, o chão do mascote é a fileira de cima dos chips: ele só pisa e anda na largura que eles ocupam. Quando o chão muda com ele fora, pousa no ponto mais perto, sem atravessar o ar. Num chão curto, o gráfico e as moedas, que ficam no chão ao lado dele, saem do ciclo e do clique. A caixa de texto avisa essa largura (`topSpanChange`), sem saber do mascote | Pietro, 20/10: "o boneco só pode andar por cima de onde tem chão" |

## Escopo

### Página da POLI

- As 11 rotas passam a ser filhas do shell. A rota marca a página como tela cheia
  (`data.shellContent: 'full'`), e o shell tira a margem do conteúdo, para o chat ocupar a altura
  toda.
- A coluna de histórico ganha:
  - no topo, o título do departamento (o mesmo texto de hoje), acima do "Novo chat";
  - ao lado do título, um botão de configuração (engrenagem) com o menu de mascote e animação
    (D88);
  - recolhida, o mesmo botão.
- O chat vazio mostra a frase no lugar do vídeo, da saudação e do texto sobre a POLI.
- O aviso do modelo, embaixo da caixa, continua.

### Mascote

- **Palco:** uma faixa sobre a barra de digitar, da largura dela, com os pés na borda de cima. A
  faixa fica por cima do fim das mensagens e não bloqueia clique, a não ser no próprio mascote.
  As mensagens ganham um espaço embaixo para a última linha não ficar atrás dele.
- **Tamanho (D87):** cada pixel do desenho vale 2 px de tela no Cofre, na Moeda e na Nota (44 px
  de altura) e 1,5 px na Poli, cujo desenho é maior (51 px). Igual no computador e no celular.
- **Personagens:** Poli, Cofre, Moeda e Nota. O Cofre e os destaques dos itens (contrato, gráfico e
  escudo) usam a cor primária da marca. A Poli, a Moeda e a Nota têm as cores próprias.
- **Chão (D89):** com anexos, a fileira de cima dos chips; sem anexos, a caixa inteira.
- **Sem balão e sem texto de status.** O mascote é decorativo: fica fora do leitor de tela e da
  navegação por Tab.
- **Preferências** (no navegador, chave `portal.mascot`): o personagem (padrão Poli) e a animação
  (padrão: segue o sistema).

### O que dispara as ações

| Momento | Animação ligada | Animação desligada |
|---|---|---|
| Parado | ciclo do artefato (lupa, passear, contrato, calculadora, gráfico, passear, moedas, escudo, dormir), com 8 a 15 s de pausa entre as ações | parado à direita da barra, na pose de repouso |
| Pergunta enviada | larga o que fazia e alterna lupa e calculadora até a resposta | pose "pensando" (olhos para cima) |
| Resposta pronta | comemora (pulinho e gema acesa) | pose feliz por ~1,2 s, com esmaecimento |
| Resposta com arquivo gerado | "Assinar cessão" | pose feliz |
| Erro | para e volta ao ciclo | pose de repouso |
| Clique | se estiver dormindo, acorda comemorando; senão, faz uma ação sorteada diferente da atual | pose feliz |

### Home

- Para a organização interna, o mascote escolhido anda sobre a caixa da POLI no lugar do vídeo, e a
  saudação e o texto sobre a POLI viram a mesma frase do chat vazio. Na Home não há troca de mascote.
- Continuam: a caixa, o aviso do modelo e o rodapé. A Home dos parceiros não muda.

### Diferenças em relação ao artefato

Fora estas, as matrizes de pixels e as fases das ações ficam iguais às do artefato:

- sem balão (`bubble`) e sem status;
- a largura do palco acompanha a barra (o artefato tem 1120 px fixos);
- a pausa entre ações é configurável (no artefato, 12 quadros, ou 1,3 s);
- o sorteio de destino e de ação vem de um gerador injetável, para os testes;
- ação nova `comemorar`, só com a fase de pulinho;
- modo "pensando", que encadeia lupa e calculadora até ser desligado;
- `pose()` e `dirOf()`, repetidos no `poli.js`, viram um só.

## Fora do escopo

- Mascote em outras páginas e ações ligadas a eventos de outras áreas (ex.: pagamento conciliado). O
  serviço já aceita `play(ação)`, mas só a POLI e a Home o usam.
- Sugestões de pergunta no chat vazio (D81).
- Mudanças no BFF.

## Critérios de aceite

1. As 11 rotas da POLI abrem dentro do shell, com as mesmas URLs, guards e departamentos; não há
   mais `poli-header`.
2. O título do departamento aparece no topo da coluna de histórico; usuário e sair, só na sidebar
   do portal.
3. O chat vazio mostra só "Escreva algo para iniciar um chat".
4. Os quatro mascotes aparecem sobre a barra, idênticos ao artefato (as matrizes do porte batem
   caractere a caractere com as do código original, e os prints conferem com o `spritesheet.png`).
5. As reações seguem a tabela acima, com a animação ligada e desligada.
6. A escolha do mascote e da animação fica salva no navegador e vale também na Home.
7. Sem *reduced motion* o mascote anda; com *reduced motion* fica parado, até a pessoa ligar a
   animação.
8. Responsivo até ~400 px, claro e escuro, Poliedro e Dots, sem rolagem lateral.
9. O vídeo do robô e o `poli.svg` não estão mais no repositório.

## Validação

- **Fidelidade:** um script gera todas as poses e itens dos quatro personagens pelo código original
  (`poli.js` e `Palco.dc.html`) e grava um fixture; o spec do porte compara caractere a caractere.
- **Specs:**
  - motor: fases, caminhada, próxima ação, pensando, comemorar e clique;
  - componente: desenho, clique e modo parado;
  - serviço: padrão pelo sistema, escolha salva e comandos;
  - troca de mascote, rotas, shell, página da POLI, chat e Home.
- **`validate-batch.sh`** com a base `6303b2e5`, rotas `/home /poli-chat /legal-poli-chat`.
- **Prints:** POLI vazia, POLI com conversa, POLI com a coluna recolhida e Home. Em claro, escuro,
  Dots e celular, com e sem *reduced motion*. Conferir os quatro personagens contra o
  `spritesheet.png` e o artefato.

## O que foi feito

Implementada e validada em 19–20/10 e commitada em 20/10, depois da revisão do Pietro, na worktree
28. Falta publicar a branch.

### Commits

Cada um compila sozinho e passa nos specs das pastas que toca, conferido numa cópia limpa da base.

| SHA | Commit | O que entra |
|---|---|---|
| `797602fc` | `feat(TS-5406): motor de pixel art dos mascotes em shared/ui` | sprites, itens, paletas, quadro, controlador e chão; fixture de fidelidade; a exceção do `check-patterns` (D86) |
| `066d947d` | `feat(TS-5406): app-mascot e troca de mascote, com exemplo na vitrine` | serviço, componente, cena, troca de mascote (D88), vitrine e `.ai/` |
| `f4927a83` | `feat(TS-5406): caixa de texto avisa a largura do que fica em cima` | `topSpanChange` do `app-textbox-component` (D89) e a linha da `.ai/` |
| `a7ee4ee8` | `refact(TS-5406): POLI dentro do shell, sem cabeçalho próprio` | rotas, shell (`data.shellContent`), título na coluna, `poli-header` apagado |
| `e343931e` | `feat(TS-5406): chat vazio com frase e mascote sobre a barra da POLI` | frase, palco do mascote, chão, espaço reservado, botão de configuração na coluna |
| `2b3846df` | `feat(TS-5406): mascote reage ao chat da POLI` | pensando, comemorar, contrato, erro |
| `f16f3a6d` | `feat(TS-5406): mascote na Home no lugar do vídeo do robô` | Home da organização interna, com o chão |
| `91b75672` | `chore(TS-5406): remove vídeo e ícone do robô da POLI` | `poli-animation.webm` (7,3 MB) e `poli.svg` |

### Mudanças visíveis para a PR

- **POLI dentro do portal:**
  - as 11 rotas abrem com a sidebar do portal;
  - sem o cabeçalho próprio (voltar, robô, usuário e sair);
  - o título do departamento fica no topo da coluna de histórico.
- **Chat vazio:** só "Escreva algo para iniciar um chat", no lugar do vídeo, da saudação e do texto
  sobre a POLI.
- **Mascote sobre a barra de digitar:**
  - Poli, Cofre, Moeda ou Nota;
  - anda e faz as ações do pacote;
  - pensa enquanto a POLI responde e comemora no fim;
  - faz o "Assinar cessão" quando a resposta traz arquivo;
  - no clique, reage;
  - com anexos, anda só sobre os chips.
- **Animação:** com *reduced motion* o mascote fica parado à direita e só troca de pose. A troca de
  mascote tem o switch "Animação".
- **Troca de mascote:** um botão de configuração (engrenagem) ao lado do título da coluna, com o
  menu dos quatro mascotes e do "Animação"; na coluna recolhida, o mesmo botão.
- **Home:** o mascote escolhido fica sobre a caixa da POLI, com a frase, no lugar do vídeo e da
  saudação.
- **Cores:** o Cofre e os destaques dos itens seguem a cor primária da marca.

### Validação

- **Fidelidade:**
  - o porte bate caractere a caractere com o código original (fixture com 4.564 quadros, poses e
    itens);
  - a folha renderizada do original e a do porte têm 0 pixel diferente;
  - as 9 poses da Poli e os 6 itens batem 100% com o `spritesheet.png`.
- **Specs, build e lint:**
  - suíte inteira: 3.106 de 3.106 passando;
  - build ok, bundle inicial de 430 kB, igual ao da base;
  - lint com 20 erros e 162 avisos, iguais aos da base;
  - `tsc` sem erro; `check-patterns` sem achado.
- **Prints:** em claro, escuro e Dots, desktop e celular, animado e com *reduced motion*. As
  verificações conferem que:
  - o mascote anda (e fica parado com *reduced motion*);
  - reage ao clique, ao pensar, à resposta e ao arquivo;
  - os quatro personagens aparecem;
  - a escolha fica salva e vale na Home;
  - não há rolagem da página nem lateral.

### Observações

- O fixture tem 212 kB (dados de teste).
- O intervalo do mascote roda fora da zona do Angular e depende do agendador híbrido do Angular 20.
  Se o app ligar `ignoreChangesOutsideZone`, o mascote para.
