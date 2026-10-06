#!/usr/bin/env python3
"""Punto de entrada: `archcleaner analizar`, etc. Enlazado en ~/.local/bin/archcleaner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from archcleaner.cli import main  # noqa: E402

sys.exit(main())
