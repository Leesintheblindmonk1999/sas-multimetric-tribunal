#!/usr/bin/env python3
"""auditoria_v6_forense.py — Auditoría forense de TODOS los números de la v6.

Verifica cada cifra del paper contra los reportes JSON fuente, como
haría un revisor serio (Arsentev-grade). Reporta discrepancias.

Chequeos:
  1. N1 matrix (audit n1 guard v4)
  2. Global metrics (original vs con guard)
  3. Recalibración v6 (multiplicativo vs promedio)
  4. Correlación longitud-ISI
  5. FinQA evaluation
  6. Wilson intervals
  7. Manifest hashes
"""

import hashlib
import json
import math
from pathlib import Path

REPORTS = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports")
V6 = Path(r"C:\Users\conno\Downloads\SAS-Semántico\papers\v6")

DISCR = []


def check(nombre, condicion, detalle=""):
    estado = "OK" if condicion else "DISCREPANCIA"
    print(f"  [{estado}] {nombre} {detalle}")
    if not condicion:
        DISCR.append((nombre, detalle))


def wilson(p, n, z=1.96):
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - margin, center + margin


print("=" * 72)
print("  AUDITORÍA FORENSE v6 — TODOS LOS NÚMEROS")
print("=" * 72)

# ── 1. N1 guard v4 audit ────────────────────────────────────────────
print("\n── 1. N1 audit (guard v4, threshold 0.95) ──")
audit = json.load(open(REPORTS / "audit_n1_guard_v3_20261013_125240.json", encoding="utf-8"))
m = audit["metricas_por_condicion"]

check("A_A 100% equiv", m["A_A"]["n_equiv_guard"] == 1800 and m["A_A"]["tasa_equiv_guard"] == 1.0,
      f"(guard_equiv={m['A_A']['n_equiv_guard']})")
check("A_Ap correcciones=1133", m["A_Ap"]["n_correcciones"] == 1133 and m["A_Ap"]["n_regresiones"] == 0,
      f"(corr={m['A_Ap']['n_correcciones']}, reg={m['A_Ap']['n_regresiones']})")
check("A_Ap guard_equiv=1364 (75.8%)",
      m["A_Ap"]["n_equiv_guard"] == 1364 and abs(m["A_Ap"]["tasa_equiv_guard"] - 0.7578) < 0.001,
      f"(equiv={m['A_Ap']['n_equiv_guard']}, tasa={m['A_Ap']['tasa_equiv_guard']:.4f})")
check("A_B regresiones=168",
      m["A_B"]["n_regresiones"] == 168,
      f"(reg={m['A_B']['n_regresiones']})")
check("A_B guard_equiv=204 (11.3%)",
      m["A_B"]["n_equiv_guard"] == 204 and abs(m["A_B"]["tasa_equiv_guard"] - 0.1133) < 0.001,
      f"(equiv={m['A_B']['n_equiv_guard']}, tasa={m['A_B']['tasa_equiv_guard']:.4f})")

# ── 2. Global metrics ────────────────────────────────────────────────
print("\n── 2. Global metrics ──")
g = audit["metricas_globales"]
check("Original FP=1569, Recall=0.98, F1=0.6873",
      g["original"]["fp"] == 1569 and abs(g["original"]["recall"] - 0.98) < 0.001
      and abs(g["original"]["f1"] - 0.6873) < 0.001,
      f"(FP={g['original']['fp']}, Recall={g['original']['recall']:.4f}, F1={g['original']['f1']:.4f})")
check("Guard FP=436, Recall=0.8867, F1=0.8330",
      g["con_guard"]["fp"] == 436 and abs(g["con_guard"]["recall"] - 0.8867) < 0.001
      and abs(g["con_guard"]["f1"] - 0.8330) < 0.001,
      f"(FP={g['con_guard']['fp']}, Recall={g['con_guard']['recall']:.4f}, F1={g['con_guard']['f1']:.4f})")

# ── 3. Recalibración v6 ──────────────────────────────────────────────
print("\n── 3. Recalibración v6 ──")
rc = json.load(open(REPORTS / "recalibracion_v6.json", encoding="utf-8"))
mult_fijo = rc["multiplicativo"]["fijo_kd056"]
mult_opt = rc["multiplicativo"]["optimizado"]
avg_opt = rc["promedio"]["optimizado"]

check("Mult fijo κD=0.56: TP=1764, FP=1569, F1=0.6873",
      mult_fijo["tp"] == 1764 and mult_fijo["fp"] == 1569 and abs(mult_fijo["f1"] - 0.6873) < 0.001,
      f"(TP={mult_fijo['tp']}, FP={mult_fijo['fp']}, F1={mult_fijo['f1']:.4f})")
check("Mult opt u=0.550: TP=1762, FP=1561, F1=0.6879",
      mult_opt["tp"] == 1762 and mult_opt["fp"] == 1561 and abs(mult_opt["f1"] - 0.6879) < 0.001,
      f"(TP={mult_opt['tp']}, FP={mult_opt['fp']}, F1={mult_opt['f1']:.4f})")
check("Avg opt u=0.830: TP=1735, FP=1461, F1=0.6946",
      avg_opt["tp"] == 1735 and avg_opt["fp"] == 1461 and abs(avg_opt["f1"] - 0.6946) < 0.001,
      f"(TP={avg_opt['tp']}, FP={avg_opt['fp']}, F1={avg_opt['f1']:.4f})")
check("ΔF1(opt vs opt) = -0.0067",
      abs(rc["delta_f1_opt_vs_opt"] - (-0.0067)) < 0.001,
      f"(Δ={rc['delta_f1_opt_vs_opt']:.4f})")

# ── 4. Correlación longitud-ISI ──────────────────────────────────────
print("\n── 4. Correlación longitud-ISI ──")
check("A_B r=+0.5996", abs(rc["longitud_isi"]["corr_b"] - 0.5996) < 0.001,
      f"(r={rc['longitud_isi']['corr_b']:.4f})")
check("A_Ap r=+0.8696", abs(rc["longitud_isi"]["corr_ap"] - 0.8696) < 0.001,
      f"(r={rc['longitud_isi']['corr_ap']:.4f})")

# ── 5. FinQA ─────────────────────────────────────────────────────────
print("\n── 5. FinQA evaluation ──")
fq = json.load(open(REPORTS / "evaluacion_finqa_guard.json", encoding="utf-8"))
check("A_B_cross: 208/239 noequiv (87.0%)",
      fq["A_B_cross"]["n_noequiv"] == 208 and abs(fq["A_B_cross"]["tasa_noequiv"] - 0.8703) < 0.01,
      f"(noequiv={fq['A_B_cross']['n_noequiv']}/{fq['A_B_cross']['n']})")
check("A_B_cross regresiones=0",
      fq["A_B_cross"]["n_equiv"] == 0,
      f"(equiv={fq['A_B_cross']['n_equiv']})")

# ── 6. Wilson intervals ──────────────────────────────────────────────
print("\n── 6. Wilson intervals ──")
lo1, hi1 = wilson(1569 / 1800, 1800)
lo2, hi2 = wilson(0.98, 1800)
print(f"  87.2% CI: [{lo1:.4f}, {hi1:.4f}]")
print(f"  98.0% CI: [{lo2:.4f}, {hi2:.4f}]")
check("No overlap", hi1 < lo2, f"(hi1={hi1:.4f} < lo2={lo2:.4f})")

# ── 7. Manifest hashes ───────────────────────────────────────────────
print("\n── 7. Manifest hashes ──")
manifest = json.load(open(V6 / "Manifest_hashes.json", encoding="utf-8"))
n_ok = 0
n_fail = 0
for dst, info in manifest["archivos"].items():
    with open(info["origen"], "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    if actual == info["sha256"]:
        n_ok += 1
    else:
        n_fail += 1
        print(f"  [FAIL] {dst}")
check(f"Manifest: {n_ok} OK / {n_fail} FAIL", n_fail == 0)

# ── Resumen ──────────────────────────────────────────────────────────
print("\n" + "=" * 72)
if DISCR:
    print(f"  DISCREPANCIAS: {len(DISCR)}")
    for nombre, detalle in DISCR:
        print(f"    • {nombre}: {detalle}")
else:
    print("  ✓ TODOS LOS NÚMEROS VERIFICADOS — CERO DISCREPANCIAS")
print("=" * 72)
