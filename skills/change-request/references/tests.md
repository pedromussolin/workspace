# Running the platform-cessao tests in Docker

Used by step 3 of the survey in [../SKILL.md](../SKILL.md). The suite takes
about 12 minutes, so run it in the background, from a worktree of the branch.

```bash
docker run --rm --network <network> -v <worktree>:/workspace -w /workspace \
  -e ENV=docker -e DD_TRACE_ENABLED=false \
  -e DB_POSTGRESQL_PLATFORM_CESSAO=postgresql://<test-user>:<test-password>@<postgres-container>:5432/platform-cessao \
  platform-cessao_devcontainer-web:latest \
  bash -lc "pip install -q -e . >/dev/null; python -m pytest -q -p no:cacheprovider test"
```

## Placeholders

- `<worktree>`: the worktree of the branch under test.
- `<postgres-container>`: the container's **name** on the host. More than one
  container has the alias `db`, so the alias is not enough.
- `<network>`: taken from the container itself:
  `docker inspect <postgres-container> --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}'`
- `<test-user>`, `<test-password>`: the credentials of the local test
  Postgres. They live in `~/.config/workspace/private/cessao-tests.md`, never
  in a committed file.

## Cleanup

The container writes files as root, so a plain `rm` fails. Remove the
worktree through Docker, then prune it:

```bash
docker run --rm -v <parent-dir>:/s alpine rm -rf /s/<folder>
git worktree prune
```

`<parent-dir>` is the directory that holds the worktree and `<folder>` is the
worktree's folder name.

## When it cannot run

Report the date of the last run and say it is not current.
