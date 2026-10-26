import { ICONS } from './icons.mjs';
import fs from 'node:fs';
const sw = process.argv[3] || '1.75', size = process.argv[4] || 48;
const tiles = ICONS.map(([n,,b]) => `<div class="t"><svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round">${b}</svg><span>${n}</span></div>`).join('');
fs.writeFileSync(process.argv[2], `<html><body style="margin:0;background:#fff;font:11px sans-serif;color:#0F3443"><div style="display:grid;grid-template-columns:repeat(12,110px);gap:6px;padding:10px">${tiles}</div><style>.t{display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 2px;border:1px solid #eee}svg{background:repeating-linear-gradient(0deg,#f4f4f4 0 1px,transparent 1px ${size/24}px)}</style></body></html>`);
