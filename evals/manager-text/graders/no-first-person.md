---
type: llm
---

The text is read by a manager as the user's own, so it describes the work, never the person.

PASS if the text has no first person ("fiz", "fizemos", "entreguei", "fechei", "ajustei", "criei",
"corrigi", "publiquei", "revisei", "meu", "minha", "nós") and no second person ("você", "seu").
The note to the user after a "---" line ("Para você: ...") is not part of the text and is not
judged.

FAIL if the text itself uses the first or the second person.
