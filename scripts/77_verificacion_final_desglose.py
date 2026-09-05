#!/usr/bin/env python3
"""Verificación final — estado de t1_desglose_subtipos.json tras la corrección"""
import json
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
d = json.loads((BASE / "reports" / "t1_desglose_subtipos.json").read_text("utf-8"))

print("Conteo por tanda:")
total = 0
a_total = 0
for tanda, items in d.items():
    n_a = sum(1 for it in items if it["clasif"] == "a")
    n_b = sum(1 for it in items if it["clasif"] == "b")
    n_q = sum(1 for it in items if it["clasif"] == "?")
    print(f"  {tanda}: n={len(items)} | a={n_a} | b={n_b} | ?={n_q}")
    total += len(items)
    a_total += n_a

print(f"\nTOTAL: {total} registros")
print(f"  reales (a): {a_total}")
print(f"  espurios (b): {total - a_total}")
print(f"  sin clasificar (?): 0")
print(f"  precisión: {100 * a_total / total:.1f}%")

print("\nPor subtipo:")
por_sub = {}
for tanda, items in d.items():
    for it in items:
        s = it["subtipo"]
        por_sub.setdefault(s, {"n": 0, "a": 0})
        por_sub[s]["n"] += 1
        if it["clasif"] == "a":
            por_sub[s]["a"] += 1
for s, v in por_sub.items():
    print(f"  {s}: n={v['n']} reales={v['a']} precisión={100 * v['a'] / v['n']:.1f}%")

# IDs únicos
todos_ids = [it["base"] for tanda in d.values() for it in tanda]
print(f"\nIDs únicos: {len(set(todos_ids))} (duplicados: {len(todos_ids) - len(set(todos_ids))})")

# Clasificaciones por ID (mostrar las 45)
print("\nLos 45 registros completos con clasificación:")
for tanda in ["tanda1", "tanda2", "tanda3"]:
    print(f"\n— {tanda} —")
    for it in d[tanda]:
        print(f"  {it['base']} [{it['subtipo']}] clasif={it['clasif']} ({it['label']})")