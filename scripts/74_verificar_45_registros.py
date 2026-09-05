#!/usr/bin/env python3
"""Verificación final — t1_desglose_subtipos.json: 45 registros completos con clasificación a/b"""
import json
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
DESGLOSE = BASE / "reports" / "t1_desglose_subtipos.json"

d = json.loads(DESGLOSE.read_text("utf-8"))
print(f"Claves del archivo: {list(d.keys())}")

# ── Conteo por tanda ──
total = 0
ids_por_tanda = {}
for tanda in ["tanda1", "tanda2", "tanda3"]:
    items = d.get(tanda, [])
    ids = [it["base"] for it in items]
    ids_por_tanda[tanda] = ids
    print(f"{tanda}: {len(items)} registros")
    total += len(items)

print(f"\nTOTAL: {total} registros")

# ── IDs únicos? ──
todas_ids = [i for ids in ids_por_tanda.values() for i in ids]
print(f"IDs únicos: {len(set(todas_ids))} (duplicados: {len(todas_ids) - len(set(todas_ids))})")

# ── ¿Tiene clasificación a/b? ──
primer_item = d["tanda1"][0]
print(f"\nClaves de un item de tanda1: {list(primer_item.keys())}")
tiene_clasif = "clasif" in primer_item or "label" in primer_item or "tipo" in primer_item
print(f"¿El archivo incluye clasificación a/b?: {tiene_clasif}")

# ── Las clasificaciones a/b están en script 67 (hardcodeadas por ID) ──
# Verificar que el script 67 tiene las 45 clasificaciones
from pathlib import Path as P
s67 = (BASE / "scripts" / "67_rederivar_desglose_subtipos.py").read_text("utf-8")
import re
n_clasif_t1 = len(re.findall(r'"[0-9]+": "[ab]"', s67.split("CLASIF_T2")[0]))
n_clasif_t2 = len(re.findall(r'"[0-9]+": "[ab]"', s67.split("CLASIF_T2")[1].split("CLASIF_T3")[0]))
n_clasif_t3 = len(re.findall(r'"[0-9]+": "[ab]"', s67.split("CLASIF_T3")[1]))
print(f"\nClasificaciones a/b en script 67:")
print(f"  Tanda 1: {n_clasif_t1} | Tanda 2: {n_clasif_t2} | Tanda 3: {n_clasif_t3} | Total: {n_clasif_t1 + n_clasif_t2 + n_clasif_t3}")

# ── Los IDs de cada tanda en el desglose vs los del script 67 ──
# Extraer los IDs del script 67 por tanda
def extraer_ids_bloque(bloque):
    return set(re.findall(r'"([0-9]{4})": "[ab]"', bloque))

s67t1 = s67.split("CLASIF_T2")[0]
s67t2 = s67.split("CLASIF_T2")[1].split("CLASIF_T3")[0]
s67t3 = s67.split("CLASIF_T3")[1]
ids67_t1, ids67_t2, ids67_t3 = extraer_ids_bloque(s67t1), extraer_ids_bloque(s67t2), extraer_ids_bloque(s67t3)

for tanda, ids_desg, ids_67 in [("tanda1", set(ids_por_tanda["tanda1"]), ids67_t1),
                                 ("tanda2", set(ids_por_tanda["tanda2"]), ids67_t2),
                                 ("tanda3", set(ids_por_tanda["tanda3"]), ids67_t3)]:
    faltan = ids_desg - ids_67
    sobran = ids_67 - ids_desg
    print(f"{tanda}: IDs desglose={len(ids_desg)} | IDs script67={len(ids_67)} | "
          f"en desglose pero no en 67={sorted(faltan)} | en 67 pero no en desglose={sorted(sobran)}")

# ── Verificación de consistencia: los IDs del desglose son los mismos que los muestreos
# de los scripts 57/58/59? Comparar tanda1 con la muestra de script 57 (seed=42)
print(f"\nIDs tanda1 (deberían ser los 10 de script 57 seed=42): {sorted(ids_por_tanda['tanda1'])}")