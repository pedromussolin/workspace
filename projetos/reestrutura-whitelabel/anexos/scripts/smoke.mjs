// Smoke test visual do front sem BFF real: serve o dist e um BFF falso (sessão válida, todas as
// rotas liberadas, dados vazios) e tira prints de cada rota em desktop e celular.
// Uso: node smoke.mjs <dist/browser> <pasta-de-saida> [rota ...]
// NO_SESSION=1 abre sem sessão (tela de login); SCHEME=dark força o esquema escuro; THEME_KEY troca a marca (chave real do tema, ver privado.md); FIXTURES=<arquivo.json> dá dados
// ao BFF falso ({"caminho/da/api": resposta}, sem a barra inicial e sem a query).
// Requer playwright-core e CHROME_BIN apontando para um Chromium.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(process.env.PW_DIR ? path.join(process.env.PW_DIR, 'x.js') : import.meta.url);
const { chromium } = require('playwright-core');

const [dist, out, ...argRoutes] = process.argv.slice(2);
// SCENES='[["nome", "/rota", "texto de um app-toggle a clicar" | null], ...]' tira print da página
// inteira depois do clique, para visões sem URL própria (abas, troca de visão).
const SCENES = process.env.SCENES ? JSON.parse(process.env.SCENES) : null;
const routes = argRoutes.length
  ? argRoutes
  : ['/home', '/pre-trade', '/liquidation-batches', '/report-transfer', '/formalization', '/orchestrator', '/users', '/not-found'];
fs.mkdirSync(out, { recursive: true });

const PATHS = [
  '/poli-chat', '/knowledge-base', '/assignment-batches', '/liquidation-batches', '/formalization',
  '/report-transfer', '/portfolio-performance', '/cerc-reconciliation', '/pdd', '/pre-trade',
  '/cash-consolidation', '/orchestrator', '/orchestrator/product-config', '/users', '/onboarding-bgt/monitoring',
  '/api-docs', '/design-system',
];
const IAM = {
  'iam/status': !process.env.NO_SESSION,
  'iam/navigation': true,
  'iam/paths': PATHS,
  'iam/organization': 'plgn',
  'iam/profile': { name: 'Pessoa de Teste', email: 'teste@exemplo.com' },
};
const FIXTURES = process.env.FIXTURES ? JSON.parse(fs.readFileSync(process.env.FIXTURES, 'utf8')) : {};

const bff = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  const key = url.pathname.replace(/^\//, '');
  res.setHeader('Access-Control-Allow-Origin', 'http://localhost:4300');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Headers', '*');
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'OPTIONS') return res.end();
  res.end(JSON.stringify(key in IAM ? IAM[key] : key in FIXTURES ? FIXTURES[key] : []));
});

const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.mp4': 'video/mp4' };
const web = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p === '/assets/env.js') {
    res.setHeader('Content-Type', 'text/javascript');
    return res.end(`window.__CONFIG__ = { apiUrl: "http://localhost:8765", themeKey: "${process.env.THEME_KEY || 'default'}", authLoginPath: "/auth/login", authCallbackPath: "/auth/callback", production: false };`);
  }
  let f = path.join(dist, p);
  if (!f.startsWith(dist) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(dist, 'index.html');
  res.setHeader('Content-Type', types[path.extname(f)] || 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
});

await new Promise((r) => bff.listen(8765, r));
await new Promise((r) => web.listen(4300, r));

const browser = await chromium.launch({ executablePath: process.env.CHROME_BIN });
const errors = [];
const VIEWPORTS = [['desktop', { width: 1440, height: 900 }], ['celular', { width: 390, height: 844 }]].filter(
  ([label]) => !process.env.ONLY || process.env.ONLY === label
);
for (const [label, viewport] of VIEWPORTS) {
  const page = await browser.newPage({ viewport });
  if (process.env.SCHEME) {
    // A mesma chave que o ColorSchemeService grava; o script do index.html aplica antes do Angular subir.
    await page.addInitScript((scheme) => localStorage.setItem('portal.color-scheme', scheme), process.env.SCHEME);
  }
  page.on('pageerror', (e) => errors.push(`${label} ${page.url()}: ${e.message}`));
  // O Angular entrega os erros de template ao ErrorHandler, que só escreve no console.
  page.on('console', (m) => m.type() === 'error' && errors.push(`${label} ${page.url()} [console]: ${m.text().slice(0, 300)}`));
  for (const [name, route, toggle] of SCENES ?? []) {
    await page.goto(`http://localhost:4300${route}`, { waitUntil: 'load', timeout: 20000 });
    await page.waitForTimeout(1500);
    if (toggle) {
      await page.locator('app-toggle', { hasText: toggle }).first().click();
      await page.waitForTimeout(1000);
    }
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (wide > 0) errors.push(`${label} ${name}: página ${wide} px mais larga que a tela (rolagem lateral)`);
    await page.screenshot({ path: path.join(out, `${label}_${name}.png`), fullPage: true });
    console.log(`${label} ${name} ok`);
  }
  for (const route of SCENES ? [] : routes) {
    const ok = await page.goto(`http://localhost:4300${route}`, { waitUntil: 'load', timeout: 20000 }).then(() => true, () => false);
    if (!ok) { console.log(`${label} ${route} -> TIMEOUT ao carregar`); continue; }
    await page.waitForTimeout(1500);
    const name = `${label}${route.replace(/\//g, '_')}.png`;
    const shot = await page.screenshot({ path: path.join(out, name), timeout: 15000 }).then(() => true, () => false);
    if (!shot) { console.log(`${label} ${route} -> TIMEOUT no print (página travada)`); continue; }
    const shell = await page.locator('app-shell').count();
    const wide = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (wide > 0) errors.push(`${label} ${route}: página ${wide} px mais larga que a tela (rolagem lateral)`);
    const header = await page.locator('app-page-header h1').first().textContent().catch(() => null);
    console.log(`${label} ${route} -> ${page.url().replace('http://localhost:4300', '')} | shell=${shell} | título=${header?.trim() ?? '-'}`);
  }
  // Navegação interna (popstate, como o botão voltar): o shell tem que continuar o mesmo elemento.
  await page.goto('http://localhost:4300/pre-trade', { waitUntil: 'load' });
  await page.waitForSelector('app-page-header h1, app-layout h1', { timeout: 10000 }).catch(() => undefined);
  const sameShell = await page.evaluate(async () => {
    const before = document.querySelector('app-shell');
    history.pushState({}, '', '/liquidation-batches');
    dispatchEvent(new PopStateEvent('popstate', { state: {} }));
    await new Promise((r) => setTimeout(r, 800));
    const title = document.querySelector('app-page-header h1')?.textContent?.trim();
    return { same: before === document.querySelector('app-shell'), title };
  });
  console.log(`${label} navegação interna /pre-trade -> /liquidation-batches | mesmo shell=${sameShell.same} | título=${sameShell.title}`);
  await page.close();
}
console.log(errors.length ? 'ERROS NO CONSOLE:\n' + errors.join('\n') : 'sem erros de página');
await browser.close();
bff.close();
web.close();
