---
type: tool_used
tool: Bash
input_match: 'ws deploy-check script bff --env sandbox\b'
---

The program for the BFF comes from `ws deploy-check script`, which reads the deploy moment and the
expected version from the local argocd repo.
