# Validate a change

From the cheapest check to the most expensive. Rules: [testing](../conventions/testing.md),
[agents](../conventions/agents.md), [git](../conventions/git.md).

1. **Run `scripts/validate`.** It runs `ruff check`, `ruff format --check`, the boundary tests,
   the skill-word tests, `tests/test_agent_docs.py` and `ws names pending`, prints what failed and
   exits 0 only when everything passes. A pending word needs the user's answer; see
   [confidentiality](../conventions/confidentiality.md).
2. **Run the focused tests:** the test files of what changed, with the pytest command of
   [testing](../conventions/testing.md), then clean its `--basetemp` folder.
3. **Run the full suite once**, in the background, and wait for the notification, never in a
   loop. See [agents](../conventions/agents.md).
4. **Run the changed eval cases** when a skill changed, one run each; see
   [new-eval](new-eval.md).
5. **Review.** Read `git diff` against the `[review]` rules of the conventions that the change
   touches, since no test sees those. Then commit as [git](../conventions/git.md) says.
