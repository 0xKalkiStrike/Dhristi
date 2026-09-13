"""DRISHTI-V — Root Launcher Entrypoint.
Delegates execution to scripts/run_all.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from scripts.run_all import main

if __name__ == "__main__":
    main()
