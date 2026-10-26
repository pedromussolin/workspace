// Folha de contato das ilustrações num Chromium headless, para conferir o desenho.
// Uso: PW_DIR=<node_modules com playwright-core> node sheet.mjs <pasta-de-saída> [direção] [--guias] [--escala=2]
//      PW_DIR=... node sheet.mjs <pasta-de-saída> --marca=poliedro   (uma marca, as três direções nos dois esquemas)
// Gera <direção>-<esquema>.png (cenas nas colunas, marcas nas linhas) e imprime o peso visual de
// cada cena (fração da área pintada e contraste médio com o fundo), para comparar as cenas.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { DIRECTIONS, SCENES, BRANDS, SCHEMES, ILLUSTRATIONS, illuVars, svg } from './illustrations.mjs';

const args = process.argv.slice(2);
const out = args.find((a) => !a.startsWith('--') && !DIRECTIONS.some((d) => d.id === a));
if (!out || !process.env.PW_DIR) {
  console.error('Uso: PW_DIR=<node_modules> node sheet.mjs <pasta-de-saída> [a|b|c] [--guias] [--escala=2]');
  process.exit(1);
}
const only = args.find((a) => DIRECTIONS.some((d) => d.id === a));
const guides = args.includes('--guias');
const brandOnly = (args.find((a) => a.startsWith('--marca=')) || '').split('=')[1];
const scale = Number((args.find((a) => a.startsWith('--escala=')) || '--escala=1.5').split('=')[1]);
const CHROME = path.join(process.env.HOME, '.cache/ms-playwright/chromium-1243/chrome-linux64/chrome');
const { chromium } = createRequire(path.join(process.env.PW_DIR, '/'))('playwright-core');

const W = Math.round(240 * scale), H = Math.round(160 * scale);
const guide = guides
  ? `<rect x="0.5" y="0.5" width="239" height="159" fill="none" stroke="#f0f" stroke-opacity=".35" stroke-width="1"/><rect x="16" y="12" width="208" height="136" fill="none" stroke="#f0f" stroke-opacity=".35" stroke-width="1" stroke-dasharray="2 3"/><path d="M120 0v160M0 80h240" stroke="#f0f" stroke-opacity=".2" stroke-width="1"/>`
  : '';

function page(dir, scheme) {
  const s = SCHEMES[scheme];
  const rows = BRANDS.map((b) => {
    const vars = Object.entries(illuVars(b.id, scheme)).map(([k, val]) => `${k}:${val}`).join(';');
    const tiles = ILLUSTRATIONS.filter(([d]) => d === dir)
      .map(([, sc, body]) => `<div class="t" data-scene="${sc}" style="${vars}">${svg(body + guide, ` width="${W}" height="${H}"`)}</div>`)
      .join('');
    return `<div class="lbl">${b.name}</div>${tiles}`;
  }).join('');
  const head = SCENES.map((sc) => `<div class="h">${sc.name}</div>`).join('');
  return `<html><body style="margin:0;background:${s.bg};font:12px sans-serif;color:${s.text3}">
<div style="display:grid;grid-template-columns:70px repeat(${SCENES.length},${W + 16}px);gap:8px;padding:12px">
<div></div>${head}${rows}</div>
<style>.t{background:${s.surface};border:1px solid ${s.border};border-radius:10px;padding:8px;display:flex}.lbl,.h{align-self:center}.h{text-align:center}</style></body></html>`;
}

// Peso visual: desenha cada SVG num canvas com as cores já resolvidas e mede a área pintada e o
// contraste médio de luminância com a superfície.
async function weight(p) {
  return p.evaluate(async () => {
    const res = [];
    for (const t of document.querySelectorAll('.t')) {
      const cs = getComputedStyle(t);
      let src = t.querySelector('svg').outerHTML;
      src = src.replace(/var\((--illu-[a-z-]+)\)/g, (_, k) => {
        const probe = document.createElement('i');
        probe.style.color = cs.getPropertyValue(k);
        t.appendChild(probe);
        const c = getComputedStyle(probe).color;
        probe.remove();
        return c;
      });
      const img = new Image();
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(src);
      await img.decode();
      const c = document.createElement('canvas');
      c.width = 240; c.height = 160;
      const x = c.getContext('2d');
      x.fillStyle = getComputedStyle(t).backgroundColor;
      x.fillRect(0, 0, 240, 160);
      const base = x.getImageData(0, 0, 1, 1).data;
      x.drawImage(img, 0, 0, 240, 160);
      const d = x.getImageData(0, 0, 240, 160).data;
      const L = (r, g, b) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const l0 = L(base[0], base[1], base[2]);
      let painted = 0, contrast = 0;
      for (let i = 0; i < d.length; i += 4) {
        const dl = Math.abs(L(d[i], d[i + 1], d[i + 2]) - l0);
        if (dl > 4 || Math.abs(d[i] - base[0]) + Math.abs(d[i + 1] - base[1]) + Math.abs(d[i + 2] - base[2]) > 12) painted++;
        contrast += dl;
      }
      res.push({ scene: t.dataset.scene, area: painted / (240 * 160), contrast: contrast / (240 * 160) });
    }
    return res;
  });
}

// Uma marca só: linhas = direção x esquema.
function brandPage(brand) {
  const rows = DIRECTIONS.flatMap((d) =>
    Object.keys(SCHEMES).map((scheme) => {
      const s = SCHEMES[scheme];
      const vars = Object.entries(illuVars(brand, scheme)).map(([k, val]) => `${k}:${val}`).join(';');
      const tiles = ILLUSTRATIONS.filter(([x]) => x === d.id)
        .map(([, , body]) => `<div class="t" style="${vars};background:${s.surface};border-color:${s.border}">${svg(body + guide, ` width="${W}" height="${H}"`)}</div>`)
        .join('');
      return `<div class="lbl">${d.id.toUpperCase()} ${scheme === 'light' ? 'claro' : 'escuro'}</div>${tiles}`;
    })
  ).join('');
  return `<html><body style="margin:0;background:#e9edf1;font:12px sans-serif;color:#475569">
<div style="display:grid;grid-template-columns:80px repeat(${SCENES.length},${W + 16}px);gap:6px;padding:10px">${rows}</div>
<style>.t{border:1px solid;border-radius:10px;padding:8px;display:flex}.lbl{align-self:center}</style></body></html>`;
}

fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME });
const pg = await browser.newPage({ viewport: { width: 90 + SCENES.length * (W + 24), height: 400 } });
if (brandOnly) {
  const file = path.join(out, `marca-${brandOnly}.html`);
  fs.writeFileSync(file, brandPage(brandOnly));
  await pg.goto('file://' + file);
  await pg.screenshot({ path: file.replace(/html$/, 'png'), fullPage: true });
  console.log('ok', file.replace(/html$/, 'png'));
  await browser.close();
  process.exit(0);
}
for (const d of DIRECTIONS.filter((x) => !only || x.id === only)) {
  for (const scheme of Object.keys(SCHEMES)) {
    const file = path.join(out, `${d.id}-${scheme}.html`);
    fs.writeFileSync(file, page(d.id, scheme));
    await pg.goto('file://' + file);
    const png = path.join(out, `${d.id}-${scheme}.png`);
    await pg.screenshot({ path: png, fullPage: true });
    if (scheme === 'light' && !guides) {
      const w = await weight(pg);
      const by = {};
      for (const r of w) (by[r.scene] ||= []).push(r);
      const line = SCENES.map((sc) => {
        const rs = by[sc.id];
        const a = rs.reduce((s, r) => s + r.area, 0) / rs.length, c = rs.reduce((s, r) => s + r.contrast, 0) / rs.length;
        return `${sc.id} área ${(a * 100).toFixed(0)}% contraste ${c.toFixed(1)}`;
      });
      console.log(`${d.id} (${d.name}): ${line.join(' · ')}`);
    }
    console.log('ok', png);
  }
}
await browser.close();
