"""Frozen-app entry point — what `python -m suite` does, without -m.

PyInstaller analyzes this file; keep it a bare import + call so the module
graph is exactly the suite's own.
"""

import sys

from suite.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
