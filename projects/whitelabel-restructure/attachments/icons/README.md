# Ícones próprios

| Arquivo | O que é |
|---|---|
| `icons.mjs` | Fonte da verdade: nome, categoria, miolo do SVG e nomes do Material que cada ícone substitui |
| `svg/` | Um `.svg` por ícone (gerado) |
| `material-para-novo.json` | Mapa nome do Material → nome novo (gerado), usado na migração de cada área |
| `material-usados-no-front.txt` | Os 179 nomes do Material usados no front em `d0bc3de` |
| `gallery.tpl.html` | Modelo da página de revisão |
| `build.mjs` | Gera `svg/`, o JSON e `gallery.html` |
| `check.mjs` | Confere se todo nome usado tem ícone e se não há nome repetido |
| `sheet.mjs`, `zoom.mjs` | Folha de contato e zoom, para conferir o desenho num navegador headless |

```bash
cd anexos/icones
node check.mjs material-usados-no-front.txt
node build.mjs
```

Página publicada: https://claude.ai/artifact/Hi6hgNKrGGRgofWWHh3Dds (para
republicar, publique o `gallery.html` gerado no mesmo artifact).
