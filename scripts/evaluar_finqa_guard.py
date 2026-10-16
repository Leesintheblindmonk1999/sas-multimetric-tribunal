#!/usr/bin/env python3
"""evaluar_finqa_guard.py — Evalúa el R3.1 Guard v4 sobre financiero_finqa.

Diseño:
  financiero_finqa NO tiene queries pareadas (0 pares query-idénticos).
  Por lo tanto NO podemos hacer A_B clásico (A correcta vs B alucinada
  de la misma query). En su lugar:

  1. A_Ap (correctas): A (completa) vs A' (correcta sola)
     → Test de FP rate: ¿el guard dice equiv cuando debería?
     → Esperado: grounding ≥ 0.95 → equiv

  2. A_B_cross (alucinadas vs correctas): A_correcta vs B_alucinada
     → Test de recall cross-query: ¿el guard detecta que una respuesta
       alucinada NO es equivalente a un contexto financiero correcto?
     → Esperado: grounding < 0.95 → NO equiv
     → Nota: como query y contexto son distintos, esto mide si el guard
       puede distinguir respuestas financieras válidas de inválidas
       incluso cuando el contexto difiere.

  3. Análisis de respuestas numéricas cortas (media 7 chars):
     → ¿Las heurísticas de entidad aislada funcionan con números?
     → ¿El threshold 0.95 es suficiente para respuestas numéricas?

Salida: reports/evaluacion_finqa_guard.json
"""

import json
import sys
import time
import random
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(r"C:\Users\conno\Downloads\SAS-Semántico\scripts")))
from r3_1_differential import compute_structural_delta

FINQA = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\pairs_finqa.jsonl")
OUTPUT = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\evaluacion_finqa_guard.json")

print("=" * 72)
print("  EVALUACIÓN — R3.1 Guard v4 sobre financiero_finqa")
print("=" * 72)

pares = [json.loads(line) for line in open(FINQA, encoding="utf-8")]
correctas = [p for p in pares if p["is_correct"]]
alucinadas = [p for p in pares if not p["is_correct"]]
print(f"\n  {len(pares)} pares cargados")
print(f"  correctas: {len(correctas)}  alucinadas: {len(alucinadas)}")

t0 = time.time()

# ── 1. Identidad (A vs A) — sanity check ──────────────────────────────
n_id_equiv = 0
for p in correctas[:100]:  # sample 100 for speed
    r = compute_structural_delta(p["A"], p["A"])
    if r["is_structurally_equivalent"] is True:
        n_id_equiv += 1
print(f"\n  Identidad (A vs A, n=100): {n_id_equiv}/100 equiv")

# ── 2. A_Ap: correcta completa vs correcta sola ───────────────────────
n_ap_equiv = 0
n_ap_noequiv = 0
n_ap_abst = 0
ap_detalles = []

for p in correctas:
    r = compute_structural_delta(p["A"], p["A_prime"])
    if r["is_structurally_equivalent"] is True:
        n_ap_equiv += 1
    elif r["is_structurally_equivalent"] is False:
        n_ap_noequiv += 1
    else:
        n_ap_abst += 1
    ap_detalles.append({
        "id": p["id"],
        "equiv": r["is_structurally_equivalent"],
        "score": r["differential_score"],
        "grounding": (r.get("grounding") or {}).get("grounding_score"),
        "n_words": (r.get("grounding") or {}).get("n_response_words"),
        "abstain": r.get("abstain_reason"),
    })

print(f"\n── A_Ap (correcta completa vs correcta sola) ──")
print(f"  equiv={n_ap_equiv} ({n_ap_equiv/len(correctas):.1%})  "
      f"noequiv={n_ap_noequiv}  abst={n_ap_abst}")

# ── 3. A_B_cross: A correcta vs B alucinada (cross-query) ────────────
# Para cada alucinada, elegir una correcta al azar (misma seed)
rng = random.Random(42)
n_b_noequiv = 0
n_b_equiv = 0
n_b_abst = 0
b_detalles = []

for p in alucinadas:
    # Elegir una correcta al azar como source
    src = rng.choice(correctas)["A"]
    r = compute_structural_delta(src, p["B"])
    if r["is_structurally_equivalent"] is False:
        n_b_noequiv += 1
    elif r["is_structurally_equivalent"] is True:
        n_b_equiv += 1
    else:
        n_b_abst += 1
    b_detalles.append({
        "id": p["id"],
        "equiv": r["is_structurally_equivalent"],
        "score": r["differential_score"],
        "grounding": (r.get("grounding") or {}).get("grounding_score"),
        "n_words": (r.get("grounding") or {}).get("n_response_words"),
        "abstain": r.get("abstain_reason"),
    })

print(f"\n── A_B_cross (A correcta vs B alucinada, cross-query) ──")
print(f"  noequiv={n_b_noequiv} ({n_b_noequiv/len(alucinadas):.1%})  "
      f"equiv={n_b_equiv}  abst={n_b_abst}")

# ── 4. Análisis de regresiones ────────────────────────────────────────
print(f"\n── Análisis de regresiones ──")

# A_Ap regresiones (correctas que guard dice no-equiv)
ap_regs = [d for d in ap_detalles if d["equiv"] is False]
print(f"  A_Ap regresiones (correcta → no-equiv): {len(ap_regs)}")
if ap_regs:
    gs_dist = Counter(round(d["grounding"] or 0, 2) for d in ap_regs)
    print("  Grounding scores:")
    for gs in sorted(gs_dist):
        print(f"    {gs:.2f}: {gs_dist[gs]}")
    print("  Primeros 5:")
    for d in ap_regs[:5]:
        print(f"    id={d['id']} grounding={d['grounding']} n_words={d['n_words']}")

# A_B regresiones (alucinadas que guard dice equiv)
b_regs = [d for d in b_detalles if d["equiv"] is True]
print(f"\n  A_B regresiones (alucinada → equiv): {len(b_regs)}")
if b_regs:
    gs_dist = Counter(round(d["grounding"] or 0, 2) for d in b_regs)
    print("  Grounding scores:")
    for gs in sorted(gs_dist):
        print(f"    {gs:.2f}: {gs_dist[gs]}")
    print("  Primeros 5:")
    for d in b_regs[:5]:
        print(f"    id={d['id']} grounding={d['grounding']} n_words={d['n_words']} abstain={d['abstain']}")

latencia = (time.time() - t0) / len(pares) * 1e6
print(f"\n  Latencia: {latencia:.1f} µs/par")

# ── Guardar ─────────────────────────────────────────────────────────────
import hashlib
salida = {
    "experimento": "R3.1 Guard v4 sobre financiero_finqa",
    "fecha": "2026-10-13",
    "n_correctas": len(correctas),
    "n_alucinadas": len(alucinadas),
    "identidad": {"n": 100, "n_equiv": n_id_equiv},
    "A_Ap": {
        "n": len(correctas),
        "n_equiv": n_ap_equiv,
        "tasa_equiv": round(n_ap_equiv / len(correctas), 6),
        "n_noequiv": n_ap_noequiv,
        "n_abst": n_ap_abst,
    },
    "A_B_cross": {
        "n": len(alucinadas),
        "n_noequiv": n_b_noequiv,
        "tasa_noequiv": round(n_b_noequiv / len(alucinadas), 6),
        "n_equiv": n_b_equiv,
        "n_abst": n_b_abst,
    },
    "latencia_us": round(latencia, 2),
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(salida, f, indent=2, ensure_ascii=False)

h = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
print(f"\nGuardado: {OUTPUT}")
print(f"SHA-256: {h}")
print("=" * 72)
