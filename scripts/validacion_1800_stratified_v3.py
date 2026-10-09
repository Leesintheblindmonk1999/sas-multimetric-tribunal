#!/usr/bin/env python3
"""
scripts/validacion_1800_stratified_v3.py — Validación estratificada 1,800+1,800 con core actual

Estructura: 600 alucinaciones + 600 controles por suite (3 suites) = 1,800 + 1,800.
Muestra: sorted(glob(...)) + random.Random(42).sample(..., 600) por suite.
Core: actual (tribunal v1.0.1 + negation v1.3 + reference v1.3).

Registry: EX-2026-18792778 (TAD, Argentina)
Author: Gonzalo Emir Durante — Project Manifold 0.56
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Tuple

# Core real — el path debe ser el PADRE de core/ para que los imports
# absolutos internos (from core.X import Y) resuelvan.
CORE_PARENT = Path(r"C:\Users\conno\Downloads\SAS-Semántico\SAS\SAS")
sys.path.insert(0, str(CORE_PARENT))

from core.tribunal_multimetrico import (
    TribunalMultimetrico,
    ZonaEstructural,
    KAPPA_D,
)

CORPUS = Path(r"C:\ProgramData\benchmark_corpus")
SUITES = ["halueval_dialogue", "halueval_qa", "truthfulqa"]
N_PER_SUITE = 600
SEED = 42  # override con --seed
KAPPA_R = 0.15

import argparse

def parse_args():
    p = argparse.ArgumentParser(description="Validación estratificada 1,800+1,800")
    p.add_argument("--seed", type=int, default=42, help="Seed para la muestra estratificada")
    p.add_argument("--output", type=str, default=None, help="Ruta JSON de salida (default: reports/validacion_1800_stratified_v3.json)")
    return p.parse_args()


def cargar_muestra_estratificada() -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], List[dict]]:
    """Carga 600 pares por suite con sorted(glob) + random.Random(42).sample."""
    pares_control: List[Tuple[str, str]] = []
    pares_alucinacion: List[Tuple[str, str]] = []
    metadatos: List[dict] = []

    for suite in SUITES:
        suite_dir = CORPUS / suite
        if not suite_dir.exists():
            print(f"  [WARN] Suite no encontrada: {suite_dir}")
            continue

        clean_files = sorted(suite_dir.glob("*_A_clean.txt"))
        print(f"  [{suite}] {len(clean_files)} archivos A_clean")

        # Filtrar pares válidos (A y B existen, ambos no vacíos)
        candidatos = []
        for cf in clean_files:
            hf = cf.with_name(cf.name.replace("_A_clean.txt", "_B_hallucination.txt"))
            if not hf.exists():
                continue
            try:
                a = cf.read_text(encoding="utf-8", errors="replace").strip()
                b = hf.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                continue
            if not a or not b:
                continue
            candidatos.append((cf, hf, a, b))

        print(f"  [{suite}] {len(candidatos)} pares válidos (A+B)")

        # Muestra estratificada con seed fijo
        rng = random.Random(SEED)
        muestra = rng.sample(candidatos, min(N_PER_SUITE, len(candidatos)))
        print(f"  [{suite}] Muestra: {len(muestra)} pares (seed={SEED})")

        for cf, hf, a, b in muestra:
            pares_control.append((a, a))  # A→A sanity check
            pares_alucinacion.append((a, b))  # A→B hallucination
            metadatos.append({
                "suite": suite,
                "id": cf.name.replace("_A_clean.txt", ""),
                "archivo_a": str(cf),
                "archivo_b": str(hf),
            })

    return pares_control, pares_alucinacion, metadatos


def main():
    global SEED
    args = parse_args()
    SEED = args.seed
    out_base = Path(args.output) if args.output else Path(r"C:\Users\conno\Downloads\SAS-Semántico\variado\sas-multimetric-tribunal\reports\validacion_1800_stratified_v3.json")
    print("=" * 72)
    print("  VALIDACIÓN ESTRATIFICADA 1,800+1,800 — CORE ACTUAL")
    print(f"  Corpus: {CORPUS}")
    print(f"  Suites: {', '.join(SUITES)}")
    print(f"  Muestra: {N_PER_SUITE} por suite, seed={SEED}")
    print(f"  κD={KAPPA_D}, κR={KAPPA_R}")
    print("=" * 72)

    # 1. Cargar muestra
    print("\n[1/4] Cargando muestra estratificada...")
    pares_control, pares_alucinacion, metadatos = cargar_muestra_estratificada()
    print(f"  Total: {len(pares_control)} control, {len(pares_alucinacion)} alucinación")

    # 2. Configurar tribunal
    print("\n[2/4] Configurando tribunal (core actual)...")
    tribunal = TribunalMultimetrico(kappa_d=KAPPA_D, kappa_r=KAPPA_R)

    # Verificar carga de módulos — cortar si falta alguno
    modulos = tribunal._modulos_cargados
    print("  Módulos cargados:", modulos)
    expected = {
        "flow_coherence", "negation_probe", "ricci_enhanced_cre",
        "arithmetic_detector", "reference_check", "entropy_density",
    }
    missing = expected - {k for k, v in modulos.items() if v}
    if missing:
        raise RuntimeError(f"Módulos no cargados: {missing}. El path del core está mal.")

    # 3. Ejecutar
    print("\n[3/4] Ejecutando tribunal...")
    t0 = time.time()
    veredictos_control = []
    for i, (src, rsp) in enumerate(pares_control):
        v = tribunal.evaluar(src, rsp, request_id=f"control-{i:05d}")
        veredictos_control.append(v)
    t_control = time.time() - t0

    t0 = time.time()
    veredictos_alucinacion = []
    for i, (src, rsp) in enumerate(pares_alucinacion):
        v = tribunal.evaluar(src, rsp, request_id=f"aluc-{i:05d}")
        veredictos_alucinacion.append(v)
    t_aluc = time.time() - t0
    print(f"  Control: {len(veredictos_control)} en {t_control:.1f}s")
    print(f"  Alucinación: {len(veredictos_alucinacion)} en {t_aluc:.1f}s")

    # 4. Analizar
    print("\n[4/4] Analizando resultados...")

    # Zonas
    zonas_control = Counter()
    zonas_aluc = Counter()
    for v in veredictos_control:
        zonas_control[v.zona] += 1
    for v in veredictos_alucinacion:
        zonas_aluc[v.zona] += 1

    # Métricas
    n_col_aluc = zonas_aluc.get(ZonaEstructural.COLAPSO_ESTRUCTURAL.value, 0)
    n_rup_aluc = zonas_aluc.get(ZonaEstructural.RUPTURA_RECUPERABLE.value, 0)
    n_coh_aluc = zonas_aluc.get(ZonaEstructural.COHERENTE.value, 0)
    n_col_ctrl = zonas_control.get(ZonaEstructural.COLAPSO_ESTRUCTURAL.value, 0)
    n_rup_ctrl = zonas_control.get(ZonaEstructural.RUPTURA_RECUPERABLE.value, 0)
    n_coh_ctrl = zonas_control.get(ZonaEstructural.COHERENTE.value, 0)

    tp = n_col_aluc + n_rup_aluc
    fp = n_col_ctrl + n_rup_ctrl
    fn = n_coh_aluc
    tn = n_coh_ctrl

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0

    # Firing frequency por módulo
    modulos_firing = Counter()
    for v in veredictos_alucinacion:
        for m in getattr(v, "modulos_disparados", []) or []:
            modulos_firing[m.nombre] += 1

    # Por suite
    por_suite = {}
    for i, v in enumerate(veredictos_alucinacion):
        suite = metadatos[i]["suite"]
        por_suite.setdefault(suite, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        if v.zona in (ZonaEstructural.COLAPSO_ESTRUCTURAL.value, ZonaEstructural.RUPTURA_RECUPERABLE.value):
            por_suite[suite]["tp"] += 1
        else:
            por_suite[suite]["fn"] += 1
    for i, v in enumerate(veredictos_control):
        suite = metadatos[i]["suite"]
        por_suite.setdefault(suite, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
        if v.zona == ZonaEstructural.COHERENTE.value:
            por_suite[suite]["tn"] += 1
        else:
            por_suite[suite]["fp"] += 1

    # Reporte
    print("\n" + "=" * 72)
    print("  RESULTADOS — VALIDACIÓN ESTRATIFICADA 1,800+1,800")
    print("=" * 72)
    print(f"  F1:        {f1:.4f} ({100*f1:.2f}%)")
    print(f"  Precision: {precision:.4f} ({100*precision:.2f}%)")
    print(f"  Recall:    {recall:.4f} ({100*recall:.2f}%)")
    print(f"  Accuracy:  {accuracy:.4f} ({100*accuracy:.2f}%)")
    print(f"  TP={tp} FP={fp} FN={fn} TN={tn}")
    print()
    print("  Zonas control:")
    for z, n in zonas_control.most_common():
        print(f"    {z}: {n} ({100*n/len(veredictos_control):.1f}%)")
    print("  Zonas alucinación:")
    for z, n in zonas_aluc.most_common():
        print(f"    {z}: {n} ({100*n/len(veredictos_alucinacion):.1f}%)")
    print()
    print("  Firing frequency (alucinación):")
    for m, n in modulos_firing.most_common():
        print(f"    {m}: {n} ({100*n/len(veredictos_alucinacion):.1f}%)")
    print()
    print("  Por suite (alucinación):")
    for s, d in por_suite.items():
        n = d["tp"] + d["fn"]
        rec = d["tp"] / n if n > 0 else 0
        print(f"    {s}: TP={d['tp']} FN={d['fn']} recall={100*rec:.1f}%")

    # Guardar JSON
    out = {
        "fecha": "2026-09-11",
        "estructura": "1,800 alucinación + 1,800 control (600 por suite × 3 suites)",
        "seed": SEED,
        "kappa_d": KAPPA_D,
        "kappa_r": KAPPA_R,
        "core": "tribunal v1.0.1 + negation v1.3 + reference v1.3",
        "metricas": {
            "f1": round(f1, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "accuracy": round(accuracy, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        },
        "zonas_control": {k: v for k, v in zonas_control.items()},
        "zonas_alucinacion": {k: v for k, v in zonas_aluc.items()},
        "firing_frequency": {k: v for k, v in modulos_firing.most_common()},
        "por_suite": por_suite,
        "n_control": len(pares_control),
        "n_alucinacion": len(pares_alucinacion),
    }

    out_path = out_base
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    print(f"\n  Guardado: {out_path}")

    # Reporte txt
    txt_path = out_path.with_suffix(".txt")
    lines = [
        "=" * 72,
        "VALIDACIÓN ESTRATIFICADA 1,800+1,800 — CORE ACTUAL",
        "=" * 72,
        f"Fecha: 2026-09-11",
        f"Estructura: 1,800 alucinación + 1,800 control (600 por suite × 3 suites)",
        f"Seed: {SEED}",
        f"κD={KAPPA_D}, κR={KAPPA_R}",
        f"Core: tribunal v1.0.1 + negation v1.3 + reference v1.3",
        "",
        f"F1: {100*f1:.2f}%",
        f"Precision: {100*precision:.2f}%",
        f"Recall: {100*recall:.2f}%",
        f"Accuracy: {100*accuracy:.2f}%",
        f"TP={tp} FP={fp} FN={fn} TN={tn}",
        "",
        "Zonas control:",
    ]
    for z, n in zonas_control.most_common():
        lines.append(f"  {z}: {n} ({100*n/len(veredictos_control):.1f}%)")
    lines.append("Zonas alucinación:")
    for z, n in zonas_aluc.most_common():
        lines.append(f"  {z}: {n} ({100*n/len(veredictos_alucinacion):.1f}%)")
    lines.append("")
    lines.append("Firing frequency (alucinación):")
    for m, n in modulos_firing.most_common():
        lines.append(f"  {m}: {n} ({100*n/len(veredictos_alucinacion):.1f}%)")
    lines.append("")
    lines.append("Por suite (alucinación):")
    for s, d in por_suite.items():
        n = d["tp"] + d["fn"]
        rec = d["tp"] / n if n > 0 else 0
        lines.append(f"  {s}: TP={d['tp']} FN={d['fn']} recall={100*rec:.1f}%")
    txt_path.write_text("\n".join(lines), "utf-8")
    print(f"  Guardado: {txt_path}")


if __name__ == "__main__":
    main()