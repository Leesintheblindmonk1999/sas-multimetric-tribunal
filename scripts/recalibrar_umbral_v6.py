#!/usr/bin/env python3
"""recalibrar_umbral_v6.py — Recalibración v6: ambos esquemas con umbral optimizado.

Responde al punto 1 del revisor (Arsentev, 4ª ronda):
  "Table 8 is titled per-scheme calibration, but the multiplicative row stays
   at the fixed κD=0.56 while the weighted average gets an optimized 0.83."

Solución: barrer también el umbral del esquema multiplicativo sobre
A_B vs A_Ap, y reportar ambas filas como "optimized" (o "fixed").

Además calcula la medida que pide el punto 4 del revisor:
  ISI vs ratio de longitudes (response/source).

Salida: reports/recalibracion_v6.json
"""

import json
import sys
import hashlib
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Cargar N1 ──────────────────────────────────────────────────────────
N1 = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\pairs_conditions_1800_seed42.json")
d = json.load(open(N1, encoding="utf-8"))
r = d["resultados"]

positivos = {(x["suite"], x["id"]): x for x in r if x["condicion"] == "A_B"}
negativos = {(x["suite"], x["id"]): x for x in r if x["condicion"] == "A_Ap"}
identicos = {(x["suite"], x["id"]): x for x in r if x["condicion"] == "A_A"}
formato   = {(x["suite"], x["id"]): x for x in r if x["condicion"] == "A_App"}

ids = sorted(set(positivos.keys()) & set(negativos.keys()))
assert len(ids) == 1800

pos_final = np.array([positivos[k]["isi_final"] for k in ids])
neg_final = np.array([negativos[k]["isi_final"] for k in ids])
pos_avg   = np.array([positivos[k]["isi_avg"] for k in ids])
neg_avg   = np.array([negativos[k]["isi_avg"] for k in ids])


def f1_at(y_pos, y_neg, umbral):
    """F1 tratando 'score < umbral' como detección de alucinación."""
    tp = int((y_pos < umbral).sum())
    fn = int((y_pos >= umbral).sum())
    fp = int((y_neg < umbral).sum())
    tn = int((y_neg >= umbral).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "precision": round(prec, 6), "recall": round(rec, 6),
            "f1": round(f1, 6), "umbral": round(float(umbral), 6)}


def mejor_umbral(y_pos, y_neg, paso=0.005):
    mejor = None
    mejor_f1 = -1.0
    for u in np.arange(0.01, 0.99, paso):
        res = f1_at(y_pos, y_neg, u)
        if res["f1"] > mejor_f1:
            mejor_f1 = res["f1"]
            mejor = res
    return mejor


def auc_aprox(y_pos, y_neg):
    """AUROC simple: proporción de pares donde pos < neg."""
    n = 0
    ties = 0
    for p in y_pos:
        for q in y_neg:
            if p < q:
                n += 1
            elif p == q:
                ties += 0.5
    n_pairs = len(y_pos) * len(y_neg)
    return (n + ties) / n_pairs


print("=" * 72)
print("  RECALIBRACIÓN v6 — responde punto 1 de Arsentev")
print("=" * 72)

# ── Multiplicativo: umbral fijo κD=0.56 ────────────────────────────────
mult_fijo = f1_at(pos_final, neg_final, 0.56)
mult_fijo_auc = auc_aprox(pos_final, neg_final)

# ── Multiplicativo: umbral optimizado ──────────────────────────────────
mult_opt = mejor_umbral(pos_final, neg_final)
mult_opt_auc = auc_aprox(pos_final, neg_final)  # AUROC no depende del umbral

# ── Promedio: umbral fijo κD=0.56 (para comparación justa) ─────────────
avg_fijo = f1_at(pos_avg, neg_avg, 0.56)
avg_fijo_auc = auc_aprox(pos_avg, neg_avg)

# ── Promedio: umbral optimizado ────────────────────────────────────────
avg_opt = mejor_umbral(pos_avg, neg_avg)
avg_opt_auc = auc_aprox(pos_avg, neg_avg)

print(f"\n── Esquema MULTIPLICATIVO (isi_final) ──")
print(f"  Fijo κD=0.56      → F1={mult_fijo['f1']:.4f}  (TP={mult_fijo['tp']}, FP={mult_fijo['fp']})")
print(f"  Optimizado u={mult_opt['umbral']:.3f} → F1={mult_opt['f1']:.4f}  (TP={mult_opt['tp']}, FP={mult_opt['fp']})")
print(f"  AUROC = {mult_fijo_auc:.4f}")
print(f"\n── Esquema PROMEDIO (isi_avg) ──")
print(f"  Fijo κD=0.56      → F1={avg_fijo['f1']:.4f}  (TP={avg_fijo['tp']}, FP={avg_fijo['fp']})")
print(f"  Optimizado u={avg_opt['umbral']:.3f} → F1={avg_opt['f1']:.4f}  (TP={avg_opt['tp']}, FP={avg_opt['fp']})")
print(f"  AUROC = {avg_opt_auc:.4f}")

print(f"\n── Gap original (v4): 87.97 F1 ──")
print(f"  Multiplicativo optimizado vs promedio optimizado: ΔF1 = {mult_opt['f1'] - avg_opt['f1']:+.4f}")
print(f"  Multiplicativo fijo vs promedio optimizado:       ΔF1 = {mult_fijo['f1'] - avg_opt['f1']:+.4f}")

# ── Punto 4: ISI vs ratio de longitud ─────────────────────────────────
print(f"\n── Punto 4: relación entre ISI y ratio de longitudes ──")

# Cargar textos del corpus para calcular longitud real
CORPUS = Path(r"C:\ProgramData\benchmark_corpus")
SUITES = ["halueval_dialogue", "halueval_qa", "truthfulqa"]
TEXTO = {}
for suite in SUITES:
    suite_dir = CORPUS / suite
    for cf in sorted(suite_dir.glob("*_A_clean.txt")):
        hf = cf.with_name(cf.name.replace("_A_clean.txt", "_B_hallucination.txt"))
        if not hf.exists():
            continue
        a = cf.read_text(encoding="utf-8", errors="replace").strip()
        b = hf.read_text(encoding="utf-8", errors="replace").strip()
        pid = cf.name.replace("_A_clean.txt", "")
        TEXTO[(suite, pid)] = (a, b)

# Ratios de longitud por condición
ratios_b = []
ratios_ap = []
ratios_app = []
isi_b = []
isi_ap = []

for suite, pid in ids:
    a, b = TEXTO.get((suite, pid), ("", ""))
    ra = len(a) if a else 1
    rb = len(b)
    b_entry = positivos[(suite, pid)]
    ap_entry = negativos[(suite, pid)]
    app_entry = formato[(suite, pid)]

    # Ratio para A_B: len(B)/len(A)
    ratios_b.append(rb / ra)
    isi_b.append(b_entry["isi_final"])

    # Ratio para A_Ap: len(A')/len(A) — dividir A
    # A' = después del marcador
    marcadores = {
        "halueval_dialogue": "Correct response: ",
        "halueval_qa": "Correct answer: ",
        "truthfulqa": "Correct answer: ",
    }
    idx = a.find(marcadores[suite])
    ap_len = len(a[idx + len(marcadores[suite]):].strip()) if idx >= 0 else rb
    ratios_ap.append(ap_len / ra)
    isi_ap.append(ap_entry["isi_final"])

corr_b = np.corrcoef(ratios_b, isi_b)[0, 1]
corr_ap = np.corrcoef(ratios_ap, isi_ap)[0, 1]

print(f"  A_B:  corr(ratio_longitud, ISI_final) = {corr_b:+.4f}")
print(f"  A_Ap: corr(ratio_longitud, ISI_final) = {corr_ap:+.4f}")

# ── Guardar resultado ──────────────────────────────────────────────────
salida = {
    "version": "v6",
    "fecha": "2026-10-13",
    "multiplicativo": {
        "fijo_kd056": mult_fijo,
        "optimizado": mult_opt,
        "auc": round(mult_fijo_auc, 6),
    },
    "promedio": {
        "fijo_kd056": avg_fijo,
        "optimizado": avg_opt,
        "auc": round(avg_opt_auc, 6),
    },
    "gap_v4_original": 87.97,
    "delta_f1_opt_vs_opt": round(mult_opt["f1"] - avg_opt["f1"], 6),
    "longitud_isi": {
        "corr_b": round(corr_b, 6),
        "corr_ap": round(corr_ap, 6),
        "n": len(ids),
    },
}

out = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\recalibracion_v6.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(salida, f, indent=2, ensure_ascii=False)

h = hashlib.sha256(out.read_bytes()).hexdigest()
print(f"\nGuardado: {out}")
print(f"SHA-256: {h}")

salida["sha256"] = h
with open(out, "w", encoding="utf-8") as f:
    json.dump(salida, f, indent=2, ensure_ascii=False)

print("\nDONE")
