---
type: tool_used
tool: Write
input_match: '"file_path"\s*:\s*"/[^"]+/TS-5\.2026-11-11\.result\.json"'
---

The tool's JSON answer is saved with Write at `observability.result_path`. The fixture prints it in
the run's working directory, where the eval grants Write (see scripts/eval_observe.py).
