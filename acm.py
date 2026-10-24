#!/usr/bin/env python3
"""Fachada de compatibilidade do AC Manager.

A implementação fica em ``acm_lib``. Este arquivo mantém ``import acm`` e a
CLI ``python3 acm.py ...`` funcionando para a GUI e scripts existentes.
"""

from __future__ import annotations

from acm_lib import *
from acm_lib.cli import *
from acm_lib.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
