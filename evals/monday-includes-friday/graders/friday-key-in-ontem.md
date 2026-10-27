---
type: regex
pattern: 'Ontem[\s\S]*?TS-106[\s\S]*?Hoje'
---

"Today" in the fixture is Monday 2026-10-26, so Friday's commit "TS-106 ajusta o contraste do
botão" is in the window. TS-106 has no card in the Jira mock and no PR, so the key can only come
from that commit, and it must sit between the Ontem and the Hoje headings. The case asks for the
detailed daily, so `--top` cuts nothing and TS-106 cannot fall into "E mais N tarefas".
