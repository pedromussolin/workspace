// Gera svg/<direção>/<cena>.svg e proposta.html (a partir de proposta.tpl.html).
// Confere as regras do conjunto em cada arquivo: sem cor fixa, sem texto, sem filter, traço entre
// 1,75 e 2 e menos de 4 KB. Uso: node build.mjs
import fs from 'node:fs';
import { DIRECTIONS, SCENES, SCHEMES, BRANDS, ILLUSTRATIONS, svg, illuMap } from './ilustracoes.mjs';
import { ICONS } from '../icones/icons.mjs';

const here = (f) => new URL('./' + f, import.meta.url);
const LIMIT = 4096;

const errors = [];
const sizes = {};
for (const [dir, scene, body] of ILLUSTRATIONS) {
  const d = DIRECTIONS.find((x) => x.id === dir);
  const out = svg(body) + '\n';
  const where = `${d.slug}/${scene}`;
  if (/#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i.test(out)) errors.push(`${where}: cor fixa`);
  if (/<text|<tspan/.test(out)) errors.push(`${where}: texto no desenho`);
  if (/filter|<image|href=/.test(out)) errors.push(`${where}: filter, imagem ou link`);
  if (/\bid=/.test(out)) errors.push(`${where}: id (conflita entre cópias na página)`);
  for (const [, w] of out.matchAll(/stroke-width="([\d.]+)"/g)) if (+w < 1.75 || +w > 2) errors.push(`${where}: stroke-width ${w}`);
  const bytes = Buffer.byteLength(out);
  if (bytes >= LIMIT) errors.push(`${where}: ${bytes} bytes`);
  fs.mkdirSync(here(`svg/${d.slug}`), { recursive: true });
  fs.writeFileSync(here(`svg/${d.slug}/${scene}.svg`), out);
  (sizes[dir] ||= []).push([scene, bytes]);
}
if (errors.length) {
  console.error(errors.join('\n'));
  process.exit(1);
}

const kb = (b) => (b / 1024).toFixed(1).replace('.', ',');
const art = (dir, scene) => svg(ILLUSTRATIONS.find(([d, s]) => d === dir && s === scene)[2], ' class="illu"');
const iconBody = Object.fromEntries(ICONS.map(([name, , body]) => [name, body]));
const ic = (name) =>
  `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconBody[name]}</svg>`;

/* Tokens: as cores fixas ficam todas no :root; o #app escolhe as do esquema e da marca da prévia. */
const schemeKeys = ['bg', 'surface', 'muted', 'sunken', 'line', 'border', 'strong', 'text', 'ink', 'text2', 'text3', 'sidebar', 'sideline', 'shadow'];
const tokens = [
  ...Object.entries(SCHEMES).flatMap(([sid, s]) => schemeKeys.map((k) => `--${sid[0]}-${k}: ${s[k]};`)),
  ...BRANDS.flatMap((b) => ['light', 'dark'].flatMap((sid) => Object.entries(b[sid]).map(([k, val]) => `--${b.id}-${sid[0]}-${k}: ${val};`))),
].join('\n    ');
const decl = (obj) => Object.entries(obj).map(([k, val]) => `${k}: ${val};`).join(' ');
const scopes = [
  ...Object.entries(SCHEMES).map(([sid, s]) => {
    const vars = Object.fromEntries(schemeKeys.map((k) => [`--m-${k}`, `var(--${sid[0]}-${k})`]));
    Object.assign(vars, { '--m-soft': s.soft, '--m-deep': s.deep, '--m-tonal': s.tonal });
    return `#app[data-scheme='${sid}'] { ${decl(vars)} }`;
  }),
  ...BRANDS.flatMap((b) =>
    ['light', 'dark'].map((sid) => {
      const p = `--${b.id}-${sid[0]}`;
      const vars = { '--m-accent': `var(${p}-accent)`, '--m-primary': `var(${p}-primary)`, '--m-secondary': `var(${p}-secondary)` };
      vars['--m-brand-ink'] = b[sid].ink ? `var(${p}-ink)` : 'color-mix(in srgb, var(--m-secondary) 82%, var(--m-text))';
      return `#app[data-brand='${b.id}'][data-scheme='${sid}'] { ${decl(vars)} }`;
    })
  ),
  `#app { ${decl(illuMap({ accent: 'var(--m-accent)', soft: 'var(--m-soft)', deep: 'var(--m-deep)', surface: 'var(--m-surface)', text: 'var(--m-text)', text2: 'var(--m-text2)', strong: 'var(--m-strong)', sunken: 'var(--m-sunken)' }))} }`,
].join('\n  ');

const segButtons = (items, cur) =>
  items.map(([v, label]) => `<button type="button" data-v="${v}" aria-pressed="${v === cur}">${label}</button>`).join('');
const brandButtons = segButtons(BRANDS.map((b) => [b.id, b.name]), 'poliedro');
const focusButtons = segButtons([['all', 'Todas'], ...DIRECTIONS.map((d) => [d.id, d.id.toUpperCase()])], 'all');
const ctxButtons = segButtons(DIRECTIONS.map((d) => [d.id, `${d.id.toUpperCase()} · ${d.name}`]), 'a');

const compare = DIRECTIONS.map((d) => {
  const sz = sizes[d.id].map(([, b]) => b);
  const scenes = SCENES.map(
    (s) => `<figure class="scene"><div class="art">${art(d.id, s.id)}</div><figcaption>${s.name}</figcaption></figure>`
  ).join('\n      ');
  return `<section class="dir" data-dir="${d.id}" aria-labelledby="dir-${d.id}">
    <header class="dir-head">
      <span class="tag" aria-hidden="true">${d.id.toUpperCase()}</span>
      <div class="dir-text">
        <h3 id="dir-${d.id}">${d.name}</h3>
        <p>${d.desc}</p>
      </div>
      <p class="dir-size">${SCENES.length} arquivos, de ${kb(Math.min(...sz))} a ${kb(Math.max(...sz))} KB</p>
    </header>
    <div class="scenes">
      ${scenes}
    </div>
  </section>`;
}).join('\n  ');

const listMock = (dir) => `<div class="mock">
        <div class="m-rail" aria-hidden="true"><span class="m-mark"></span>${['layout-dashboard', 'briefcase', 'landmark', 'line-chart', 'users', 'settings']
          .map((n, i) => `<span class="m-nav${i === 1 ? ' on' : ''}">${ic(n)}</span>`)
          .join('')}</div>
        <div class="m-main">
          <div class="m-crumbs">${ic('briefcase')}<span>Operações</span>${ic('chevron-right')}<b>Pré-Trade</b></div>
          <div class="m-head">
            <div><p class="m-title">Pré-Trade</p><p class="m-desc">Gerencie os pré-trades e acompanhe as aprovações necessárias das operações.</p></div>
            <span class="m-btn primary">${ic('plus')}Novo Pré-Trade</span>
          </div>
          <div class="m-card m-filters">
            <div class="m-field"><span class="m-label">Data de criação</span><span class="m-input"><span>Início – fim</span>${ic('calendar')}</span></div>
            <div class="m-field"><span class="m-label">Data limite</span><span class="m-input"><span>Início – fim</span>${ic('calendar')}</span></div>
            <div class="m-field"><span class="m-label">Fundo(s)</span><span class="m-input"><span>Todos os fundos</span>${ic('caret-down')}</span></div>
            <div class="m-field wide"><span class="m-label">Status</span><span class="m-input"><span>Todos os Status</span>${ic('caret-down')}</span></div>
            <span class="m-btn">${ic('filter-x')}Limpar filtros</span>
          </div>
          <div class="m-card m-table">
            <div class="m-thead">${['ID', 'Data de criação', 'Data limite', 'Usuário criador', 'Tipo', 'Fundo(s)', 'Volume (R$)', 'Etapa', 'Status']
              .map((c) => `<span>${c}</span>`)
              .join('')}</div>
            <div class="m-empty">
              <div class="m-art">${art(dir, 'lista-vazia')}</div>
              <p class="m-empty-title">Nenhum pré-trade por aqui ainda</p>
              <p class="m-empty-text">Crie a primeira solicitação: ela começa como rascunho e só vai para aprovação quando você enviar.</p>
              <span class="m-btn primary">${ic('plus')}Criar o primeiro Pré-Trade</span>
            </div>
          </div>
        </div>
      </div>`;

const denied = (dir) => `<div class="status">
          <div class="status-art">${art(dir, 'acesso-negado')}</div>
          <p class="status-title">Acesso negado</p>
          <p class="status-msg">Você não tem permissão para acessar esta página.</p>
          <p class="status-hint">Entre em contato com o administrador caso precise de acesso.</p>
          <span class="m-btn primary">Voltar para o início</span>
        </div>`;

const context = DIRECTIONS.map(
  (d) => `<div class="ctx-dir" data-dir="${d.id}">
    <figure class="shot">
      <figcaption><b>Lista vazia</b> na página do Pré-Trade</figcaption>
      <div class="frame frame-app">${listMock(d.id)}</div>
    </figure>
    <div class="shot-row">
      <figure class="shot">
        <figcaption><b>Acesso negado</b> no computador</figcaption>
        <div class="frame frame-desk">${denied(d.id)}</div>
      </figure>
      <figure class="shot shot-phone">
        <figcaption><b>Acesso negado</b> no celular</figcaption>
        <div class="phone"><div class="phone-screen">${denied(d.id)}</div></div>
      </figure>
    </div>
  </div>`
).join('\n  ');

const tpl = fs.readFileSync(here('proposta.tpl.html'), 'utf8');
const page = tpl
  .replace('/*__TOKENS__*/', () => tokens)
  .replace('/*__SCOPES__*/', () => scopes)
  .replace('<!--__BRANDS__-->', () => brandButtons)
  .replace('<!--__FOCUS__-->', () => focusButtons)
  .replace('<!--__CTX_TABS__-->', () => ctxButtons)
  .replace('<!--__COMPARE__-->', () => compare)
  .replace('<!--__CONTEXT__-->', () => context);
if (/__[A-Z_]+__/.test(page)) throw new Error('marcador sem substituir no modelo');
fs.writeFileSync(here('proposta.html'), page);

for (const d of DIRECTIONS) console.log(`${d.id} ${d.slug}: ${sizes[d.id].map(([s, b]) => `${s} ${b} B`).join(' · ')}`);
console.log('ok', ILLUSTRATIONS.length, 'svgs,', 'proposta.html', Math.round(Buffer.byteLength(page) / 1024), 'KB');
