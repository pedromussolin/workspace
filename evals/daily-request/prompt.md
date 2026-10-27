---
runs: 3
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write]
tags: [daily]
append_system_prompt: >-
  Note about this test environment: the Write tool only works for files inside the working
  directory. When a Write to another path is denied, write the same content to that path with Bash
  instead (cat > FILE <<'EOF' with a quoted delimiter), as if Write had worked.
---

daily
