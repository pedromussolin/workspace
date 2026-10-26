// Move arquivos/pastas do src/app com `git mv` e reescreve os imports relativos dos .ts.
// Uso: node move.mjs <raiz-do-repo> <moves.json>
// moves.json: [["auth", "core/auth"], ["utils/api-error.ts", "core/http/api-error.ts"], ...]
// (caminhos relativos a src/app). Imports que atravessam core/shared/layouts viram alias
// (@core/..., @shared/..., @layouts/...); os demais continuam relativos.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const [repo, movesFile] = process.argv.slice(2);
const app = path.resolve(repo, 'src/app');
const moves = JSON.parse(fs.readFileSync(movesFile, 'utf8')).map(([a, b]) => [
  path.join(app, a),
  path.join(app, b),
]);
const ALIASED = ['core', 'shared', 'layouts'];

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else out.push(p);
  }
  return out;
}

const before = walk(path.resolve(repo, 'src'));
const newOf = (p) => {
  for (const [a, b] of moves) {
    if (p === a) return b;
    if (p.startsWith(a + path.sep)) return path.join(b, p.slice(a.length + 1));
  }
  return p;
};
const oldOf = new Map(before.map((p) => [newOf(p), p]));

for (const [a, b] of moves) {
  fs.mkdirSync(path.dirname(b), { recursive: true });
  execFileSync('git', ['mv', a, b], { cwd: repo });
}

const exists = new Set(before);
function resolveOld(fromOld, spec) {
  const base = path.resolve(path.dirname(fromOld), spec);
  for (const c of [base + '.ts', base + '.d.ts', path.join(base, 'index.ts'), base]) {
    if (exists.has(c)) return c;
  }
  return null;
}

const topOf = (p) => path.relative(app, p).split(path.sep)[0];

function specifierFor(fromNew, targetNew, origSpec, targetOld) {
  let t = targetNew;
  const usedIndex = targetOld.endsWith(path.sep + 'index.ts') && !origSpec.endsWith('index');
  if (usedIndex) t = path.dirname(t);
  else if (t.endsWith('.d.ts')) t = t.slice(0, -5);
  else if (t.endsWith('.ts')) t = t.slice(0, -3);
  const top = topOf(targetNew);
  if (ALIASED.includes(top) && topOf(fromNew) !== top) {
    return '@' + path.relative(app, t).split(path.sep).join('/');
  }
  let rel = path.relative(path.dirname(fromNew), t).split(path.sep).join('/');
  if (!rel.startsWith('.')) rel = './' + rel;
  return rel;
}

const RE = /(\bfrom\s*|\bimport\s*\(\s*|\bimport\s+)(['"])(\.{1,2}\/[^'"]*)\2/g;
let changed = 0;
for (const fileNew of walk(app).filter((f) => f.endsWith('.ts'))) {
  const fileOld = oldOf.get(fileNew) ?? fileNew;
  const src = fs.readFileSync(fileNew, 'utf8');
  const out = src.replace(RE, (m, lead, q, spec) => {
    const targetOld = resolveOld(fileOld, spec);
    if (!targetOld) return m;
    const targetNew = newOf(targetOld);
    if (targetNew === targetOld && fileNew === fileOld) return m;
    return `${lead}${q}${specifierFor(fileNew, targetNew, spec, targetOld)}${q}`;
  });
  if (out !== src) {
    fs.writeFileSync(fileNew, out);
    changed++;
  }
}
console.log(`movidos: ${moves.length} itens; arquivos .ts reescritos: ${changed}`);
