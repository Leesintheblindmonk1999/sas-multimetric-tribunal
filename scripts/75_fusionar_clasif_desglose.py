#!/usr/bin/env python3
"""Verificación robusta — los 45 IDs del script 67 coinciden con los 45 del desglose"""
import json
import re
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
DESGLOSE = BASE / "reports" / "t1_desglose_subtipos.json"
S67 = BASE / "scripts" / "67_rederivar_desglose_subtipos.py"

d = json.loads(DESGLOSE.read_text("utf-8"))
s67 = S67.read_text("utf-8")

# IDs del desglose (todas las tandas)
ids_desglose = set()
for tanda in ["tanda1", "tanda2", "tanda3"]:
    for it in d[tanda]:
        ids_desglose.add(it["base"])
print(f"IDs en desglose: {len(ids_desglose)}")

# IDs del script 67 — extraer TODOS los pares "XXXX": "a|b" del bloque de clasificaciones
# (después de la línea CLASIF_T1 = { hasta el assert)
bloque = s67.split("CLASIF_T1 = {")[1].split("# Verificar que no haya IDs duplicados")[0]
ids_67 = set(re.findall(r'"(\d{4})": "[ab]"', bloque))
print(f"IDs en script 67: {len(ids_67)}")

# Comparar
faltan_en_67 = ids_desglose - ids_67
sobran_en_67 = ids_67 - ids_desglose
print(f"En desglose pero NO en 67: {sorted(faltan_en_67)}")
print(f"En 67 pero NO en desglose: {sorted(sobran_en_67)}")

# Verificar que cada ID del 67 tiene clasificación válida
clasifs = re.findall(r'"(\d{4})": "([ab])"', bloque)
print(f"\nClasificaciones totales en 67: {len(clasifs)}")
from collections import Counter
cnt = Counter(c for _, c in clasifs)
print(f"  (a) real: {cnt['a']} | (b) espurio: {cnt['b']}")

# Verificar que los IDs del 67 están TODOS en el desglose (para poder fusionar)
if not faltan_en_67 and not sobran_en_67:
    print("\n✅ Los 45 IDs coinciden exactamente entre desglose y script 67")
else:
    print("\n⚠️ Discrepancia de IDs")

# ── Fusionar: agregar clasificación a/b al desglose ──
clasif_map = dict(clasifs)
for tanda in ["tanda1", "tanda2", "tanda3"]:
    for it in d[tanda]:
        it["clasif"] = clasif_map.get(it["base"], "?")
        it["label"] = "real" if it["clasif"] == "a" else "espurio"

# Guardar versión enriquecida
out_path = BASE / "reports" / "t1_desglose_subtipos.json"
out_path.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
print(f"\n[OK] t1_desglose_subtipos.json enriquecido con clasificación a/b por registro")

# Re-verificar conteos
n_a = sum(1 for tanda in d.values() for it in tanda if it["clasif"] == "a")
n_b = sum(1 for tanda in d.values() for it in tanda if it["clasif"] == "b")
print(f"Re-verificación: {n_a} reales + {n_b} espurios = {n_a + n_b} (esperado 32 + 13 = 45)")