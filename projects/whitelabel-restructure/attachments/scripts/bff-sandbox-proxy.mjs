// Faz o front local (http://localhost:4200) conversar com o BFF da sandbox sem mudar nada no repo.
//
// O front local chama a API em http://localhost:8000 (padrão do assets/env.js). Este proxy escuta
// nessa porta e repassa tudo para <url-da-sandbox>/api, que é a mesma
// entrada /api que o front da sandbox usa.
//
// Login: o Azure só devolve para o callback da sandbox, então a sessão nasce lá. Entre na sandbox,
// copie o valor do cookie `session_id` e abra http://localhost:8000/__sessao?id=<valor>. O proxy
// grava o cookie em localhost e manda para http://localhost:4200/home.
//
// Uso: TARGET=<url-da-sandbox>/api node bff-sandbox-proxy.mjs   (opcionais: PORT, FRONT)
// A URL real fica no privado.md, fora do repo.
import http from 'node:http';
import https from 'node:https';

const PORT = Number(process.env.PORT || 8000);
if (!process.env.TARGET) {
  console.error('Informe TARGET=<url-da-sandbox>/api (valor no privado.md).');
  process.exit(1);
}
const TARGET = new URL(process.env.TARGET);
const FRONT = process.env.FRONT || 'http://localhost:4200';

function cors(res) {
  res.setHeader('Access-Control-Allow-Origin', FRONT);
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  res.setHeader('Access-Control-Expose-Headers', 'Content-Disposition');
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  if (url.pathname === '/__sessao') {
    const id = url.searchParams.get('id');
    if (!id) {
      res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Informe ?id=<valor do cookie session_id da sandbox>');
    }
    res.writeHead(302, {
      'Set-Cookie': `session_id=${encodeURIComponent(id)}; Path=/; HttpOnly; SameSite=Lax`,
      Location: `${FRONT}/home`,
    });
    return res.end();
  }

  cors(res);
  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    return res.end();
  }

  const headers = { ...req.headers, host: TARGET.host, origin: TARGET.origin };
  delete headers.referer;
  const upstream = https.request(
    {
      protocol: TARGET.protocol,
      hostname: TARGET.hostname,
      port: TARGET.port || 443,
      method: req.method,
      path: TARGET.pathname.replace(/\/$/, '') + url.pathname + url.search,
      headers,
    },
    (up) => {
      const out = { ...up.headers };
      delete out['access-control-allow-origin'];
      delete out['access-control-allow-credentials'];
      if (out['set-cookie']) {
        out['set-cookie'] = out['set-cookie'].map((c) =>
          c.replace(/;\s*Domain=[^;]*/i, '').replace(/;\s*Secure/i, '')
        );
      }
      res.writeHead(up.statusCode || 502, out);
      up.pipe(res);
      console.log(`${req.method} ${url.pathname}${url.search} -> ${up.statusCode}`);
    }
  );
  upstream.on('error', (err) => {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: `Proxy da sandbox: ${err.message}` }));
  });
  req.pipe(upstream);
});

server.listen(PORT, () => {
  console.log(`BFF da sandbox em http://localhost:${PORT} -> ${TARGET.href}`);
  console.log(`Sessão: http://localhost:${PORT}/__sessao?id=<session_id da sandbox>`);
});
