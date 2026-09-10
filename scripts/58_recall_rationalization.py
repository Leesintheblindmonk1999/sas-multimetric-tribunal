#!/usr/bin/env python3
"""scripts/58_recall_rationalization.py — T1 (recall real), T2 (ampliar muestra), T3 (nota de alcance)"""
import importlib.util
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
RATBIN = Path(r"C:\ProgramData\benchmark_corpus") / "halogen" / "rationalization_binary"
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"
RESULT = BASE / "reports" / "t1_rationalization_binary.json"

NEGACION = re.compile(
    r"\b(shall not|will not|must not|cannot|is not|are not|was not|were not"
    r"|has not|have not|had not|does not|do not|did not"
    r"|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|declines|refuses|rejects|denies|disputes"
    r"|never|none|neither|nor"
    r"|no|nunca|jamás|ningún|ninguna|tampoco|ni)\b",
    re.IGNORECASE,
)

# Cargar los 200 pares detallados
detalles = json.loads(RESULT.read_text("utf-8"))
print(f"Total pares: {len(detalles)}")

dispararon = [d for d in detalles if d["fired"]]
no_dispararon = [d for d in detalles if not d["fired"]]
print(f"Dispararon: {len(dispararon)} | No dispararon: {len(no_dispararon)}")

# ═══════════════════════════════════════════════════════════
# TAREA 1 — 30 pares al azar de los 138 que NO dispararon
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*80}")
print("TAREA 1 — 30 pares que NO dispararon (seed=42)")
print(f"{'='*80}")

rng = random.Random(42)
muestra_fn = rng.sample(no_dispararon, 30)

# Clasificación manual asistida: mostrar texto + tokens
for i, d in enumerate(muestra_fn):
    A, B = d["A"], d["B"]
    neg_a_tokens = [m.group(0) for m in NEGACION.finditer(A.lower())]
    neg_b_tokens = [m.group(0) for m in NEGACION.finditer(B.lower())]
    print(f"\n[{i+1}] base={d['base']} | negA={d['negA']} negB={d['negB']}")
    print(f"  Tokens A: {neg_a_tokens if neg_a_tokens else '(ninguno)'}")
    print(f"  Tokens B: {neg_b_tokens if neg_b_tokens else '(ninguno)'}")
    print(f"  A: {A[:200]}")
    print(f"  B: {B[:200]}")

# ═══════════════════════════════════════════════════════════
# TAREA 2 — 15 pares MÁS de los 62 que dispararon (siguientes en seed=42)
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*80}")
print("TAREA 2 — 15 pares MÁS de los 62 que dispararon (siguientes en seed=42)")
print(f"{'='*80}")

# Los 10 ya vistos en la tarea anterior (script 57, seed=42)
rng2 = random.Random(42)
ya_vistos = rng2.sample(dispararon, 10)
ya_vistos_ids = {d["base"] for d in ya_vistos}

# Siguientes 15 sin repetir
restantes = [d for d in dispararon if d["base"] not in ya_vistos_ids]
# Para reproducir el orden de muestreo, re-muestreamos con el mismo rng
# pero tomando los siguientes: sample() no da orden, así que usamos shuffle
rng3 = random.Random(42)
copia = list(dispararon)
rng3.shuffle(copia)
# Los primeros 10 son los ya vistos; los siguientes 15 son los nuevos
siguientes_15 = [d for d in copia if d["base"] not in ya_vistos_ids][:15]

for i, d in enumerate(siguientes_15):
    A, B = d["A"], d["B"]
    neg_a_tokens = [m.group(0) for m in NEGACION.finditer(A.lower())]
    neg_b_tokens = [m.group(0) for m in NEGACION.finditer(B.lower())]
    print(f"\n[{i+1}] base={d['base']} | inv={d['inv']} | negA={d['negA']} negB={d['negB']}")
    print(f"  Tokens A: {neg_a_tokens if neg_a_tokens else '(ninguno)'}")
    print(f"  Tokens B: {neg_b_tokens if neg_b_tokens else '(ninguno)'}")
    print(f"  A: {A[:200]}")
    print(f"  B: {B[:200]}")

# ═══════════════════════════════════════════════════════════
# TAREA 3 — Nota de alcance: variedad de estilos en los 200
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*80}")
print("TAREA 3 — Variedad de estilos de pregunta en los 200")
print(f"{'='*80}")

# Detectar patrones de pregunta
patrones = Counter()
for d in detalles:
    A = d["A"]
    if "prime number" in A.lower():
        patrones["primalidad (Is X a prime number?)"] += 1
    elif "series of flights" in A.lower():
        patrones["vuelos (Is there a series of flights...)"] += 1
    elif "senator" in A.lower():
        patrones["senador (Was there ever a US senator...)"] += 1
    elif "yes or no" in A.lower():
        patrones["binario sí/no (plantilla)"] += 1
    else:
        patrones["otro"] += 1

print(f"\nDistribución de estilos en los 200:")
for k, v in patrones.most_common():
    print(f"  {k}: {v}")

# ¿Todos tienen "yes or no" en la plantilla?
con_yes_no = sum(1 for d in detalles if "yes or no" in d["A"].lower())
print(f"\nCon plantilla 'yes or no' en A: {con_yes_no}/200 ({100*con_yes_no/200:.0f}%)")

# Guardar
out = BASE / "reports" / "t1_recall_rationalization.json"
json.dump({
    "tarea1_muestra_fn": [{"base": d["base"], "A": d["A"], "B": d["B"]} for d in muestra_fn],
    "tarea2_muestra_tp": [{"base": d["base"], "A": d["A"], "B": d["B"]} for d in siguientes_15],
    "tarea3_estilos": dict(patrones),
    "con_yes_no": con_yes_no,
}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n[OK] Guardado en {out}")