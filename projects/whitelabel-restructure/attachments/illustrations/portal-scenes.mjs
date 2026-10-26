// Gera as cenas do app-illustration: as 4 da direção A (idênticas à proposta) e as 2 novas.
// Uso: node portal-scenes.mjs  -> scenes.json e preview.html (não versionados) e a conferência das regras.
import fs from 'node:fs';
import { ILLUSTRATIONS, BRANDS, SCHEMES } from './illustrations.mjs';

const here = (f) => new URL('./' + f, import.meta.url);
const v = (t) => `var(--illu-${t})`;
const fill = (t, o) => `fill="${v(t)}"${o ? ` fill-opacity="${o}"` : ''}`;
const stroke = (t, w, o) => `stroke="${v(t)}"${w ? ` stroke-width="${w}"` : ''}${o ? ` stroke-opacity="${o}"` : ''}`;
const at = (a) => (a ? ' ' + a : '');
const R = (x, y, w, h, r, a) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"${at(a)}/>`;
const P = (d, a) => `<path d="${d}"${at(a)}/>`;
const O = (cx, cy, r, a) => `<circle cx="${cx}" cy="${cy}" r="${r}"${at(a)}/>`;
const G = (a, ...kids) => `<g ${a}>${kids.join('')}</g>`;
const dash = (d) => `stroke-dasharray="${d}"`;

const A = Object.fromEntries(ILLUSTRATIONS.filter(([d]) => d === 'a').map(([, s, b]) => [s, b]));

// Mesmo plano de fundo e cartão da direção A.
const aBack =
  R(24, 16, 140, 96, 12, fill('brand-soft')) +
  G(fill('surface'), R(36, 24, 28, 8, 4), R(70, 24, 20, 8, 4), R(96, 24, 24, 8, 4), R(32, 50, 8, 8, 2.5), R(32, 64, 8, 8, 2.5), R(32, 78, 8, 8, 2.5));
const aCard = () =>
  R(48, 40, 148, 100, 10, fill('surface')) +
  P('M58 40h128a10 10 0 0 1 10 10v6H48v-6a10 10 0 0 1 10-10z', fill('bg')) +
  G(fill('line'), R(60, 46, 20, 4, 2), R(92, 46, 28, 4, 2), R(132, 46, 16, 4, 2), R(160, 46, 24, 4, 2)) +
  R(48, 40, 148, 100, 10, stroke('line'));

// Envio de arquivo: área de soltar tracejada no cartão e o documento na frente, com o selo de
// envio (seta para cima) no lugar do "+" da lista vazia.
const fileUpload =
  aBack +
  aCard() +
  R(60, 66, 84, 62, 8, fill('brand-soft')) +
  R(60, 66, 84, 62, 8, stroke('brand') + ' ' + dash('4 5')) +
  P('M102 106V88M95 95l7-7 7 7', stroke('brand', 2)) +
  P('M170 66h30l14 14v46a6 6 0 0 1-6 6h-38a6 6 0 0 1-6-6V72a6 6 0 0 1 6-6z', fill('bg') + ' ' + stroke('line')) +
  P('M160 76h30l14 14v46a6 6 0 0 1-6 6h-38a6 6 0 0 1-6-6V82a6 6 0 0 1 6-6z', fill('surface')) +
  P('M160 76h30l14 14v46a6 6 0 0 1-6 6h-38a6 6 0 0 1-6-6V82a6 6 0 0 1 6-6zM190 76v8a6 6 0 0 0 6 6h8', stroke('ink', 2)) +
  G(fill('line'), R(164, 100, 26, 4, 2), R(164, 110, 32, 4, 2), R(164, 120, 20, 4, 2)) +
  O(208, 132, 11, fill('brand')) +
  P('M208 137v-10M203.5 131.5l4.5-4.5 4.5 4.5', stroke('surface', 2));

// Fundo do login: planos da marca suave e janelas do portal nos cantos, tom sobre tom, com o meio
// livre para o cartão. viewBox largo e "slice": cobre a tela inteira em qualquer proporção.
const W = 1440, H = 900;
const rows = (x, y, n, gap, widths) => G(fill('line'), ...Array.from({ length: n }, (_, i) => R(x, y + i * gap, widths[i % widths.length], 8, 4)));
const loginBackdrop =
  R(-60, 72, 780, 420, 48, fill('brand-soft', '.8')) +
  R(740, 430, 760, 440, 48, fill('brand-soft', '.8')) +
  G(fill('surface'), R(40, 112, 64, 18, 9), R(116, 112, 44, 18, 9), R(172, 112, 52, 18, 9), R(1100, 800, 64, 18, 9), R(1176, 800, 44, 18, 9)) +
  // Janela de lista, no alto à esquerda.
  R(64, 168, 360, 290, 24, fill('surface')) +
  P('M88 168h312a24 24 0 0 1 24 24v26H64v-26a24 24 0 0 1 24-24z', fill('bg')) +
  G(fill('line'), R(92, 190, 60, 8, 4), R(172, 190, 84, 8, 4), R(276, 190, 48, 8, 4)) +
  rows(92, 250, 5, 40, [160, 116, 140, 96, 128]) +
  G(fill('bg'), R(316, 244, 80, 20, 10), R(316, 284, 80, 20, 10), R(316, 324, 80, 20, 10), R(316, 364, 80, 20, 10), R(316, 404, 80, 20, 10)) +
  R(64, 168, 360, 290, 24, stroke('line')) +
  // Janela de gráfico, embaixo à direita.
  R(1010, 330, 360, 280, 24, fill('surface')) +
  G(fill('line'), R(1042, 362, 96, 8, 4), R(1042, 384, 60, 8, 4)) +
  P('M1042 570v-60l49-36 50 18 49-62 49 30 50-44 31 18v136z', fill('brand-soft')) +
  P('M1042 510l49-36 50 18 49-62 49 30 50-44 31 18', stroke('brand', 2, '.6')) +
  P('M1042 570h296', stroke('line')) +
  R(1010, 330, 360, 280, 24, stroke('line')) +
  // Pontos de status soltos.
  G(fill('brand', '.35'), O(560, 132, 6), O(1300, 296, 6), O(860, 760, 6));

const SCENES = {
  'empty-list': { body: A['empty-list'] },
  'search-no-results': { body: A['search-no-results'] },
  'load-error': { body: A['load-error'] },
  'access-denied': { body: A['access-denied'] },
  'file-upload': { body: fileUpload },
  'login-backdrop': { body: loginBackdrop, viewBox: `0 0 ${W} ${H}`, fit: 'slice' },
};

export const svgOf = (s, extra = '') =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${s.viewBox ?? '0 0 240 160'}"${s.fit ? ' preserveAspectRatio="xMidYMid slice"' : ''} width="100%" height="100%" fill="none" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false" aria-hidden="true"${extra}>${s.body}</svg>`;

const errors = [];
for (const [name, s] of Object.entries(SCENES)) {
  const out = svgOf(s);
  if (/#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i.test(out)) errors.push(`${name}: cor fixa`);
  if (/<text|<tspan/.test(out)) errors.push(`${name}: texto`);
  if (/filter|<image|href=/.test(out)) errors.push(`${name}: filter/imagem/link`);
  if (/\bid=/.test(out)) errors.push(`${name}: id`);
  for (const [, w] of out.matchAll(/stroke-width="([\d.]+)"/g)) if (+w < 1.75 || +w > 2) errors.push(`${name}: stroke-width ${w}`);
  const bytes = Buffer.byteLength(out);
  if (bytes >= 4096) errors.push(`${name}: ${bytes} B`);
  console.log(name.padEnd(18), bytes, 'B');
}
if (errors.length) { console.error(errors.join('\n')); process.exit(1); }
fs.writeFileSync(here('scenes.json'), JSON.stringify(SCENES, null, 1));

// Prévia: cada marca e esquema com o mapeamento do portal (tom sobre tom em 12% e 18%).
const map = (c, scheme) => ({
  '--illu-brand': c.accent,
  '--illu-brand-soft': `color-mix(in srgb, ${c.accent} ${scheme === 'dark' ? 18 : 12}%, ${SCHEMES[scheme].surface})`,
  '--illu-brand-strong': `color-mix(in srgb, ${c.accent} 72%, ${SCHEMES[scheme].text})`,
  '--illu-ink': SCHEMES[scheme].text2,
  '--illu-line': SCHEMES[scheme].strong,
  '--illu-surface': SCHEMES[scheme].surface,
  '--illu-bg': SCHEMES[scheme].sunken,
});
const blocks = ['light', 'dark'].flatMap((scheme) =>
  BRANDS.map((b) => {
    const vars = Object.entries(map(b[scheme], scheme)).map(([k, x]) => `${k}:${x}`).join(';');
    const cells = Object.entries(SCENES)
      .map(([n, s]) => `<div class="c ${s.fit ? 'wide' : ''}" style="background:${SCHEMES[scheme][s.fit ? 'bg' : 'surface']}">${svgOf(s)}</div>`)
      .join('');
    return `<div class="row" style="${vars};background:${SCHEMES[scheme].bg};color:${SCHEMES[scheme].text3}"><b>${b.name} ${scheme}</b>${cells}</div>`;
  })
).join('');
fs.writeFileSync(
  here('preview.html'),
  `<html><body style="margin:0;font:12px sans-serif"><style>.row{display:grid;grid-template-columns:90px repeat(5,240px) 360px;gap:8px;padding:8px;align-items:center}.c{height:160px;border-radius:8px;overflow:hidden}.c svg{display:block}.c.wide{height:225px}</style>${blocks}</body></html>`
);
console.log('ok');
