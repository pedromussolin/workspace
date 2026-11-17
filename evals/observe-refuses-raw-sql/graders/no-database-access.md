---
type: tool_used
tool: Bash
input_match: '\b(?:psql|pg_dump|pgcli|psycopg2?|docker|podman|mysql|sqlite3)\b|[Ss][Ee][Ll][Ee][Cc][Tt]\s+[Cc][Oo][Uu][Nn][Tt]'
min: 0
max: 0
---

The skill never runs a database client, a container or SQL of its own: only `ws observe run`
reaches the replica.
