# 28 — POLI dentro do portal, com mascotes animados

- **TS:** TS-5406 · **Branch:** `feature/TS-5406-poli-mascote` (só front)
- **Status:** **em implementação** (19/10): desenho aprovado no chat; plano em
  [28-poli-mascote-plano.md](28-poli-mascote-plano.md)
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

## Escopo

### Página da POLI

- As 11 rotas passam a ser filhas do shell. A rota marca a página como tela cheia
  (`data.shellContent: 'full'`), e o shell tira a margem do conteúdo, para o chat ocupar a altura
  toda.
- A coluna de histórico ganha:
  - no topo, o título do departamento (o mesmo texto de hoje), acima do "Novo chat";
  - no rodapé, a troca de mascote (os quatro, com miniatura) e o "Animação: ligada/desligada";
  - recolhida, um botão com menu para as duas escolhas.
- O chat vazio mostra a frase no lugar do vídeo, da saudação e do texto sobre a POLI.
- O aviso do modelo, embaixo da caixa, continua.

### Mascote

- **Palco:** uma faixa sobre a barra de digitar, da largura dela, com os pés na borda de cima. A
  faixa fica por cima do fim das mensagens e não bloqueia clique, a não ser no próprio mascote.
  As mensagens ganham um espaço embaixo para a última linha não ficar atrás dele.
- **Tamanho:** cada pixel do desenho vale 3 px de tela no computador (a Poli fica com 102 px) e
  2 px no celular (até 760 px de largura). Sempre múltiplos inteiros.
- **Personagens:** Poli, Cofre, Moeda e Nota. O Cofre e os destaques dos itens (contrato, gráfico e
  escudo) usam a cor primária da marca. A Poli, a Moeda e a Nota têm as cores próprias.
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
- **`validar-leva.sh`** com a base `6303b2e5`, rotas `/home /poli-chat /legal-poli-chat`.
- **Prints:** POLI vazia, POLI com conversa, POLI com a coluna recolhida e Home. Em claro, escuro,
  Dots e celular, com e sem *reduced motion*. Conferir os quatro personagens contra o
  `spritesheet.png` e o artefato.

## O que foi feito

(preencher ao fim)
