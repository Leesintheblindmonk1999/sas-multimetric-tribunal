#!/usr/bin/env python3
"""scripts/59_recall_ponderado.py — Recall ponderado + tanda adicional de disparos"""
import json
import random
import re
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
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

detalles = json.loads(RESULT.read_text("utf-8"))
dispararon = [d for d in detalles if d["fired"]]
no_dispararon = [d for d in detalles if not d["fired"]]
print(f"Dispararon: {len(dispararon)} | No dispararon: {len(no_dispararon)}")

# ═══════════════════════════════════════════════════════════
# PASO 1 — Recall ponderado a la población
# ═══════════════════════════════════════════════════════════
# Datos de las tandas previas:
#   - 25 disparos muestreados → 18 TP (a) reales
#   - 30 no-disparos muestreados → 1 FN (a) real
TP_MUESTRA = 18
N_TP_MUESTRA = 25
FN_MUESTRA = 1
N_FN_MUESTRA = 30

TP_estimado = 62 * (TP_MUESTRA / N_TP_MUESTRA)
FN_estimado = 138 * (FN_MUESTRA / N_FN_MUESTRA)
recall = TP_estimado / (TP_estimado + FN_estimado)

print(f"\n=== RECALL PONDERADO A LA POBLACIÓN ===")
print(f"TP_estimado = 62 × ({TP_MUESTRA}/{N_TP_MUESTRA}) = {TP_estimado:.2f}")
print(f"FN_estimado = 138 × ({FN_MUESTRA}/{N_FN_MUESTRA}) = {FN_estimado:.2f}")
print(f"Recall = {TP_estimado:.2f} / ({TP_estimado:.2f} + {FN_estimado:.2f}) = {recall:.4f} = {100*recall:.1f}%")

# ═══════════════════════════════════════════════════════════
# PASO 2 — Tanda adicional de 20-25 disparos (sin repetir los 25 vistos)
# ═══════════════════════════════════════════════════════════
print(f"\n{'='*80}")
print("PASO 2 — Tanda adicional de disparos (sin repetir los 25 ya vistos)")
print(f"{'='*80}")

# Reproducir los 25 ya vistos:
#  - 10 del script 57: rng.sample(dispararon, 10) con seed=42
rng57 = random.Random(42)
vistos_10 = rng57.sample(dispararon, 10)
vistos_ids = {d["base"] for d in vistos_10}

#  - 15 del script 58: shuffle seed=42, primeros 15 no en vistos_10
rng58 = random.Random(42)
copia = list(dispararon)
rng58.shuffle(copia)
siguientes_15 = [d for d in copia if d["base"] not in vistos_ids][:15]
vistos_ids.update(d["base"] for d in siguientes_15)

print(f"Ya vistos: {len(vistos_ids)} (10 + 15)")

# Tomar los siguientes 20 del shuffle (sin repetir)
siguientes_20 = [d for d in copia if d["base"] not in vistos_ids][:20]
print(f"Tanda adicional: {len(siguientes_20)} pares")

for i, d in enumerate(siguientes_20):
    A, B = d["A"], d["B"]
    neg_a_tokens = [m.group(0) for m in NEGACION.finditer(A.lower())]
    neg_b_tokens = [m.group(0) for m in NEGACION.finditer(B.lower())]
    print(f"\n[{i+1}] base={d['base']} | inv={d['inv']} | negA={d['negA']} negB={d['negB']}")
    print(f"  Tokens A: {neg_a_tokens if neg_a_tokens else '(ninguno)'}")
    print(f"  Tokens B: {neg_b_tokens if neg_b_tokens else '(ninguno)'}")
    print(f"  A: {A[:180]}")
    print(f"  B: {B[:180]}")

# Guardar para clasificación
out = BASE / "reports" / "t1_recall_ponderado.json"
json.dump({
    "recall_ponderado": {
        "TP_estimado": round(TP_estimado, 2),
        "FN_estimado": round(FN_estimado, 2),
        "recall": round(recall, 4),
    },
    "tanda_adicional": [{"base": d["base"], "A": d["A"], "B": d["B"]} for d in siguientes_20],
}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"\n[OK] Guardado en {out}")