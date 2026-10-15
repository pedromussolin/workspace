// Telas da prévia. Dados de exemplo.

/* ======================= Lotes de Liquidação ======================= */
const LB_STATUS = {
  cadastrado: ['Cadastrado', '--st-cadastrado', 'clipboard-list'],
  pendente: ['Pendente', '--st-pendente', 'hourglass'],
  apto: ['Apto', '--st-cadastrado', 'list-check'],
  registrando: ['Registrando', '--st-liquidando', 'refresh'],
  callback: ['Callback', '--st-callback', 'rotate-ccw'],
  errado: ['Errado', '--st-errado', 'alert-circle'],
  aguarda: ['Aguardando conciliação', '--st-pendente', 'clock'],
  manual: ['Conciliação manual', '--st-cadastrado', 'list-check'],
  liquidando: ['Liquidando', '--st-liquidando', 'hourglass'],
  liquidado: ['Liquidado', '--st-liquidado', 'clipboard-check'],
  concluido: ['Concluído', '--brand-secondary', 'check-circle'],
};
const lbPill = (k) => solid(...LB_STATUS[k]);
const CNPJ = { 'FIDC Poliedro Crédito I': '41.987.654/0001-20', 'FIDC Poliedro Crédito II': '42.118.203/0001-77', 'FIDC Varejo Sênior': '38.551.902/0001-04' };
const FAKE = [
  { id: 'f1', data: '09/10/2026', valor: 2384120.55, fundo: 'FIDC Poliedro Crédito I', produto: 'Consignado Privado', status: 'cadastrado', origem: 'CNAB 500' },
  { id: 'f2', data: '09/10/2026', valor: 418772.1, fundo: 'FIDC Poliedro Crédito I', produto: 'Antecipação FGTS', status: 'pendente', origem: 'API' },
  { id: 'f3', data: '09/10/2026', valor: 1172003.9, fundo: 'FIDC Varejo Sênior', produto: 'Crediário Digital', status: 'registrando', origem: 'CNAB 500' },
  { id: 'f4', data: '08/10/2026', valor: 9120.0, fundo: 'FIDC Varejo Sênior', produto: 'Crediário Digital', status: 'errado', origem: null },
  { id: 'f5', data: '08/10/2026', valor: 655480.33, fundo: 'FIDC Poliedro Crédito II', produto: 'Capital de Giro com Garantia Real de Recebíveis', status: 'callback', origem: 'CNAB 500' },
];
const REAL = [
  { id: 'r1', lote: 1828920, data: '09/10/2026', fundo: 'FIDC Poliedro Crédito I', produto: 'Consignado Privado', valor: 2384120.55, status: 'manual', proc: 'PRC-20261009-0042', lotes: 3 },
  { id: 'r2', lote: 1828918, data: '09/10/2026', fundo: 'FIDC Poliedro Crédito I', produto: 'Antecipação FGTS', valor: 418772.1, status: 'aguarda', proc: 'PRC-20261009-0039', lotes: 1 },
  { id: 'r3', lote: 1828911, data: '08/10/2026', fundo: 'FIDC Varejo Sênior', produto: 'Crediário Digital', valor: 1172003.9, status: 'liquidado', proc: 'PRC-20261008-0115', lotes: 1 },
  { id: 'r4', lote: 1828904, data: '08/10/2026', fundo: 'FIDC Varejo Sênior', produto: 'Crediário Digital', valor: 9120.0, status: 'errado', proc: 'PRC-20261008-0098', lotes: 2 },
  { id: 'r5', lote: 1828899, data: '07/10/2026', fundo: 'FIDC Poliedro Crédito II', produto: 'Capital de Giro', valor: 655480.33, status: 'concluido', proc: 'PRC-20261007-0301', lotes: 1 },
];
const PAGTOS = [
  { ctrl: 'CCB-00098812', ident: '0042-0001', valor: 1873.4, sacado: 'Maria Aparecida Souza', tipo: 'Baixa pelo sacado' },
  { ctrl: 'CCB-00098813', ident: '0042-0002', valor: 512.06, sacado: 'João Pietro Lima', tipo: 'Pagamento parcial' },
  { ctrl: 'CCB-00101377', ident: '0042-0003', valor: 2210.0, sacado: 'Comercial Andrade Ltda.', tipo: null },
];
function paymentsTable(withTabs) {
  const tab = ui.ptab || 'ativos';
  const rows = (tab === 'ativos' ? PAGTOS : PAGTOS.slice(0, 1)).map(
    (p) => `<tr><td class="mono">${p.ctrl}</td><td class="mono">${p.ident}</td><td class="r tnum">${brl(p.valor)}</td><td class="l"><span class="ellipsis" style="max-width:200px" data-tip-trunc="${p.sacado}">${p.sacado}</span></td><td>${v(p.tipo)}</td></tr>`
  );
  return `<div class="row" style="justify-content:space-between;margin-bottom:8px"><span class="overline" style="margin:0">Pagamentos do lote</span>
      ${withTabs ? `<span class="row">${tab === 'rejeitados' ? `<button class="btn sm"${tip('Baixa os rejeitados com o motivo de cada um')} data-act="noop" aria-label="Exportar rejeitados">${ic('download')}Exportar rejeitados</button>` : ''}
        ${seg('ptab', tab, [['ativos', 'Ativos (3)', 'check-circle'], ['rejeitados', 'Rejeitados (1)', 'x-circle']], { sm: true })}</span>` : ''}</div>
    <div class="tbl-wrap${withTabs ? fresh('ptab', tab) : ''}"><table class="tbl nested"><thead><tr><th>Número de controle</th><th>Identificador</th><th class="r">Valor pago</th><th class="l">Sacado</th><th>Tipo de baixa</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}
function batchDetail(r) {
  const short = r.status === 'errado';
  return `<div class="xin" style="padding:16px 20px;display:grid;gap:14px">
    <div class="row" style="justify-content:space-between"><div class="row"><b style="font-size:1.05rem">Lote ${r.lote}</b>${lbPill(r.status)}</div>
      <button class="btn sm"${tip(`Processo (proc_id) ${r.proc}`)} data-act="noop" aria-label="Baixar CNAB">${ic('download')}Baixar CNAB</button></div>
    <div class="grid-cols">
      <div class="panel-soft"><h4>Informações gerais</h4>
        <div class="kv"><span>Fundo</span><span>${r.fundo}</span></div><div class="kv"><span>Produto</span><span>${r.produto}</span></div>
        <div class="kv"><span>Data do lote</span><span>${r.data}</span></div><div class="kv"><span>Valor original</span><span class="tnum">${brl(r.valor)}</span></div>
        <div class="kv"><span>Valor aprovado</span><span class="tnum" style="color:var(--success)">${brl(r.valor * 0.98)} <small class="muted" style="font-weight:400">(1.262 pagamentos)</small></span></div>
        <div class="kv"><span>Valor liquidado</span><span style="font-style:italic;color:var(--text-muted);font-weight:500">Aguardando retorno da ADM</span></div>
        <div class="kv"><span>Rejeitado PLGN</span><span class="tnum" style="color:var(--danger)">${brl(r.valor * 0.02)} <small class="muted" style="font-weight:400">(22)</small></span></div></div>
      <div class="panel-soft"><h4>Conciliação financeira</h4>
        <div class="kv"><span>Valor necessário</span><span class="tnum">${brl(r.valor)}</span></div>
        <div class="kv"><span>Saldo disponível em conta</span><span class="tnum">${brl(short ? r.valor * 0.6 : r.valor * 1.2)}</span></div>
        <div class="kv"><span>Diferença</span><span class="row" style="justify-content:flex-end;color:var(${short ? '--danger' : '--success'})">${ic(short ? 'alert-circle' : 'check-circle')}<span class="tnum">${short ? '−' + brl(r.valor * 0.4).replace('R$', 'R$') : 'Saldo suficiente'}</span></span></div></div>
    </div>
    ${r.lotes > 1 ? `<div class="panel-soft" style="border:1px dashed var(--remit-line);background:var(--remit-soft)"><h4>Processo (proc_id) · ${r.lotes} lotes</h4><p class="muted" style="margin:0 0 8px;font-size:0.75rem">A remessa ${r.proc} foi dividida em ${r.lotes} lotes.</p><button class="btn sm ghost" style="color:var(--st-liquidando);padding:0" data-act="noop" aria-label="Ver os lotes deste processo">${ic('filter')}Ver os ${r.lotes} lotes deste processo</button></div>` : ''}
    ${paymentsTable(true)}
  </div>`;
}
function screenLotes() {
  const tab = ui.lbtab || 'fechamento';
  const toolbar = `<div class="card toolbar-card"><div class="toolbar">
      ${seg('lbtab', tab, [['fechamento', 'Fechamento de Lotes', 'archive-box'], ['conciliacao', 'Conciliação manual', 'list-check']])}
      <span class="vdiv"></span>
      <div class="field"><label>Fundo <span class="req">*</span></label><div class="input focus" data-tip-trunc="FIDC Poliedro Crédito I"><span class="val">FIDC Poliedro Crédito I</span>${ic('chevron-down')}</div></div>
      <div class="field"><label>Produtos</label><div class="input"><span class="val">Consignado Privado <span class="more">(+2 Outros)</span></span>${ic('x')}${ic('caret-down')}</div></div>
      <div class="field"><label>Data</label><div class="input"><span class="val">09/10/2026</span>${ic('calendar')}</div></div>
      <span class="vdiv"></span>
      <div class="field"><label>Status</label><div class="input"><span class="val ph">Todos os Status</span>${ic('caret-down')}</div></div>
    </div></div>`;
  let body;
  if (loading()) {
    body = `<table class="tbl"><thead><tr>${['Data', 'Valor pago', 'Fundo', 'Produto', 'Status', 'Origem', 'Ações', ''].map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${Array.from({ length: 4 }, () => `<tr>${['80px', '110px', '150px', '130px', '110px', '70px', '80px', '24px'].map((w) => `<td><span style="display:flex;justify-content:center">${sk(w)}</span></td>`).join('')}</tr>`).join('')}</tbody></table>`;
  } else if (isEmpty()) {
    body = emptyState('search', 'Nenhum lote para esses filtros', 'Troque a data, o fundo ou o status para ver outros lotes.', 'Limpar filtros');
  } else if (tab === 'fechamento') {
    const rows = FAKE.map((r) =>
      xrow(r.id, `<td class="tnum">${r.data}</td><td class="tnum">${brl(r.valor)}</td><td class="l"><span class="cell2"><span class="ellipsis" style="max-width:190px" data-tip-trunc="${r.fundo}">${r.fundo}</span><small>${CNPJ[r.fundo]}</small></span></td><td class="l"><span class="ellipsis" style="max-width:180px" data-tip-trunc="${r.produto}">${r.produto}</span></td><td>${lbPill(r.status)}</td><td>${v(r.origem)}</td>
        <td><span class="acts">${act('check-circle', 'Fechar lote', 'info', r.status === 'cadastrado' ? '' : `Lote em "${LB_STATUS[r.status][0]}": só é possível fechar lote cadastrado.`)}${act('trash', 'Excluir lote', 'danger')}</span></td>`,
        () => `<div class="xin" style="padding:16px 20px">${paymentsTable(false)}</div>`)
    ).join('');
    body = `<div class="tbl-wrap resp"><table class="tbl"><thead><tr><th>Data</th><th class="sort">Valor pago${ic('arrow-down')}</th><th class="l">Fundo</th><th class="l">Produto</th><th>Status</th><th class="sort">Origem${ic('arrows-up-down')}</th><th>Ações</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="m-list">${FAKE.map((r) => `<div class="m-item"><div class="top"><div><b>${brl(r.valor)}</b><div class="muted" style="font-size:.78rem">${r.data} · ${v(r.origem)}</div></div>${lbPill(r.status)}</div><dl><dt>Fundo</dt><dd>${r.fundo}</dd><dt>Produto</dt><dd>${r.produto}</dd></dl><span class="acts" style="justify-content:flex-end">${act('check-circle', 'Fechar lote', 'info', r.status === 'cadastrado' ? '' : 'Só é possível fechar lote cadastrado.')}${act('trash', 'Excluir lote', 'danger')}</span></div>`).join('')}</div>
      ${pager(1, 5, 18)}`;
  } else {
    const rows = REAL.map((r) =>
      xrow(r.id, `<td class="mono">${r.lote}${r.lotes > 1 ? `<span class="remit" data-act="noop" aria-label="Ver os lotes do processo"${tip(`Este processo (proc_id) está em ${r.lotes} lotes. Clique para ver todos.`)}>${ic('split')}${r.lotes}</span>` : ''}</td><td class="tnum">${r.data}</td><td><span class="ellipsis" style="max-width:180px" data-tip-trunc="${r.fundo}">${r.fundo}</span></td><td>${r.produto}</td><td class="tnum">${brl(r.valor)}</td><td>${lbPill(r.status)}</td>
        <td><span class="acts">${act('eye', 'Detalhes')}${act('refresh', 'Reprocessar lote', 'info', r.status === 'errado' ? '' : 'Só lotes com erro podem ser reprocessados.')}${r.status === 'manual' ? `<button class="act success" aria-label="Aprovar lote"${tip('Aprovar lote')} data-dlg="aprovarLote">${ic('check-circle')}</button>` : act('check-circle', 'Aprovar lote', 'success', 'Só lotes em conciliação manual podem ser aprovados.')}${act('trash', 'Excluir lote', 'danger', r.status === 'manual' ? '' : 'Só lotes em conciliação manual podem ser excluídos.')}</span></td>`,
        () => batchDetail(r), { group: 'real' })
    ).join('');
    body = `<div class="tbl-wrap resp"><table class="tbl"><thead><tr><th>ID lote</th><th>Data</th><th>Fundo</th><th>Produto</th><th>Valor do lote</th><th>Status</th><th>Ações</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="m-list">${REAL.map((r) => `<div class="m-item"><div class="top"><div><b>Lote ${r.lote}</b><div class="mono">${r.proc}</div></div>${lbPill(r.status)}</div><dl><dt>Fundo</dt><dd>${r.fundo}</dd><dt>Valor</dt><dd>${brl(r.valor)}</dd></dl></div>`).join('')}</div>
      ${pager(1, 5, 42)}`;
  }
  return shell(`<div class="stack">${toolbar}
      ${tab === 'conciliacao' && !loading() && !isEmpty() && ui.real === 'r1' ? `<div class="panel-soft row" style="border:1px dashed var(--remit-line);background:var(--remit-soft);padding:8px 12px;font-size:.8rem;color:var(--text-secondary)">${ic('filter')}<span>Mostrando os lotes do processo <b>PRC-20261009-0042</b> (proc_id). O filtro de data não se aplica aqui.</span></div>` : ''}
      <div class="card${fresh('lbtab', tab)}" style="overflow:hidden">${body}</div></div>`,
    { title: SCREENS.lotes, help: 'Fechamento e conciliação dos lotes de liquidação por fundo e data.' });
}
DIALOGS.aprovarLote = () => `<div class="dlg-scrim"><div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t">
  <header>${ic('check-circle')}<h3 id="dlg-t">Aprovar conciliação manual</h3><button class="x" data-act="close" aria-label="Fechar">${ic('x')}</button></header>
  <p class="sub">A aprovação retoma a esteira de baixa do lote mesmo sem saldo conciliado.</p>
  <div class="panel-soft" style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;padding:14px 16px">
    <div><div class="lbl">Lote</div><b>1828920</b></div><div><div class="lbl">Fundo</div><b>FIDC Poliedro Crédito I</b></div><div><div class="lbl">Produto</div><b>Consignado Privado</b></div><div><div class="lbl">Valor</div><b class="tnum">R$ 2.384.120,55</b></div></div>
  <div class="form"><div class="field full"><label>Observação <span class="req">*</span></label><textarea placeholder="Ex.: Alinhado com a tesouraria">Alinhado com a tesouraria; saldo entra amanhã.</textarea></div></div>
  <footer><button class="btn" data-act="close">Cancelar</button><button class="btn primary" data-act="confirm">${ic('check-circle')}Aprovar</button></footer></div></div>`;
DIALOG_DONE.aprovarLote = () => {
  toast('Lote 1828920 aprovado');
  flashRow('r1', '--success-soft');
};

function emptyState(icon, title, text, btn) {
  return `<div class="empty"><svg class="float" width="140" height="104" viewBox="0 0 160 120" aria-hidden="true"><ellipse cx="80" cy="108" rx="44" ry="6" fill="var(--surface-sunken)"/><rect x="44" y="14" width="72" height="86" rx="10" fill="var(--surface)" stroke="var(--border-strong)" stroke-width="2"/><rect x="66" y="8" width="28" height="12" rx="4" fill="var(--brand-primary)"/>
    ${icon === 'search' ? '<circle cx="80" cy="56" r="14" fill="var(--surface-sunken)" stroke="var(--text-faint)" stroke-width="4"/><path d="M90 66l10 10" stroke="var(--text-faint)" stroke-width="5" stroke-linecap="round"/>' : '<rect x="56" y="34" width="48" height="6" rx="3" fill="var(--surface-sunken)"/><rect x="56" y="48" width="36" height="6" rx="3" fill="var(--surface-sunken)"/><rect x="56" y="62" width="42" height="6" rx="3" fill="var(--surface-sunken)"/><circle cx="110" cy="86" r="14" fill="var(--brand-secondary)"/><path d="M110 79v14M103 86h14" stroke="var(--surface)" stroke-width="3" stroke-linecap="round"/>'}</svg>
    <h3>${title}</h3><p>${text}</p>${btn ? `<button class="btn" style="margin-top:8px" data-act="noop" aria-label="${btn}">${ic(icon === 'search' ? 'filter-x' : 'plus')}${btn}</button>` : ''}</div>`;
}

/* ======================= Detalhes do Contrato ======================= */
function screenContrato() {
  const geral = [
    ['Núm. controle', '000123456'], ['Data de emissão', '12/03/2026'], ['Data de vencimento', '12/03/2029'], ['Data de cessão', '15/03/2026'],
    ['Data de desembolso', '16/03/2026'], ['Taxa pré-anual', '24,60%'], ['Taxa pré-mensal', '1,85%'], ['Valor principal', 'R$ 48.500,00'],
    ['TAC', 'R$ 650,00'], ['Ágio', null], ['Valor de aquisição', 'R$ 47.120,33'], ['Valor título', 'R$ 61.844,40'], ['Valor pago', 'R$ 12.368,88'],
    ['Valor aberto', 'R$ 49.475,52'], ['Status', 'Ativo'], ['Tipo de cobrança', 'Boleto'], ['Data de aquisição anterior', null], ['Qtd. parcelas', '36'],
    ['Qtd. parcelas em aberto', '28'], ['Indexador (Produto)', 'Pré-fixado'], ['Direitos creditórios', 'CCB'], ['Identificador (Processo)', 'PRC-20260315-0007'],
  ];
  const secs = [
    ['Fundo', 'landmark', [['ID', '112'], ['Nome', 'FIDC Poliedro Crédito I'], ['CNPJ', '41.987.654/0001-20']]],
    ['Cedente', 'building', [['Nome', 'Crédito Fácil Sociedade de Crédito Direto S.A.'], ['Tipo de pessoa', 'Jurídica'], ['Tipo do documento', 'CNPJ'], ['Documento', '33.221.110/0001-09']]],
    ['Sacado', 'user', [['Nome', 'Maria Aparecida Souza'], ['Documento', '123.456.789-09']]],
    ['Emissor', 'id-card', [['Nome', 'Banco Emissor S.A.'], ['CNPJ', '12.345.678/0001-90']]],
  ];
  const open = ui.acc ?? 'Parcelas';
  const accItem = (name, icon, inner) => {
    const f = fx('acc:' + name, open === name);
    return `<div class="acc ${f.cls}"${f.attr}><button data-set="acc=${open === name ? '' : name}" aria-expanded="${open === name}"><span class="ci">${ic(icon)}</span>${name}${ic('chevron-down', 'chev')}</button>
    <div class="xwrap"><div><div class="xin2">${inner}</div></div></div></div>`;
  };
  const kvs = (rows) => rows.map(([k, val]) => `<div class="kv"><span>${k}</span><span>${v(val)}</span></div>`).join('');
  const parcelas = [1, 2, 3].map((n) => `<div class="subcard" style="padding:12px 14px"><div class="row" style="justify-content:space-between"><b>${n} - Parcela ${8800 + n}</b>${n === 1 ? soft('Paga', 'success', 'check-circle') : n === 2 ? soft('Vence em 12 dias', 'warning', 'clock') : soft('Em aberto', 'neutral')}</div>
    ${kvs([['PMT', n], ['Data ajustada', `1${n}/0${3 + n}/2026`], ['Valor nominal', 'R$ 1.717,90'], ['Valor pago', n === 1 ? 'R$ 1.717,90' : null], ['Valor em aberto', n === 1 ? 'R$ 0,00' : 'R$ 1.717,90']])}</div>`).join('');
  const regras = `<div class="subcard" style="padding:12px 14px"><b>1 - Prazo máximo</b><p class="muted" style="margin:2px 0 6px;font-size:.8rem">Contrato com até 48 parcelas.</p>${kvs([['max_parcelas', '48'], ['atual', '36']])}</div>`;
  const left = loading()
    ? `<div class="card card-pad">${Array.from({ length: 9 }, () => `<div class="kv">${sk('120px', 16)}${sk('90px', 16)}</div>`).join('')}</div>`
    : `<div class="card raised" style="overflow:hidden"><div class="card-head"><h2 class="card-title">Dados gerais</h2>${soft('Ativo', 'success', 'check-circle')}</div><div style="padding:6px 22px 14px">${kvs(geral)}</div></div>`;
  return shell(`<div class="grid-cols">${left}
      <div class="stack" style="gap:0"><div class="card raised" style="overflow:hidden"><div class="card-head"><h2 class="card-title">Detalhes</h2><span class="muted" style="font-size:.8rem">Clique para abrir cada seção</span></div><div style="padding:14px">
        ${secs.map(([n, icn, rows]) => accItem(n, icn, kvs(rows))).join('')}${accItem('Parcelas', 'calendar', `<div style="display:grid;gap:10px">${parcelas}</div>`)}${accItem('Regras de Elegibilidade', 'list-check', regras)}
      </div></div></div></div>`,
    { title: `${SCREENS.contrato} - 000123456`, crumbs: [['Lotes de Cessão', '']], help: 'Página de detalhes do contrato.' });
}

/* ======================= Pré-Trade ======================= */
const PT = [
  { id: 187, key: 'PT-2026-0187', criado: '06/10/2026', prazo: ['soon', 'vence amanhã', 'clock', '11/10/2026'], user: 'Ana Ribeiro', tipo: 'Fundos', fundos: ['FIDC Poliedro Crédito I', 'FIC FIM Estratégia Crédito Privado'], vol: 12500000, stage: 'Aguardando 1ª aprovação', tone: 'neutral', you: true, step: 1, dots: [['ok', 'no', 'pending'], ['next']] },
  { id: 186, key: 'PT-2026-0186', criado: '03/10/2026', prazo: ['overdue', 'venceu ontem', 'alert-circle', '09/10/2026'], user: 'Bruno Carvalho', tipo: 'Títulos de dívida', fundos: ['FIDC Varejo Sênior'], vol: 4800000, stage: 'Aguardando 2ª aprovação', tone: 'neutral', you: false, step: 2, dots: [['all'], ['ok', 'pending']] },
  { id: 184, key: 'PT-2026-0184', criado: '01/10/2026', prazo: ['normal', 'vence em 6 dias', 'calendar', '16/10/2026'], user: 'Carla Menezes', tipo: 'Carteira e CCB', fundos: ['FIDC Poliedro Crédito II'], vol: 2250000, stage: 'Aguardando execução do trade', tone: 'success', you: false, step: 3, dots: [['all'], ['all']] },
  { id: 181, key: 'PT-2026-0181', criado: '29/09/2026', prazo: ['normal', 'vence em 9 dias', 'calendar', '19/10/2026'], user: 'Ana Ribeiro', tipo: 'Derivativos', fundos: ['FIC FIM Estratégia Crédito Privado'], vol: 900000, stage: 'Rascunho', tone: 'neutral', you: true, step: 0, dots: null },
  { id: 175, key: 'PT-2026-0175', criado: '22/09/2026', prazo: null, user: 'Diego Prado', tipo: 'Fundos', fundos: ['FIDC Saúde Mezanino', 'FIDC Poliedro Crédito I', 'FIDC Varejo Sênior'], vol: 7300000, stage: 'Concluída', tone: 'success', you: false, step: 6, dots: [['all'], ['all']] },
];
const STEPS = ['Rascunho', '1ª aprovação', '2ª aprovação', 'Trade', 'Conferência', 'Concluído'];
const stagePill = (p) => `<span class="pill soft tone-${p.tone === 'success' ? 'success' : p.tone === 'danger' ? 'danger' : 'neutral'}">${p.stage}</span>`;
function dotsHtml(p) {
  if (!p.dots) return `<span class="empty-val"${tip('Ainda não enviado para aprovação')}>—</span>`;
  const one = (d) => (d === 'all' ? `<span class="dot all">${ic('check')}</span>` : `<span class="dot ${({ ok: 'ok', no: 'no', back: 'back', pending: '', next: 'next' })[d]}"></span>`);
  return `<span class="dots" tabindex="0" data-tip-html="dots-${p.id}" aria-label="Situação das aprovações">${p.dots.map((g) => g.map(one).join('')).join('<span class="dash"></span>')}</span>`;
}
PT.forEach((p) => {
  TIP_HTML['dots-' + p.id] = () => {
    const W = { ok: ['Aprovado', '#86efac'], no: ['Recusado', '#fca5a5'], pending: ['Pendente', '#cbd5e1'] };
    const sec = (title, state, color, slots) => `<div class="balloon-sec"><b>${title}</b> · <span style="color:${color}">${state}</span>${slots
      .map(([alias, st, meta, reason]) => `<div class="balloon-row"><span class="dot ${st === 'ok' ? 'ok' : st === 'no' ? 'no' : ''}" style="background:transparent"></span><span><b>${alias}</b> · <span style="color:${W[st][1]}">${W[st][0]}</span></span>${meta ? `<small>${meta}</small>` : ''}${reason ? `<small style="font-style:italic">“${reason}”</small>` : ''}</div>`)
      .join('')}</div>`;
    if (p.id === 187)
      return sec('1ª aprovação', 'Em andamento', '#67e8f9', [['Risco', 'ok', 'Carla Menezes · 07/10/2026 14:12'], ['Compliance', 'no', 'Diego Prado · 08/10/2026 09:40', 'Falta o parecer jurídico do ativo.'], ['Jurídico', 'pending']]) + sec('2ª aprovação', 'Não iniciada', '#94a3b8', []);
    if (p.id === 186) return sec('1ª aprovação', 'Aprovada', '#86efac', [['Risco', 'ok', 'Carla Menezes · 04/10/2026 10:02']]) + sec('2ª aprovação', 'Em andamento', '#67e8f9', [['Comitê', 'ok', 'Diretoria · 06/10/2026 17:30'], ['Gestão', 'pending']]);
    return sec('1ª aprovação', 'Aprovada', '#86efac', []) + sec('2ª aprovação', 'Aprovada', '#86efac', []);
  };
});
function track(step, { approvals = false, rejected = false } = {}) {
  const items = STEPS.map((s, i) => {
    const st = i < step ? 'done' : i === step ? (rejected ? 'refused' : step >= 6 ? 'done' : 'now') : '';
    return `<li class="${st}"><span class="bubble">${st === 'done' ? ic('check') : st === 'refused' ? ic('x') : i + 1}</span><span class="lbl2">${s}</span></li>`;
  }).join('');
  const cap = step >= 6 ? 'Todas as etapas concluídas' : `Etapa ${step + 1} de 6 · ${STEPS[step]}`;
  return `<div class="track ${rejected ? 'rejected' : ''}"><ol>${items}</ol><div class="foot"><span>${cap}</span>${approvals ? `<span class="row" style="gap:6px"><b style="color:var(--text-secondary)">1 de 3 aprovaram</b><span class="perm ok">${ic('check-circle')}Risco</span><span class="perm">${ic('circle')}Compliance</span><span class="perm">${ic('circle')}Jurídico</span></span>` : ''}</div></div>`;
}
function ptPreview(p) {
  const total = p.vol;
  const parts = p.fundos.map((f, i) => [f, i === 0 ? total * 0.62 : total * (0.38 / (p.fundos.length - 1 || 1))]);
  return `<div class="xin">
    <div style="padding:18px 24px 16px;border-bottom:1px solid var(--line)">${track(p.step)}</div>
    <div class="grid-3" style="gap:0">
      <section style="padding:20px 24px;display:grid;gap:14px"><b style="color:var(--text-ink)">Operação</b><dl class="facts" style="grid-template-columns:repeat(auto-fill,minmax(150px,1fr))">
        ${[['arrows-up-down', 'Compra / Venda', 'Compra'], ['store', 'Mercado', 'Secundário'], ['percent', 'Taxa', 'CDI + 3,20%'], ['handshake', 'Contraparte', 'Banco Alfa S.A.']].map(([i, l, val]) => `<div class="fact"><span class="ci" style="width:32px;height:32px">${ic(i)}</span><div style="min-width:0"><dt>${l}</dt><dd>${val}</dd></div></div>`).join('')}</dl></section>
      <section style="padding:20px 24px;display:grid;gap:12px;border-left:1px solid var(--line)"><div class="row" style="justify-content:space-between"><b style="color:var(--text-ink)">Volumes por fundo</b><b class="tnum" style="color:var(--brand-ink)">${brl(total)}</b></div>
        ${parts.map(([f, val]) => `<div><div class="row" style="justify-content:space-between;font-size:.82rem"><span class="ellipsis" style="max-width:60%" data-tip-trunc="${f}">${f}</span><b class="tnum">${brl(val)}</b></div><div class="bar" style="margin-top:6px"><span style="width:${(val / total) * 100}%"></span></div></div>`).join('')}</section>
      <section style="padding:20px 24px;display:grid;gap:12px;border-left:1px solid var(--line)"><b style="color:var(--text-ink)">Etapas</b>
        <div><div class="row" style="justify-content:space-between"><b style="font-size:.82rem">1ª aprovação</b>${soft('Em andamento', 'progress')}</div>
          ${[['check-circle', 'Risco', 'Aprovado', '--success'], ['x-circle', 'Compliance', 'Recusado', '--danger'], ['clock', 'Jurídico', 'Pendente', '--text-muted']].map(([i, g, s, c]) => `<div class="row" style="margin-top:8px;font-size:.82rem"><span style="color:var(${c})">${ic(i)}</span><b>${g}</b><span style="color:var(${c})">${s}</span></div>`).join('')}</div></section>
    </div>
    <div style="display:flex;justify-content:flex-end;padding:10px 20px;border-top:1px solid var(--line)"><a href="#" class="link-pill" data-go="ptdetalhe">Ver detalhes completos${ic('arrow-right')}</a></div>
  </div>`;
}
function screenPreTrade() {
  const kpis = loading()
    ? [1, 2, 3, 4].map(kpiSkeleton).join('')
    : kpi('Itens criados', '27', 'list-check', 'neutral') + kpi('Operações em andamento', '9', 'hourglass', 'progress') + kpi('Operações aprovadas', '15', 'check-circle', 'success') + kpi('Operações reprovadas', '3', 'x-circle', 'danger');
  const rows = PT.map((p) =>
    xrow(String(p.id), `<td class="mono">#${p.id}</td><td class="tnum">${p.criado}</td>
      <td>${p.prazo ? `<span class="deadline ${p.prazo[0]}" tabindex="0"${tip('Data limite: ' + p.prazo[3])}>${ic(p.prazo[2])}${p.prazo[1]}</span>` : EMPTY}</td>
      <td><span class="who-cell"><span class="avatar sm">${p.user.split(' ').map((x) => x[0]).join('')}</span>${p.user}</span></td><td>${p.tipo}</td><td><span class="chips">${p.fundos.slice(0, 2).map((f) => `<span class="chip" data-tip-trunc="${f}" style="max-width:150px">${f}</span>`).join('')}${p.fundos.length > 2 ? `<span class="chip"${tip(p.fundos.slice(2).join(', '))}>+${p.fundos.length - 2}</span>` : ''}</span></td>
      <td class="tnum"><span${tip(brl(p.vol))} tabindex="0">${mm(p.vol)}</span></td>
      <td><span style="display:inline-flex;flex-direction:column;align-items:center;gap:4px">${stagePill(p)}${p.you ? `<span class="awaiting"${tip('Esta solicitação espera uma ação sua')}>Aguardando você</span>` : ''}</span></td>
      <td>${dotsHtml(p)}</td>
      <td><span class="acts">${act('eye', 'Ver detalhes')}${p.step === 0 ? act('pencil', 'Editar') + act('send', 'Enviar para aprovação', 'primary') : ''}${p.you && p.step > 0 ? `<button class="act success" aria-label="Aprovar"${tip('Aprovar')} data-dlg="aprovarPT">${ic('check-circle')}</button>${act('x-circle', 'Recusar', 'danger')}${act('undo', 'Devolver')}` : ''}${p.step === 3 ? act('clipboard-check', 'Enviar para conferência', 'primary') : ''}</span></td>`,
      () => ptPreview(p), { group: 'pt' })
  ).join('');
  const table = loading()
    ? `<table class="tbl"><tbody>${Array.from({ length: 4 }, () => `<tr>${['40px', '80px', '110px', '100px', '90px', '150px', '60px', '150px', '80px', '110px'].map((w) => `<td><span style="display:flex;justify-content:center">${sk(w)}</span></td>`).join('')}</tr>`).join('')}</tbody></table>`
    : isEmpty()
      ? emptyState('plus', 'Nenhum pré-trade por aqui ainda', 'Crie a primeira solicitação: ela começa como rascunho e só vai para aprovação quando você enviar.', 'Criar o primeiro Pré-Trade')
      : `<div class="tbl-wrap resp"><table class="tbl"><thead><tr><th class="sort">ID${ic('arrow-down')}</th><th class="sort">Data de criação${ic('arrows-up-down')}</th><th class="sort">Data limite${ic('arrows-up-down')}</th><th>Usuário criador</th><th>Tipo</th><th>Fundo(s)</th><th>Volume (R$)</th><th>Etapa</th><th>Status</th><th>Ações</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="m-list">${PT.map((p) => `<div class="m-item" data-go="ptdetalhe"><div class="top"><div><b>#${p.id} · ${p.tipo}</b><div class="muted" style="font-size:.78rem">${p.user} · ${p.criado}</div></div>${stagePill(p)}</div><dl><dt>Volume</dt><dd>${brl(p.vol)}</dd><dt>Fundos</dt><dd>${p.fundos.length}</dd><dt>Prazo</dt><dd>${p.prazo ? p.prazo[1] : EMPTY}</dd></dl>${p.you ? '<span class="awaiting" style="align-self:flex-start">Aguardando você</span>' : ''}</div>`).join('')}</div>
      ${pager(1, 5, 27)}`;
  return shell(`<div class="stack">
    <div class="kpis">${kpis}</div>
    <div class="card"><div class="card-head"><div><h2>Lista de Pré-Trades</h2><p>Acompanhe as solicitações e as etapas do fluxo de aprovação.</p></div></div>
      <div class="toolbar" style="padding:14px 22px">
        <div class="field"><label>Data de criação</label><div class="input"><span class="val ph">Início – fim</span>${ic('calendar')}</div></div>
        <div class="field"><label>Data limite</label><div class="input"><span class="val ph">Início – fim</span>${ic('calendar')}</div></div>
        <div class="field"><label>Fundo(s)</label><div class="input"><span class="val">FIDC Poliedro Crédito I <span class="more">(+1 Outro)</span></span>${ic('x')}${ic('caret-down')}</div></div>
        <span class="vdiv"></span>
        <div class="field" style="flex:1.6 1 240px"><label>Status</label><div class="input"><span class="val ph">Todos os Status</span>${ic('caret-down')}</div></div>
        <button class="btn sm" style="min-height:40px" data-act="noop" aria-label="Limpar filtros">${ic('filter-x')}Limpar filtros</button>
      </div></div>
    <div class="card" style="overflow:hidden">${table}</div></div>`,
    { title: SCREENS.pretrade, help: 'Gerencie os pré-trades e acompanhe as aprovações necessárias das operações.', actions: `<button class="btn primary sm" data-dlg="novoPT">${ic('plus')}Novo Pré-Trade</button>` });
}
DIALOGS.aprovarPT = () => `<div class="dlg-scrim"><div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t">
  <header>${ic('check-circle')}<h3 id="dlg-t">Aprovar pré-trade #187</h3><button class="x" data-act="close" aria-label="Fechar">${ic('x')}</button></header>
  <p class="sub">Você está aprovando como <b>Jurídico</b> na 1ª aprovação.</p>
  <div class="note">Esta ação atualiza o status para todos os usuários com acesso ao fluxo.</div>
  <footer><button class="btn" data-act="close">Cancelar</button><button class="btn primary" data-act="confirm">${ic('check')}Aprovar</button></footer></div></div>`;
DIALOG_DONE.aprovarPT = () => {
  toast('Pré-trade #187 em "Aguardando 2ª aprovação"');
  flashRow('187', '--success-soft');
};
DIALOGS.novoPT = () => `<div class="dlg-scrim"><div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t" style="width:min(620px,100%)">
  <header>${ic('plus')}<h3 id="dlg-t">Novo Pré-Trade</h3><button class="x" data-act="close" aria-label="Fechar">${ic('x')}</button></header>
  <p class="sub">A solicitação começa como rascunho. Ela só vai para aprovação quando você enviar.</p>
  <div class="form">
    <div class="field"><label>Tipo de operação <span class="req">*</span></label><div class="input focus"><span class="val">Fundos</span>${ic('chevron-down')}</div></div>
    <div class="field"><label>Data limite</label><div class="input"><span class="val">16/10/2026</span>${ic('calendar')}</div></div>
    <div class="field full"><label>Veículo investidor <span class="req">*</span></label><div class="input"><span class="val ph">Buscar no Bluedeck</span>${ic('search')}</div></div>
    <div class="field"><label>Volume (R$) <span class="req">*</span></label><div class="input invalid"><span class="val">0,00</span></div><span class="err">Informe um volume maior que zero.</span></div>
    <div class="field"><label>Taxa</label><div class="input"><span class="val">CDI + 3,20%</span></div></div>
  </div>
  <footer><button class="btn" data-act="close">Cancelar</button><button class="btn primary" data-act="confirm">Salvar rascunho</button></footer></div></div>`;
DIALOG_DONE.novoPT = () => toast('Rascunho #188 criado');

/* ======================= Detalhe do Pré-Trade ======================= */
function screenPtDetalhe() {
  const p = PT[0];
  const hist = [
    ['Hoje', [['tone-danger', 'x-circle', 'Compliance recusou', 'Diego Prado', 'há 3 h', ['Pendente', 'progress'], ['Recusado', 'danger'], 'Falta o parecer jurídico do ativo.'], ['tone-success', 'check-circle', 'Risco aprovou', 'Carla Menezes', 'há 5 h', ['Pendente', 'progress'], ['Aprovado', 'success']]]],
    ['Últimos 7 dias', [['tone-neutral', 'paperclip', 'Anexo adicionado: parecer-risco.pdf', 'Ana Ribeiro', 'há 2 dias'], ['tone-warning', 'arrow-right', 'Enviada para a 1ª aprovação', 'Ana Ribeiro', 'há 4 dias', ['Rascunho', 'neutral'], ['1ª aprovação', 'progress']], ['tone-neutral', 'plus-circle', 'Solicitação criada', 'Ana Ribeiro', 'há 4 dias']]],
  ];
  const tl = hist.map(([g, items]) => `<div class="tl-group">${g}</div><div class="tl">${items.map(([tone, icon, title, by, when, from, to, note]) => `<div class="tl-item"><span class="ti ${tone}">${ic(icon)}</span><div><h5>${title}</h5><div class="by">Por ${by}</div>${from ? `<span class="ft"><span class="pill soft tone-${from[1]}">${from[0]}</span><span class="muted">${ic('arrow-right')}</span><span class="pill soft tone-${to[1]}">${to[0]}</span></span>` : ''}</div><time${tip('08/10/2026 09:40')}>${when}</time>${note ? `<blockquote>${note}</blockquote>` : ''}</div>`).join('')}</div>`).join('');
  const atts = [['pdf', 'parecer-risco.pdf', '238 KB · Ana Ribeiro · há 2 dias', '--danger', '--danger-soft', 'file-pdf'], ['xlsx', 'alocacoes-fundos.xlsx', '64 KB · Ana Ribeiro · há 4 dias', '--success', '--success-soft', 'table']];
  return shell(`<div class="stack" style="gap:20px">
    <div class="card raised card-pad" style="display:grid;gap:20px">
      <div class="row" style="justify-content:space-between;gap:16px 24px"><div class="row" style="gap:10px 12px">
        <span class="pill tone-progress" style="height:28px;padding:0 12px 0 10px">● ${p.stage}</span><span class="awaiting" style="height:28px;padding:0 12px 0 10px;font-size:.8rem">Aguardando você</span>
        <span class="muted" style="font-size:.86rem">Fundos · aberto por <b style="color:var(--text)">${p.user}</b> · <span class="deadline soon"${tip('Data limite: 11/10/2026')} tabindex="0">${ic('clock')}vence amanhã</span></span></div>
        <div class="row"><button class="btn pill" data-act="noop" aria-label="Editar">${ic('pencil')}Editar</button><button class="btn pill danger-out" data-act="noop" aria-label="Recusar">${ic('x-circle')}Recusar</button><button class="btn pill success" data-dlg="aprovarPT">${ic('check-circle')}Aprovar</button></div></div>
      <div style="padding-top:20px;border-top:1px solid var(--line)">${track(1, { approvals: true })}</div></div>
    <div class="grid-2">
      <div class="stack" style="gap:20px">
        <div class="card raised card-pad"><h3 class="card-title" style="margin-bottom:16px">Dados da operação</h3><dl class="facts">
          ${[['shapes', 'Tipo de operação', 'Fundos'], ['arrows-up-down', 'Compra / Venda', 'Compra'], ['store', 'Mercado', 'Secundário'], ['percent', 'Taxa', 'CDI + 3,20%'], ['handshake', 'Contraparte', 'Banco Alfa S.A.'], ['banknote', 'Volume da operação', brl(p.vol)]].map(([i, l, val]) => `<div class="fact"><span class="ci">${ic(i)}</span><div style="min-width:0"><dt>${l}</dt><dd>${val}</dd></div></div>`).join('')}</dl>
          <dl class="facts" style="margin-top:18px;padding-top:18px;border-top:1px solid var(--line)">${[['user', 'Criado por', 'Ana Ribeiro'], ['calendar', 'Criado em', '06/10/2026 10:14'], ['clock', 'Na etapa atual desde', '06/10/2026 16:02']].map(([i, l, val]) => `<div class="fact"><span class="ci grey">${ic(i)}</span><div><dt>${l}</dt><dd>${val}</dd></div></div>`).join('')}</dl></div>
        <div class="card raised card-pad"><h3 class="card-title" style="margin-bottom:14px">Alocações<span class="count-badge">2</span></h3>
          ${p.fundos.map((f, i) => `<div class="subcard"><div class="row" style="justify-content:space-between"><b>${f}</b><b class="tnum" style="color:var(--brand-ink)">${brl(i ? 4750000 : 7750000)}</b></div><dl class="infogrid">${[['Ativo', 'CCB Varejo — lote 14'], ['Liquidação', '15/10/2026'], ['Spread sobre CDI', '3,20%'], ['Movimento', 'Compra'], ['Gestor', 'Poliedro Capital'], ['Administrador', i ? null : 'Genius']].map(([k, val]) => `<div><dt>${k}</dt><dd>${v(val)}</dd></div>`).join('')}</dl></div>`).join('')}</div>
      </div>
      <div class="stack aside" style="gap:20px">
        <div class="card raised card-pad"><h3 class="card-title" style="margin-bottom:6px">Etapas</h3>
          <div style="padding:12px 0;border-bottom:1px solid var(--line)"><div class="row" style="justify-content:space-between"><b style="font-size:.86rem">1ª aprovação</b>${soft('Em andamento', 'progress')}<span class="muted tnum" style="font-size:.76rem">1 de 3</span></div>
            <div class="bar" style="height:6px;margin:10px 0"><span style="width:33%;background:var(--success-strong)"></span></div>
            ${[['Risco', 'Carla Menezes · 07/10 14:12', 'Aprovado', 'success', 'check-circle'], ['Compliance', 'Diego Prado · 08/10 09:40', 'Recusado', 'danger', 'x-circle'], ['Jurídico', 'Aguardando', 'Pendente', 'neutral', 'clock']].map(([g, m, s, t, i]) => `<div class="row" style="justify-content:space-between;padding:6px 0"><div><b style="font-size:.88rem">${g}</b><div class="muted" style="font-size:.76rem">${m}</div></div><span class="pill tone-${t}">${ic(i)}${s}</span></div>`).join('')}</div>
          <div style="padding:12px 0 0"><div class="row" style="justify-content:space-between"><b style="font-size:.86rem;color:var(--text-faint)">2ª aprovação</b>${soft('Não iniciada', 'neutral')}</div></div></div>
        <div class="card raised card-pad"><h3 class="card-title" style="margin-bottom:12px">Documentos e anexos<span class="count-badge">2</span></h3>
          ${atts.map(([ext, nm, meta, c, s, i]) => `<div class="att"><span class="ci" style="background:var(${s});color:var(${c})">${ic(i)}</span><div style="min-width:0;flex:1"><div class="row" style="gap:0;flex-wrap:nowrap"><span class="nm" data-tip-trunc="${nm}">${nm}</span><span class="ext" style="color:var(${c})">${ext}</span></div><div class="meta">${meta}</div></div><button class="toggle" aria-label="Baixar"${tip('Baixar')}>${ic('download')}</button><button class="toggle" aria-label="Remover"${tip('Remover')}>${ic('trash')}</button></div>`).join('')}
          <div class="drop">${ic('cloud-upload')}<span><b>Arraste arquivos para cá</b> ou clique para anexar</span></div></div>
      </div>
    </div>
    <div class="card raised card-pad"><h3 class="card-title">Histórico</h3>${tl}</div></div>`,
    { title: `Pré-Trade #${p.id}`, crumbs: [['Pré-Trade', 'pretrade']] });
}

/* ======================= Formalização ======================= */
function screenForm() {
  const CONDS = [
    { id: 412, nome: 'Residencial Jardim das Flores', cnpj: '12.345.678/0001-90', vgv: 18500000, taxa: 620.5, status: ['Ativo', 'success', 'check-circle'], coob: 'Sim', data: '02/10/2026' },
    { id: 411, nome: 'Condomínio Vila Serena', cnpj: '98.765.432/0001-10', vgv: null, taxa: 455.0, status: ['Pendente', 'warning', 'clock'], coob: 'Não', data: '30/09/2026' },
    { id: 409, nome: 'Edifício Atlântico Business Tower', cnpj: '45.678.901/0001-23', vgv: 9200000, taxa: null, status: ['Inativo', 'neutral', 'minus-circle'], coob: 'Não', data: '21/09/2026' },
  ];
  const rows = CONDS.map((c) => `<tr class="item" data-act="noop" aria-label="Abrir condomínio"><td class="mono">${c.id}</td><td class="l"><span class="ellipsis" style="max-width:220px" data-tip-trunc="${c.nome}">${c.nome}</span></td><td class="mono">${c.cnpj}</td><td class="r tnum">${brl(c.vgv)}</td><td class="r tnum">${brl(c.taxa)}</td><td>${soft(...c.status)}</td><td>${c.coob}</td><td class="tnum">${c.data}</td><td><span class="acts">${act('pencil', 'Editar')}${act('external-link', 'Abrir em nova aba')}</span></td></tr>`).join('');
  return shell(`<div class="stack">
    <div class="kpis">${kpi('Total de condomínios', '128', 'building', 'neutral') + kpi('Pendentes', '14', 'hourglass', 'warning') + kpi('Ativos', '101', 'check-circle', 'success') + kpi('Inativos', '13', 'minus-circle', 'neutral')}</div>
    <div class="card"><div class="card-head"><div><h2>Condomínios</h2><p>Cadastro e acompanhamento da formalização.</p></div></div>
      <div class="toolbar" style="padding:14px 22px"><div class="field"><label>Nome do condomínio</label><div class="input">${ic('search')}<span class="val ph">Buscar por nome</span></div></div><div class="field"><label>CNPJ</label><div class="input"><span class="val ph">00.000.000/0000-00</span></div></div>
        <div class="field" style="flex:0 1 auto"><label>Status</label>${seg('fst', ui.fst || 'todos', [['todos', 'Todos', 'list'], ['pendente', 'Pendente', 'hourglass'], ['ativo', 'Ativo', 'check-circle'], ['inativo', 'Inativo', 'minus-circle']])}</div></div>
      <div class="tbl-wrap resp" style="border-top:1px solid var(--line)"><table class="tbl"><thead><tr><th class="sort">ID${ic('arrow-down')}</th><th class="l">Condomínio</th><th>CNPJ</th><th class="r">VGV</th><th class="r">Taxa condominial</th><th>Status</th><th>Coobrigação</th><th>Cadastro</th><th>Ações</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="m-list">${CONDS.map((c) => `<div class="m-item"><div class="top"><div><b>${c.nome}</b><div class="mono">${c.cnpj}</div></div>${soft(...c.status)}</div><dl><dt>VGV</dt><dd>${brl(c.vgv)}</dd><dt>Taxa condominial</dt><dd>${brl(c.taxa)}</dd><dt>Coobrigação</dt><dd>${c.coob}</dd></dl></div>`).join('')}</div>
      ${pager(1, 3, 128)}</div></div>`,
    { title: SCREENS.formalizacao, help: 'Cadastro e acompanhamento da formalização dos condomínios.', actions: `<button class="btn primary sm" data-dlg="novoCond">${ic('plus')}Novo cadastro</button>` });
}
DIALOGS.novoCond = () => `<div class="dlg-scrim"><div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlg-t">
  <header>${ic('building')}<h3 id="dlg-t">Novo cadastro</h3><button class="x" data-act="close" aria-label="Fechar">${ic('x')}</button></header>
  <p class="sub">Preencha os dados abaixo. Campos com * são obrigatórios.</p>
  <div class="form"><div class="field full"><label>Nome <span class="req">*</span></label><div class="input focus"><span class="val">Residencial Parque das Águas</span></div></div>
    <div class="field"><label>CNPJ <span class="req">*</span></label><div class="input invalid"><span class="val">12.345.678/0001</span></div><span class="err">CNPJ incompleto: faltam 2 dígitos.</span></div>
    <div class="field"><label>Status</label><div class="input"><span class="val">Pendente</span>${ic('chevron-down')}</div></div>
    <div class="field"><label>VGV (R$)</label><div class="input"><span class="val ph">0,00</span></div></div>
    <div class="field"><label>Início da vigência</label><div class="input"><span class="val">01/11/2026</span>${ic('calendar')}</div></div></div>
  <footer><button class="btn" data-act="close">Cancelar</button><button class="btn primary" data-act="confirm">Salvar cadastro</button></footer></div></div>`;
DIALOG_DONE.novoCond = () => toast('Condomínio cadastrado');

/* ======================= Desempenho da Carteira ======================= */
const MONTHS = ['nov/25', 'dez/25', 'jan/26', 'fev/26', 'mar/26', 'abr/26', 'mai/26', 'jun/26', 'jul/26', 'ago/26', 'set/26', 'out/26'];
const SERIES = [
  { name: 'Aquisição', kind: 'bar', axis: 'l', color: 'var(--chart-3)', data: [42, 38, 51, 47, 55, 60, 58, 64, 61, 70, 73, 68], projected: [11] },
  { name: 'Liquidação', kind: 'bar', axis: 'l', color: 'var(--chart-2)', data: [31, 35, 33, 40, 44, 41, 49, 52, 57, 55, 61, 63], projected: [11] },
  { name: 'VP', kind: 'line', axis: 'r', color: 'var(--chart-1)', data: [410, 418, 432, 441, 456, 470, 481, 497, 503, 520, 534, 541], area: true },
  { name: 'PDD', kind: 'line', axis: 'r', color: 'var(--chart-4)', data: [21, 22, 22, 24, 25, 25, 27, 28, 28, 30, 31, 31].map((x) => x * 6), real: [21, 22, 22, 24, 25, 25, 27, 28, 28, 30, 31, 31], dashed: true },
];
function screenPerformance() {
  const hidden = new Set(Object.keys(ui).filter((k) => k.startsWith('hide:') && ui[k]).map((k) => k.slice(5)));
  const legend = `<div class="ch-legend">${SERIES.map((s) => `<button aria-pressed="${!hidden.has(s.name)}" data-tog="hide:${s.name}"${tip(hidden.has(s.name) ? 'Mostrar série' : 'Esconder série')}><i class="${s.dashed ? 'dashed' : ''}" style="${s.dashed ? `color:${s.color}` : `background:${s.color}`}"></i>${s.name}</button>`).join('')}</div>`;
  const per = ui.per || 'mes';
  const donut = CH.donut([
    { name: 'Consignado', value: 41, color: 'var(--chart-1)' },
    { name: 'Crediário', value: 27, color: 'var(--chart-3)' },
    { name: 'Capital de giro', value: 19, color: 'var(--chart-2)' },
    { name: 'Outros', value: 13, color: 'var(--chart-4)' },
  ], { center: '541', sub: 'R$ mi em carteira' });
  const radial = CH.radial([
    { name: 'Poliedro I', pct: 92, color: 'var(--chart-3)' },
    { name: 'Poliedro II', pct: 81, color: 'var(--chart-1)' },
    { name: 'Varejo Sênior', pct: 67, color: 'color-mix(in srgb, var(--chart-1) 70%, var(--surface))' },
    { name: 'Saúde Mezanino', pct: 54, color: 'var(--chart-2)' },
    { name: 'Estratégia FIC', pct: 38, color: 'color-mix(in srgb, var(--chart-1) 30%, var(--surface))' },
  ]);
  const heat = CH.heatmap(['08h', '10h', '12h', '14h', '16h', '18h'], ['Seg', 'Ter', 'Qua', 'Qui', 'Sex'], [
    [12, 18, 25, 22, 9], [30, 42, 51, 38, 20], [22, 35, 61, 44, 18], [28, 47, 72, 55, 31], [18, 29, 40, 36, 52], [6, 9, 12, 10, 24]]);
  const card = (title, sub, body, extra = '') => `<div class="card raised" style="padding:18px 20px;display:grid;gap:12px;align-content:start"><div class="row" style="justify-content:space-between;align-items:flex-start"><div><h3 class="card-title">${title}</h3>${sub ? `<p class="muted" style="margin:2px 0 0;font-size:.8rem">${sub}</p>` : ''}</div>${extra || `<button class="round-btn" aria-label="Abrir"${tip('Abrir em tela cheia')}>${ic('arrow-up-right')}</button>`}</div>${body}</div>`;
  return shell(`<div class="stack">
    <div class="kpis">${loading() ? [1, 2, 3, 4].map(kpiSkeleton).join('') : kpi('VP atual', 'R$ 541 mi', 'line-chart', 'progress') + kpi('PDD atual', 'R$ 31 mi', 'alert-triangle', 'danger') + kpi('Aquisição no mês', 'R$ 68 mi', 'plus', 'neutral') + kpi('Liquidação no mês', 'R$ 63 mi', 'check-circle', 'success')}</div>
    ${card('Aquisição, liquidação, VP e PDD', 'Barras no eixo da esquerda (R$ mi), linhas no da direita. Mês corrente em andamento, hachurado.',
      loading() ? sk('100%', 300, '12px') : `<div class="ch-box" style="position:relative">${CH.combo({ labels: MONTHS, series: SERIES, hidden, highlight: 11, unitL: '', unitR: '' })}<div class="ch-tip"></div></div>${legend}`,
      seg('per', per, [['sem', 'Semana'], ['mes', 'Mês'], ['ano', 'Ano']], { sm: true }))}
    <div class="grid-3">
      ${card('Carteira por produto', 'Participação no VP', `<div class="row" style="flex-wrap:nowrap;gap:18px">${donut}<div class="ch-legend" style="flex-direction:column;gap:8px">${[['Consignado', 41, 'var(--chart-1)'], ['Crediário', 27, 'var(--chart-3)'], ['Capital de giro', 19, 'var(--chart-2)'], ['Outros', 13, 'var(--chart-4)']].map(([n, p, c]) => `<span class="row" style="gap:8px"><i style="width:10px;height:10px;border-radius:3px;background:${c}"></i>${n} <b class="tnum" style="color:var(--text)">${p}%</b></span>`).join('')}</div></div>`)}
      ${card('Conciliação por fundo', 'Pagamentos conciliados no mês', `<div style="display:grid;place-items:center">${radial}</div>`)}
      ${card('Liquidações por horário', 'Média da semana', `${heat}<div class="row" style="justify-content:flex-end;font-size:.72rem;color:var(--text-muted);gap:4px">Menos ${[10, 35, 60, 85].map((k) => `<i style="width:12px;height:12px;border-radius:3px;background:color-mix(in srgb, var(--chart-1) ${k}%, var(--surface))"></i>`).join('')} Mais</div>`)}
    </div>
    ${card('Maiores originadores', 'Volume adquirido no mês (R$ mi)', CH.hbars([{ name: 'Crédito Fácil SCD', value: 22.4 }, { name: 'Varejo Plus', value: 15.1 }, { name: 'AgroCred', value: 11.8 }, { name: 'Saúde Pay', value: 8.2 }, { name: 'Outros', value: 10.5 }], { unit: ' mi' }))}
    </div>`,
    { title: SCREENS.performance, crumbs: [['Controladoria', 'performance']], help: 'Aquisição, liquidação, VP e PDD da carteira nos últimos 12 meses.' });
}
function bindCharts() {
  portal.querySelectorAll('.ch-hit').forEach((hit) => {
    const svg = hit.ownerSVGElement, box = svg.parentElement, tipBox = box.querySelector('.ch-tip'), cursor = svg.querySelector('.ch-cursor');
    const L = +hit.dataset.l, step = +hit.dataset.step, n = +hit.dataset.n, W = +hit.dataset.w;
    const hidden = new Set(Object.keys(ui).filter((k) => k.startsWith('hide:') && ui[k]).map((k) => k.slice(5)));
    hit.addEventListener('pointermove', (e) => {
      const r = svg.getBoundingClientRect();
      const x = ((e.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(n - 1, Math.floor((x - L) / step)));
      const cx = L + step * i + step / 2;
      cursor.setAttribute('x1', cx);
      cursor.setAttribute('x2', cx);
      cursor.setAttribute('visibility', 'visible');
      tipBox.innerHTML = `<b>${MONTHS[i]}${i === n - 1 ? ' · parcial' : ''}</b>` + SERIES.filter((s) => !hidden.has(s.name)).map((s) => `<div><span><i style="background:${s.color}"></i>${s.name}</span><span>R$ ${(s.real || s.data)[i]} mi</span></div>`).join('');
      const hb = box.getBoundingClientRect();
      let left = ((cx / W) * r.width) + (r.left - hb.left) + 14;
      if (left + 180 > hb.width) left -= 200;
      tipBox.style.left = left + 'px';
      tipBox.style.top = Math.max(0, e.clientY - hb.top - 30) + 'px';
      tipBox.classList.add('show');
    });
    hit.addEventListener('pointerleave', () => {
      tipBox.classList.remove('show');
      cursor.setAttribute('visibility', 'hidden');
    });
  });
}

/* ======================= Orquestrador ======================= */
const OR_ST = {
  COMPLETED: ['Sucesso', 'success', 'check-circle'],
  FAILED: ['Falha', 'danger', 'x-circle'],
  PENDING: ['Pendente', 'warning', 'clock'],
  CANCELED: ['Cancelado', 'neutral', 'minus-circle'],
  NOT_STARTED: ['Não iniciado', 'neutral', 'circle'],
  IN_PROGRESS: ['Em andamento', 'info', 'refresh'],
};
const orChip = (s) => soft(...OR_ST[s]);
const JSON_REQ = `{
  <span class="k">"operation_id"</span>: <span class="s">"OP-20261009-88123"</span>,
  <span class="k">"document"</span>: <span class="s">"123.456.789-09"</span>,
  <span class="k">"amount"</span>: <span class="n">48500.00</span>,
  <span class="k">"installments"</span>: <span class="n">36</span>,
  <span class="k">"simulate"</span>: <span class="b">false</span>
}`;
function screenOrq() {
  const view = ui.view || 'flows';
  const st = ui.st || null;
  const counts = { COMPLETED: 184, FAILED: 12, PENDING: 9, CANCELED: 3, NOT_STARTED: 27 };
  const statusChips = Object.entries(counts).map(([k, n]) => `<button class="statchip tone-${OR_ST[k][1]} ${st === k ? 'on' : ''}" data-set="st=${st === k ? '' : k}">${ic(OR_ST[k][2])}${OR_ST[k][0]}<span class="n">${n}</span></button>`).join('');
  const funnel = ['consulta_margem', 'analise_credito', 'formalizacao'].map((sf, i) => {
    const vals = [[120, 8, 4, 1, 2], [52, 3, 4, 2, 15], [12, 1, 1, 0, 10]][i];
    const tot = vals.reduce((a, b) => a + b, 0);
    return `<div class="funnel-row"><div class="row"><span class="pill tonal" style="--c:var(--brand-secondary);padding:3px 6px">${ic('corner-down-right')}</span><b style="text-transform:capitalize">${sf.replace('_', ' ')}</b><span class="muted" style="margin-left:auto;font-size:.8rem">${tot} execuções</span></div>
      <div class="fcards">${Object.keys(counts).map((k, j) => `<div class="fcard ${OR_ST[k][1] === 'info' ? 'neutral' : OR_ST[k][1]}" tabindex="0"${tip(`${OR_ST[k][0]}: ${vals[j]} (${Math.round((vals[j] / tot) * 100)}%)`)}>${ic(OR_ST[k][2])}<strong>${vals[j]}</strong><small>${OR_ST[k][0]}</small></div>`).join('')}</div></div>`;
  }).join('');
  const procs = [['consulta_cpf', 'COMPLETED'], ['consulta_margem_dataprev', 'FAILED'], ['envio_proposta', 'NOT_STARTED']];
  const procCard = (name, s, i, key) => {
    const open = ui.proc === key;
    const tab = ui.rr || 'req';
    const f = fx('proc:' + key, open);
    return `<div class="nest ${f.cls}"${f.attr}><div class="nh" data-set="proc=${open ? '' : key}"><span class="idx">${i + 1}</span>${ic('chevron-right', 'chev')}<b style="font-size:.88rem;text-transform:capitalize">${name.replace(/_/g, ' ')}</b>${orChip(s)}${s === 'FAILED' ? `<span class="pill soft tone-warning"${tip('Substatus')}>${ic('flag')}timeout_dataprev</span>` : ''}<button class="rerun" data-act="noop" aria-label="Re-executar processo"${tip('Re-executar processo')}>${ic('rotate-ccw')}Re-run</button></div>
      ${f.show ? `<div class="nx"><div><div class="nb">${seg('rr', tab, [['req', 'Request', 'arrow-up-right'], ['res', 'Response', 'arrow-down-left']], { sm: true })}
        <div class="overline" style="margin-top:14px">Body</div><div class="code-box${open ? fresh('rr', tab) : ''}"><pre class="json">${tab === 'req' ? JSON_REQ : `{\n  <span class="k">"status"</span>: <span class="n">504</span>,\n  <span class="k">"detail"</span>: <span class="s">"Dataprev não respondeu em 30 s"</span>\n}`}</pre><button class="copy" data-act="noop" aria-label="Copiar">${ic('copy')}Copiar</button></div></div></div></div>` : ''}</div>`;
  };
  const flows = [['9f1c2a7e-41b2-4c55-9a10-7d2e63b8a0f1', 'FAILED', '09/10/2026 14:32:08', 3], ['4b7e0d13-0c8f-4a8e-b1c4-2f6a9d1e7c55', 'COMPLETED', '09/10/2026 13:58:41', 3], ['c2d84e90-6a71-4f0b-8e52-91b3a7f0d4e2', 'PENDING', '09/10/2026 13:12:27', 3]];
  const flowList = flows.map(([id, s, when, n]) => {
    const open = ui.flow === id;
    const f = fx('flow:' + id, open);
    return `<div class="nest ${f.cls}"${f.attr}><div class="nh" data-set="flow=${open ? '' : id}">${ic('chevron-right', 'chev')}<span class="mono" style="color:var(--text)">${id}</span>${orChip(s)}<span class="muted" style="margin-left:auto;font-size:.8rem">Criado em: <span class="mono">${when}</span> · Subflows: <b>${n}</b></span><button class="toggle" data-act="noop" aria-label="Abrir detalhes em nova aba"${tip('Abrir detalhes em nova aba (todos os processos expandidos)')}>${ic('external-link')}</button></div>
      ${f.show ? `<div class="nx"><div><div class="nb" style="display:grid;grid-template-columns:minmax(0,1fr);gap:10px">${['consulta_margem', 'analise_credito'].map((sf, k) => {
        const so = ui.sub === sf;
        const fs = fx('sub:' + id + sf, so);
        return `<div class="nest sub ${fs.cls}"${fs.attr}><div class="nh" data-set="sub=${so ? '' : sf}">${ic('chevron-right', 'chev')}<b style="text-transform:capitalize">${sf.replace('_', ' ')}</b>${orChip(k ? 'NOT_STARTED' : 'FAILED')}<span class="row muted" style="margin-left:auto;font-size:.78rem;gap:10px"><span>3 processos</span><span style="color:var(--success)" class="row">${ic('check-circle')}1</span><span style="color:var(--danger)" class="row">${ic('x-circle')}1</span></span></div>
          ${fs.show ? `<div class="nx"><div><div class="nb"><div class="overline">Processos</div>${procs.map(([p, s2], i) => procCard(p, s2, i, sf + p)).join('')}</div></div></div>` : ''}</div>`;
      }).join('')}</div></div></div>` : ''}</div>`;
  }).join('');
  return shell(`<div class="stack">
    <div class="card toolbar-card"><div class="toolbar">
      <div class="field" style="flex:1 1 220px"><label>Produto</label><div class="input"><span class="val mono" style="color:var(--text)">consignado_privado_v2</span>${ic('chevron-down')}</div></div>
      <div class="field" style="flex:0 0 auto"><label>Visualização</label>${seg('view', view, [['flows', 'Flows', 'list'], ['proc', 'Processos', 'sliders']])}</div>
      <div class="field" style="flex:2 1 420px"><label>Status</label><div class="row" style="gap:6px">${statusChips}</div></div>
      <div class="field"><label>Período</label><div class="input"><span class="val">03/10/2026 – 09/10/2026</span>${ic('calendar')}</div></div>
      ${st ? `<button class="btn ghost sm" data-set="st=">${ic('filter-x')}Limpar filtros</button>` : ''}
    </div></div>
    <div>${funnel}</div>
    <p class="muted" style="margin:0;font-size:.82rem">${view === 'flows' ? '235 flows encontrados' : '702 processos encontrados'}${st ? ' <i>(com filtros aplicados)</i>' : ''}</p>
    <div class="${fresh('view', view).trim()}">${flowList}</div>
    <div class="card">${pager(1, 20, 235)}</div></div>`,
    { title: SCREENS.orquestrador, help: 'Visualização e acompanhamento de flows do orquestrador.' });
}

/* ======================= Onboarding BGT ======================= */
const MON_LABEL = { total: 'Total no período', ok: 'Aceitos e enviados ao BGT', bypass: 'Aprovados (janela vigente)', rej: 'Rejeitados internamente', fail: 'Falha no envio ao BGT', err: 'Erro interno', wait: 'Aguardando resultado', apr: 'Aprovados', rep: 'Reprovados' };
const OB_ST = {
  IN_PROGRESS: ['Aguardando decisão', 'neutral'],
  APPROVED: ['Aprovado', 'success'],
  REJECTED: ['Reprovado', 'danger'],
  NOT_ACCEPTED: ['Rejeitado internamente', 'warning'],
  REQUEST_REJECTED: ['Falha no envio', 'warning'],
  BYPASSED_APPROVAL: ['Aprovado (janela vigente)', 'success'],
};
const OB = [
  ['OP-20261009-88123', 'Maria Aparecida Souza', 'PF consignado', '33.221.110/0001-09', '123.456.789-09', 'APPROVED', 'Autorizado', null],
  ['OP-20261009-88118', 'Comercial Andrade Ltda.', 'PJ', '41.987.654/0001-20', null, 'REJECTED', 'Reprovado', 'Empresa com restrição cadastral ativa na Receita Federal desde 2024'],
  ['OP-20261009-88102', null, 'PF pagador', '33.221.110/0001-09', '987.654.321-00', 'IN_PROGRESS', null, null],
  ['OP-20261008-87990', 'João Pietro Lima', 'PF consignado', '33.221.110/0001-09', '456.123.789-55', 'REQUEST_REJECTED', null, null],
];
function screenOnboarding() {
  const tab = ui.obtab || 'mon';
  const tabs = `<div>${seg('obtab', tab, [['list', 'Onboardings', 'list'], ['mon', 'Monitoramento', 'activity']])}</div>`;
  const quick = (opts, on) => `<div class="qchips">${opts.map((o) => `<button class="${o === on ? 'on' : ''}">${o}</button>`).join('')}</div>`;
  let body;
  if (tab === 'mon') {
    const sel = ui.box || 'total';
    const col = (title, color, icon, total, cards) => `<div class="kcol"><div class="mcol-head" style="--c:${color}">${ic(icon)}${title}<span class="tot tnum">${total}</span></div>${cards.map(([k, label, ico, tone, n]) => kpi(label, n, ico, tone, { on: sel === k, set: `box=${k}` })).join('')}</div>`;
    body = `<div class="card toolbar-card"><div class="toolbar"><div class="field"><label>Período (última atualização)</label><div class="input"><span class="val">09/10/2026</span>${ic('calendar')}</div></div><div class="field" style="flex:0 1 280px;margin-left:auto"><label>Produtos</label><div class="input"><span class="val ph">Todos os produtos</span>${ic('chevron-down')}</div></div></div><div style="margin-top:12px">${quick(['Hoje', 'Ontem', '3 dias', '7 dias', '14 dias', 'Este mês', '30 dias'], 'Hoje')}</div></div>
      <div class="grid-4">
        ${col('Recebidos', '#475569', 'monitor', 312, [['total', 'Total no período', 'monitor', 'neutral', 312]])}
        ${col('Validação interna', '#2563eb', 'clipboard-check', 312, [['ok', 'Aceitos e enviados ao BGT', 'cloud-upload', 'success', 268], ['bypass', 'Aprovados (janela vigente)', 'badge-check', 'success', 9], ['rej', 'Rejeitados internamente', 'ban', 'warning', 21], ['fail', 'Falha no envio ao BGT', 'cloud-off', 'warning', 11], ['err', 'Erro interno', 'alert-circle', 'danger', 3]])}
        ${col('Em andamento no BGT', '#334155', 'hourglass', 41, [['wait', 'Aguardando resultado', 'hourglass', 'neutral', 41]])}
        ${col('Resultado do BGT', '#15803d', 'gavel', 227, [['apr', 'Aprovados', 'thumbs-up', 'success', 198], ['rep', 'Reprovados', 'thumbs-down', 'danger', 29]])}
      </div>
      <div class="card"><div class="card-head"><h2 class="card-title row">${ic('monitor')}Mais recentes — ${MON_LABEL[sel]}</h2><button class="btn primary sm" data-set="obtab=list">Ver listagem completa${ic('arrow-right')}</button></div>
        <div class="tbl-wrap"><table class="tbl nested"><thead><tr><th class="l">OPID</th><th class="l">Cliente</th><th>Tipo</th><th>CNPJ</th><th>Status interno</th><th>Criado</th><th></th></tr></thead><tbody>${OB.map((o) => `<tr class="item"><td class="l mono">${o[0]}</td><td class="l">${o[1] ?? EMPTY}</td><td>${o[2]}</td><td class="mono">${o[2] === 'PJ' ? o[3] : EMPTY}</td><td>${soft(...OB_ST[o[5]])}</td><td class="tnum">09/10/2026, 14:3${OB.indexOf(o)}</td><td><button class="toggle" aria-label="Abrir detalhes"${tip('Abrir detalhes')}>${ic('external-link')}</button></td></tr>`).join('')}</tbody></table></div></div>`;
  } else {
    const sel = ui.sel || {};
    const nSel = Object.values(sel).filter(Boolean).length;
    body = `<div class="card toolbar-card"><div class="toolbar">
        <div class="field"><label>Período (última atualização)</label><div class="input"><span class="val ph">Início – fim</span>${ic('calendar')}</div></div>
        <div class="field"><label>Produto</label><div class="input"><span class="val ph">Todos os produtos</span>${ic('chevron-down')}</div></div>
        <div class="field"><label>Status interno</label><div class="input"><span class="val">Aprovados <span class="more">(+1 Outro)</span></span>${ic('chevron-down')}</div></div>
        <div class="field"><label>Tipo</label><div class="input"><span class="val ph">Todos</span>${ic('chevron-down')}</div></div></div>
        <div class="toolbar" style="margin-top:12px"><div class="field"><label>Buscar por nome</label><div class="input"><span class="val ph">Nome do cliente…</span>${ic('search')}</div></div><div class="field"><label>OPID (busca exata)</label><div class="input"><span class="val ph">Cole o OPID…</span>${ic('hash')}</div></div><button class="btn sm" style="min-height:40px">${ic('filter-x')}Limpar filtros</button></div>
        <div style="margin-top:12px">${quick(['Hoje', '7 dias', '14 dias', 'Este mês', '30 dias'], '7 dias')}</div></div>
      <div class="card" style="overflow:hidden"><div class="tbl-wrap resp"><table class="tbl"><thead><tr><th><span class="cbx ${nSel === OB.length ? 'on' : ''}" role="checkbox" aria-checked="${nSel === OB.length}" aria-label="Selecionar todos" data-act="selAll">${nSel === OB.length ? ic('check') : ''}</span></th><th class="l">OPID</th><th class="l">Cliente</th><th>Tipo</th><th>CNPJ consignante</th><th>CPF</th><th>Status interno</th><th>Status BGT</th><th class="l">Motivo BGT</th><th>Atualizado</th><th>Ações</th></tr></thead><tbody>
        ${OB.map((o, i) => `<tr class="item ${sel[i] ? 'open' : ''}" data-act="noop" aria-label="Abrir onboarding"><td><span class="cbx ${sel[i] ? 'on' : ''}" role="checkbox" aria-checked="${!!sel[i]}" aria-label="Selecionar ${o[1] || o[0]}" data-act="sel" data-i="${i}">${sel[i] ? ic('check') : ''}</span></td><td class="l mono"><span${tip(o[0])}>${o[0]}</span></td><td class="l"><b>${o[1] ?? '<i class="empty-val">—</i>'}</b></td><td>${o[2]}</td><td class="mono">${o[3]}</td><td class="mono">${o[4] ?? EMPTY}</td><td>${soft(...OB_ST[o[5]])}</td><td>${o[6] ? `<span class="pill" style="background:var(--surface-sunken);border-radius:6px;color:var(--text-secondary)">${o[6]}</span>` : EMPTY}</td>
          <td class="l">${o[7] ? `<span class="ellipsis" style="max-width:200px;color:var(--danger);cursor:help" data-tip-trunc="${o[7]}">${o[7]}</span>` : EMPTY}</td><td class="tnum">09/10/2026, 14:3${i}</td><td><button class="act" aria-label="Abrir detalhes"${tip('Abrir detalhes')} data-act="noop">${ic('external-link')}</button></td></tr>`).join('')}
        </tbody></table></div>
        <div class="m-list">${OB.map((o) => `<div class="m-item"><div class="top"><div><b>${o[1] ?? '—'}</b><div class="mono">${o[0]}</div></div>${soft(...OB_ST[o[5]])}</div><dl><dt>Tipo</dt><dd>${o[2]}</dd><dt>CPF</dt><dd>${o[4] ?? '—'}</dd></dl></div>`).join('')}</div>
        ${pager(1, 20, 312)}</div>
      ${nSel ? `<div class="bulkbar"><span>${nSel} selecionado(s)</span><button class="btn primary sm pill" data-act="noop" aria-label="Reprocessar">${ic('refresh')}Reprocessar (${nSel})</button><button class="btn ghost sm" data-set="sel=">Limpar</button></div>` : ''}`;
  }
  return shell(`<div class="stack">${tabs}<div class="stack${fresh('obtab', tab)}">${body}</div></div>`, { title: tab === 'mon' ? 'Monitoramento BGT' : SCREENS.onboarding, help: tab === 'mon' ? 'Funil e totais por status dos onboardings BGT.' : 'Listagem e gestão dos onboardings BGT.' });
}
ACTIONS.sel = (t) => {
  ui.sel = { ...(ui.sel || {}), [t.dataset.i]: !(ui.sel || {})[t.dataset.i] };
  render();
};
ACTIONS.selAll = () => {
  const all = Object.values(ui.sel || {}).filter(Boolean).length === OB.length;
  ui.sel = all ? {} : Object.fromEntries(OB.map((_, i) => [i, true]));
  render();
};

const RENDER = {
  lotes: screenLotes,
  contrato: screenContrato,
  pretrade: screenPreTrade,
  ptdetalhe: screenPtDetalhe,
  formalizacao: screenForm,
  performance: screenPerformance,
  orquestrador: screenOrq,
  onboarding: screenOnboarding,
};
