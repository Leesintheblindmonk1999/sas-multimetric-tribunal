#!/usr/bin/env python3
"""sweep_threshold_guard.py — Barre el threshold de grounding del guard.

Pregunta: ¿qué threshold minimiza regresiones en A_B sin perder
correcciones en A_Ap?

Usa los datos ya auditados (guard.score por entrada).
"""

import json
from pathlib import Path

AUDIT = Path(r"c:\Users\conno\Downloads\SAS-Semántico\reports\audit_n1_guard_v3_20261012_222645.json")
audit = json.load(open(AUDIT, encoding="utf-8"))
resultados = audit["resultados"]

# Guard score por (suite, id, condicion)
scores = {(r["suite"], r["id"], r["condicion"]): r["guard"] for r in resultados}

# Ground truth por condición
GT = {
    "A_A": True,
    "A_Ap": True,
    "A_B": False,
    "A_App": False,
}


def evaluar_con_umbral(gt_map, umbral):
    """Simula el guard con un threshold distinto.

    Reglas:
      - Byte-identical (score=1.0, abstain=None) → equiv=True
      - response_too_long (abstain) → abstiene (None)
      - short_response con polarity_inversion → equiv=False (se mantiene)
      - short_response con isolated_entity → abstiene (se mantiene)
      - Si score >= umbral → equiv=True
      - Si score < umbral → equiv=False
    """
    n_corr_ap = 0  # A_Ap: original mal, guard bien
    n_reg_ap = 0   # A_Ap: original bien, guard mal
    n_reg_b = 0    # A_B: original bien, guard mal
    n_corr_b = 0   # A_B: original mal, guard bien
    n_abst = 0

    for (suite, pid, cond), guard in scores.items():
        if cond == "A_A":
            continue
        if cond == "A_App":
            continue

        score = guard.get("score", 0.0)
        abstain = guard.get("abstain_reason")
        equiv_original = guard.get("equiv")  # decisión con threshold 0.50

        # Si el guard abstuvo por compression, mantiene abstinencia
        if abstain == "response_too_long_for_grounding":
            n_abst += 1
            continue

        # Si el guard usó short_response heuristics (polarity/entity),
        # respetar su decisión original (es lógica, no de threshold)
        if abstain and "short_response" in abstain:
            # short_response_grounding_ok → equiv según threshold original
            # polarity_inversion → equiv=False
            # isolated_entity_abstain → abstiene
            if "polarity_inversion" in abstain:
                nuevo_equiv = False
            elif "isolated_entity" in abstain:
                n_abst += 1
                continue
            else:
                # short_response_grounding_ok: aplicar nuevo threshold
                nuevo_equiv = score >= umbral
        else:
            # Respuesta normal: aplicar threshold
            nuevo_equiv = score >= umbral

        gt = gt_map[cond]

        if cond == "A_Ap":
            # GT: equivalente → guard debería decir equiv=True
            if nuevo_equiv:
                pass  # correcto
            else:
                n_reg_ap += 1  # guard dice no-equiv cuando debería ser equiv
        elif cond == "A_B":
            # GT: no equivalente → guard debería decir equiv=False
            if nuevo_equiv:
                n_reg_b += 1  # guard dice equiv cuando debería ser no-equiv
            else:
                n_corr_b += 1  # guard correctamente dice no-equiv

    return {
        "n_corr_ap": n_corr_ap,
        "n_reg_ap": n_reg_ap,
        "n_corr_b": n_corr_b,
        "n_reg_b": n_reg_b,
        "n_abst": n_abst,
    }


# Barrido de umbral
print(f"{'umbral':>8} {'A_Ap_reg':>10} {'A_B_reg':>10} {'A_B_corr':>10} {'abst':>6} {'total_err':>10}")
print("-" * 60)

mejor = None
mejor_total_err = float("inf")

for u in [x / 100 for x in range(30, 96, 5)]:
    s = evaluar_con_umbral(GT, u)
    total_err = s["n_reg_ap"] + s["n_reg_b"]
    print(f"{u:>8.2f} {s['n_reg_ap']:>10d} {s['n_reg_b']:>10d} {s['n_corr_b']:>10d} {s['n_abst']:>6d} {total_err:>10d}")
    if total_err < mejor_total_err:
        mejor_total_err = total_err
        mejor = (u, s)

print(f"\nMejor umbral: {mejor[0]:.2f} (total_error={mejor_total_err})")
print(f"  A_Ap regresiones: {mejor[1]['n_reg_ap']}")
print(f"  A_B regresiones:  {mejor[1]['n_reg_b']}")
print(f"  A_B correcciones: {mejor[1]['n_corr_b']}")
print(f"  Abstenciones:     {mejor[1]['n_abst']}")
