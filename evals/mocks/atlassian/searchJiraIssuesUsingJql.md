---
expect:
  cloudId: 11111111-2222-3333-4444-555555555555
---

{"issues":{"nodes":[
{"expand":"renderedFields,names,schema","id":"10101","key":"TS-101","fields":{"summary":"[FRONT] Corrige a validação do formulário","status":{"name":"In Progress","statusCategory":{"key":"indeterminate"}},"parent":{"key":"TS-100","fields":{"summary":"[FRONT] Épico de exemplo"}},"reporter":{"accountId":"acc-me"},"updated":"2026-10-23T17:30:00.000-0300"},"webUrl":"https://example.atlassian.net/browse/TS-101"},
{"expand":"renderedFields,names,schema","id":"10102","key":"TS-102","fields":{"summary":"[API] Cria a rota de exemplo","status":{"name":"To Do","statusCategory":{"key":"new"}},"parent":{"key":"TS-200","fields":{"summary":"[API] Épico de rotas"}},"reporter":{"accountId":"acc-me"},"updated":"2026-10-19T09:00:00.000-0300"},"webUrl":"https://example.atlassian.net/browse/TS-102"},
{"expand":"renderedFields,names,schema","id":"10103","key":"TS-103","fields":{"summary":"[API] Ajusta a resposta da rota","status":{"name":"In Progress","statusCategory":{"key":"indeterminate"}},"reporter":{"accountId":"acc-other"},"updated":"2026-10-23T18:10:00.000-0300"},"webUrl":"https://example.atlassian.net/browse/TS-103"},
{"expand":"renderedFields,names,schema","id":"10104","key":"TS-104","fields":{"summary":"[API] Revisa o log de exemplo","status":{"name":"In Progress","statusCategory":{"key":"indeterminate"}},"parent":{"key":"TS-200","fields":{"summary":"[API] Épico de rotas"}},"reporter":{"accountId":"acc-me"},"updated":"2026-10-15T14:00:00.000-0300"},"webUrl":"https://example.atlassian.net/browse/TS-104"},
{"expand":"renderedFields,names,schema","id":"10105","key":"TS-105","fields":{"summary":"[API] Publica a documentação de exemplo","status":{"name":"Done","statusCategory":{"key":"done"}},"parent":{"key":"TS-200","fields":{"summary":"[API] Épico de rotas"}},"reporter":{"accountId":"acc-me"},"updated":"2026-10-23T09:00:00.000-0300"},"webUrl":"https://example.atlassian.net/browse/TS-105"}
],"pageInfo":{"hasNextPage":false,"endCursor":null}},"webUrl":"https://example.atlassian.net/issues?jql=assignee%20%3D%20currentUser()"}
