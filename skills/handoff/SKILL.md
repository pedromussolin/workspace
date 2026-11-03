---
name: handoff
description: Writes a handoff for a new chat (a private HANDOFF file with every front of the session, the repos, worktrees and open PRs, then the project's checkpoint and a memory pointer), and resumes a chat from one. Use when the user asks for it ("handoff", "faz a passagem", "passagem de chat", "vou fechar o chat", "vou desligar", "shutdown", "continua do handoff"), or says yes after the model proposed one because the context grew; never on its own.
---

# Handoff

## Overview

A long chat ends in a deliberate handoff at a natural pause: the next chat starts small and keeps
the detail, which auto-compaction would lose. The file is private (outside git, mode 600) and may
hold real names, branch names and paths; it never holds secrets, Parameter Store values or log
dumps. Prose in the file is PT-BR; these instructions are in English.

The `ws handoff` commands do the deterministic part (collect the state of the repos, create the
file from the template, refresh its state block, check it). The model writes the prose and decides
nothing else: never build by hand what a command builds.

The `context_watch` hook warns at 300k tokens of context and then every 100k. When that note
arrives, finish the current step, then **propose** a handoff to the user (one line) and wait for
their yes. Never start it without the user's word and never compact.

## Writing a handoff

1. **Project.** The slug of the project the session works on (`projects/<slug>/`). If it is not
   clear, ask the user. A chat that belongs to no project uses `standalone`.
2. **In-flight work.** List the running agents and ask whether to wait for them or stop them;
   never stop one silently. For each agent note the worktree, the branch, the last commit and
   whether its suite passed. A brief that exists only in the chat is saved to
   `<private folder>/agents/brief-<name>.md` (private folder:
   `~/.local/share/workspace/projects/<slug>/`), so the next chat can relaunch it. Nothing is
   committed, stashed or pushed to save work: the state block shows what is uncommitted.
3. **Create the file.** `ws handoff new <slug> --topic <tema>` (the topic is lowercase words joined
   by hyphens, at most 40 characters; `--date YYYY-MM-DD` only for another day). It prints the
   path, how many repos and PRs it found, and any warnings (read them: a failed `gh` means the PR
   table is empty for a reason). It refuses an existing file; pick another topic.
4. **Write the prose** in the file with Edit, keeping the template's shape:
   - the line under the title: why the chat stopped and how to read the file, in 1 to 3 lines;
   - one `## N. <frente>` section per front of the session, with **Estado** (what is done, what is
     half-done and where: branch, worktree, commit), **Decisões do usuário** (in their words when
     it matters), **Decidido e não feito de propósito** (what was left out and why) and
     **Próximos passos** (concrete actions, numbered);
   - `## Agentes interrompidos` and `## Para o usuário fazer` when there is something; delete a
     section that has nothing, and delete the "apague se não houver" hint;
   - `## Ordem sugerida ao retomar`: the order to continue, starting with "Ler este arquivo
     inteiro".

   Cite files and lines; never paste logs, query output or values. Keep drafts outside `/tmp`
   (it is gone after a WSL shutdown); the check warns about a `/tmp/` path.
5. **Refresh and check.** `ws handoff refresh <file>` when something changed since step 3 (it
   rewrites only the marked state block), then `ws handoff check <file>` until it says
   `"ok": true`. Fix each listed problem; a warning is the user's call, mention it in the reply.
6. **Checkpoint.** For a workspace project with a `CONTINUE.md`, follow the `checkpoint` skill:
   "Onde parei" gets one line that points to the private file by its `~` path, and "Próximo
   passo" the first next step, both masked (`ws mask`), then the skill's check, diff and commit.
   `standalone` has no `CONTINUE.md`: skip this step and say so in the reply. The handoff file
   itself is never copied into the repo.
7. **Memory pointer.** Overwrite `handoff-<slug>.md` in the session's memory folder (what the
   handoff covers, its path, "ler inteiro antes de agir"), with the frontmatter that the memory
   instructions of the session prescribe, and replace that project's line in `MEMORY.md`, for
   example `- [Handoff <slug>](handoff-<slug>.md) — retomar pelo HANDOFF-<data>-<tema>.md`. One
   line per project, replaced in place: the index must not grow with each handoff. This is the one
   write of the skill that is not a script: the memory files belong to the harness.
8. **Reply.** The path, the sentence to open the next chat with ("Continue do handoff <path>"),
   and what is left for the user. Short.

## Resuming from a handoff

A new chat may start with a pointer from the `handoff_pointer` hook (paths and titles only) or
with the user naming the file. When the user's request continues one:

1. Read the file in full.
2. Run `ws handoff refresh <file> --diff`: it writes nothing and prints what changed in the repos,
   worktrees and PRs since the file was written (a branch that moved, a PR merged, a worktree
   gone). Report that to the user before acting; `no changes` means the state is as written.
3. Continue from `## Ordem sugerida ao retomar`.

When the user says a handoff is finished, write `Status: encerrado` on its second line: the hook
stops listing it. If the request does not continue any handoff, ignore the pointer.

## Never

- Commit, push, stash or merge in a company repo to "save" work.
- Stop an agent without asking the user.
- Copy the handoff, or any real name from it, into the repo (the checkpoint text is masked).
- Compact the context.
- Start a handoff without the user's word.
- Put credentials, Parameter Store values or log dumps in the file.
