// Kit de gráficos da prévia, em SVG puro. As cores vêm dos tokens (var(--chart-*)), então seguem
// a marca e o esquema. Cada função devolve uma string de SVG; a interação (tooltip, legenda) é
// ligada por bindCharts() depois de renderizar.
const CH = (() => {
  let uid = 0;
  const id = (p) => `${p}-${++uid}`;
  const fmt = (n, d = 0) => n.toLocaleString('pt-BR', { maximumFractionDigits: d, minimumFractionDigits: d });

  function niceMax(v, ticks = 4) {
    const raw = v / ticks;
    const mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    return { max: step * ticks, step };
  }

  // Curva suave (monotone cubic, Fritsch–Carlson): não passa do valor real entre dois pontos.
  function smooth(pts) {
    if (pts.length < 3) return pts.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join('');
    const n = pts.length, dx = [], dy = [], m = [], t = [];
    for (let i = 0; i < n - 1; i++) {
      dx[i] = pts[i + 1][0] - pts[i][0];
      dy[i] = pts[i + 1][1] - pts[i][1];
      m[i] = dy[i] / dx[i];
    }
    t[0] = m[0];
    t[n - 1] = m[n - 2];
    for (let i = 1; i < n - 1; i++) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < n - 1; i++) {
      const c1 = [pts[i][0] + dx[i] / 3, pts[i][1] + (t[i] * dx[i]) / 3];
      const c2 = [pts[i + 1][0] - dx[i] / 3, pts[i + 1][1] - (t[i + 1] * dx[i]) / 3];
      d += `C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${pts[i + 1][0]},${pts[i + 1][1]}`;
    }
    return d;
  }

  const hatchDef = (pid, color) =>
    `<pattern id="${pid}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="6" height="6" fill="${color}" opacity=".08"/><line x1="0" y1="0" x2="0" y2="6" stroke="${color}" stroke-width="2" opacity=".35"/></pattern>`;

  /**
   * Combinado: barras arredondadas (eixo esquerdo) + linhas suaves (eixo direito).
   * series: [{name, kind:'bar'|'line', axis:'l'|'r', color, data, dashed?, area?, projected?:[idx]}]
   */
  function combo({ labels, series, height = 300, unitL = '', unitR = '', hidden = new Set(), highlight = -1 }) {
    const W = 860, H = height, L = 48, R = 52, T = 18, B = 30;
    const iw = W - L - R, ih = H - T - B, n = labels.length, step = iw / n;
    const vis = series.filter((s) => !hidden.has(s.name));
    const maxOf = (axis) => Math.max(1, ...vis.filter((s) => s.axis === axis).flatMap((s) => s.data));
    const sl = niceMax(maxOf('l')), sr = niceMax(maxOf('r'));
    const yL = (v) => T + ih - (v / sl.max) * ih, yR = (v) => T + ih - (v / sr.max) * ih;
    const bars = vis.filter((s) => s.kind === 'bar');
    const bw = Math.min(14, (step * 0.62) / Math.max(bars.length, 1));
    const gid = id('g');
    let defs = `<linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--chart-1)" stop-opacity=".28"/><stop offset="1" stop-color="var(--chart-1)" stop-opacity="0"/></linearGradient>`;
    let g = '';
    for (let k = 0; k <= 4; k++) {
      const y = T + (ih * k) / 4;
      g += `<line x1="${L}" x2="${W - R}" y1="${y}" y2="${y}" class="ch-grid"/>`;
      g += `<text x="${L - 10}" y="${y + 4}" text-anchor="end" class="ch-tick">${fmt(sl.max - sl.step * k)}${unitL}</text>`;
      if (vis.some((s) => s.axis === 'r')) g += `<text x="${W - R + 10}" y="${y + 4}" class="ch-tick">${fmt(sr.max - sr.step * k)}${unitR}</text>`;
    }
    if (highlight >= 0) g += `<rect x="${L + step * highlight + 2}" y="${T}" width="${step - 4}" height="${ih}" rx="10" class="ch-band"/>`;
    labels.forEach((lab, i) => {
      if (n <= 12 || i % 2 === 0) g += `<text x="${L + step * i + step / 2}" y="${H - 8}" text-anchor="middle" class="ch-tick">${lab}</text>`;
      bars.forEach((s, j) => {
        const x = L + step * i + step / 2 - (bw * bars.length) / 2 + j * bw + 1;
        const y = yL(s.data[i]);
        const h = T + ih - y;
        const proj = s.projected?.includes(i);
        let fill = s.color;
        if (proj) {
          const pid = id('h');
          defs += hatchDef(pid, s.color);
          fill = `url(#${pid})`;
        }
        g += `<rect class="ch-bar" x="${x}" y="${y}" width="${bw - 2}" height="${Math.max(h, 2)}" rx="${(bw - 2) / 2}" fill="${fill}" style="--d:${i * 25}ms"/>`;
      });
    });
    vis.filter((s) => s.kind === 'line').forEach((s) => {
      const y = s.axis === 'r' ? yR : yL;
      const pts = s.data.map((v, i) => [L + step * i + step / 2, y(v)]);
      const d = smooth(pts);
      if (s.area) g += `<path d="${d}L${pts[pts.length - 1][0]},${T + ih}L${pts[0][0]},${T + ih}Z" fill="url(#${gid})"/>`;
      g += `<path class="ch-line" d="${d}" fill="none" stroke="${s.color}" stroke-width="2.25" ${s.dashed ? 'stroke-dasharray="5 5"' : ''} stroke-linecap="round"/>`;
      const last = pts[pts.length - 1];
      g += `<circle cx="${last[0]}" cy="${last[1]}" r="4.5" fill="${s.color}" stroke="var(--surface)" stroke-width="2.5"/>`;
    });
    g += `<line class="ch-cursor" x1="0" x2="0" y1="${T}" y2="${T + ih}" visibility="hidden"/>`;
    g += `<rect class="ch-hit" x="${L}" y="${T}" width="${iw}" height="${ih}" fill="transparent" data-l="${L}" data-step="${step}" data-n="${n}" data-w="${W}"/>`;
    return `<svg class="ch" viewBox="0 0 ${W} ${H}" role="img"><defs>${defs}</defs>${g}</svg>`;
  }

  /** Sparkline de KPI: linha suave com área em degradê. */
  function spark(data, color = 'var(--chart-1)', w = 96, h = 36) {
    const min = Math.min(...data), max = Math.max(...data);
    const pts = data.map((v, i) => [2 + (i * (w - 4)) / (data.length - 1), h - 3 - ((v - min) / (max - min || 1)) * (h - 8)]);
    const gid = id('sp');
    const d = smooth(pts);
    return `<svg class="ch-spark" viewBox="0 0 ${w} ${h}" aria-hidden="true"><defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".3"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><path d="${d}L${w - 2},${h}L2,${h}Z" fill="url(#${gid})"/><path d="${d}" fill="none" stroke="${color}" stroke-width="1.75" stroke-linecap="round"/></svg>`;
  }

  /** Rosca com segmentos arredondados e separados. items: [{name, value, color}] */
  function donut(items, { size = 200, thickness = 26, center = '', sub = '' } = {}) {
    const total = items.reduce((a, b) => a + b.value, 0);
    const r = (size - thickness) / 2, c = size / 2, circ = 2 * Math.PI * r, gap = 6;
    let acc = 0, g = '';
    items.forEach((it, i) => {
      const len = (it.value / total) * circ;
      const dash = Math.max(len - gap, 0.1);
      g += `<circle class="ch-seg" data-i="${i}" cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${it.color}" stroke-width="${thickness}" stroke-linecap="round" stroke-dasharray="${dash} ${circ - dash}" stroke-dashoffset="${-acc - gap / 2}" transform="rotate(-90 ${c} ${c})"><title>${it.name}: ${fmt((it.value / total) * 100, 0)}%</title></circle>`;
      acc += len;
    });
    return `<svg class="ch-donut" viewBox="0 0 ${size} ${size}" role="img" aria-label="${items.map((i) => `${i.name} ${fmt((i.value / total) * 100)}%`).join(', ')}">${g}<text x="${c}" y="${c + 2}" text-anchor="middle" class="ch-center">${center}</text><text x="${c}" y="${c + 22}" text-anchor="middle" class="ch-sub">${sub}</text></svg>`;
  }

  /** Barras radiais concêntricas (percentuais). items: [{name, pct, color}] */
  function radial(items, { size = 260 } = {}) {
    const c = size / 2, sw = 9, gap = 4;
    let g = '', labels = '';
    items.forEach((it, i) => {
      const r = c - 8 - i * (sw + gap);
      const circ = 2 * Math.PI * r, arc = circ * 0.75;
      // Começa às 12 h e anda 270° no sentido horário; o quadrante de cima à esquerda fica livre
      // para os rótulos, alinhados ao início de cada arco.
      g += `<circle cx="${c}" cy="${c}" r="${r}" fill="none" class="ch-track" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="${arc} ${circ}" transform="rotate(-90 ${c} ${c})"/>`;
      g += `<circle class="ch-arc" cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${it.color}" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="${(arc * it.pct) / 100} ${circ}" transform="rotate(-90 ${c} ${c})"><title>${it.name}: ${it.pct}%</title></circle>`;
      labels += `<text x="${c - 10}" y="${c - r + 3.5}" text-anchor="end" class="ch-tick ch-small">${it.name} <tspan class="ch-strong">${it.pct}%</tspan></text>`;
    });
    return `<svg class="ch-radial" viewBox="0 0 ${size} ${size}" role="img">${g}${labels}</svg>`;
  }

  /** Mapa de calor (dias × horas), células arredondadas. */
  function heatmap(rows, cols, values) {
    const cw = 34, ch = 22, gx = 5, gy = 5, L = 44, T = 22;
    const max = Math.max(...values.flat());
    let g = '';
    cols.forEach((col, j) => (g += `<text x="${L + j * (cw + gx) + cw / 2}" y="12" text-anchor="middle" class="ch-tick">${col}</text>`));
    rows.forEach((row, i) => {
      g += `<text x="${L - 8}" y="${T + i * (ch + gy) + ch / 2 + 4}" text-anchor="end" class="ch-tick">${row}</text>`;
      cols.forEach((col, j) => {
        const v = values[i][j], k = v / max;
        g += `<rect class="ch-cell" x="${L + j * (cw + gx)}" y="${T + i * (ch + gy)}" width="${cw}" height="${ch}" rx="6" fill="color-mix(in srgb, var(--chart-1) ${Math.round(8 + k * 92)}%, var(--surface))"><title>${col}, ${row}: ${v} liquidações</title></rect>`;
      });
    });
    const W = L + cols.length * (cw + gx), H = T + rows.length * (ch + gy);
    return `<svg class="ch-heat" viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
  }

  /** Barras horizontais com trilho listrado. items: [{name, value}] */
  function hbars(items, { unit = '' } = {}) {
    const max = niceMax(Math.max(...items.map((i) => i.value))).max;
    return `<div class="ch-hbars">${items
      .map((it, i) => `<div class="ch-hrow"><span class="ch-hlabel">${it.name}</span><span class="ch-htrack"><span class="ch-hfill" style="width:${(it.value / max) * 100}%;--d:${i * 60}ms;background:${i === 0 ? 'var(--chart-1)' : 'var(--chart-2)'}"></span></span><span class="ch-hval">${fmt(it.value)}${unit}</span></div>`)
      .join('')}</div>`;
  }

  return { combo, spark, donut, radial, heatmap, hbars, fmt };
})();
