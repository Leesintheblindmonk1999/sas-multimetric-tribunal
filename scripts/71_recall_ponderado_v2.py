#!/usr/bin/env python3
"""scripts/71_recall_ponderado_v2.py — Recalcula el recall ponderado con la precisión corregida (32/45)

Corrección aprobada de la Tarea 2:
  - Precisión consolidada: 32/45 = 71.1% (era 30/45 = 66.7% — error de suma)
  - TP_estimado = 62 × (32/45)
  - FN_estimado = 138 × (1/60)  [FN sample duplicado de 30 a 60, script 88]
  - recall = TP_estimado / (TP_estimado + FN_estimado)
  - Rango de sensibilidad con 2 FN hipotéticos: FN_est = 138 × (2/60)

Regenera reports/t1_recall_ponderado.json sobreescribiendo el viejo.
"""
import json
from datetime import date
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")

# ── Corrección aprobada (Tarea 2, re-verificada independientemente) ──
# Precisión consolidada sobre 45 disparos clasificados: 32 reales / 13 espurios
TP_MUESTRA = 32
N_TP_MUESTRA = 45
FN_MUESTRA = 1
N_FN_MUESTRA = 60  # duplicado de 30 a 60 (script 88_tanda_30_fn_negation.py)
N_DISPARARON = 62
N_NO_DISPARARON = 138

# ── Recall ponderado con precisión corregida ──
TP_estimado = N_DISPARARON * (TP_MUESTRA / N_TP_MUESTRA)
FN_estimado = N_NO_DISPARARON * (FN_MUESTRA / N_FN_MUESTRA)
recall = TP_estimado / (TP_estimado + FN_estimado)

# ── Sensibilidad con 2 FN hipotéticos ──
FN_estimado_2 = N_NO_DISPARARON * (2 / N_FN_MUESTRA)
recall_2fn = TP_estimado / (TP_estimado + FN_estimado_2)

print("=" * 70)
print("RECALL PONDERADO — precisión corregida 32/45")
print("=" * 70)
print(f"TP_estimado = 62 × (32/45) = {TP_estimado:.4f}")
print(f"FN_estimado = 138 × (1/60) = {FN_estimado:.4f}")
print(f"recall = {TP_estimado:.4f} / ({TP_estimado:.4f} + {FN_estimado:.4f}) = {recall:.4f} = {100*recall:.1f}%")
print()
print(f"Sensibilidad (2 FN hipotéticos):")
print(f"  FN_est = 138 × (2/60) = {FN_estimado_2:.4f}")
print(f"  recall = {TP_estimado:.4f} / ({TP_estimado:.4f} + {FN_estimado_2:.4f}) = {recall_2fn:.4f} = {100*recall_2fn:.1f}%")
print(f"  Rango: {100*min(recall, recall_2fn):.1f}%–{100*max(recall, recall_2fn):.1f}%")

# ── Desglose por subtipo (corregido) ──
subtipos = {
    "primalidad": {"n": 26, "n_a": 22, "prec": 0.846},
    "vuelos": {"n": 9, "n_a": 6, "prec": 0.667},
    "senador": {"n": 10, "n_a": 4, "prec": 0.400},
}
print()
print("Desglose por subtipo (corregido):")
for s, d in subtipos.items():
    print(f"  {s}: n={d['n']} reales={d['n_a']} espurios={d['n']-d['n_a']} precisión={100*d['prec']:.1f}%")

# ── Guardar JSON (sobreescribe) ──
out = {
    "fecha": str(date.today()),
    "precision_corregida": "32/45 = 71.1% (nota: reemplaza 30/45 = 66.7%, que tenía errores de suma en tandas 1-3; las clasificaciones individuales por ID estaban bien)",
    "recall_ponderado": {
        "TP_estimado": round(TP_estimado, 4),
        "FN_estimado": round(FN_estimado, 4),
        "recall": round(recall, 4),
        "recall_pct": round(100 * recall, 1),
    },
    "sensibilidad_2fn": {
        "FN_estimado": round(FN_estimado_2, 4),
        "recall": round(recall_2fn, 4),
        "recall_pct": round(100 * recall_2fn, 1),
    },
    "rango": f"{round(100*min(recall, recall_2fn), 1)}%–{round(100*max(recall, recall_2fn), 1)}%",
    "inputs": {
        "n_dispararon": N_DISPARARON,
        "n_no_dispararon": N_NO_DISPARARON,
        "tp_muestra": TP_MUESTRA,
        "n_tp_muestra": N_TP_MUESTRA,
        "fn_muestra": FN_MUESTRA,
        "n_fn_muestra": N_FN_MUESTRA,
    },
    "desglose_subtipos": {
        s: {"n": d["n"], "reales": d["n_a"], "espurios": d["n"] - d["n_a"], "precision": round(100 * d["prec"], 1)}
        for s, d in subtipos.items()
    },
}
out_path = BASE / "reports" / "t1_recall_ponderado.json"
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
print(f"\n[OK] Sobreescrito {out_path}")