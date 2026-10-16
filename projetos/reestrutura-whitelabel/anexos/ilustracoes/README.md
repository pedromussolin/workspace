# Ilustrações próprias

Proposta visual da tarefa 23. São três direções, cada uma com as mesmas quatro cenas:
- **direções:** A (interface em camadas), B (traço fino) e C (geométrico);
- **cenas:** lista vazia, busca sem resultado, erro ao carregar e acesso negado.

A página não encontrada (404) fica simples, sem ilustração.

| Arquivo | O que é |
|---|---|
| `ilustracoes.mjs` | Fonte da verdade: direções, cenas, miolo de cada SVG, cores das marcas e a regra das variáveis `--illu-*` |
| `svg/<direção>/<cena>.svg` | Um arquivo por ilustração (gerado) |
| `proposta.tpl.html` | Modelo da página de comparação |
| `proposta.html` | A página gerada, para publicar como artifact |
| `build.mjs` | Gera os SVGs e a página e confere as regras: sem cor fixa, sem texto, sem `filter`, sem `id`, traço entre 1,75 e 2 e menos de 4 KB |
| `sheet.mjs` | Folha de contato num Chromium headless, com o peso visual de cada cena (área pintada e contraste) |

```bash
cd anexos/ilustracoes
node build.mjs
# os prints vão para uma pasta fora do repo
PW_DIR=~/repos/.reestrutura_whitelabel/pw/node_modules node sheet.mjs <pasta> [a|b|c] [--guias] [--escala=2]
PW_DIR=~/repos/.reestrutura_whitelabel/pw/node_modules node sheet.mjs <pasta> --marca=poliedro
```

## Variáveis

O SVG só usa estas variáveis. Quem mostra a ilustração (a página aqui, o `app-illustration` no
portal) liga cada uma a um token.

| Variável | Onde aparece | Token no portal |
|---|---|---|
| `--illu-brand` | destaque da cena | cor de destaque da marca: a secundária, ou a primária na Cerys (a secundária dela é neutra) |
| `--illu-brand-soft` | planos suaves | marca a 14% sobre `--surface` (20% no escuro) |
| `--illu-brand-strong` | detalhes fortes | marca a 72% com `--text` |
| `--illu-ink` | traço principal | `--text-secondary` |
| `--illu-line` | traço secundário e linhas de texto | `--border-strong` |
| `--illu-surface` | cartões e janelas | `--surface` |
| `--illu-bg` | faixas de fundo | `--surface-sunken` |

Em C, o degradê de tom vem de opacidades da marca, e não de `<linearGradient>`: o gradiente
precisa de `id`, e o `id` se repete quando a mesma ilustração aparece duas vezes na tela.
