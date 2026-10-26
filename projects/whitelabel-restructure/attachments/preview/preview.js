// Núcleo da prévia: estado, marcas, menu, helpers de marcação, tooltip, diálogo, toast e controles.
const BRANDS = {
  poliedro: {
    name: 'Poliedro',
    logo: ['POLIEDRO', 'CAPITAL'],
    light: { primary: '#0f3443', secondary: '#0d8291', on: '#ffffff' },
    dark: { primary: '#5fb8c6', secondary: '#4fc3d0', on: '#062029' },
  },
  dots: {
    name: 'Dots',
    logo: ['dots', ''],
    light: { primary: '#e04508', secondary: '#ee7342', on: '#ffffff' },
    dark: { primary: '#ff7a45', secondary: '#ff9a6e', on: '#1a0a03' },
  },
  cerys: {
    name: 'Cerys',
    logo: ['CERYS', 'CAPITAL'],
    light: { primary: '#ff8f1c', secondary: '#1e1e1e', on: '#ffffff' },
    dark: { primary: '#ffa64d', secondary: '#d4d4d4', on: '#1f1300' },
  },
  viva: {
    name: 'Viva',
    logo: ['viva', ''],
    light: { primary: '#79009d', secondary: '#9333ea', on: '#ffffff' },
    dark: { primary: '#c77dff', secondary: '#b98cff', on: '#1f0029' },
  },
};

// Menu do portal, com a mesma separação por módulos de hoje (GERAL / MÓDULOS / ADMINISTRATIVO).
const NAV = [
  {
    cat: 'GERAL',
    groups: [
      {
        name: 'POLI',
        icon: 'bot',
        items: [
          ['message', 'POLI Geral', ''],
          ['bar-chart', 'POLI Dados e Analytics', ''],
          ['books', 'Base de Conhecimento - POLI', ''],
        ],
      },
    ],
  },
  {
    cat: 'MÓDULOS',
    groups: [
      {
        name: 'Operações',
        icon: 'briefcase',
        items: [
          ['file-text', 'Lotes de Cessão', 'contrato'],
          ['credit-card', 'Lotes de Liquidação', 'lotes'],
          ['clipboard-list', 'Formalização', 'formalizacao'],
          ['mail-send', 'Envio de Relatórios', ''],
        ],
      },
      {
        name: 'Controladoria',
        icon: 'wallet',
        items: [
          ['line-chart', 'Desempenho da Carteira', 'performance'],
          ['clipboard-check', 'Conciliação de Registros CERC', ''],
          ['chart-search', 'Conciliação de Estoques e VALIDs', ''],
        ],
      },
      {
        name: 'Gestão',
        icon: 'landmark',
        items: [
          ['clipboard-check', 'Pré-Trade', 'pretrade'],
          ['wallet', 'Consolidado de Caixa', ''],
        ],
      },
    ],
  },
  {
    cat: 'ADMINISTRATIVO',
    groups: [
      {
        name: 'Admin',
        icon: 'shield',
        items: [
          ['hierarchy', 'Orquestrador', 'orquestrador'],
          ['archive-box', 'Produtos', ''],
          ['users', 'Usuários', ''],
          ['activity', 'Monitoramento BGT', 'onboarding'],
        ],
      },
    ],
  },
];

const SCREENS = {
  lotes: 'Lotes de Liquidação',
  contrato: 'Detalhes do Contrato',
  pretrade: 'Pré-Trade',
  ptdetalhe: 'Detalhes do Pré-Trade',
  formalizacao: 'Formalização',
  performance: 'Desempenho da Carteira',
  orquestrador: 'Orquestrador',
  onboarding: 'Onboarding BGT',
};

const state = {
  screen: 'lotes',
  brand: 'poliedro',
  scheme: 'light',
  width: 'desktop',
  load: 'ok',
  motion: 'full',
  rail: false,
  ui: {},
};
try {
  const saved = JSON.parse(localStorage.getItem('previa-portal-v2') || 'null');
  if (saved) Object.assign(state, saved, { ui: {} });
} catch {}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
const ic = (n, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ''}</svg>`;
const tip = (t, pos) => ` data-tip="${esc(t)}"${pos ? ` data-tip-pos="${pos}"` : ''}`;
const EMPTY = '<span class="empty-val" data-tip="Sem valor">—</span>';
const v = (x) => (x === null || x === undefined || x === '' ? EMPTY : x);
const brl = (n) => (n == null ? EMPTY : n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }));
const int = (n) => n.toLocaleString('pt-BR');
const mm = (n) => `${(n / 1e6).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mm`;
const sk = (w, h = 12, r) => `<span class="sk" style="width:${w};height:${h}px${r ? `;border-radius:${r}` : ''}"></span>`;
const loading = () => state.load === 'loading';
const isEmpty = () => state.load === 'empty';
const ui = state.ui;

/** Pílula de status tom sobre tom: fundo claro da cor e texto/ícone na mesma cor mais forte. */
const solid = (label, color, icon) => `<span class="pill tonal" style="--c:var(${color})">${ic(icon)}${label}</span>`;
/** Pílula suave por tom. */
const soft = (label, tone, icon) => `<span class="pill soft tone-${tone}">${icon ? ic(icon) : ''}${label}</span>`;
const act = (icon, label, cls = '', disabledReason = '') =>
  `<button class="act ${cls}" aria-label="${esc(label)}"${disabledReason ? ` aria-disabled="true"${tip(disabledReason)}` : tip(label)} data-act="noop">${ic(icon)}</button>`;

/** KPI: ícone, título e valor. Quando filtra a lista, vira botão e diz isso num texto curto. */
function kpi(label, value, icon, tone, filter) {
  const num = tone === 'warning' || tone === 'info' ? 'progress' : tone;
  const hint = filter
    ? `<small class="kpi-hint">${ic('filter')}${filter.on ? 'Filtrando a lista abaixo' : 'Clique para filtrar a lista'}</small>`
    : '';
  const body = `<span class="ico tone-${tone}">${ic(icon)}</span><span class="kpi-t"><span class="kpi-l">${label}</span><strong class="num-${num}">${value}</strong>${hint}</span>`;
  return filter
    ? `<button class="kpi ${filter.on ? 'on' : ''}" aria-pressed="${!!filter.on}" data-set="${filter.set}">${body}</button>`
    : `<div class="kpi">${body}</div>`;
}
const kpiSkeleton = () =>
  `<div class="kpi">${sk('44px', 44, '10px')}<div style="flex:1;width:100%;display:grid;gap:8px">${sk('70%')}${sk('40%', 24)}</div></div>`;

function pager(from, to, total) {
  return `<div class="pager"><span class="size">Itens por página <span class="box">${to - from + 1 > 5 ? 10 : 5}${ic('chevron-down')}</span></span>
    <span class="tnum">${from}–${to} de ${int(total)}</span>
    <span class="nav"><button disabled aria-label="Primeira página">${ic('chevrons-left')}</button><button disabled aria-label="Página anterior">${ic('chevron-left')}</button><button aria-label="Próxima página"${tip('Próxima página')}>${ic('chevron-right')}</button><button aria-label="Última página"${tip('Última página')}>${ic('chevrons-right')}</button></span></div>`;
}

/* O render refaz o DOM a cada clique, então transição nenhuma rodaria sozinha. Para abrir/fechar com
   animação, o HTML sai no estado anterior (data-flip) e a troca acontece no quadro seguinte. */
let fxOn = false;
let fxPrev = new Set();
let fxNext = new Set();
let valPrev = {};
let valNext = {};
function fx(key, open) {
  if (open) fxNext.add(key);
  const was = fxOn ? fxPrev.has(key) : open;
  return { cls: was ? 'open' : '', attr: was === open ? '' : ` data-flip="${open ? 'open' : 'close'}"`, show: open || was };
}
/** Valor que estava na tela no render anterior (para animar a troca). */
function prevVal(key, val) {
  valNext[key] = val;
  return fxOn && key in valPrev ? valPrev[key] : val;
}
/** ' fx-in' quando a visão mudou desde o último render: o conteúdo novo entra com um fade curto. */
const fresh = (key, val) => (prevVal(key, val) !== val ? ' fx-in' : '');
/** Segmentado padrão do portal (o da tela de Lotes): ícone + rótulo; a troca de opção é animada. */
function seg(key, cur, opts, { sm = false, act } = {}) {
  const was = prevVal(key, cur);
  const btn = ([val, label, icon]) =>
    `<button role="tab" aria-selected="${val === cur}" class="${val === was ? 'on' : ''}" data-v="${val}" ${act ? act(val) : `data-set="${key}=${val}"`}>${icon ? ic(icon) : ''}${label}</button>`;
  return `<span class="segctl${sm ? ' sm' : ''}" role="tablist"${was !== cur ? ` data-seg="${cur}"` : ''}>${opts.map(btn).join('')}</span>`;
}

/** Linha expansível: devolve o <tr> da linha e o <tr> do detalhe. */
function xrow(id, cells, detail, { group = 'row', cls = '' } = {}) {
  const open = ui[group] === id;
  const f = fx(`${group}:${id}`, open);
  return `<tr class="item ${f.cls} ${cls}"${f.attr} data-one="${group}=${id}" data-row="${id}">${cells}<td><button class="toggle" aria-label="${open ? 'Recolher' : 'Expandir'}" aria-expanded="${open}">${ic('chevron-down')}</button></td></tr>
    <tr class="detail"><td colspan="40"><div class="xwrap"><div>${f.show ? detail() : ''}</div></div></td></tr>`;
}

const PAGE_ICON = {
  lotes: 'credit-card',
  contrato: 'file-text',
  pretrade: 'clipboard-check',
  ptdetalhe: 'clipboard-check',
  formalizacao: 'clipboard-list',
  performance: 'line-chart',
  orquestrador: 'hierarchy',
  onboarding: 'activity',
};
const SEC_LABEL = { GERAL: ['Geral', 'Geral'], MÓDULOS: ['Módulos', 'Módulos'], ADMINISTRATIVO: ['Administrativo', 'Admin'] };
const SCHEMES = [['light', 'Claro', 'sun'], ['dark', 'Escuro', 'moon'], ['system', 'Sistema', 'monitor']];
function shell(content, { title, crumbs, help, actions = '' }) {
  const b = BRANDS[state.brand];
  const rail = state.width !== 'phone' && state.rail;
  const cur = activeNav();
  const brandName = b.name + (b.logo[1] ? ' ' + b.logo[1].toLowerCase().replace(/^./, (c) => c.toUpperCase()) : '');
  const link = ([icn, label, s]) =>
    `<li><a href="#" class="sl ${s && s === cur ? 'on' : ''}" ${s ? `data-go="${s}"` : `data-act="soon"${tip('Fora desta prévia')}`}>${ic(icn)}<span class="ellipsis" data-tip-trunc="${esc(label)}">${label}</span></a></li>`;
  const group = (g) => {
    const isCur = g.items.some((it) => it[2] === cur);
    const open = !rail && (ui['g:' + g.name] ?? isCur);
    const f = fx('g:' + g.name, open);
    return `<div class="g ${isCur ? 'cur' : ''} ${f.cls}"${f.attr}>
      <button class="nv" ${rail ? `data-act="rail" data-g="${g.name}" aria-label="${g.name}"` : `data-set="g:${g.name}=${!open}" aria-expanded="${open}"`}>${ic(g.icon)}<span class="nl">${g.name}</span>${ic('chevron-down', 'chev')}</button>
      <div class="g-sub"><div><ul>${g.items.map(link).join('')}</ul></div></div>
      ${rail ? `<div class="fly" role="menu"><h5>${g.name}</h5><ul>${g.items.map(link).join('')}</ul></div>` : ''}
    </div>`;
  };
  const sections = NAV.map((m) => {
    const [full, short] = SEC_LABEL[m.cat];
    const open = rail || !ui['sx:' + m.cat];
    const f = fx('sx:' + m.cat, open);
    return `<section class="sec ${f.cls}"${f.attr}><button class="sec-h" ${rail ? 'tabindex="-1"' : `data-set="sx:${m.cat}=${open}" aria-expanded="${open}"`}><span class="full">${full}</span><span class="short">${short}</span>${ic('chevron-down')}</button>
      <div class="sec-b"><div>${m.groups.map(group).join('')}</div></div></section>`;
  }).join('');
  const extra = [['code', 'Docs da API'], ['shapes', 'Design system']]
    .map(([i, l]) => `<a href="#" class="nv" data-act="soon" aria-label="${l}"${tip(rail ? l + ' · nova' : 'Página nova, fora desta prévia', rail ? 'right' : '')}>${ic(i)}<span class="nl">${l}</span><span class="nbadge">Nova</span></a>`)
    .join('');
  const pref = state.schemePref === 'system' ? 'system' : state.scheme;
  const um = !!ui.um;
  const me = `<div class="me-wrap"><button class="me" data-tog="um" aria-haspopup="menu" aria-expanded="${um}" aria-label="Conta e aparência"><span class="avatar">PT</span><span class="who-t"><b>Pessoa de Teste</b><small>pessoa@exemplo.com</small></span>${ic('chevrons-up-down', 'chev')}</button>
      ${um ? `<div class="menu-pop" role="menu" data-stop>
        <div class="who"><span class="avatar">PT</span><span>Pessoa de Teste<small>pessoa@exemplo.com</small></span></div><hr />
        <span class="lbl">Aparência</span>
        ${seg('schemePref', pref, SCHEMES, { sm: true, act: () => 'data-act="scheme"' })}<hr />
        <button class="mi danger" role="menuitem" data-act="noop" aria-label="Sair">${ic('log-out')}Sair</button>
      </div>` : ''}</div>`;

  // Trilha: grupo do menu › tela-mãe (nas telas de detalhe) › tela atual.
  const grp = NAV.flatMap((m) => m.groups).find((g) => g.items.some((it) => it[2] === cur));
  const parents = (crumbs || []).filter(([l]) => l !== grp?.name);
  const back = parents.filter(([, s]) => s).pop();
  const sep = ic('chevron-right', 'sep');
  const trail = `<nav class="p-crumbs" aria-label="Trilha">
      ${grp ? `<span class="c">${ic(grp.icon)}${grp.name}</span>${sep}` : ''}
      ${parents.map(([l, s]) => (s ? `<a href="#" class="c" data-go="${s}">${ic(PAGE_ICON[s] || 'file')}${l}</a>` : `<span class="c">${l}</span>`) + sep).join('')}
      <span class="c cur">${ic(PAGE_ICON[state.screen] || 'file')}<span>${title.replace(/ - .*/, '')}</span></span></nav>`;

  return `
    <div class="p-scrim ${ui.drawer ? 'open' : ''}" data-set="drawer=false"></div>
    <aside class="p-side ${rail ? 'rail' : ''} ${ui.drawer ? 'open' : ''}" aria-label="Menu">
      <div class="p-ws"><span class="p-mark" data-go="lotes"${rail ? tip(brandName + ' · página inicial', 'right') : ''}>${b.logo[0][0].toUpperCase()}</span><span class="nm"><b>${brandName}</b><small>Portal de crédito</small></span>
        <button class="p-iconbtn sm collapse" data-act="rail" aria-label="${rail ? 'Expandir menu' : 'Recolher menu'}"${tip(rail ? 'Expandir menu' : 'Recolher menu', rail ? 'right' : '')}>${ic(rail ? 'chevrons-right' : 'chevrons-left')}</button></div>
      <nav class="p-nav">${sections}</nav>
      <div class="p-foot">${extra}<div class="p-sep"></div>${me}</div>
    </aside>
    <div class="p-panel">
      <header class="p-top">
        <button class="p-iconbtn phone-only" data-tog="drawer" aria-label="Abrir menu">${ic('menu')}</button><span class="p-mark phone-only" data-go="lotes" style="width:30px;height:30px;border-radius:9px;font-size:.85rem">${b.logo[0][0].toUpperCase()}</span>
        ${back ? `<button class="p-iconbtn sm back" data-go="${back[1]}" aria-label="Voltar para ${back[0]}"${tip('Voltar para ' + back[0])}>${ic('arrow-left')}</button>` : ''}
        ${trail}
        ${actions ? `<div class="acts-top">${actions}</div>` : ''}
      </header>
      <main class="p-main"><div class="p-page">
        <div class="p-head"><h1 class="p-title">${title}</h1>${help ? `<p class="p-desc">${help}</p>` : ''}</div>
        ${content}
      </div></main>
    </div>
    ${ui.dialog ? DIALOGS[ui.dialog]() : ''}`;
}
const activeNav = () => ({ ptdetalhe: 'pretrade' })[state.screen] || state.screen;

/* ---------------- Tooltip ---------------- */
const tipEl = document.createElement('div');
tipEl.className = 'p-tip';
tipEl.setAttribute('role', 'tooltip');
let tipTimer, tipTarget;
function showTip(el) {
  let html = null;
  if (el.dataset.tipTrunc !== undefined) {
    if (el.scrollWidth <= el.clientWidth + 1) return;
    html = esc(el.dataset.tipTrunc);
  } else if (el.dataset.tipHtml) html = TIP_HTML[el.dataset.tipHtml]?.() ?? '';
  else html = esc(el.dataset.tip);
  tipEl.innerHTML = html;
  tipEl.className = 'p-tip' + (el.dataset.tipHtml ? ' rich' : '');
  const cs = getComputedStyle(portal);
  for (const k of TIP_VARS) tipEl.style.setProperty(k, cs.getPropertyValue(k));
  document.body.appendChild(tipEl);
  const r = el.getBoundingClientRect(), t = tipEl.getBoundingClientRect();
  let left, top, cls = '';
  if (el.dataset.tipPos === 'right') {
    left = r.right + 10;
    top = r.top + r.height / 2 - t.height / 2;
    cls = 'right';
  } else {
    left = Math.min(Math.max(8, r.left + r.width / 2 - t.width / 2), innerWidth - t.width - 8);
    top = r.top - t.height - 10;
    if (top < 8) {
      top = r.bottom + 10;
      cls = 'below';
    }
    tipEl.style.setProperty('--ax', `${r.left + r.width / 2 - left}px`);
  }
  if (cls) tipEl.classList.add(cls);
  tipEl.style.left = left + 'px';
  tipEl.style.top = top + 'px';
  requestAnimationFrame(() => tipEl.classList.add('show'));
}
function hideTip() {
  clearTimeout(tipTimer);
  tipTarget = null;
  tipEl.classList.remove('show');
}
const TIP_SEL = '[data-tip],[data-tip-trunc],[data-tip-html]';
document.addEventListener('pointerover', (e) => {
  const el = e.target.closest?.(TIP_SEL);
  if (el === tipTarget) return;
  hideTip();
  if (!el) return;
  tipTarget = el;
  tipTimer = setTimeout(() => showTip(el), el.dataset.tipHtml ? 120 : 300);
});
document.addEventListener('focusin', (e) => {
  const el = e.target.closest?.(TIP_SEL);
  if (el) {
    hideTip();
    tipTarget = el;
    showTip(el);
  }
});
document.addEventListener('focusout', hideTip);
document.addEventListener('scroll', hideTip, true);
const TIP_HTML = {};
const TIP_VARS = ['--tip-bg', '--tip-fg', '--surface', '--surface-sunken', '--border-strong', '--text-faint', '--success-soft', '--success-line', '--success-strong', '--danger-soft', '--danger-line', '--danger-strong', '--warning-soft', '--warning-line', '--warning-strong', '--radius-sm'];

/* ---------------- Toast ---------------- */
function toast(msg, icon = 'check-circle') {
  const host = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `${ic(icon)}<span>${msg}</span>`;
  host.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

/* ---------------- Render ---------------- */
const portal = document.getElementById('portal');
const DIALOGS = {};
let lastScreen = null;
function render() {
  const b = BRANDS[state.brand];
  for (const m of ['light', 'dark']) {
    portal.style.setProperty(`--brand-primary-${m}`, b[m].primary);
    portal.style.setProperty(`--brand-secondary-${m}`, b[m].secondary);
    portal.style.setProperty(`--brand-on-primary-${m}`, b[m].on);
  }
  portal.dataset.scheme = state.scheme;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  portal.dataset.motion = state.motion === 'full' ? 'full' : reduced ? 'reduced' : 'full';
  document.getElementById('frame').classList.toggle('phone', state.width === 'phone');
  const main = portal.querySelector('.p-main');
  const keep = lastScreen === state.screen && main ? main.scrollTop : 0;
  portal.classList.toggle('enter', lastScreen !== state.screen || ui.replay);
  ui.replay = false;
  hideTip();
  fxOn = lastScreen === state.screen;
  fxNext = new Set();
  valNext = {};
  portal.innerHTML = RENDER[state.screen]();
  fxPrev = fxNext;
  valPrev = valNext;
  const nm = portal.querySelector('.p-main');
  if (nm) nm.scrollTop = keep;
  lastScreen = state.screen;
  const nextFrame = (fn) => requestAnimationFrame(() => requestAnimationFrame(fn));
  portal.querySelectorAll('[data-flip]').forEach((el) => nextFrame(() => el.classList.toggle('open', el.dataset.flip === 'open')));
  portal.querySelectorAll('[data-seg]').forEach((el) =>
    nextFrame(() => el.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.v === el.dataset.seg)))
  );
  bindCharts();
  portal.querySelectorAll('.tbl-wrap').forEach((w) => w.style.setProperty('--vw', w.clientWidth + 'px'));
  const bb = b[state.scheme];
  document.getElementById('note').textContent =
    `${b.name}, ${state.scheme === 'dark' ? 'escuro' : 'claro'}: primária ${bb.primary}, secundária ${bb.secondary}. ` +
    (portal.dataset.motion === 'reduced' ? 'Seu sistema pede menos movimento: as animações viram só transições de opacidade. ' : '') +
    'Passe o mouse nos ícones, nos valores e nas bolinhas de aprovação para ver os tooltips.';
  try {
    const { ui: _u, ...rest } = state;
    localStorage.setItem('previa-portal-v2', JSON.stringify(rest));
  } catch {}
}

portal.addEventListener('click', (e) => {
  const t = e.target.closest('[data-go],[data-set],[data-tog],[data-one],[data-act],[data-dlg]');
  if (ui.um && !e.target.closest('.me-wrap')) {
    ui.um = false;
    if (!t) return render();
  }
  if (!t || t.closest('[aria-disabled="true"]')) return;
  if (t.closest('.menu-pop') && !t.dataset.act) return;
  if (t.tagName === 'A') e.preventDefault();
  if (t.dataset.go) {
    state.screen = t.dataset.go;
    // O estado do menu lateral (grupos e seções abertos) sobrevive à navegação; o resto da tela não.
    Object.keys(ui).forEach((k) => /^(g|sx):/.test(k) || delete ui[k]);
  } else if (t.dataset.set) {
    const [k, val] = t.dataset.set.split('=');
    ui[k] = val === 'true' ? true : val === 'false' ? false : val;
  } else if (t.dataset.tog) ui[t.dataset.tog] = !ui[t.dataset.tog];
  else if (t.dataset.one) {
    if (e.target.closest('.act,.remit,.cbx,[data-stop]')) return;
    const [g, id] = t.dataset.one.split('=');
    ui[g] = ui[g] === id ? null : id;
  } else if (t.dataset.dlg) ui.dialog = t.dataset.dlg;
  else if (t.dataset.act) return ACTIONS[t.dataset.act]?.(t, e);
  render();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && (ui.dialog || ui.um)) {
    ui.dialog = null;
    ui.um = false;
    render();
  }
});

const ACTIONS = {
  scheme: (t) => {
    const v = t.dataset.v;
    state.schemePref = v;
    state.scheme = v === 'system' ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : v;
    render();
    syncControls();
  },
  noop: (t) => toast(`${t.getAttribute('aria-label')} (exemplo)`, 'info'),
  soon: () => toast('Tela fora desta prévia', 'info'),
  rail: (t) => {
    state.rail = !state.rail;
    if (t.dataset.g) ui['g:' + t.dataset.g] = true;
    render();
  },
  close: () => {
    ui.dialog = null;
    render();
  },
  confirm: (btn) => {
    // Botão vira spinner e depois check antes de fechar, como nos diálogos do Pré-Trade.
    btn.disabled = true;
    btn.classList.add('busy');
    btn.innerHTML = '<span class="spin"></span>Processando…';
    setTimeout(() => {
      btn.classList.remove('primary');
      btn.classList.add('done');
      btn.innerHTML = `${ic('check')}Pronto`;
      setTimeout(() => {
        const done = DIALOG_DONE[ui.dialog];
        ui.dialog = null;
        render();
        done?.();
      }, 700);
    }, 900);
  },
};
const DIALOG_DONE = {};
function flashRow(id, color) {
  const tr = portal.querySelector(`tr[data-row="${id}"]`);
  if (!tr) return;
  tr.style.setProperty('--flash', `var(${color})`);
  tr.classList.remove('flash');
  void tr.offsetWidth;
  tr.classList.add('flash');
}

/* ---------------- Controles da prévia ---------------- */
const CONTROLS = {
  'c-screen': ['screen', Object.entries(SCREENS)],
  'c-brand': ['brand', Object.entries(BRANDS).map(([k, b]) => [k, b.name])],
  'c-scheme': ['scheme', [['light', 'Claro'], ['dark', 'Escuro']]],
  'c-width': ['width', [['desktop', 'Desktop'], ['phone', 'Celular']]],
  'c-state': ['load', [['ok', 'Com dados'], ['loading', 'Carregando'], ['empty', 'Vazio']]],
  'c-motion': ['motion', [['full', 'Animações ligadas'], ['system', 'Seguir o sistema']]],
};
function syncControls() {
  for (const [id, [key, opts]] of Object.entries(CONTROLS)) {
    const el = document.getElementById(id);
    if (!el.childElementCount) {
      el.innerHTML = opts.map(([val, l]) => `<button type="button" data-v="${val}">${l}</button>`).join('');
      el.addEventListener('click', (e) => {
        const b = e.target.closest('button');
        if (!b) return;
        state[key] = b.dataset.v;
        if (key === 'screen') Object.keys(ui).forEach((k) => delete ui[k]);
        ui.dialog = null;
        ui.um = false;
        if (key === 'scheme') state.schemePref = state.scheme;
        if (key === 'load' || key === 'motion') ui.replay = true;
        render();
        syncControls();
      });
    }
    el.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === state[key])));
  }
}
