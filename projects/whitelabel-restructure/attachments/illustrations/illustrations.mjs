// Ilustrações do portal. viewBox 0 0 240 160, traço 1.75 (2 no motivo), pontas e junções
// arredondadas. Cor só por variável CSS (--illu-*): quem usa a ilustração mapeia as variáveis
// para os tokens da marca e do esquema. Cada entrada traz o miolo do <svg>.

export const VIEWBOX = '0 0 240 160';

export const DIRECTIONS = [
  {
    id: 'a',
    slug: 'layers',
    name: 'Interface em camadas',
    desc: 'Pedaços do próprio portal em planos sobrepostos, tom sobre tom da marca, com o motivo da cena grande na frente.',
  },
  {
    id: 'b',
    slug: 'thin-line',
    name: 'Traço fino',
    desc: 'Desenho de linha no traço dos ícones, em tinta neutra, com um único plano suave da marca.',
  },
  {
    id: 'c',
    slug: 'geometric',
    name: 'Geométrico',
    desc: 'Círculos, arcos, grade de pontos e retângulos em degraus de tom da marca, com um símbolo só por cena.',
  },
];

export const SCENES = [
  { id: 'empty-list', name: 'Lista vazia' },
  { id: 'search-no-results', name: 'Busca sem resultado' },
  { id: 'load-error', name: 'Erro ao carregar' },
  { id: 'access-denied', name: 'Acesso negado' },
];

// Cores reais das marcas e dos esquemas (core/theme/themes.ts e styles/_tokens.scss da 13), para a
// página e a folha de contato montarem as variáveis. `accent` é a cor de destaque da marca na
// ilustração: a secundária, menos na Cerys, cuja secundária é neutra e cede lugar à primária.
// `secondary` e `ink` servem só à maquete do portal (botão tom sobre tom e texto da marca).
export const SCHEMES = {
  light: {
    bg: '#fbfcfd', surface: '#ffffff', muted: '#f8fafc', sunken: '#f1f5f9', line: '#eef0f3',
    border: '#e2e8f0', strong: '#cbd5e1', text: '#0f172a', ink: '#0f2a3a', text2: '#475569',
    text3: '#64748b', sidebar: '#f5f7fa', sideline: '#e2e7ee',
    shadow: '0 1px 2px rgb(15 23 42 / 0.04), 0 6px 20px -14px rgb(15 52 67 / 0.22)',
    soft: '14%', deep: '72%', tonal: '12%',
  },
  dark: {
    bg: '#0e171e', surface: '#141f27', muted: '#18242d', sunken: '#1c2a34', line: '#22313b',
    border: '#2a3a45', strong: '#3a4c58', text: '#e6edf2', ink: '#eef3f7', text2: '#b4c2cc',
    text3: '#93a3b0', sidebar: '#0b1217', sideline: '#1e2b35',
    shadow: '0 1px 2px rgb(0 0 0 / 0.35)',
    soft: '20%', deep: '72%', tonal: '18%',
  },
};

export const BRANDS = [
  {
    id: 'poliedro', name: 'Poliedro',
    light: { accent: '#0d8291', primary: '#0f3443', secondary: '#0d8291' },
    dark: { accent: '#4fc3d0', primary: '#5fb8c6', secondary: '#4fc3d0' },
  },
  {
    id: 'dots', name: 'Dots',
    light: { accent: '#ee7342', primary: '#d34108', secondary: '#ee7342', ink: '#ae5433' },
    dark: { accent: '#ff9a6e', primary: '#ff7a45', secondary: '#ff9a6e' },
  },
  {
    id: 'cerys', name: 'Cerys',
    light: { accent: '#ff8f1c', primary: '#ff8f1c', secondary: '#1e1e1e' },
    dark: { accent: '#ffa64d', primary: '#ffa64d', secondary: '#d4d4d4' },
  },
  {
    id: 'viva', name: 'Viva',
    light: { accent: '#9333ea', primary: '#79009d', secondary: '#9333ea' },
    dark: { accent: '#b98cff', primary: '#c77dff', secondary: '#b98cff' },
  },
];

// Regra das variáveis. Recebe as cores (valores ou var()) e devolve as --illu-*. No portal, cada
// uma aponta para um token: accent para a cor de destaque da marca, surface para --surface etc.
export const illuMap = (c) => ({
  '--illu-brand': c.accent,
  '--illu-brand-soft': `color-mix(in srgb, ${c.accent} ${c.soft}, ${c.surface})`,
  '--illu-brand-strong': `color-mix(in srgb, ${c.accent} ${c.deep}, ${c.text})`,
  '--illu-ink': c.text2,
  '--illu-line': c.strong,
  '--illu-surface': c.surface,
  '--illu-bg': c.sunken,
});
export const illuVars = (brand, scheme) => illuMap({ ...SCHEMES[scheme], ...BRANDS.find((b) => b.id === brand)[scheme] });

const n = (x) => Math.round(x * 10) / 10;
const v = (t) => `var(--illu-${t})`;
const fill = (t, o) => `fill="${v(t)}"${o ? ` fill-opacity="${o}"` : ''}`;
const stroke = (t, w) => `stroke="${v(t)}"${w ? ` stroke-width="${w}"` : ''}`;
const at = (a) => (a ? ' ' + a : '');
const R = (x, y, w, h, r, a) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"${at(a)}/>`;
const P = (d, a) => `<path d="${d}"${at(a)}/>`;
const O = (cx, cy, r, a) => `<circle cx="${cx}" cy="${cy}" r="${r}"${at(a)}/>`;
const G = (a, ...kids) => `<g ${a}>${kids.join('')}</g>`;
const dash = (d) => `stroke-dasharray="${d}"`;

const pt = (cx, cy, r, deg) => {
  const a = (deg * Math.PI) / 180;
  return `${n(cx + r * Math.cos(a))} ${n(cy + r * Math.sin(a))}`;
};

// Figura de cantos arredondados (o triângulo de alerta).
function roundedPoly(pts, r) {
  const len = (x, y) => Math.hypot(x, y);
  let d = '';
  pts.forEach(([vx, vy], i) => {
    const [px, py] = pts[(i - 1 + pts.length) % pts.length];
    const [qx, qy] = pts[(i + 1) % pts.length];
    const ax = (px - vx) / len(px - vx, py - vy), ay = (py - vy) / len(px - vx, py - vy);
    const bx = (qx - vx) / len(qx - vx, qy - vy), by = (qy - vy) / len(qx - vx, qy - vy);
    const t = r / Math.tan(Math.acos(ax * bx + ay * by) / 2);
    d += `${i ? 'L' : 'M'}${n(vx + ax * t)} ${n(vy + ay * t)}Q${vx} ${vy} ${n(vx + bx * t)} ${n(vy + by * t)}`;
  });
  return d + 'z';
}

// Faixa de anel entre dois ângulos, com as pontas arredondadas (a0 < a1, em graus, sentido horário).
function arcBand(cx, cy, ro, ri, a0, a1) {
  const big = a1 - a0 > 180 ? 1 : 0, rc = n((ro - ri) / 2);
  return `M${pt(cx, cy, ro, a0)}A${ro} ${ro} 0 ${big} 1 ${pt(cx, cy, ro, a1)}A${rc} ${rc} 0 0 1 ${pt(cx, cy, ri, a1)}A${ri} ${ri} 0 ${big} 0 ${pt(cx, cy, ri, a0)}A${rc} ${rc} 0 0 1 ${pt(cx, cy, ro, a0)}z`;
}

// Grade de pontos.
const dots = (x, y, cols, rows, gap, r, a) => {
  let s = '';
  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) s += O(x + i * gap, y + j * gap, r);
  return G(a, s);
};

// Barra arredondada girada (cabo da lupa), presa em (x, y) e apontando para baixo e à direita.
const handle = (x, y, w, h, a) =>
  `<rect x="${-w / 2}" y="0" width="${w}" height="${h}" rx="${w / 2}" transform="translate(${x} ${y}) rotate(-45)"${at(a)}/>`;

/* A: interface em camadas. Plano de fundo na marca suave (filtros e menu), cartão da tela na
   frente e o motivo grande sobre a borda do cartão. */
const aBack =
  R(24, 16, 140, 96, 12, fill('brand-soft')) +
  G(fill('surface'), R(36, 24, 28, 8, 4), R(70, 24, 20, 8, 4), R(96, 24, 24, 8, 4), R(32, 50, 8, 8, 2.5), R(32, 64, 8, 8, 2.5), R(32, 78, 8, 8, 2.5));
const aCard = (head = true) =>
  R(48, 40, 148, 100, 10, fill('surface')) +
  (head ? P('M58 40h128a10 10 0 0 1 10 10v6H48v-6a10 10 0 0 1 10-10z', fill('bg')) + G(fill('line'), R(60, 46, 20, 4, 2), R(92, 46, 28, 4, 2), R(132, 46, 16, 4, 2), R(160, 46, 24, 4, 2)) : '') +
  R(48, 40, 148, 100, 10, stroke('line'));

const A = {
  'empty-list':
    aBack +
    aCard() +
    P('M60 72h70M60 88h70M60 104h70M60 120h70', stroke('line') + ' ' + dash('3 5')) +
    P('M157 82h50l9 25v19a6 6 0 0 1-6 6h-56a6 6 0 0 1-6-6v-19z', fill('surface')) +
    P('M148 107h18l4.5 8h23l4.5-8h18v19a6 6 0 0 1-6 6h-56a6 6 0 0 1-6-6z', fill('brand-soft')) +
    P('M157 82h50l9 25v19a6 6 0 0 1-6 6h-56a6 6 0 0 1-6-6v-19zM148 107h18l4.5 8h23l4.5-8h18', stroke('ink', 2)) +
    O(207, 82, 11, fill('brand')) +
    P('M207 77v10M202 82h10', stroke('surface', 2)),
  'search-no-results':
    aBack +
    aCard(false) +
    R(58, 49, 96, 14, 7, fill('bg')) +
    G(stroke('line'), O(67, 56, 3), P('M69.2 58.2l2.3 2.3')) +
    G(fill('line'), R(78, 54, 40, 4, 2), R(60, 76, 34, 4, 2), R(104, 76, 24, 4, 2), R(60, 92, 26, 4, 2), R(104, 92, 32, 4, 2), R(60, 108, 38, 4, 2), R(104, 108, 20, 4, 2), R(60, 124, 30, 4, 2), R(104, 124, 28, 4, 2)) +
    handle(196, 118, 10, 24, fill('brand')) +
    O(176, 98, 27, fill('surface') + ' ' + stroke('ink', 2)) +
    P('M168 90l16 16M184 90l-16 16', stroke('brand-strong', 2)),
  'load-error':
    aBack +
    aCard() +
    P('M60 130v-10l14-12 14 5 14-18 12 7v28z', fill('brand-soft')) +
    P('M60 120l14-12 14 5 14-18 9 5.3', stroke('brand', 2)) +
    P('M60 130h76', stroke('line')) +
    P('M114 102h22', stroke('line') + ' ' + dash('3 4')) +
    O(114, 102, 3, fill('surface') + ' ' + stroke('brand', 2)) +
    G(fill('line'), R(60, 64, 30, 4, 2)) +
    P(roundedPoly([[182, 68], [216, 128], [148, 128]], 7), fill('surface') + ' ' + stroke('ink', 2)) +
    P('M182 90v17', stroke('brand-strong', 2)) +
    O(182, 116, 2.4, fill('brand-strong')),
  'access-denied':
    aBack +
    aCard() +
    G(fill('bg'), R(60, 66, 74, 10, 5), R(60, 84, 58, 10, 5), R(60, 102, 66, 10, 5), R(60, 120, 44, 10, 5)) +
    P('M165 92V82a16 16 0 0 1 32 0v10', stroke('ink', 2)) +
    R(152, 92, 58, 42, 9, fill('surface') + ' ' + stroke('ink', 2)) +
    O(181, 110, 5.5, fill('brand')) +
    R(178.75, 112, 4.5, 12, 2.25, fill('brand')),
};

/* B: traço fino. Objeto neutro em linha (cartão, tabela, janela), o motivo em linha e um só
   plano suave da marca. */
const B = {
  'empty-list':
    R(56, 28, 128, 104, 10, stroke('ink')) +
    P('M56 48h128', stroke('ink')) +
    P('M70 38h18M100 38h26M138 38h14M164 38h8', stroke('line')) +
    R(72, 66, 96, 32, 8, fill('brand-soft')) +
    R(72, 66, 96, 32, 8, stroke('ink') + ' ' + dash('4 5')) +
    P('M120 75v14M113 82h14', stroke('ink')) +
    P('M72 114h48M132 114h36', stroke('line') + ' ' + dash('4 5')),
  'search-no-results':
    R(40, 26, 120, 96, 10, stroke('ink')) +
    P('M54 44h44M54 52h26M54 70h52M54 78h30M54 96h40M54 104h22', stroke('line')) +
    P('M54 61h92M54 87h92', stroke('line')) +
    handle(184, 120, 8, 24, stroke('ink')) +
    O(162, 98, 28, fill('brand-soft') + ' ' + stroke('ink')) +
    P('M154 90l16 16M170 90l-16 16', stroke('ink')),
  'load-error':
    R(40, 32, 124, 96, 10, stroke('ink')) +
    P('M54 48h28M54 56h44', stroke('line')) +
    P('M54 112h96', stroke('line')) +
    P('M54 104l14-12 12 6 12.4-16', stroke('ink')) +
    P('M98 80h26', stroke('line') + ' ' + dash('3 4')) +
    O(94, 80, 2.6, fill('surface') + ' ' + stroke('ink')) +
    O(168, 100, 32, fill('brand-soft')) +
    P(roundedPoly([[168, 76], [192, 118], [144, 118]], 4), stroke('ink')) +
    P('M168 92v12', stroke('ink')) +
    O(168, 110.5, 1.6, fill('ink')),
  'access-denied':
    R(40, 28, 160, 104, 10, stroke('ink')) +
    P('M40 46h160', stroke('ink')) +
    P('M54 37h20M82 37h12', stroke('line')) +
    P('M54 62h56M54 70h34M54 88h48M54 96h28M54 114h52', stroke('line')) +
    P('M144 82V72a14 14 0 0 1 28 0v10', stroke('ink')) +
    R(132, 82, 52, 38, 8, fill('brand-soft') + ' ' + stroke('ink')) +
    O(158, 98, 4, stroke('ink')) +
    P('M158 102v6', stroke('ink')),
};

/* C: geométrico. Grade de módulos (36, vão de 8) com formas primárias em degraus de tom da marca
   (suave, marca a 25 e 50% e a marca cheia) e o símbolo da cena num bloco de 2 x 2. Sem degradê
   com id: ele conflitaria entre cópias na mesma página. */
const M = 36, GAP = 8, X0 = 36, Y0 = 18;
const mx = (i) => X0 + i * (M + GAP), my = (j) => Y0 + j * (M + GAP);
// Quarto de disco com o centro num canto do módulo (tl, tr, br, bl).
const quarter = (i, j, corner, a) => {
  const x = mx(i), y = my(j);
  const [cx, cy, a0] = { tl: [x, y, 0], tr: [x + M, y, 90], br: [x + M, y + M, 180], bl: [x, y + M, 270] }[corner];
  return P(`M${cx} ${cy}L${pt(cx, cy, M, a0)}A${M} ${M} 0 0 1 ${pt(cx, cy, M, a0 + 90)}z`, a);
};
// Meio disco com o lado reto numa borda do módulo (t, r, b, l).
const half = (i, j, side, a) => {
  const x = mx(i), y = my(j), h = M / 2;
  const [cx, cy, a0] = { t: [x + h, y, 0], r: [x + M, y + h, 90], b: [x + h, y + M, 180], l: [x, y + h, 270] }[side];
  return P(`M${pt(cx, cy, h, a0)}A${h} ${h} 0 0 1 ${pt(cx, cy, h, a0 + 180)}z`, a);
};
const disc = (i, j, a) => O(mx(i) + M / 2, my(j) + M / 2, M / 2, a);
const tile = (i, j, a) => R(mx(i), my(j), M, M, 8, a);
const grid3 = (i, j, a) => dots(mx(i) + 6, my(j) + 6, 4, 4, 8, 1.8, a);

// Os módulos em volta do bloco: as mesmas sete formas e tons em todas as cenas (peso igual),
// em posições e giros diferentes. Vagas: colunas 0 e 3 nas linhas 0 e 1, e a linha 2 inteira.
const FORMS = {
  q: (i, j, o, a) => quarter(i, j, o, a),
  h: (i, j, o, a) => half(i, j, o, a),
  o: (i, j, _, a) => disc(i, j, a),
  s: (i, j, _, a) => tile(i, j, a),
  d: (i, j, _, a) => grid3(i, j, a),
};
const TONE = { soft: fill('brand-soft'), t25: fill('brand', '.25'), t50: fill('brand', '.5') };
const cFrame = (mods) => mods.map(([i, j, f, o, t]) => FORMS[f](i, j, o, TONE[t])).join('');
const FRAMES = {
  'empty-list': [[0, 0, 'q', 'br', 'soft'], [3, 0, 'd', '', 't50'], [0, 1, 'h', 'r', 't25'], [3, 1, 'o', '', 'soft'], [1, 2, 's', '', 'soft'], [2, 2, 'q', 'tl', 't50'], [3, 2, 'h', 't', 't25']],
  'search-no-results': [[0, 0, 'd', '', 't50'], [3, 0, 'q', 'bl', 'soft'], [0, 1, 'o', '', 'soft'], [3, 1, 'h', 'l', 't25'], [0, 2, 'h', 't', 't25'], [1, 2, 'q', 'tr', 't50'], [3, 2, 's', '', 'soft']],
  'load-error': [[0, 0, 's', '', 'soft'], [3, 0, 'h', 'b', 't25'], [0, 1, 'q', 'tr', 't50'], [3, 1, 'd', '', 't50'], [1, 2, 'h', 't', 't25'], [2, 2, 'o', '', 'soft'], [3, 2, 'q', 'tl', 'soft']],
  'access-denied': [[0, 0, 'h', 'r', 't25'], [3, 0, 'o', '', 'soft'], [0, 1, 'd', '', 't50'], [3, 1, 'q', 'bl', 't50'], [0, 2, 'q', 'tr', 'soft'], [2, 2, 's', '', 'soft'], [3, 2, 'h', 't', 't25']],
};
// Bloco do símbolo: colunas 1 e 2, linhas 0 e 1 (x 80 a 160, y 18 a 98), centro em (120, 58).
const cBlock = R(80, 18, 80, 80, 16, fill('brand-soft'));

const C = {
  'empty-list':
    cFrame(FRAMES['empty-list']) +
    cBlock +
    R(114, 36, 12, 44, 6, fill('brand')) +
    R(98, 52, 44, 12, 6, fill('brand')),
  'search-no-results':
    cFrame(FRAMES['search-no-results']) +
    cBlock +
    handle(129.9, 67.9, 12, 34, fill('brand-strong')) +
    P('M88 52a26 26 0 1 0 52 0a26 26 0 1 0-52 0zM98 52a16 16 0 1 1 32 0a16 16 0 1 1-32 0z', fill('brand') + ' fill-rule="evenodd"'),
  'load-error':
    cFrame(FRAMES['load-error']) +
    cBlock +
    P(roundedPoly([[120, 28], [150, 82], [90, 82]], 8), fill('brand')) +
    R(117, 44, 6, 20, 3, fill('surface')) +
    O(120, 71, 3.2, fill('surface')),
  'access-denied':
    cFrame(FRAMES['access-denied']) +
    cBlock +
    P('M106 58V46a14 14 0 0 1 28 0v12h-8V46a6 6 0 0 0-12 0v12z', fill('brand-strong')) +
    R(98, 54, 44, 34, 9, fill('brand')) +
    O(120, 68, 4.5, fill('surface')) +
    R(118, 70, 4, 10, 2, fill('surface')),
};

const BODIES = { a: A, b: B, c: C };

// [direção, cena, miolo do svg]
export const ILLUSTRATIONS = DIRECTIONS.flatMap((d) => SCENES.map((s) => [d.id, s.id, BODIES[d.id][s.id]]));

export const svg = (body, extra = '') =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${VIEWBOX}" fill="none" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"${extra}>${body}</svg>`;
