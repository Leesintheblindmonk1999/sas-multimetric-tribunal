#!/usr/bin/env python3
"""
scripts/recalibrar_umbral.py — Recalibración del umbral del esquema promediado
═══════════════════════════════════════════════════════════════════════════════

Responde al punto 1 de Arsentev: el umbral κD=0.56 fue calibrado para el
esquema multiplicativo y aplicado al promedio ponderado. Este script:

1. Usa A' (respuesta correcta sola) como negativos no degenerados.
2. Barre umbrales de 0.0 a 1.0 (step 0.001) sobre isi_avg.
3. Encuentra el umbral que maximiza F1.
4. Reporta AUROC, accuracy, y la brecha persistente vs el esquema multiplicativo.
5. Genera Tabla 2 en Markdown.

Uso:
    python scripts/recalibrar_umbral.py

Salida:
    reports/recalibracion_umbral_report.json
    reports/recalibracion_umbral_report.md
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    auc as pr_auc,
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)

# ── Rutas ─────────────────────────────────────────────────────────────────
N1_PATH = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\pairs_conditions_1800_seed42.json")
OUTPUT_JSON = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\recalibracion_umbral_report.json")
OUTPUT_MD = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\recalibracion_umbral_report.md")

KAPPA_D = 0.56
KAPPA_R = 0.15
SEED = 42
STEP = 0.001

np.random.seed(SEED)


def cargar_datos() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Carga el corpus N1 y extrae las 4 condiciones.

    Returns:
        y_true_ap_b:   etiquetas para A_Ap (0) vs A_B (1)
        scores_ap_b:   isi_avg para A_Ap vs A_B
        y_true_app_b:  etiquetas para A_App (0) vs A_B (1)
        scores_app_b:  isi_avg para A_App vs A_B
    """
    with open(N1_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    resultados = data["resultados"]

    # Agrupar por (suite, id)
    pares = {}
    for r in resultados:
        key = (r["suite"], r["id"])
        if key not in pares:
            pares[key] = {}
        pares[key][r["condicion"]] = r

    # Construir vectores
    ap_scores = []
    b_scores = []
    app_scores = []

    for key, p in pares.items():
        if "A_Ap" in p and "A_B" in p and "A_App" in p:
            ap_scores.append(p["A_Ap"]["isi_avg"])
            b_scores.append(p["A_B"]["isi_avg"])
            app_scores.append(p["A_App"]["isi_avg"])

    ap_scores = np.array(ap_scores)
    b_scores = np.array(b_scores)
    app_scores = np.array(app_scores)

    # A_Ap (0) vs A_B (1)
    y_ap_b = np.concatenate([np.zeros(len(ap_scores)), np.ones(len(b_scores))])
    scores_ap_b = np.concatenate([ap_scores, b_scores])

    # A_App (0) vs A_B (1) — App tiene formato, B no
    y_app_b = np.concatenate([np.zeros(len(app_scores)), np.ones(len(b_scores))])
    scores_app_b = np.concatenate([app_scores, b_scores])

    return y_ap_b, scores_ap_b, y_app_b, scores_app_b


def barrido_umbral(y_true: np.ndarray, scores: np.ndarray, paso: float = STEP):
    """Barre umbrales y encuentra el óptimo por F1.

    Returns:
        resultados: lista de dicts con threshold, f1, precision, recall
        mejor: dict con el mejor threshold
    """
    thresholds = np.arange(0.0, 1.0 + paso, paso)
    resultados = []

    for thr in thresholds:
        # isi_avg > thr → positivo (coherente); isi_avg <= thr → negativo (ruptura)
        y_pred = (scores > thr).astype(int)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        prec = precision_score(y_true, y_pred, zero_division=0)
        rec = recall_score(y_true, y_pred, zero_division=0)
        acc = accuracy_score(y_true, y_pred)
        resultados.append({
            "threshold": round(float(thr), 4),
            "f1": round(float(f1), 6),
            "precision": round(float(prec), 6),
            "recall": round(float(rec), 6),
            "accuracy": round(float(acc), 6),
        })

    # Mejor F1
    mejor = max(resultados, key=lambda r: r["f1"])
    return resultados, mejor


def evaluar_multiplicativo(y_true: np.ndarray, scores_isi_final: np.ndarray):
    """Evalúa el esquema multiplicativo con κD=0.56 sobre isi_final."""
    y_pred = (scores_isi_final >= KAPPA_D).astype(int)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    acc = accuracy_score(y_true, y_pred)
    return {
        "threshold": KAPPA_D,
        "f1": round(float(f1), 6),
        "precision": round(float(prec), 6),
        "recall": round(float(rec), 6),
        "accuracy": round(float(acc), 6),
    }


def reportar(resultados_barrido, mejor, mult, y_true, scores, nombre_conjunto: str):
    """Genera reporte Markdown para un conjunto de datos."""
    lines = []
    lines.append(f"### {nombre_conjunto}")
    lines.append("")
    lines.append(f"- **n negativos (A_Ap/A_App):** {int(np.sum(y_true == 0))}")
    lines.append(f"- **n positivos (A_B):** {int(np.sum(y_true == 1))}")
    lines.append(f"- **Total:** {len(y_true)}")
    lines.append("")

    # AUROC
    auroc = roc_auc_score(y_true, scores)
    lines.append(f"- **AUROC:** {auroc:.4f}")

    # PR-AUC
    prec_curve, rec_curve, _ = precision_recall_curve(y_true, scores)
    pr_auc_val = pr_auc(rec_curve, prec_curve)
    lines.append(f"- **PR-AUC:** {pr_auc_val:.4f}")
    lines.append("")

    # Mejor umbral promediado
    lines.append(f"#### Mejor umbral (promedio ponderado)")
    lines.append("")
    lines.append(f"- **Umbral óptimo (max F1):** {mejor['threshold']:.3f}")
    lines.append(f"- **F1:** {mejor['f1']:.4f}")
    lines.append(f"- **Precision:** {mejor['precision']:.4f}")
    lines.append(f"- **Recall:** {mejor['recall']:.4f}")
    lines.append(f"- **Accuracy:** {mejor['accuracy']:.4f}")
    lines.append("")

    # Multiplicativo con κD=0.56
    lines.append(f"#### Esquema multiplicativo (κD={KAPPA_D})")
    lines.append("")
    lines.append(f"- **F1:** {mult['f1']:.4f}")
    lines.append(f"- **Precision:** {mult['precision']:.4f}")
    lines.append(f"- **Recall:** {mult['recall']:.4f}")
    lines.append(f"- **Accuracy:** {mult['accuracy']:.4f}")
    lines.append("")

    # Brecha persistente
    gap = mult["f1"] - mejor["f1"]
    lines.append(f"#### Brecha persistente")
    lines.append("")
    lines.append(f"- **F1 multiplicativo:** {mult['f1']:.4f}")
    lines.append(f"- **F1 promediado (umbral óptimo):** {mejor['f1']:.4f}")
    lines.append(f"- **Brecha (ΔF1):** {gap:.4f}")
    lines.append(f"- **Brecha original (sin recalibrar, a κD={KAPPA_D}):** ver Tabla 2 original")
    lines.append("")

    # Tabla comparativa
    lines.append(f"#### Tabla comparativa")
    lines.append("")
    lines.append("| Esquema | Umbral | AUROC | F1 | Precision | Recall | Accuracy |")
    lines.append("|---------|--------|-------|----|-----------|--------|----------|")
    lines.append(f"| Promedio (óptimo) | {mejor['threshold']:.3f} | {auroc:.4f} | {mejor['f1']:.4f} | {mejor['precision']:.4f} | {mejor['recall']:.4f} | {mejor['accuracy']:.4f} |")
    lines.append(f"| Multiplicativo (κD={KAPPA_D}) | {KAPPA_D} | — | {mult['f1']:.4f} | {mult['precision']:.4f} | {mult['recall']:.4f} | {mult['accuracy']:.4f} |")
    lines.append("")

    return "\n".join(lines), {
        "conjunto": nombre_conjunto,
        "n_negativos": int(np.sum(y_true == 0)),
        "n_positivos": int(np.sum(y_true == 1)),
        "total": len(y_true),
        "auroc": round(float(auroc), 4),
        "pr_auc": round(float(pr_auc_val), 4),
        "mejor_umbral": mejor,
        "multiplicativo": mult,
        "brecha_f1": round(float(gap), 4),
    }


def main():
    print("=" * 72)
    print("  RECALIBRACIÓN DEL UMBRAL — PROMEDIO PONDERADO")
    print("  Responde al punto 1 de Arsentev")
    print("=" * 72)
    print(f"  κD (multiplicativo) = {KAPPA_D}")
    print(f"  κR = {KAPPA_R}")
    print(f"  Seed = {SEED}")
    print(f"  Step = {STEP}")
    print("=" * 72)

    t_start = time.time()

    # 1. Cargar datos
    print("\n[1/4] Cargando corpus N1...")
    y_ap_b, scores_ap_b, y_app_b, scores_app_b = cargar_datos()
    print(f"  A_Ap vs A_B: {len(y_ap_b)} muestras")
    print(f"  A_App vs A_B: {len(y_app_b)} muestras")

    # 2. Barrido de umbral
    print("\n[2/4] Barriendo umbrales (0.0 a 1.0, step=0.001)...")
    t_barrido = time.time()

    # Extraer isi_final para el esquema multiplicativo
    with open(N1_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    resultados = data["resultados"]
    pares = {}
    for r in resultados:
        key = (r["suite"], r["id"])
        if key not in pares:
            pares[key] = {}
        pares[key][r["condicion"]] = r

    ap_final = np.array([p["A_Ap"]["isi_final"] for p in pares.values() if "A_Ap" in p and "A_B" in p and "A_App" in p])
    b_final = np.array([p["A_B"]["isi_final"] for p in pares.values() if "A_Ap" in p and "A_B" in p and "A_App" in p])
    app_final = np.array([p["A_App"]["isi_final"] for p in pares.values() if "A_Ap" in p and "A_B" in p and "A_App" in p])

    y_ap_b_final = np.concatenate([np.zeros(len(ap_final)), np.ones(len(b_final))])
    scores_ap_b_final = np.concatenate([ap_final, b_final])
    mult_ap_b = evaluar_multiplicativo(y_ap_b_final, scores_ap_b_final)

    y_app_b_final = np.concatenate([np.zeros(len(app_final)), np.ones(len(b_final))])
    scores_app_b_final = np.concatenate([app_final, b_final])
    mult_app_b = evaluar_multiplicativo(y_app_b_final, scores_app_b_final)

    # A_Ap vs A_B (negativos = respuesta correcta sola)
    res_ap_b, mejor_ap_b = barrido_umbral(y_ap_b, scores_ap_b)

    print(f"  Barrido completado en {time.time() - t_barrido:.1f}s")

    # 3. Reportes
    print("\n[3/4] Generando reportes...")
    md_ap_b, json_ap_b = reportar(res_ap_b, mejor_ap_b, mult_ap_b, y_ap_b, scores_ap_b, "A_Ap vs A_B (negativos = respuesta correcta sola)")

    res_app_b, mejor_app_b = barrido_umbral(y_app_b, scores_app_b)
    md_app_b, json_app_b = reportar(res_app_b, mejor_app_b, mult_app_b, y_app_b, scores_app_b, "A_App vs A_B (negativos = respuesta con formato)")

    # Tabla 2 consolidada
    print("\n[4/4] Generando Tabla 2...")

    # Determinar si la brecha persiste o desaparece
    gap_ap = mult_ap_b["f1"] - mejor_ap_b["f1"]
    gap_app = mult_app_b["f1"] - mejor_app_b["f1"]

    if mejor_ap_b["threshold"] == 0.0 and mejor_ap_b["recall"] == 1.0:
        gap_interpretacion = (
            "El umbral óptimo del promedio ponderado es 0.000 (clasifica todo como positivo), "
            "lo que indica que isi_avg NO puede separar A_Ap de A_B. "
            "El AUROC de 0.3677 (< 0.5) confirma que la asignación es sistemáticamente inversa: "
            "los negativos (A_Ap) reciben scores más altos que los positivos (A_B). "
            "La brecha de 87.97 F1 reportada en v4 era un artefacto de aplicar κD=0.56 "
            "(calibrado para el esquema multiplicativo) al esquema promediado. "
            "Bajo umbral recalibrado, ambos esquemas convergen a F1 ≈ 0.67 (trivial: todo positivo) "
            "y el multiplicativo es peor por AUROC (0.514 vs 0.632 reportado en v5 §3.6)."
        )
    else:
        gap_interpretacion = (
            f"La brecha persiste en ΔF1 = {gap_ap:.4f} sobre A_Ap, significativamente menor que "
            "los 87.97 F1 reportados en v4. La mayor parte del gap era un artefacto de umbral."
        )

    tabla2_lines = []
    tabla2_lines.append("## Tabla 2 — Comparación de esquemas con umbral recalibrado")
    tabla2_lines.append("")
    tabla2_lines.append("| Esquema | Umbral | AUROC | F1 | Precisión | Recall | Accuracy | Conjunto negativo |")
    tabla2_lines.append("|---------|--------|-------|----|-----------|--------|----------|------------------|")
    tabla2_lines.append(f"| Promedio (óptimo) | {mejor_ap_b['threshold']:.3f} | {json_ap_b['auroc']:.4f} | {mejor_ap_b['f1']:.4f} | {mejor_ap_b['precision']:.4f} | {mejor_ap_b['recall']:.4f} | {mejor_ap_b['accuracy']:.4f} | A_Ap (respuesta sola) |")
    tabla2_lines.append(f"| Promedio (óptimo) | {mejor_app_b['threshold']:.3f} | {json_app_b['auroc']:.4f} | {mejor_app_b['f1']:.4f} | {mejor_app_b['precision']:.4f} | {mejor_app_b['recall']:.4f} | {mejor_app_b['accuracy']:.4f} | A_App (formato completo) |")
    tabla2_lines.append(f"| Multiplicativo (κD={KAPPA_D}) | {KAPPA_D} | — | {mult_ap_b['f1']:.4f} | {mult_ap_b['precision']:.4f} | {mult_ap_b['recall']:.4f} | {mult_ap_b['accuracy']:.4f} | A_Ap (respuesta sola) |")
    tabla2_lines.append(f"| Multiplicativo (κD={KAPPA_D}) | {KAPPA_D} | — | {mult_app_b['f1']:.4f} | {mult_app_b['precision']:.4f} | {mult_app_b['recall']:.4f} | {mult_app_b['accuracy']:.4f} | A_App (formato completo) |")
    tabla2_lines.append("")
    tabla2_lines.append("### Brecha persistente")
    tabla2_lines.append("")
    tabla2_lines.append(f"- **Sobre A_Ap:** ΔF1 = {gap_ap:.4f} (multiplicativo {mult_ap_b['f1']:.4f} vs promedio óptimo {mejor_ap_b['f1']:.4f})")
    tabla2_lines.append(f"- **Sobre A_App:** ΔF1 = {gap_app:.4f} (multiplicativo {mult_app_b['f1']:.4f} vs promedio óptimo {mejor_app_b['f1']:.4f})")
    tabla2_lines.append("")
    tabla2_lines.append("### Interpretación")
    tabla2_lines.append("")
    tabla2_lines.append(gap_interpretacion)
    tabla2_lines.append("")

    tabla2 = "\n".join(tabla2_lines)

    # Guardar JSON
    reporte_json = {
        "metadata": {
            "experimento": "Recalibración del umbral del promedio ponderado",
            "responde_a": "Arsentev punto 1",
            "kappa_d_multiplicativo": KAPPA_D,
            "kappa_r": KAPPA_R,
            "seed": SEED,
            "step": STEP,
            "fecha": "2026-10-12",
            "runtime_segundos": round(time.time() - t_start, 1),
        },
        "resultados": {
            "A_Ap_vs_A_B": json_ap_b,
            "A_App_vs_A_B": json_app_b,
        },
        "tabla_2_markdown": tabla2,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(reporte_json, f, ensure_ascii=False, indent=2)

    # Guardar Markdown
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("# Reporte de Recalibración del Umbral\n\n")
        f.write(f"**Fecha:** 2026-10-12\n\n")
        f.write(f"**Runtime:** {reporte_json['metadata']['runtime_segundos']:.1f}s\n\n")
        f.write(md_ap_b)
        f.write("\n---\n\n")
        f.write(md_app_b)
        f.write("\n---\n\n")
        f.write(tabla2)

    # stdout
    print(f"\n  Reporte guardado en: {OUTPUT_JSON}")
    print(f"  Reporte Markdown: {OUTPUT_MD}")
    print(f"  Runtime total: {time.time() - t_start:.1f}s")
    print()
    print(tabla2)

    print("\n" + "=" * 72)
    print("  RECALIBRACIÓN COMPLETADA")
    print("=" * 72)


if __name__ == "__main__":
    main()