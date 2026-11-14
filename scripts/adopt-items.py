#!/usr/bin/env python3
"""One-off conversion of projects/ into items. Dry run by default; see adopt_items/cli.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adopt_items.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
