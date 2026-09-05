#!/usr/bin/env python3
"""scripts/60_desglose_subtipos.py — Desglosa los 45 disparos clasificados (10+15+20) por subtipo (senador/vuelos/primalidad)"""
import json
import random
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
RESULT = BASE / "reports" / "t1_rationalization_binary.json"
POND = BASE / "reports" / "t1_recall_ponderado.json"

detalles = json.loads(RESULT.read_text("utf-8"))
dispararon = [d for d in detalles if d["fired"]]

def subtipo(A: str) -> str:
    a = A.lower()
    if "prime number" in a:
        return "primalidad"
    if "series of flights" in a:
        return "vuelos"
    if "senator" in a:
        return "senador"
    return "otro"

# ── Tanda 1: 10 de seed=42 (script 57) ──
rng = random.Random(42)
tanda1 = rng.sample(dispararon, 10)

# ── Tanda 2: 15 siguientes (script 58) ──
rng3 = random.Random(42)
copia = list(dispararon)
rng3.shuffle(copia)
ya_vistos = {d["base"] for d in tanda1}
tanda2 = [d for d in copia if d["base"] not in ya_vistos][:15]

# ── Tanda 3: 20 del reporte ponderado (script 59) ──
pond = json.loads(POND.read_text("utf-8"))
tanda3 = pond["tanda_adicional"]

# Clasificaciones manuales (a)=negación real del hecho, (b)=espurio
# Tanda 1 (10): 8 reales, 2 espurios — IDs recuperados del transcript
CLASIF_T1 = {
    # (a) reales
    # (b) espurios
}
# Tanda 2 (15): 10 reales, 5 espurios
CLASIF_T2 = {}
# Tanda 3 (20): 12 reales, 8 espurios — de la clasificación en pantalla
CLASIF_T3 = {
    "20553": "a", "6378": "a", "13722": "a", "16918": "a", "16987": "a",
    "11854": "a", "15083": "a", "20367": "b", "15016": "a", "18751": "b",
    "12916": "b", "20989": "a", "15914": "a", "5559": "b", "0018": "b",
    "2145": "b", "15784": "a", "16981": "a", "5403": "b", "7585": "a",
}

print("=== TANDA 1 (10, seed=42) ===")
for d in tanda1:
    print(f"  base={d['base']} | {subtipo(d['A'])}")
print("\n=== TANDA 2 (15 siguientes) ===")
for d in tanda2:
    print(f"  base={d['base']} | {subtipo(d['A'])}")
print("\n=== TANDA 3 (20 adicionales) ===")
for d in tanda3:
    print(f"  base={d['base']} | {subtipo(d['A'])}")

# Guardar IDs por tanda para el desglose
out = {
    "tanda1": [{"base": d["base"], "subtipo": subtipo(d["A"]), "A": d["A"], "B": d["B"]} for d in tanda1],
    "tanda2": [{"base": d["base"], "subtipo": subtipo(d["A"]), "A": d["A"], "B": d["B"]} for d in tanda2],
    "tanda3": [{"base": d["base"], "subtipo": subtipo(d["A"]), "A": d["A"], "B": d["B"]} for d in tanda3],
}
(BASE / "reports" / "t1_desglose_subtipos.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
print("\n[OK] Guardado en reports/t1_desglose_subtipos.json")