"""`ws release preview publish` and `ws release publish`: pushes the branches and opens the PRs.

Each command first fetches the repos it publishes; `build_plan` then only reads (git refs and `gh`
lists). The preview stores the plan under a code and `publish --approve CODE` rebuilds it, checks
it is the same plan and sends it through `ws.release.plan`, the one place that writes to GitHub.
"""

import argparse
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from ws.release import folder as release_folder
from ws.release import gitops, plan, rules, status, text
from ws.release import run as run_release
from ws.release.build import load_published
from ws.release.github import Gh, PullRequest
from ws.release.plan import Call, WritePlan
from ws.release.settings import ReleaseConfig, RepoEntry

SANDBOX_PARAGRAPH = "Leva este código para a sandbox, para validar antes da master."


@dataclass
class _Create:
    """A PR to open, before its text is rendered."""

    entry: RepoEntry
    state: rules.RepoState
    kind: str
    ref: str
    head: str
    base: str
    draft: release_folder.PrDraft
    paragraphs: tuple[str, ...] = ()


def _local(branch: str) -> str:
    return f"refs/heads/{branch}"


def _origin(branch: str) -> str:
    return f"refs/remotes/{gitops.REMOTE}/{branch}"


def _known(entry: RepoEntry, pr: PullRequest) -> list:
    return plan.known_entry(entry.slug, pr.number, pr.url)


def _latest(prs: list[PullRequest]) -> PullRequest | None:
    return max(prs, key=lambda pr: pr.number) if prs else None


def _selected(
    config: ReleaseConfig, folder: Path, repos: list[str]
) -> tuple[release_folder.ReleaseFile, list[str]]:
    """The release file and the repos this run publishes, in config order. A `--repo` outside
    `release.toml` means the run cannot be evaluated (exit 2)."""
    wanted = plan.read_release(folder, tuple(entry.name for entry in config.repos))
    return wanted, release_folder.select_repos(config, wanted, repos)


def _others_known(
    config: ReleaseConfig,
    wanted: release_folder.ReleaseFile,
    selected: list[str],
    day: date,
    gh: Gh,
    known: dict,
) -> None:
    """The PRs already open (or the merged code PR) of the release's repos outside `--repo`, so a
    draft can cite them. Reads only: nothing is planned for those repos."""
    for entry in config.repos:
        includes = wanted.include.get(entry.name, ())
        if entry.name not in wanted.repos or entry.name in selected or not includes:
            continue
        code_branch = _code_branch(includes, day)
        code_prs = gh.prs(entry.slug, head=code_branch, base=config.base_branch)
        code = _latest([pr for pr in code_prs if pr.state == "OPEN"]) or _latest(
            [pr for pr in code_prs if pr.merged_at]
        )
        if code:
            known[entry.name] = _known(entry, code)
        sandbox = _latest(
            [
                pr
                for head in (f"{code_branch}-sdbx", code_branch)
                for pr in gh.prs(entry.slug, head=head, base=config.sandbox_branch)
                if pr.state == "OPEN"
            ]
        )
        if sandbox:
            known[f"{entry.name}-sandbox"] = _known(entry, sandbox)


def _push(entry: RepoEntry, branch: str, note: str, problems: list[str]) -> Call | None:
    """The push of `branch` when origin lacks it or is behind; a problem when not a fast-forward."""
    repo = entry.path
    local, remote = gitops.rev(repo, _local(branch)), gitops.rev(repo, _origin(branch))
    if local is None or local == remote:
        return None
    if remote is not None and not gitops.is_ancestor(repo, remote, local):
        problems.append(
            f"{entry.name}: origin/{branch} is not an ancestor of {branch}; "
            "the push would not be a fast-forward, and nothing here forces it"
        )
        return None
    return Call(
        repo=entry.name,
        program="git",
        args=("push", "-u", "origin", branch),
        line=f"{entry.name}: enviar {branch} para o GitHub{note}",
        cwd=str(repo),
    )


def _head_ref(repo: Path, branch: str) -> str | None:
    for ref in (_local(branch), _origin(branch)):
        if gitops.rev(repo, ref):
            return ref
    return None


def _code_branch(includes: tuple[str, ...], day: date) -> str:
    return includes[0] if len(includes) == 1 else f"release/{text.compact(day)}"


def _sandbox_draft(
    name: str, drafts: dict, merged: int, problems: list[str]
) -> tuple[release_folder.PrDraft | None, bool]:
    """The draft of the next sandbox PR and whether it is the code draft's fallback."""
    key = "sandbox" if merged == 0 else f"sandbox-{merged + 1}"
    if key in drafts:
        return drafts[key], False
    if key != "sandbox":
        problems.append(
            f"{name}: pr/{name}-{key}.md not found for the sandbox PR number {merged + 1}"
        )
        return None, False
    if "code" not in drafts:
        problems.append(f"{name}: pr/{name}.md not found")
        return None, False
    code = drafts["code"]
    return replace(code, title=code.title + rules.SANDBOX_SUFFIX), True


def _repo_items(
    config: ReleaseConfig,
    entry: RepoEntry,
    includes: tuple[str, ...],
    day: date,
    folder: Path,
    gh: Gh,
    plan_: dict,
) -> list[Call | _Create]:
    name, repo = entry.name, entry.path
    code_branch = _code_branch(includes, day)
    shape = "single" if len(includes) == 1 else "multi"
    plan_["repos"][name] = {"shape": shape, "code_branch": code_branch}
    code_prs = gh.prs(entry.slug, head=code_branch, base=config.base_branch)
    merged = [pr for pr in code_prs if pr.merged_at]
    if merged:
        plan_["skipped"].append(name)
        plan_["known"][name] = _known(entry, max(merged, key=lambda pr: pr.number))
        return []
    state = rules.assess(config, entry, includes, day, folder)
    if not state.ready:
        plan_["problems"] += state.problems or [f"{name}: {code_branch} does not exist"]
        return []
    plan_["repos"][name]["sandbox_branch"] = state.sandbox_head
    drafts = release_folder.pr_drafts(folder, name)
    open_code = [pr for pr in code_prs if pr.state == "OPEN"]
    items: list[Call | _Create] = []
    note = " (já aberta, só o push)" if open_code else ""
    heads = dict.fromkeys((code_branch, state.sandbox_head))
    for branch in heads:
        plan_["tips"].setdefault(name, {})[branch] = gitops.rev(repo, _local(branch)) or ""
        push = _push(entry, branch, note if branch == code_branch else "", plan_["problems"])
        if push:
            items.append(push)
    if open_code:
        latest = max(open_code, key=lambda pr: pr.number)
        plan_["known"][name] = _known(entry, latest)
        plan_["open"].append((entry, latest.number))
    elif "code" not in drafts:
        plan_["problems"].append(f"{name}: pr/{name}.md not found")
    else:
        items.append(
            _Create(entry, state, "code", name, code_branch, config.base_branch, drafts["code"])
        )
    sandbox_prs = gh.prs(entry.slug, head=state.sandbox_head, base=config.sandbox_branch)
    open_sandbox = [pr for pr in sandbox_prs if pr.state == "OPEN"]
    head_ref = _head_ref(repo, state.sandbox_head)
    if open_sandbox:
        latest = max(open_sandbox, key=lambda pr: pr.number)
        plan_["known"][f"{name}-sandbox"] = _known(entry, latest)
        plan_["open"].append((entry, latest.number))
    elif head_ref and gitops.count(repo, f"{_origin(config.sandbox_branch)}..{head_ref}") > 0:
        done = sum(1 for pr in sandbox_prs if pr.merged_at)
        draft, fallback = _sandbox_draft(name, drafts, done, plan_["problems"])
        if draft:
            paragraphs: tuple[str, ...] = (SANDBOX_PARAGRAPH,) if fallback else ()
            if fallback and state.sdbx and state.sandbox_head == state.sdbx:
                files = ", ".join(state.sdbx_differs)
                paragraphs += (
                    f"A {state.sdbx} tem a sandbox mesclada; difere do código só em: {files}.",
                )
            items.append(
                _Create(
                    entry,
                    state,
                    "sandbox",
                    f"{name}-sandbox",
                    state.sandbox_head,
                    config.sandbox_branch,
                    draft,
                    paragraphs,
                )
            )
    return items


def _render(config: ReleaseConfig, create: _Create, day: date, known: dict) -> str:
    rendered = release_folder.render(
        create.draft.body,
        tasks=create.draft.tasks,
        template=config.card_url_template,
        day=day,
        known=known,
    )
    parts = []
    if create.state.shape == "single":
        parts.append(release_folder.release_line(day))
    parts += create.paragraphs
    return "\n\n".join([*parts, rendered]) if parts else rendered


def _create_call(config: ReleaseConfig, create: _Create, body: str) -> Call:
    entry, draft = create.entry, create.draft
    args = (
        ("pr", "create", "-R", entry.slug, "--base", create.base, "--head", create.head)
        + ("--title", draft.title)
        + tuple(arg for label in draft.labels for arg in ("--label", label))
        + tuple(arg for who in draft.assignees for arg in ("--assignee", who))
    )
    if create.kind == "code":
        line = f"{entry.name}: abrir a PR de código ({create.head} para {create.base})"
    else:
        line = f"{entry.name}: abrir a PR da sandbox ({create.head} para {create.base})"
    return Call(repo=entry.name, program="gh", args=args, line=line, body=body, answers=create.ref)


def _completions(
    state: dict, refs: set[str], known: dict, gh: Gh, warnings: list[str]
) -> list[Call]:
    """An edit for each open PR whose body still names a PR that is known by now; a warning for a
    placeholder this publish cannot fill (a move stopped halfway leaves `{pr:repo-N}`)."""
    edits = []
    for entry, number in state["open"]:
        body = gh.pr(entry.slug, number).body
        stray = [ref for ref in release_folder.pending_refs(body) if ref not in refs]
        if stray:
            warnings.append(
                f"{entry.name}: PR #{number} cites {', '.join(stray)}, which this publish cannot "
                "fill; if a move left it, run the move again"
            )
        line = f"segunda passada: {entry.name}: completar as referências da PR #{number}"
        edit = plan.refresh_edit(entry.name, entry.slug, number, body, body, known, refs, line)
        if edit:
            edits.append(edit)
    return edits


def build_plan(
    config: ReleaseConfig,
    slug: str,
    day: date,
    repos: list[str],
    gh: Gh,
    warnings: list[str] | None = None,
    loaded: dict | None = None,
) -> WritePlan:
    """Reads the release (the fetch is the caller's); notes go to `warnings`, `published.json` to
    `loaded`."""
    folder = release_folder.release_dir(slug, day)
    wanted, selected = _selected(config, folder, repos)
    published = load_published(folder)
    if loaded is not None:
        loaded.clear()
        loaded.update(published)
    state: dict = {"known": {}, "skipped": [], "repos": {}, "problems": [], "tips": {}, "open": []}
    items: list[Call | _Create] = []
    for name in selected:
        entry = config.entry(name)
        items += _repo_items(config, entry, wanted.include[name], day, folder, gh, state)
    _others_known(config, wanted, selected, day, gh, state["known"])
    creates = [item for item in items if isinstance(item, _Create)]
    refs = set(state["known"]) | {create.ref for create in creates}
    slugs = {entry.name: entry.slug for entry in config.repos}
    known = {ref: tuple(value) for ref, value in state["known"].items()}
    calls: list[Call] = []
    drafts: dict[str, dict] = {}
    for item in items:
        if isinstance(item, Call):
            calls.append(item)
            continue
        body = _render(config, item, day, known)
        state["problems"] += rules.pr_text_problems(
            item.state, item.kind, item.draft, body, day, config.card_url_template, refs, slugs
        )
        calls.append(_create_call(config, item, body))
        path = f"pr/{item.draft.path.name}"
        drafts[path] = {"path": path, "sha256": item.draft.sha256}
    calls += plan.second_pass(calls)
    calls += _completions(state, refs, known, gh, warnings if warnings is not None else [])
    facts = {
        "known": state["known"],
        "skipped": state["skipped"],
        "repos": state["repos"],
    }
    return WritePlan(
        action="publish",
        slug=slug,
        days=(text.compact(day),),
        tips=state["tips"],
        calls=calls,
        drafts=[drafts[path] for path in sorted(drafts)],
        facts=facts,
        problems=list(dict.fromkeys(state["problems"])),
    )


@dataclass
class _Context:
    config: ReleaseConfig
    slug: str
    day: date
    names: list[str]
    gh: Gh
    fetched: list[str]
    warnings: list[str] = field(default_factory=list)
    loaded: dict = field(default_factory=dict)
    built: WritePlan | None = None

    def build(self) -> WritePlan:
        self.warnings[:] = self.fetched
        self.built = build_plan(
            self.config, self.slug, self.day, self.names, self.gh, self.warnings, self.loaded
        )
        return self.built


def _context(args: argparse.Namespace) -> _Context:
    day = text.day_argument(args.day)
    repos = list(args.repos)

    def fetched(config: ReleaseConfig, slug: str) -> list[str]:
        return _selected(config, release_folder.release_dir(slug, day), repos)[1]

    config, gh, slug, warnings = plan.session(args.project, fetched)
    return _Context(config, slug, day, repos, gh, warnings, list(warnings))


def run_preview(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        context = _context(args)
        next_command = f"ws release publish {text.compact(context.day)} --project {context.slug}"
        if args.repos:
            next_command += f" --repo {' '.join(args.repos)}"
        with plan.warnings_on_refusal(context.warnings):
            payload, code = plan.show_preview(context.build(), next_command, context.config)
        payload["warnings"] = context.warnings
        return payload, code

    return run_release("preview publish", action)


def _record(folder: Path, built: WritePlan, data: dict, known: dict) -> None:
    repos = data.get("repos") if isinstance(data.get("repos"), dict) else {}
    for name, facts in built.facts["repos"].items():
        row = repos.setdefault(name, {})
        row["shape"], row["code_branch"] = facts["shape"], facts["code_branch"]
        if "sandbox_branch" in facts:
            row["sandbox_branch"] = facts["sandbox_branch"]
        for key, ref in (("code_pr", name), ("sandbox_pr", f"{name}-sandbox")):
            if ref in known:
                row[key] = known[ref][2]
    data["repos"] = repos
    plan.write_published(folder, data)


def _save(context: _Context, known: dict) -> None:
    """`published.json` after a send, whole or partial. GitHub already has the PRs, so a failed
    write is a warning and the result is still printed."""
    assert context.built is not None
    folder = release_folder.release_dir(context.slug, context.day)
    try:
        _record(folder, context.built, context.loaded, known)
    except OSError as error:
        context.warnings.append(f"{folder / plan.PUBLISHED} was not written: {error}")


def _finish(context: _Context, result: dict) -> dict:
    built = context.built
    assert built is not None
    known = result["known"]
    _save(context, known)
    found: dict[str, PullRequest] = {}
    rows = []
    for name in built.facts["repos"]:
        row: dict = {"repo": name}
        for key, ref in (("code", name), ("sandbox", f"{name}-sandbox")):
            if ref in known:
                number, url = known[ref][2], known[ref][1]
                found[ref] = PullRequest(number, "OPEN", "", "", "", url, None)
            row[f"{key}_pr"] = known[ref][2] if ref in known else None
            row[f"{key}_url"] = known[ref][1] if ref in known else None
        row["skipped"] = name in built.facts["skipped"]
        rows.append(row)
    return {
        "date": text.compact(context.day),
        "repos": rows,
        "gmud": status.links(context.config, found),
        "warnings": context.warnings,
    }


def run_publish(args: argparse.Namespace) -> int:
    def action() -> tuple[dict, int]:
        context = _context(args)
        with plan.warnings_on_refusal(context.warnings):
            result, code = plan.approve(
                args.approve, "publish", context.build, context.gh, context.config
            )
        if code != 0:
            _save(context, result.pop("known"))
            result["warnings"] = context.warnings
            return result, code
        return _finish(context, result), 0

    return run_release("publish", action)
