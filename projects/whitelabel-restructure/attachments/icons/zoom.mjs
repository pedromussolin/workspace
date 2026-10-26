import { ICONS } from './icons.mjs';
import fs from 'node:fs';
const pick = process.argv[3].split(',');
const tiles = ICONS.filter(i => pick.includes(i[0])).map(([n,,b]) => `<div class="t"><svg width="120" height="120" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${b}</svg><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${b}</svg><span>${n}</span></div>`).join('');
fs.writeFileSync(process.argv[2], `<html><body style="margin:0;background:#fff;font:13px sans-serif;color:#0F3443"><div style="display:grid;grid-template-columns:repeat(6,150px);gap:8px;padding:10px">${tiles}</div><style>.t{display:flex;flex-direction:column;align-items:center;gap:6px;padding:8px;border:1px solid #eee}</style></body></html>`);
