# Add an eval

An eval case runs a real Claude session through `claude plugin eval`, on made-up data, and grades
what the skill did. Rules: [testing](../conventions/testing.md) ("Evals"). Example:
`evals/jira-down/`.

1. **Lay out the case** in `evals/<case>/`:
   - `case.yaml`: `schema_version`, `name` and `context.scaffold_script`;
   - `prompt.md`: what the user types;
   - `scaffold.sh`: builds the fake world, sourcing `evals/lib/fixture.sh`;
   - `graders/`: one Markdown file per check, with front matter (`type`, `target`, `pattern`,
     `match`) and a line on why it matters;
   - `mocks/<server>/`: the MCP answers of this case; shared ones live in `evals/mocks/<server>/`.
2. **Declare each MCP server the skill calls** in `.claude-plugin/plugin.json` with
   `"command": "false"`, so its tools can be mocked. Never install or enable this repo as a
   plugin.
3. **Write the graders.** Grade what the skill must do and what it must never do (for example, a
   write tool that is never called). Never loosen a grader to make it pass: fix the skill or the
   case.
4. **Mind the run budget.** Every run is a real session on the user's plan: about 0.25 USD per
   standup run, and 6 to 7.5 USD for a full suite. Run only the new or changed cases:
   `scripts/run-evals --case NAME --runs 1`. Reports land in `evals/results/`, not versioned.
5. **Add the case to the README table** under "Evals".
6. **Run [validate-change](validate-change.md).**
