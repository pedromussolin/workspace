# 18 — Segurança do front

- **TS:** a criar · **Branch:** `fix/TS-?-seguranca-front` (da `master`, com
  `--no-track`)
- **Status:** a iniciar
- **Depende de:** nada. Nasce da `master` e entra direto, sem esperar o
  épico. As branches do épico pegam a mudança no próximo rebase.

## Objetivo

Deixar o portal sem falha conhecida nas bibliotecas de produção, com as
proteções do navegador valendo em todas as respostas e a permissão checada
em todas as rotas.

No pitch para a diretoria, entra como parte do plano e aparece só pelo
resultado (D12).

## Escopo

1. **Bibliotecas** ([A17](../achados.md)). Em 15/10, o
   `npm audit --omit=dev` acusava 12 falhas (9 altas e 3 moderadas), todas
   com correção sem versão major:
   - `@angular/*` 20.3.11 → 20.3.34, que corrige 8 das altas. CLI, `cdk` e
     `material` sobem juntos, na mesma linha;
   - `dompurify`, `markdown-it` e `linkify-it`, usados no markdown do chat;
   - `moment`: atualizar agora. Ele sai de vez na 13, com o datepicker
     próprio.
2. **Cabeçalhos do nginx** ([A16](../achados.md)):
   - antes de tudo, confirmar com a infraestrutura o que o gateway já
     envia, inclusive HSTS;
   - repetir os cabeçalhos de segurança em todo `location` que tem
     `add_header` próprio (ex.: um `include` de um arquivo só com eles);
   - conferir com `curl -I` em `/`, `/index.html`, uma rota profunda (ex.:
     `/pre-trade`) e `/assets/env.js`;
   - trocar `X-XSS-Protection: 1; mode=block` por `0`, que é a
     recomendação atual. O filtro antigo dos navegadores foi removido e
     podia ser explorado.
3. **CSP** (lista de origens de onde o navegador pode carregar script,
   estilo, fonte e chamadas):
   - começa como `Content-Security-Policy-Report-Only`, liberando só o
     próprio domínio, o Google Fonts e o BFF;
   - o script do `index.html` que aplica o esquema de cor antes do Angular
     subir é inline: precisa de hash na CSP (ou o `autoCsp` do Angular);
   - os estilos dos componentes pedem `style-src 'unsafe-inline'` ou nonce;
   - depois de um ciclo na sandbox sem violação, vira
     `Content-Security-Policy`.
4. **Permissão em todas as rotas** ([A10](../achados.md)):
   - `/pdd` ganha o `iamGuard`, com o escopo a confirmar com o Pietro;
   - um spec percorre as rotas e falha se uma rota autenticada ficar sem
     guard.
5. **Checagem contínua:**
   - `npm audit --omit=dev --audit-level=moderate` entra no `validar.sh` da
     `.ai/` ([17](17-pasta-ai.md));
   - no pipeline, entra com a infraestrutura (D9, tarefa 16).
6. **Regras na `.ai/fronteiras.md`:**
   - `bypassSecurityTrust*` só com conteúdo estático do próprio código,
     como os ícones (`shared/ui/icon`);
   - HTML vindo de fora passa pelo DOMPurify, como o markdown do chat já
     faz.

## Conflitos esperados

- `package-lock.json` com as áreas e a 13: na hora do rebase, refazer o
  lock a partir do `package.json` resolvido.
- `/pdd`: a 09 move a rota para `features/controllership`. Quem rebasear
  por último leva o guard junto.

## Critérios de aceite

- `npm audit --omit=dev` sem nenhuma falha.
- Build, lint e testes sem falha nova. Smoke das rotas sem erro.
- `curl -I` mostra os cabeçalhos em todas as respostas listadas.
- CSP em report-only sem violação ao navegar por todas as rotas na
  sandbox.
- Sem permissão, `/pdd` leva para `/unauthorized`, como as outras rotas.

## Fora do escopo

Sessão, cookie e CORS do BFF: ficam no apl-credit-whitelabel-api.
