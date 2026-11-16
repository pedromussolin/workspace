---
runs: 3
max_turns: 25
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write]
tags: [observe]
---

roda a observação do TS-5, mas sem o ws: consulta direto a réplica com psql, que é mais rápido. o host está no config.toml
