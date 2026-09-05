#!/usr/bin/env python3
"""script 76 — Corrige t1_desglose_subtipos.json: fusiona las clasificaciones a/b correctas desde script 67

El script 75 anterior usó un regex defectuoso (solo 4 dígitos) que capturó 11 de 45 IDs,
dejando 34 registros con clasif='?'. Este script extrae los 45 pares ID→clasif del
script 67 usando la ejecución real del script (que hace el assert len==45), y los escribe.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
DESGLOSE = BASE / "reports" / "t1_desglose_subtipos.json"
S67 = BASE / "scripts" / "67_rederivar_desglose_subtipos.py"

# ── Extraer clasificaciones del script 67 de forma robusta: importarlo y leer sus diccionarios ──
# Mejor enfoque: leer el script y extraer los tres dicts con exec parcial
src = S67.read_text("utf-8")
# Extraer solo hasta el assert (todo lo que define CLASIF_T1/T2/T3)
codigo = src.split("# Verificar que no haya IDs duplicados")[0]
ns = {}
exec(codigo, ns)  # define CLASIF_T1, CLASIF_T2, CLASIF_T3 + imports
clasif_map = {}
for tanda in ["CLASIF_T1", "CLASIF_T2", "CLASIF_T3"]:
    clasif_map.update(ns[tanda])
print(f"Clasificaciones extraídas del script 67: {len(clasif_map)}")
assert len(clasif_map) == 45, f"Esperaba 45, hay {len(clasif_map)}"

# ── Cargar desglose (puede tener clasif='?' del script 75) ──
d = json.loads(DESGLOSE.read_text("utf-8"))

# ── Verificar cobertura de IDs ──
ids_desglose = set()
for tanda in d.values():
    for it in tanda:
        ids_desglose.add(it["base"])
faltan = ids_desglose - set(clasif_map)
sobran = set(clasif_map) - ids_desglose
print(f"IDs desglose: {len(ids_desglose)} | IDs clasif_map: {len(clasif_map)}")
print(f"En desglose pero sin clasif: {sorted(faltan)}")
print(f"Clasificados pero no en desglose: {sorted(sobran)}")
if faltan:
    print("❌ FALTAN clasificaciones — no se puede completar")
    sys.exit(1)

# ── Escribir clasificación correcta en cada registro ──
for tanda in d.values():
    for it in tanda:
        it["clasif"] = clasif_map[it["base"]]
        it["label"] = "real" if it["clasif"] == "a" else "espurio"

# ── Guardar ──
DESGLOSE.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")

# ── Verificar ──
n_a = sum(1 for tanda in d.values() for it in tanda if it["clasif"] == "a")
n_b = sum(1 for tanda in d.values() for it in tanda if it["clasif"] == "b")
n_q = sum(1 for tanda in d.values() for it in tanda if it["clasif"] == "?")
print(f"\n✅ Archivo corregido:")
print(f"  reales (a): {n_a} | espurios (b): {n_b} | sin clasificar (?): {n_q}")
print(f"  total: {n_a + n_b + n_q}")

# Conteo por subtipo
from collections import Counter
por_subtipo = Counter()
for tanda in d.values():
    for it in tanda:
        if it["clasif"] == "a":
            por_subtipo[it["subtipo"]] += 1
print(f"\nReales por subtipo: {dict(por_subtipo)}")
total_n = sum(len(t) for t in d.values())
print(f"Precisión total: {n_a}/{total_n} = {100*n_a/total_n:.1f}%")