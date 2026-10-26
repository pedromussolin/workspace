import { ICONS } from './icons.mjs';
import fs from 'node:fs';
const used = fs.readFileSync(process.argv[2], 'utf8').trim().split('\n');
const map = new Map(); const names = new Set();
for (const [n,, , rep] of ICONS) { if (names.has(n)) console.log('DUP name', n); names.add(n); for (const m of rep) { if (map.has(m)) console.log('DUP material', m); map.set(m, n); } }
console.log('novos:', names.size, 'material mapeados:', map.size);
console.log('sem mapa:', used.filter(u => !map.has(u)).join(' '));
console.log('mapeados e não usados:', [...map.keys()].filter(m => !used.includes(m)).join(' '));
