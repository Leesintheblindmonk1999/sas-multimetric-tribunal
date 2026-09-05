#!/usr/bin/env python3
"""
scripts/29_evaluar_calibracion.py — Ejecuta el tribunal sobre el split de calibración
======================================================================================
Corre el tribunal actual (v1.0.1 + v1.2 de reference_penalty) SOLO sobre el
split de calibración (686 pares) y reporta:

  - Histograma de valores de reference_penalty en positivos vs negativos
  - ¿El umbral actual (fired = fab>0 or anac>0, binario) separa bien las clases?
  - ¿Hace falta revisar REFERENCE_PENALTY_BASE o MAX_PENALTY_FLOOR?

NO toca el split de test. NO modifica ningún core/*.py.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
CORPUS = BASE / "research" / "cite_calibration" / "corpus" / "corpus_calibracion.jsonl"
TRIBUNAL = BASE / "SAS" / "SAS" / "core" / "tribunal_multimetrico.py"


def cargar_tribunal():
    core_dir = TRIBUNAL.parent
    sys.path.insert(0, str(core_dir.parent))
    spec = importlib.util.spec_from_file_location("tribunal_multimetrico", TRIBUNAL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    tribunal = mod.TribunalMultimetrico()
    cargados = getattr(tribunal, "_modulos_cargados", {})
    faltantes = [k for k, v in cargados.items() if not v]
    if faltantes:
        print(f"[ERROR] Submódulos NO cargados: {faltantes}")
        sys.exit(1)
    print(f"[OK] Tribunal cargado. Submódulos OK: {list(cargados.keys())}")
    return tribunal


def main():
    pares = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pares.append(json.loads(line))
    print(f"[INFO] {len(pares)} pares del split de calibración")

    tribunal = cargar_tribunal()

    # Clasificar por ground truth
    positivos = [p for p in pares if p["mutation_type"] != "control"]
    negativos = [p for p in pares if p["mutation_type"] == "control"]
    print(f"  Positivos: {len(positivos)}, Negativos: {len(negativos)}")

    # Evaluar
    resultados = []
    for p in pares:
        v = tribunal.evaluar(p["source"], p["response"])
        fired = [m.nombre for m in v.modulos_disparados]
        ref_fired = "reference_penalty" in fired
        # Valor del módulo reference_penalty del veredicto
        ref_val = v.reference_penalty
        resultados.append({
            "id": p["id"],
            "mutation_type": p["mutation_type"],
            "es_positivo": p["mutation_type"] != "control",
            "reference_penalty_fired": ref_fired,
            "reference_penalty_valor": ref_val,
            "isi_final": v.isi_final,
            "zona": v.codigo_zona,
            "fired": fired,
        })

    # ── Análisis ────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("ANÁLISIS — separación de clases por reference_penalty")
    print(f"{'='*70}")

    # Binario: ¿el umbral actual dispara en positivos y no en negativos?
    tp = sum(1 for r in resultados if r["es_positivo"] and r["reference_penalty_fired"])
    fn = sum(1 for r in resultados if r["es_positivo"] and not r["reference_penalty_fired"])
    fp = sum(1 for r in resultados if not r["es_positivo"] and r["reference_penalty_fired"])
    tn = sum(1 for r in resultados if not r["es_positivo"] and not r["reference_penalty_fired"])

    recall = tp / (tp + fn) if (tp + fn) else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) else 0

    print(f"\n[UMBRAL BINARIO ACTUAL] fired = fabricated_count>0 or anachronistic_count>0")
    print(f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}")
    print(f"  Recall={recall:.3f}  Precision={precision:.3f}  F1={f1:.3f}")

    # Histograma de valores de reference_penalty
    print(f"\n[HISTOGRAMA] valor de reference_penalty (1.0 = no dispara):")
    bins = Counter()
    for r in resultados:
        v = r["reference_penalty_valor"]
        if v >= 0.999:
            b = "1.00 (sin disparo)"
        elif v >= 0.75:
            b = "0.75-0.99"
        elif v >= 0.56:
            b = "0.56-0.75"
        else:
            b = "<0.56"
        bins[b] += 1
    for b in ["1.00 (sin disparo)", "0.75-0.99", "0.56-0.75", "<0.56"]:
        print(f"  {b}: {bins.get(b, 0)}")

    # Positivos vs negativos en cada bin
    print(f"\n[POSITIVOS vs NEGATIVOS por bin]:")
    for b in ["1.00 (sin disparo)", "0.75-0.99", "0.56-0.75", "<0.56"]:
        n_pos = sum(1 for r in resultados if r["es_positivo"] and
                    (r["reference_penalty_valor"] >= 0.999 if b == "1.00 (sin disparo)" else
                     0.75 <= r["reference_penalty_valor"] < 0.999 if b == "0.75-0.99" else
                     0.56 <= r["reference_penalty_valor"] < 0.75 if b == "0.56-0.75" else
                     r["reference_penalty_valor"] < 0.56))
        n_neg = sum(1 for r in resultados if not r["es_positivo"] and
                    (r["reference_penalty_valor"] >= 0.999 if b == "1.00 (sin disparo)" else
                     0.75 <= r["reference_penalty_valor"] < 0.999 if b == "0.75-0.99" else
                     0.56 <= r["reference_penalty_valor"] < 0.75 if b == "0.56-0.75" else
                     r["reference_penalty_valor"] < 0.56))
        print(f"  {b}: pos={n_pos} neg={n_neg}")

    # ¿Dónde falla el recall? Desglose por tipo de mutación
    print(f"\n[RECALL por tipo de mutación]:")
    for mut_type in ["same_author_diff_year", "same_year_diff_author"]:
        grupo = [r for r in resultados if r["mutation_type"] == mut_type]
        n_fire = sum(1 for r in grupo if r["reference_penalty_fired"])
        print(f"  {mut_type}: {n_fire}/{len(grupo)} = {100*n_fire/len(grupo):.1f}%")

    # Guardar
    out = BASE / "research" / "cite_calibration" / "resultados_calibracion.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "resumen": {
                "n": len(resultados),
                "tp": tp, "fn": fn, "fp": fp, "tn": tn,
                "recall": round(recall, 4), "precision": round(precision, 4), "f1": round(f1, 4),
            },
            "detalle": resultados,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Guardado en {out}")


if __name__ == "__main__":
    main()