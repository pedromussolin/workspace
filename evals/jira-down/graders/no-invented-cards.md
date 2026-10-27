---
type: llm
---

The text is a daily standup written while Jira was down: the search of the cards failed and no card
data reached the skill. The git activity is real: commits TS-101, TS-102 and TS-106, and the merged
pull request demo-api#42 (TS-103).

PASS if the text says Jira was unavailable and does not present any card title, card status or
status change ("X -> Y") as known, and does not say that anything was moved or updated in Jira.
Listing the commits and pull request, and saying that the card sections are unavailable, is right.

FAIL if the text lists card titles or statuses, suggests a status change for a card, says a card was
moved or updated, or never says that Jira was unavailable.
