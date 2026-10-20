// Smoke test visual do front sem BFF real: serve o dist e um BFF falso (sessão válida, todas as
// rotas liberadas, dados vazios) e tira prints de cada rota em desktop e celular.
// Uso: node smoke.mjs <dist/browser> <pasta-de-saida> [rota ...]
// SERVE=1 só serve o portal e o BFF falso, para navegar à mão. NO_SESSION=1 abre sem sessão (tela de login); SCHEME=dark força o esquema escuro; THEME_KEY troca a marca (chave real do tema, ver privado.md); ORG troca a organização (padrão plgn, a interna; outra mostra a visão de parceiro); "Sair" encerra a sessão local (cookie) e "Entrar com Microsoft" volta logado, sem Azure; /__marcas escolhe a marca e a visão (parceiro ou interna) com o portal no ar; FIXTURES=<arquivo.json> dá dados
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
  '/cash-consolidation', '/orchestrator', '/orchestrator/product-config', '/users',
  '/api-docs', '/design-system',
];
// Caminhos com nome real de parceiro ficam fora do repo, em $PRIV/smoke-paths-extra.json (lista de strings).
const PRIV = process.env.PRIV || path.join(process.env.HOME || '', 'repos/.reestrutura_whitelabel');
const EXTRA_PATHS = path.join(PRIV, 'smoke-paths-extra.json');
if (fs.existsSync(EXTRA_PATHS)) PATHS.push(...JSON.parse(fs.readFileSync(EXTRA_PATHS, 'utf8')));
const IAM = {
  'iam/status': !process.env.NO_SESSION,
  'iam/navigation': true,
  'iam/paths': PATHS,
  'iam/profile': { name: 'Pessoa de Teste', email: 'teste@exemplo.com', azureId: '00000000-0000-4000-8000-000000000001' },
};
// Relido quando o arquivo muda: dado novo vale sem reiniciar o portal.
let fixtures = { mtime: 0, data: {} };
const FIXTURES = () => {
  if (!process.env.FIXTURES) return {};
  const mtime = fs.statSync(process.env.FIXTURES).mtimeMs;
  if (mtime !== fixtures.mtime) fixtures = { mtime, data: JSON.parse(fs.readFileSync(process.env.FIXTURES, 'utf8')) };
  return fixtures.data;
};

const bff = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  // Decodificada: o front codifica o `:` das permissões (`roles/all-pre-trade%3Aread/holders`).
  const key = decodeURIComponent(url.pathname).replace(/^\//, '');
  res.setHeader('Access-Control-Allow-Origin', 'http://localhost:4300');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  // Com credenciais, o '*' não vale como curinga: devolve os cabeçalhos e métodos que o preflight pediu.
  res.setHeader('Access-Control-Allow-Headers', req.headers['access-control-request-headers'] || 'content-type');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE');
  res.setHeader('Access-Control-Expose-Headers', 'X-Request-ID');
  res.setHeader('Content-Type', 'application/json');
  if (req.method === 'OPTIONS') return res.end();
  if (key === 'iam/organization') return res.end(JSON.stringify(chosenOrg(req)));
  if (key === 'iam/status') return res.end(JSON.stringify(sessionOn(req)));
  // "Sair" ends the local session (a cookie that both ports see); "Entrar" on the portal brings it back.
  if (key === 'auth/logout') {
    res.setHeader('Set-Cookie', 'portal-sessao=off; Path=/; SameSite=Lax');
    return res.end('null');
  }
  // Like the real BFF: without a session, everything else is 401, and the front goes to /login.
  if (!sessionOn(req)) {
    res.statusCode = 401;
    return res.end(JSON.stringify({ detail: 'Not authenticated' }));
  }
  const data = FIXTURES();
  res.end(JSON.stringify(key in IAM ? IAM[key] : key in data ? peoplePage(paged(data[key], url.searchParams), url.searchParams) : []));
});

// Resposta paginada (`pagination` com `per_page` + `records`): devolve só a página pedida, como o
// BFF real. Sem isso, a tela mostra todos os registros do arquivo, com o tamanho de página dele.
// Pessoas do controle de acesso (`{ people, total, page, perPage }`): busca sem acento, situação,
// ordem e página, como o BFF faz em memória sobre o grupo do portal.
const fold = (text) => (text ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
function peoplePage(body, query) {
  if (!Array.isArray(body?.people) || body.total === undefined || body.source === undefined) return body;
  const search = fold(query.get('search')).trim();
  const status = query.get('status') || 'all';
  const sort = query.get('sort') || 'name';
  const perPage = Number(query.get('perPage')) || body.perPage;
  const page = Math.max(1, Number(query.get('page')) || 1);
  let all = body.people.filter((p) => !search || [p.displayName, p.mail, p.userPrincipalName].some((v) => fold(v).includes(search)));
  if (status === 'with-roles') all = all.filter((p) => p.roleCount > 0);
  if (status === 'without-roles') all = all.filter((p) => p.roleCount === 0);
  if (status === 'without-scope') all = all.filter((p) => p.scopeState && p.scopeState !== 'ok');
  const byName = (a, b) => fold(a.displayName).localeCompare(fold(b.displayName));
  const field = sort.replace(/^-/, '');
  all = [...all].sort((a, b) => (field === 'roles' ? a.roleCount - b.roleCount || byName(a, b) : byName(a, b)) * (sort.startsWith('-') ? -1 : 1));
  return { ...body, people: all.slice((page - 1) * perPage, page * perPage), total: all.length, page, perPage };
}

function paged(body, query) {
  const perPage = Number(query.get('per_page'));
  if (!perPage || !Array.isArray(body?.records) || body.pagination?.per_page === undefined) return body;
  const page = Math.max(1, Number(query.get('page')) || 1);
  const all = body.records;
  const pages = Math.max(1, Math.ceil(all.length / perPage));
  return {
    ...body,
    records: all.slice((page - 1) * perPage, page * perPage),
    pagination: { ...body.pagination, page, per_page: perPage, page_count: pages, total_count: all.length, has_next: page < pages },
  };
}

// Marcas do front servido, lidas do themes.ts da worktree (os nomes reais não ficam neste repo).
// /__marcas lista; /__marca/<chave> grava a escolha num cookie e volta ao portal, sem reiniciar.
const THEMES_TS = path.resolve(dist, '../../../src/app/core/theme/themes.ts');
function brands() {
  if (!fs.existsSync(THEMES_TS)) return [];
  const source = fs.readFileSync(THEMES_TS, 'utf8');
  return [...source.matchAll(/^ {2}(\w+): \{\s*\n\s*name: '([^']+)'/gm)].map(([, key, name]) => ({ key, name }));
}
function cookieValue(req, name) {
  const cookie = (req.headers.cookie || '').split(';').map((c) => c.trim()).find((c) => c.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.slice(name.length + 1)) : '';
}
function chosenBrand(req) {
  const key = cookieValue(req, 'portal-marca');
  return brands().some((b) => b.key === key) ? key : process.env.THEME_KEY || 'default';
}
// A organização decide a home (a interna tem a assistente; a de parceiro, os cartões de boas-vindas),
// como o org_type do token faz em produção. Sem ORG nem escolha, segue a marca: a padrão é a interna.
// Local session: on unless NO_SESSION or after "Sair" (cookie portal-sessao=off).
function sessionOn(req) {
  return !process.env.NO_SESSION && cookieValue(req, 'portal-sessao') !== 'off';
}
function chosenOrg(req) {
  const brand = chosenBrand(req);
  return process.env.ORG || cookieValue(req, 'portal-org') || (brand === 'default' ? 'plgn' : brand);
}

const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.mp4': 'video/mp4' };
const web = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p === '/assets/env.js') {
    res.setHeader('Content-Type', 'text/javascript');
    res.setHeader('Cache-Control', 'no-store');
    return res.end(`window.__CONFIG__ = { apiUrl: "http://localhost:8765", themeKey: "${chosenBrand(req)}", authLoginPath: "/auth/login", authCallbackPath: "/auth/callback", production: false, brandSwitcher: true };`);
  }
  // "Entrar com Microsoft" skips Azure: the session comes back and the portal opens on the home.
  if (p === '/auth/login') {
    res.writeHead(302, { 'Set-Cookie': 'portal-sessao=; Path=/; Max-Age=0', Location: '/home' });
    return res.end();
  }
  const pick = p.match(/^\/__marca\/(\w+)$/);
  if (pick) {
    // ?org=plgn: a marca vista por alguém de dentro. Sem ele, a organização segue a marca.
    const org = new URL(req.url, 'http://x').searchParams.get('org');
    res.writeHead(200, {
      'Set-Cookie': [`portal-marca=${pick[1]}; Path=/; SameSite=Lax`, org ? `portal-org=${org}; Path=/; SameSite=Lax` : 'portal-org=; Path=/; Max-Age=0'],
      'Content-Type': 'text/html; charset=utf-8',
    });
    // A marca escolhida no menu do portal (localStorage) venceria o env.js: sai junto.
    return res.end(`<!doctype html><script>localStorage.removeItem('portal.brand'); location.replace('/');</script>`);
  }
  if (p === '/__marcas' || p === '/__marca') {
    const brand = chosenBrand(req);
    const org = chosenOrg(req);
    const items = brands()
      .map((b) =>
        b.key === 'default'
          ? `<li><a href="/__marca/default">${b.name}</a>${b.key === brand ? ' (atual)' : ''}</li>`
          : `<li><a href="/__marca/${b.key}">${b.name}, visão do parceiro</a>${b.key === brand && org !== 'plgn' ? ' (atual)' : ''}` +
            ` · <a href="/__marca/${b.key}?org=plgn">visão interna</a>${b.key === brand && org === 'plgn' ? ' (atual)' : ''}</li>`
      )
      .join('');
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    return res.end(`<!doctype html><meta charset="utf-8"><title>Marca do portal local</title><body style="font: 15px system-ui; margin: 32px"><h1 style="font-size: 20px">Marca do portal local</h1><ul style="line-height: 2">${items || '<li>themes.ts não encontrado</li>'}</ul><p>A marca muda cores e logo. A organização muda a home: a visão do parceiro mostra os cartões de boas-vindas; a interna, a assistente. A escolha fica em cookies e o portal abre já com ela.</p></body>`);
  }
  let f = path.join(dist, p);
  if (!f.startsWith(dist) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(dist, 'index.html');
  res.setHeader('Content-Type', types[path.extname(f)] || 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
});

await new Promise((r) => bff.listen(8765, r));
await new Promise((r) => web.listen(4300, r));

// SERVE=1: só sobe o portal e o BFF falso, para navegar à mão; sem prints.
if (process.env.SERVE) {
  console.log('Portal em http://localhost:4300 (BFF falso em http://localhost:8765). Ctrl+C para sair.');
  await new Promise(() => {});
}

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
