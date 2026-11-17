---
type: regex
pattern: '\bTS-(?!(?:100|101|102|103|104|105|106|107|200)\b)\d+'
match: not_contains
---

Every key in the fixture is TS-100 to TS-107 or TS-200. Any other key was made up.
