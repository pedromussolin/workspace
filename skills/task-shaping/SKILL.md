---
name: task-shaping
description: Helps decide a task's nature (card type), size, epic, people and links, splits work that does not fit a sprint, and turns findings made during a task into proposed cards for the next sprint. It writes only item files in the repo, never the tracker. Use when the user plans, scopes or iterates on a task, or when a finding appears in the middle of a task.
---

# Task shaping

## Overview

A task in a workspace project is an item file (`projects/<slug>/tasks/*.md`) with the card's
contract at the top of the file (front matter). Sprints have closed scope: what turns up while
doing a card is a proposal for the next sprint, not more work in the current card. This skill
decides the card's shape and records it in the item. It never writes to the tracker: the tracker's
only writer is `/card`, which the user types. The tracker's name comes from `ws` output, never from
this file. Prose written into items is PT-BR and talks only about the task: no mention of the user,
the AI or the conversation. These instructions are in English.

## Steps

1. **Read.** The item, if there is one (its front matter and heading), the project's
   `project.toml` (the `epics` and the prefixes) and
   `~/.claude/skills/card/references/card-rules.md`. The rules there (place, type, size, links,
   findings, people) are the source of truth; do not restate or bend them here.
2. **Propose**, each point with a one-line reason, in PT-BR:
   - **Type:** the rules' ordered questions, stopping at the first yes (`task`, `bug`, `hotfix`,
     `improvement`, `feature`).
   - **Epic:** one of `project.toml`'s `epics`. If none fits, say so: the item can exist without
     an epic (`ws item check` reports it pending with `"needs": "epic"`) and the epic is set later.
   - **Size:** fits one sprint with one checkable "Pronto quando"? If not, propose the split by
     deliveries that can be validated alone, not by layer.
   - **People:** `assignee` develops, `reporter` writes and follows. Items hold dev ids
     (`dev-` plus 10 hex), never `me`. `ws people me` prints the user's id; for a colleague,
     `ws people add EMAIL [--account ID]` prints the config block to paste (and the id).
   - **Links:** `blocks`, `blocked_by`, `relates`, each to a card ref or to another item's
     relative path (`../<project>/tasks/<file>.md` for another project). One direction per pair.
3. **Wait for the user's yes** on the proposal (or the corrections).
4. **Write**, only item files:
   - New: `ws item new <project> --type T [--epic K] [--assignee DEV] [--reporter DEV]
     --heading "..." --slug <english-slug>`. It prints the repo-relative path. `--epic` is
     optional; `--slug` is the file's English name.
   - Existing: edit only the contract keys of the front matter (`card`, `type`, `epic`,
     `assignee`, `reporter`, `blocks`, `blocked_by`, `relates`, `docs`). Never touch the
     `[tracker]` table (the cache that `ws item sync` owns), never write `me`, and never change
     `card` by hand (`/card` writes it back; `ws item set-card` fixes an uncertain one).
   - The item's prose (heading and body) in PT-BR, only about the task.
5. **Check.** `ws item check <project>` until `problems` is empty (exit 0). Fix the item files; ask
   the user only what only they can settle (which epic, who develops).
6. **Offer `/card`** to create or align the card in the tracker. The user types it; this skill
   never runs `ws card` writes.

## Findings during a task

A finding (a bug, a missing piece, a cleanup) is not extra scope of the current card, unless the
user says to include it. Create a new item for it (steps 2 to 5), mention in the item's text that it
is for the next sprint, and tell the user in one line. If it blocks the current card, link the two
(`blocks`/`blocked_by`) instead of merging them.

## Table

After items change, `ws item table <project>` refreshes the project README's table between its
markers (it refuses when the markers are missing).
