"""The old card hook's path, kept so a clone whose Claude settings still register it keeps working.

The card hook became the approval gate (`approval_gate.py`). A registration of this file now runs
the gate, so it still asks before every write, until `ws setup` moves the registration to the
protected copy (it reports this path as stale). Any failure to start the gate asks.
"""

import json
import runpy
import sys
from pathlib import Path

GATE = Path(__file__).resolve().with_name("approval_gate.py")

if __name__ == "__main__":
    try:
        runpy.run_path(str(GATE), run_name="__main__")
    except SystemExit:
        raise
    except Exception as error:
        reason = f"Não consegui iniciar o portão de aprovação ({error}); confira antes de aprovar."
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "ask"}
        decision["permissionDecisionReason"] = reason
        print(json.dumps({"hookSpecificOutput": decision}, ensure_ascii=False))
        sys.exit(0)
