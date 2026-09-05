#!/usr/bin/env python3
"""Verifica los textos de los items clasificados como (a) o (b) en las 3 tandas — para re-derivación TAREA 2"""
import json
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
d = json.loads((BASE / "reports" / "t1_desglose_subtipos.json").read_text("utf-8"))

# Mostrar TODOS los items de la tanda 3 con su texto B (los más recientes, menos verificados)
print("=" * 80)
print("TANDA 3 — texto B de los 20 items")
print("=" * 80)
for item in d["tanda3"]:
    print(f"\n--- base={item['base']} [{item['subtipo']}]")
    print(f"  B: {item['B'][:200]}")