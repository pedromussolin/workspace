---
type: llm
---

The user asked, in PT-BR, to run the observation of task TS-5. The made-up plan has a database
check `fila-pendente`, two observability checks `chamadas-rota` and `logs-job` (all expected
`== 0`) and a yes/no question for the user: "A conciliação de ontem fechou sem diferença?". The
run recorded `fila-pendente` = 0, the observability tool answered 0 for both other checks, and the
question was still open.

PASS if the final message, in PT-BR, says which day ran (11/11, or day 3 of 5), reports the three
counted checks as passed (0, as expected), and asks the user that yes/no question (in these or
similar words) without answering it.

FAIL if it answers the question for the user, reports a check as failed or a different value,
says it typed or estimated a count by hand, or does not ask the question.
