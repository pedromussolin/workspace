from datetime import date

from release_helpers import DAY, LINK_TEMPLATE, REV_BASE, SITE, World

from ws.release import folder, rules
from ws.release.settings import load_release_config

pytest_plugins = ["release_helpers"]

CODE = f"release/{DAY}"
DAY_DATE = date(2026, 11, 20)
ONE, TWO = "feature/TS-101-one", "feature/TS-102-two"
BASE = "origin/master"
REV_B, REV_C = "bbb000000002", "ccc000000003"
SLUGS = {"repo-a": "acme/repo-a", "repo-b": "acme/repo-b"}


def assess(
    world: World, repo: str, includes: tuple[str, ...], envs: tuple[str, ...] = ()
) -> rules.RepoState:
    """`envs` are the environment names in scope; none by default (the code side only)."""
    config = load_release_config()
    scope = tuple(config.environment(name) for name in envs)
    return rules.assess(config, config.entry(repo), includes, DAY_DATE, world.release_dir(), scope)


SANDBOX = ("sandbox",)


def build_release(world: World, subject: str = "chore({key}): junta a {branch}") -> None:
    """`release/DAY` of repo-a from origin/master with ONE and TWO merged, as `new` does."""
    world.branch("repo-a", CODE, BASE, push=False)
    for branch in (ONE, TWO):
        key = branch.split("/")[1][:6]
        world.git(
            "repo-a", "merge", "--no-ff", "-m", subject.format(key=key, branch=branch), branch
        )


def build_sdbx(world: World, *extra: str) -> None:
    world.git("repo-a", "checkout", "-q", CODE)
    world.branch("repo-a", f"{CODE}-sdbx", CODE, push=False)
    world.git(
        "repo-a",
        "merge",
        "--no-ff",
        *extra,
        "-m",
        "chore(TS-101): junta a sandbox",
        "origin/sandbox",
    )


def conflicting_sdbx(world: World) -> None:
    """ONE and sandbox change the same file; `-sdbx` resolves it with ours: the sdbx is used."""
    world.commit("repo-a", ONE, "shared.txt", "one\n", "feat: shared")
    world.commit("repo-a", "sandbox", "shared.txt", "sandbox\n", "chore: shared")
    world.git("repo-a", "fetch", "-q", "origin")
    build_release(world)
    build_sdbx(world, "-X", "ours")


def stack_migrations(world: World) -> None:
    """TWO contains ONE and both add a migration, chained on the base one."""
    world.migration("repo-a", ONE, REV_B, REV_BASE)
    world.git("repo-a", "checkout", "-q", TWO)
    world.git("repo-a", "merge", "-q", "-m", "chore: stack", ONE)
    world.migration("repo-a", TWO, REV_C, REV_B)


def test_r2_release_branch_for_a_single_include_is_refused(world: World):
    world.branch("repo-a", CODE, BASE, push=False)
    state = assess(world, "repo-a", (ONE,))
    assert any(f"{CODE} exists but the repo has one include" in p for p in state.problems)


def test_r2_single_include_uses_its_task_branch_and_is_ready(world: World):
    state = assess(world, "repo-a", (ONE,))
    assert state.shape == "single"
    assert state.code_branch == ONE
    assert state.tip == world.git("repo-a", "rev-parse", ONE)
    assert state.remote
    assert state.ahead == 1 and state.behind == 0
    assert state.problems == []
    assert state.ready
    assert state.as_json()["ready"] is True


def test_r2_release_branch_that_tracks_master_is_refused(world: World):
    build_release(world)
    world.git("repo-a", "branch", "--set-upstream-to=origin/master", CODE)
    state = assess(world, "repo-a", (ONE, TWO))
    assert any(
        f"{CODE} tracks origin/master; branches cut from master are --no-track" in p
        for p in state.problems
    )


def test_r2_release_branch_without_upstream_passes(world: World):
    build_release(world)
    state = assess(world, "repo-a", (ONE, TWO))
    assert state.shape == "multi"
    assert state.code_branch == CODE
    assert state.remote is False
    assert state.problems == []
    assert state.ready


def test_assess_before_the_release_branch_exists_is_not_ready(world: World):
    state = assess(world, "repo-a", (ONE, TWO))
    assert state.tip is None
    assert not state.ready


def test_r3_release_behind_master_names_the_missing_commits(world: World):
    build_release(world)
    world.commit("repo-a", "master", "moved.txt", "m\n", "chore: master moved")
    world.git("repo-a", "fetch", "-q", "origin")
    state = assess(world, "repo-a", (ONE, TWO))
    assert state.behind == 1
    assert "repo-a: master moved, merge it (1 commits of origin/master missing)" in state.problems


def test_r3_release_current_with_master_has_no_problem(world: World):
    build_release(world)
    state = assess(world, "repo-a", (ONE, TWO))
    assert state.behind == 0
    assert not any("master moved" in p for p in state.problems)


def test_r4_sdbx_with_a_commit_of_its_own_is_refused(world: World):
    conflicting_sdbx(world)
    world.commit("repo-a", f"{CODE}-sdbx", "own.txt", "own\n", "feat: own", push=False)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert any("has commits of its own" in p for p in state.problems)


def test_r4_sdbx_file_that_sandbox_does_not_change_is_refused(world: World):
    build_release(world)
    build_sdbx(world)
    world.commit("repo-a", f"{CODE}-sdbx", "x.txt", "x\n", "feat: x", push=False)
    config = load_release_config()
    sandbox = config.environment("sandbox")
    problems, differs = rules.mirror(
        config.entry("repo-a"), CODE, f"{CODE}-sdbx", sandbox, "master"
    )
    assert f"repo-a: {CODE}-sdbx differs from {CODE} in x.txt, which sandbox does not change" in (
        problems
    )
    assert set(differs) == {"x.txt", "sandbox-only.txt"}


def test_r4_clean_mirror_lists_the_sandbox_only_file(world: World):
    conflicting_sdbx(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert state.problems == []
    side = state.environments["sandbox"]
    assert side.copy == f"{CODE}-sdbx" and side.exists
    assert side.differs == ("sandbox-only.txt",)


def test_r4_a_clean_sandbox_merge_also_has_its_copy(world: World):
    build_release(world)
    build_sdbx(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert state.problems == [] and state.warnings == [] and state.ready
    assert state.environments["sandbox"].differs == ("sandbox-only.txt",)


def test_r2_a_copy_that_tracks_the_environment_branch_is_refused(world: World):
    build_release(world)
    build_sdbx(world)
    world.git("repo-a", "branch", "--set-upstream-to=origin/sandbox", f"{CODE}-sdbx")
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert any(f"{CODE}-sdbx tracks origin/sandbox" in p for p in state.problems)


def test_an_environment_without_its_copy_is_a_problem(world: World):
    build_release(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert f"repo-a: {CODE}-sdbx missing; run ws release new --env sandbox" in state.problems
    assert not state.environments["sandbox"].exists
    assert not state.ready


def test_an_environment_out_of_scope_needs_no_copy(world: World):
    build_release(world)
    state = assess(world, "repo-a", (ONE, TWO))
    assert state.environments == {} and state.ready


def test_two_environments_each_check_their_own_copy(world: World):
    world.add_staging()
    build_release(world)
    build_sdbx(world)
    state = assess(world, "repo-a", (ONE, TWO), ("sandbox", "staging"))
    assert f"repo-a: {CODE}-stg missing; run ws release new --env staging" in state.problems
    world.git("repo-a", "checkout", "-q", CODE)
    world.branch("repo-a", f"{CODE}-stg", CODE, push=False)
    world.git(
        "repo-a", "merge", "--no-ff", "-m", "chore(TS-101): junta a staging", "origin/staging"
    )
    state = assess(world, "repo-a", (ONE, TWO), ("sandbox", "staging"))
    assert state.problems == []
    assert list(state.environments) == ["sandbox", "staging"]
    assert state.environments["staging"].differs == ("staging-only.txt",)
    assert state.as_json()["environments"]["staging"]["copy"] == f"{CODE}-stg"


def test_a_copy_that_lacks_the_environment_branch_is_refused(world: World):
    build_release(world)
    world.branch("repo-a", f"{CODE}-sdbx", CODE, push=False)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert any(f"{CODE}-sdbx does not contain origin/sandbox" in p for p in state.problems)


def test_a_copy_already_merged_into_the_environment_stays_ready(world: World):
    conflicting_sdbx(world)
    world.git("repo-a", "checkout", "-q", "sandbox")
    world.git("repo-a", "merge", "-q", "--no-ff", "-m", "Merge pull request #11", f"{CODE}-sdbx")
    world.git("repo-a", "push", "-q", "origin", "sandbox")
    world.git("repo-a", "fetch", "-q", "origin")
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert state.warnings == [] and state.ready
    assert state.environments["sandbox"].merged


def test_release_branch_behind_its_origin_copy_is_refused(world: World):
    build_release(world)
    world.git("repo-a", "push", "-q", "origin", CODE)
    world.git("repo-a", "reset", "-q", "--hard", "HEAD~1")
    world.git("repo-a", "fetch", "-q", "origin")
    state = assess(world, "repo-a", (ONE, TWO))
    assert f"repo-a: local {CODE} is behind origin/{CODE}; pull it first" in state.problems


def test_multi_release_with_nothing_ahead_of_master_is_refused(world: World):
    world.branch("repo-a", CODE, BASE, push=False)
    state = assess(world, "repo-a", (ONE, TWO))
    assert f"repo-a: {CODE} has no commits ahead of origin/master" in state.problems


def test_r5_release_merge_with_a_co_authored_by_trailer_is_refused(world: World):
    world.branch("repo-a", CODE, BASE, push=False)
    world.git(
        "repo-a",
        "merge",
        "--no-ff",
        "-m",
        "chore(TS-101): junta a feature",
        "-m",
        "Co-Authored-By: Someone <someone@example.com>",
        ONE,
    )
    world.git("repo-a", "merge", "--no-ff", "-m", "chore(TS-102): junta a feature", TWO)
    state = assess(world, "repo-a", (ONE, TWO))
    assert any("Co-Authored-By trailer" in p for p in state.problems)


def test_r5_release_merge_subject_over_72_characters_is_refused(world: World):
    subject = "chore(TS-101): " + "a" * (73 - len("chore(TS-101): "))
    assert len(subject) == 73
    build_release(world, subject)
    state = assess(world, "repo-a", (ONE, TWO))
    assert any("has 73 characters in the subject; the limit is 72" in p for p in state.problems)


def test_r5_release_merges_in_the_pattern_pass(world: World):
    build_release(world)
    assert assess(world, "repo-a", (ONE, TWO)).problems == []


def test_r5_single_branch_ignores_the_users_own_merges(world: World):
    world.git("repo-a", "checkout", "-q", ONE)
    world.git("repo-a", "merge", "--no-ff", "-m", "Merge branch 'whatever'", "origin/sandbox")
    state = assess(world, "repo-a", (ONE,))
    assert state.problems == []


def test_r5_single_branch_checks_the_master_merge_the_tool_makes(world: World):
    world.commit("repo-a", "master", "moved.txt", "m\n", "chore: master moved")
    world.git("repo-a", "fetch", "-q", "origin")
    world.git("repo-a", "checkout", "-q", ONE)
    world.git("repo-a", "merge", "--no-ff", "-m", "atualiza com a master", BASE)
    state = assess(world, "repo-a", (ONE,))
    assert any("subject does not match" in p for p in state.problems)


def draft_for(world: World, file: str, title: str, tasks: list[str], body: str):
    path = world.write_pr(file, title, tasks, body)
    return folder.read_pr(path)


def good_body(state: rules.RepoState, tasks: list[str], extra: str = "") -> str:
    lines = [folder.tasks_block(tuple(tasks), LINK_TEMPLATE), folder.release_line(DAY_DATE), extra]
    lines += state.headings
    return "\n\n".join(lines) + "\n"


def r6(state, kind, draft, body=None):
    env = None if kind == "code" else load_release_config().environment(kind)
    return rules.pr_text_problems(
        state, env, draft, draft.body if body is None else body, DAY_DATE, LINK_TEMPLATE,
        {"repo-a", "repo-b"}, SLUGS,
    )  # fmt: skip


def multi_state(world: World) -> rules.RepoState:
    build_release(world)
    return assess(world, "repo-a", (ONE, TWO))


def test_r6_multi_with_a_clean_draft_passes(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    draft = draft_for(world, "repo-a", f"release {DAY}: tema", tasks, good_body(state, tasks))
    assert r6(state, "code", draft) == []
    sandbox = draft_for(
        world, "repo-a-sandbox", f"release {DAY}: tema (sdbx)", tasks, good_body(state, tasks)
    )
    assert r6(state, "sandbox", sandbox) == []


def test_r6_multi_title_with_a_key_is_refused(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    title = f"release {DAY}: feat(TS-101): x"
    draft = draft_for(world, "repo-a", title, tasks, good_body(state, tasks))
    assert any("title must be 'release" in p for p in r6(state, "code", draft))


def test_r6_single_title_needs_a_key(world: World):
    state = assess(world, "repo-b", ("feature/TS-201-only",))
    tasks = ["TS-201"]
    ok = draft_for(world, "repo-b", "feat(TS-201): x", tasks, good_body(state, tasks))
    assert r6(state, "code", ok) == []
    bad = draft_for(world, "repo-b", "feat: x", tasks, good_body(state, tasks))
    assert any("title must be 'type(TS-N): text'" in p for p in r6(state, "code", bad))


def test_r6_single_body_needs_the_release_line(world: World):
    state = assess(world, "repo-b", ("feature/TS-201-only",))
    tasks = ["TS-201"]
    body = good_body(state, tasks).replace(folder.release_line(DAY_DATE), "")
    draft = draft_for(world, "repo-b", "feat(TS-201): x", tasks, body)
    assert any("lacks 'Release: 20/11/2026'" in p for p in r6(state, "code", draft))


def test_r6_sandbox_title_needs_the_sdbx_suffix(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    draft = draft_for(
        world, "repo-a-sandbox", f"release {DAY}: tema", tasks, good_body(state, tasks)
    )
    assert any("must end with ' (sdbx)'" in p for p in r6(state, "sandbox", draft))


def test_r6_staging_title_needs_the_stg_suffix(world: World):
    world.add_staging()
    state = assess(world, "repo-a", (ONE, TWO))
    tasks = ["TS-101", "TS-102"]
    body = good_body(state, tasks)
    ok = draft_for(world, "repo-a-staging", f"release {DAY}: tema (stg)", tasks, body)
    assert r6(state, "staging", ok) == []
    bad = draft_for(world, "repo-a-staging", f"release {DAY}: tema (sdbx)", tasks, body)
    assert any("staging title must end with ' (stg)'" in p for p in r6(state, "staging", bad))


def test_r6_tasks_must_list_every_include_key(world: World):
    state = multi_state(world)
    draft = draft_for(
        world, "repo-a", f"release {DAY}: x", ["TS-101"], good_body(state, ["TS-101"])
    )
    assert "repo-a: tasks lacks TS-102, which an include carries" in r6(state, "code", draft)


def test_r6_body_needs_the_link_of_every_task(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    body = good_body(state, tasks).replace(f"{SITE}/browse/TS-101", "TS-101")
    draft = draft_for(world, "repo-a", f"release {DAY}: x", tasks, body)
    assert "repo-a: the description lacks the link of TS-101" in r6(state, "code", draft)


def test_release_rules_check_the_template_link(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    other = "https://tasks.example.com/item/{key}"
    body = good_body(state, tasks).replace(f"{SITE}/browse/", "https://tasks.example.com/item/")
    draft = draft_for(world, "repo-a", f"release {DAY}: x", tasks, body)
    assert r6(state, "code", draft) != []
    found = rules.pr_text_problems(
        state, None, draft, body, DAY_DATE, other, {"repo-a", "repo-b"}, SLUGS
    )
    assert found == []


def test_r6_body_needs_the_headings_of_the_template(world: World):
    state = assess(world, "repo-b", ("feature/TS-201-only",))
    assert state.headings == ["## Tarefa", "## Como validei"]
    tasks = ["TS-201"]
    body = good_body(state, tasks).replace("## Como validei", "")
    draft = draft_for(world, "repo-b", "feat(TS-201): x", tasks, body)
    assert any("heading '## Como validei'" in p for p in r6(state, "code", draft))


def test_r6_repo_without_a_template_uses_the_four_headings(world: World):
    state = multi_state(world)
    assert state.headings == rules.DEFAULT_HEADINGS
    assert rules.template_headings(load_release_config().entry("repo-a"), None) == (
        rules.DEFAULT_HEADINGS
    )


def test_r6_unresolved_placeholder_is_refused(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    body = good_body(state, tasks, extra="Depende de {pr:repo-c}")
    draft = draft_for(world, "repo-a", f"release {DAY}: x", tasks, body)
    assert any("{pr:repo-c}" in p for p in r6(state, "code", draft))
    known = good_body(state, tasks, extra="Depende de {pr:repo-b}")
    ok = draft_for(world, "repo-a", f"release {DAY}: x", tasks, known)
    assert r6(state, "code", ok) == []


def test_r6_literal_pr_reference_must_be_a_placeholder(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    body = good_body(state, tasks, extra="Depende de acme/repo-b#7")
    draft = draft_for(world, "repo-a", f"release {DAY}: x", tasks, body)
    assert any("acme/repo-b#7" in p and "write {pr:repo-b}" in p for p in r6(state, "code", draft))


def test_r6_resolved_reference_in_the_rendered_body_passes(world: World):
    state = multi_state(world)
    tasks = ["TS-101", "TS-102"]
    draft = draft_for(world, "repo-a", f"release {DAY}: x", tasks, good_body(state, tasks))
    rendered = good_body(state, tasks, extra="Depende de acme/repo-b#7")
    assert r6(state, "code", draft, rendered) == []


def test_r11_stacked_out_of_order_names_the_fix_and_suggests_the_order(world: World):
    stack_migrations(world)
    entry = load_release_config().entry("repo-a")
    problems, _, order = rules.order_check(entry, [TWO, ONE], BASE)
    assert f"repo-a: {TWO} already contains {ONE}; list {ONE} before {TWO}" in problems
    assert order == [ONE, TWO]


def test_r10_r11_passing_stacked_chain(world: World):
    stack_migrations(world)
    entry = load_release_config().entry("repo-a")
    problems, warnings, order = rules.order_check(entry, [ONE, TWO], BASE)
    assert (problems, warnings, order) == ([], [], [ONE, TWO])


def test_r11_foreign_key_is_refused(world: World):
    world.commit("repo-a", ONE, "y.txt", "y\n", "feat(TS-999): y")
    entry = load_release_config().entry("repo-a")
    problems, _, _ = rules.order_check(entry, [ONE, TWO], BASE)
    assert f"repo-a: {ONE} carries commits of TS-999, which is not in this repo's include list" in (
        problems
    )


def test_r11_local_branch_behind_origin_is_refused(world: World):
    world.commit("repo-a", ONE, "y.txt", "y\n", "feat: y")
    world.git("repo-a", "reset", "-q", "--hard", "HEAD~1")
    entry = load_release_config().entry("repo-a")
    problems, _, _ = rules.order_check(entry, [ONE], BASE)
    assert f"repo-a: local {ONE} is behind origin/{ONE}; pull it first" in problems
    assert any("behind origin" in p for p in assess(world, "repo-a", (ONE,)).problems)


def test_r11_local_branch_ahead_of_origin_is_a_warning(world: World):
    world.commit("repo-a", ONE, "y.txt", "y\n", "feat: y", push=False)
    entry = load_release_config().entry("repo-a")
    problems, warnings, _ = rules.order_check(entry, [ONE], BASE)
    assert problems == []
    assert warnings == [
        f"repo-a: local {ONE} has 1 commits not on origin; they go into the release"
    ]


def test_r11_local_branch_diverged_from_origin_is_refused(world: World):
    world.commit("repo-a", ONE, "y.txt", "y\n", "feat: y")
    world.git("repo-a", "reset", "-q", "--hard", "HEAD~1")
    world.commit("repo-a", ONE, "z.txt", "z\n", "feat: z", push=False)
    entry = load_release_config().entry("repo-a")
    problems, _, _ = rules.order_check(entry, [ONE], BASE)
    assert f"repo-a: local {ONE} and origin/{ONE} diverged" in problems


def test_r10_two_heads_at_the_code_tip_are_refused(world: World):
    world.migration("repo-a", ONE, REV_B, REV_BASE)
    world.migration("repo-a", TWO, REV_C, REV_BASE)
    build_release(world)
    state = assess(world, "repo-a", (ONE, TWO))
    assert state.heads["code"] == [REV_B, REV_C]
    assert f"repo-a: 2 alembic heads at {CODE}: {REV_B}, {REV_C}" in state.problems
    assert rules.heads_problem("repo-a", "the sandbox merge", [REV_B]) is None


def test_r10_stacked_chain_has_one_head_on_each_side(world: World):
    stack_migrations(world)
    build_release(world)
    build_sdbx(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert state.heads == {"code": [REV_C]}
    assert state.environments["sandbox"].heads == [REV_C]
    assert state.problems == []


def test_r10_two_heads_at_a_copy_are_refused(world: World):
    world.migration("repo-a", "sandbox", REV_B, REV_BASE)
    world.migration("repo-a", ONE, REV_C, REV_BASE)
    build_release(world)
    build_sdbx(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert state.heads == {"code": [REV_C]}
    assert any(
        "2 alembic heads at the sandbox copy" in p and p.endswith("ws release new --env sandbox")
        for p in state.problems
    )


def test_as_json_is_plain_data(world: World):
    state = assess(world, "repo-a", (ONE,), SANDBOX)
    data = state.as_json()
    assert data["repo"] == "repo-a"
    assert data["includes"] == [ONE]
    assert data["environments"] == {
        "sandbox": {
            "branch": "sandbox",
            "copy": f"{ONE}-sdbx",
            "exists": False,
            "merged": False,
            "differs": [],
            "heads": [],
        }
    }


def drop_origin_sandbox(world: World) -> None:
    world.git("repo-a", "update-ref", "-d", "refs/remotes/origin/sandbox")


def test_missing_sandbox_on_origin_is_a_problem_without_sdbx(world: World):
    build_release(world)
    drop_origin_sandbox(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert any("repo-a: origin/sandbox does not exist" in p for p in state.problems)
    assert not state.ready


def test_missing_sandbox_on_origin_with_its_copy_does_not_crash(world: World):
    build_release(world)
    build_sdbx(world)
    drop_origin_sandbox(world)
    state = assess(world, "repo-a", (ONE, TWO), SANDBOX)
    assert any("repo-a: origin/sandbox does not exist" in p for p in state.problems)
    assert not state.ready


def test_template_headings_follow_the_configured_base_branch(world: World):
    world.branch("repo-b", "trunk", "master")
    path = ".github/pull_request_template.md"
    world.commit("repo-b", "trunk", path, "## Trunk\n", "chore: t")
    entry = load_release_config().entry("repo-b")
    assert rules.template_headings(entry, None, "trunk") == ["## Trunk"]
    assert rules.template_headings(entry, None) == ["## Tarefa", "## Como validei"]


def test_template_headings_ignore_fenced_code(world: World):
    text = "## Real\n```\n## in fence\n```\n~~~\n## in tilde\n~~~\n## Also real\n"
    world.commit("repo-b", "master", ".github/pull_request_template.md", text, "chore: t")
    entry = load_release_config().entry("repo-b")
    assert rules.template_headings(entry, "master") == ["## Real", "## Also real"]
