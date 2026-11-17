# Safety

External writes, the production replica and the approval gate. Decisions:
[0004](../adr/0004-model-invocable-skills-behind-the-box.md),
[0007](../adr/0007-gate-threat-model.md),
[0008](../adr/0008-gate-denies-endless-waits.md),
[0009](../adr/0009-tracker-writes-only-the-users-cards.md).

- Every external write goes through these steps:
  1. draft;
  2. preview, which prints an approval code and saves a pending record valid for 30 minutes;
  3. apply, in a separate Bash call with `--approve CODE`, behind the gate box.

  Preview and apply never share one command line.
  [test: tests/test_approval.py; tests/test_gate_bash.py]
- Apply re-plans and compares the code, stops at the first failure, never retries, and keeps
  uncertain results aside. What is approved is exactly what is sent.
  [test: tests/test_tracker_write.py; tests/test_card.py]
- The tracker writes only cards where the user is the assignee or the reporter.
  [test: tests/test_card.py; tests/test_card_create.py]
- The production replica is read-only. An observation's checks run through `ws observe run`,
  behind the box. [gate]
- A task may also query the replica directly, as the user authorized: read-only session, a
  statement timeout, one query at a time, `pg_is_in_recovery()` checked first; the host and the
  access live in the project's private file. [review]
- `ws observe` keeps numbers only, never rows or customer data.
  [test: tests/test_database_port.py; tests/test_observe_cli.py]
- From a direct query, only numbers and aggregates enter the repo; rows and customer data never
  do. [review]
- Database stderr is never printed or stored. [test: tests/test_database_postgres.py]
- The gate reads command text. It covers mistakes and plausible workarounds, not deliberate
  obfuscation. [review]
- The gate denies instead of asking when a box would only stall a background agent: wait loops
  without `timeout`, and `pgrep -f`/`pkill -f` that match their own command.
  [test: tests/test_gate_bash.py]
- A hard rule is a hook or a deny rule, never prose alone. [review]

## Current behaviour

`ws` itself refuses a preview and an approval run in the same shell session, so the one-line form
fails even where the gate does not see it. The box cannot see a script file that runs
`ws card apply` or `ws observe run`.
