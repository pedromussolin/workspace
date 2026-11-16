# Confidentiality

This repo sits on a personal GitHub account.

## What never enters the repo

- Credentials, access tokens, passwords, keys, connection strings, `.env` content ("design token"
  is a different thing and is fine). [hook]
- Internal hosts, URLs, IPs, ports, database or infrastructure user names, Parameter Store paths
  and values (write "replica host", `<sandbox-url>`). [hook]
- End-customer data (tax IDs, names of payers and assignors, contract values) and query dumps.
  [review]
- Build, test and lint logs of the company repos. [review]
- Company source code, patches included: cite `path/file.py:line` instead. Own generic prototypes
  in a project's `attachments/` are fine, with local test credentials only. [review]
- Real names of people, the company, partner brands, customers, administrators and suppliers: use
  the analog, also in file names, anchors, theme keys and cited paths. Numbers and metrics may
  stay. [hook]
- `/home/<user>` paths: always write `~`. [hook]

## Masking

- The table lives in `~/.config/workspace/names.toml`, read only through `ws mask`. Never copy its
  entries into the repo. [review]
- Outside the repo (chat, company repos) real names are used. [review]

## Hooks

Enforcement starts after `ws setup`, which sets `core.hooksPath` (a fresh clone has no hooks) and
makes the hooks executable. The git hooks call `ws check-secrets` (secret patterns, real names,
company domains) and fail closed, also without `names.toml`: `pre-commit` and `pre-merge-commit`
check the staged lines, `commit-msg` the message, `pre-push` every pushed commit (lines, message,
author and committer e-mails). A Claude Code gate (`hooks/block_hook_bypass.py`) blocks
`--no-verify`, `git commit -n` and `core.hooksPath` overrides, in every repo. The check cannot see
names missing from `names.toml` or the content of binary files (a staged binary is reported, not
read).

- When a hook blocks, fix the text or mask it (`ws mask --in-place FILE`); never skip the hook.
  [gate]
- A true false positive goes to `.secrets-allow` (path glob, rule, regex) with a `#` reason above
  it, and the reply says that it was added. The file is read from the index, and an entry excuses
  only the span it matches. [review]

## New words

- A capitalized word that is new to the repo may be a real name with no entry yet. `pre-commit`
  and `commit-msg` warn about it and `pre-push` blocks until it is answered (`ws names pending`
  lists them). [hook]
- Ask the user in the conversation, all pending words in one question with your guess for each
  ("Acme: real name or harmless term?"), then apply the answer: `ws names add REAL --analog
  ANALOG` and mask what carries it, or `ws names known WORD...` and commit `.known-words`.
  [review]
- A word goes to `.known-words` only after the user's answer, and the reply says so. [review]
- Never put the question on GitHub (issue, PR): it would carry the real name. [review]

## Private values

- Hosts, URLs, credentials and the real names behind the analogs live in
  `~/.config/workspace/private/<slug>.md`, one file per project, outside git. [review]
- Read it when a document uses an analog or a placeholder such as "replica host". [review]
- A new sensitive value goes there; the repo gets only the generic reference. [review]
- Never read `~/.config/workspace/credentials`. [gate]
