#!/usr/bin/env python3
"""
scripts/audit_n1_corpus.py — Auditoría del Differential Guard v3 sobre corpus N1
═══════════════════════════════════════════════════════════════════════════════

Mide el impacto real del guard en FP rate, F1, recall y precisión sobre los
1,800 pares × 4 condiciones del N1.

Seguridad:
  - Carga el N1 JSON en modo solo lectura. Nunca lo modifica.
  - El tribunal original NO se toca. Se usa un hook de integración que
    captura excepciones y fallback al comportamiento original.
  - Backup del tribunal: no necesario porque NO modificamos tribunal_multimetrico.py.
    El hash del tribunal (D6A8AB5CFEFF09B408FF945FF9F294BCA031DA2CCEEA7CEBC0CECEA4BDA154D0)
    queda intacto.

Integración:
  SI guard se abstiene (compression_ratio > 0.5):
      ISI_HARD = min(lexical_baseline, source_target_guard, cre_isi)  # tribunal original
  SI guard opina:
      SI is_structurally_equivalent:
          ISI_HARD = max(lexical_baseline, differential_score)
      SI NO:
          ISI_HARD = min(lexical_baseline, differential_score)
  ISI_FINAL = ISI_HARD × Π(penalties de módulos que dispararon)
  Zona según κD=0.56, κR=0.15

Uso:
    python scripts/audit_n1_corpus.py

Salida:
    reports/audit_n1_guard_v3_[timestamp].json  (resultados completos)
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── R3.1 Differential Guard v3 ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
from r3_1_differential import compute_structural_delta

# ── Rutas (solo lectura) ──────────────────────────────────────────────────
N1_PATH = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\pairs_conditions_1800_seed42.json")
CORPUS = Path(r"C:\ProgramData\benchmark_corpus")
OUTPUT_DIR = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports")

KAPPA_D = 0.56
KAPPA_R = 0.15
SEED = 42
SUITES = ["halueval_dialogue", "halueval_qa", "truthfulqa"]
N_PER_SUITE = 600

MARCADORES = {
    "halueval_dialogue": "Correct response: ",
    "halueval_qa": "Correct answer: ",
    "truthfulqa": "Correct answer: ",
}

# ── Cargar textos del corpus (solo lectura) ───────────────────────────────

def cargar_textos_n1() -> Tuple[List[dict], List[str], List[str], List[str], List[str]]:
    """Carga los 1,800 pares del N1 con sus 4 variantes de texto.

    Returns:
        metadatos: lista de dicts con suite, id
        textos_a:  lista de A (contexto + respuesta correcta)
        textos_ap: lista de A' (respuesta correcta sola)
        textos_b:  lista de B (respuesta alucinada sola)
        textos_app: lista de A'' (contexto + respuesta alucinada)
    """
    metadatos: List[dict] = []
    textos_a: List[str] = []
    textos_ap: List[str] = []
    textos_b: List[str] = []
    textos_app: List[str] = []

    for suite in SUITES:
        suite_dir = CORPUS / suite
        clean_files = sorted(suite_dir.glob("*_A_clean.txt"))
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

        rng = random.Random(SEED)
        muestra = rng.sample(candidatos, min(N_PER_SUITE, len(candidatos)))

        for cf, hf, a, b in muestra:
            pair_id = cf.name.replace("_A_clean.txt", "")
            marcador = MARCADORES[suite]
            idx = a.find(marcador)
            if idx == -1:
                continue
            ctx = a[:idx].rstrip()
            ap = a[idx + len(marcador):].strip()
            app = f"{ctx}\n\n{marcador}{b}"

            metadatos.append({"suite": suite, "id": pair_id})
            textos_a.append(a)
            textos_ap.append(ap)
            textos_b.append(b)
            textos_app.append(app)

    return metadatos, textos_a, textos_ap, textos_b, textos_app


# ── Cargar resultados del tribunal original (solo lectura) ────────────────

def cargar_tribunal_original() -> Dict[Tuple[str, str, str], dict]:
    """Carga los resultados del tribunal original desde el N1 JSON.

    Returns:
        Dict keyed by (suite, id, condicion) → entry
    """
    with open(N1_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    resultados = {}
    for r in data["resultados"]:
        key = (r["suite"], r["id"], r["condicion"])
        resultados[key] = r
    return resultados


# ── Hook de integración del guard con fallback ────────────────────────────

def integrar_guard(
    source: str,
    response: str,
    lexical_baseline: float,
    stg_val: float,
    cre_val: float,
    stg_fired: bool,
    flow_val: float,
    flow_fired: bool,
    neg_val: float,
    neg_fired: bool,
    arith_val: float,
    arith_fired: bool,
    ref_val: float,
    ref_fired: bool,
    textos_identicos: bool,
) -> dict:
    """Aplica el Differential Guard v3 con fallback al tribunal original.

    Args:
        source: texto fuente (A)
        response: texto respuesta (A', B, o A'')
        lexical_baseline: score del baseline léxico
        stg_val, stg_fired: source_target_guard
        cre_val: cre_isi score
        flow_val, flow_fired: flow_penalty
        neg_val, neg_fired: negation_penalty
        arith_val, arith_fired: arithmetic_penalty
        ref_val, ref_fired: reference_penalty
        textos_identicos: True si source == response

    Returns:
        dict con isi_hard, isi_final, zona, guard_opinó, guard_score
    """
    try:
        guard_result = compute_structural_delta(source, response)
    except Exception as e:
        # Fallback: tribunal original
        guard_result = {
            "differential_score": 0.0,
            "is_structurally_equivalent": None,
            "abstain_reason": f"guard_exception: {e}",
        }

    # ── ISI_HARD según árbol de decisión ──────────────────────────────────
    if guard_result.get("is_structurally_equivalent") is None:
        # Guard se abstiene → tribunal original
        if cre_val is not None and not textos_identicos:
            isi_hard = min(lexical_baseline, stg_val, cre_val)
        else:
            isi_hard = min(lexical_baseline, stg_val)
        guard_opinó = False
    elif guard_result["is_structurally_equivalent"]:
        # Guard detecta equivalencia → max
        isi_hard = max(lexical_baseline, guard_result["differential_score"])
        guard_opinó = True
    else:
        # Guard detecta NO equivalencia → min
        isi_hard = min(lexical_baseline, guard_result["differential_score"])
        guard_opinó = True

    # ── ISI_FINAL = ISI_HARD × Π(penalties) ───────────────────────────────
    penalizaciones = []
    if stg_fired:
        penalizaciones.append(stg_val)
    if flow_fired:
        penalizaciones.append(flow_val)
    if neg_fired:
        penalizaciones.append(neg_val)
    if arith_fired:
        penalizaciones.append(arith_val)
    if ref_fired:
        penalizaciones.append(ref_val)

    if penalizaciones:
        factor = 1.0
        for p in penalizaciones:
            factor *= p
        isi_final = isi_hard * factor
    else:
        isi_final = isi_hard

    isi_final = max(0.0, min(1.0, isi_final))

    # ── Zona ──────────────────────────────────────────────────────────────
    if isi_final < KAPPA_R:
        zona = "F-S"
    elif isi_final < KAPPA_D:
        zona = "B"
    else:
        zona = "A"

    return {
        "isi_hard": round(isi_hard, 6),
        "isi_final": round(isi_final, 6),
        "zona": zona,
        "guard_opinó": guard_opinó,
        "guard_score": guard_result.get("differential_score", 0.0),
        "guard_equiv": guard_result.get("is_structurally_equivalent"),
        "guard_abstain_reason": guard_result.get("abstain_reason"),
    }


# ── Auditoría principal ───────────────────────────────────────────────────

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 72)
    print("  AUDITORÍA — DIFFERENTIAL GUARD v3 SOBRE CORPUS N1")
    print(f"  Fecha: {timestamp}")
    print(f"  κD={KAPPA_D}, κR={KAPPA_R}")
    print("  Modo: solo lectura sobre N1 JSON y corpus")
    print("=" * 72)

    t_start = time.time()

    # 1. Cargar textos (solo lectura)
    print("\n[1/5] Cargando textos del corpus N1 (solo lectura)...")
    metadatos, textos_a, textos_ap, textos_b, textos_app = cargar_textos_n1()
    print(f"  {len(metadatos)} pares cargados")

    # 2. Cargar resultados del tribunal original (solo lectura)
    print("\n[2/5] Cargando resultados del tribunal original (solo lectura)...")
    tribunal_original = cargar_tribunal_original()
    print(f"  {len(tribunal_original)} entradas cargadas desde {N1_PATH.name}")

    # 3. Evaluar guard sobre cada par
    print("\n[3/5] Evaluando Differential Guard v3 sobre 1,800 pares × 4 condiciones...")
    resultados_auditoria = []
    tiempos_guard: List[float] = []

    for i, (md, a, ap, b, app) in enumerate(zip(metadatos, textos_a, textos_ap, textos_b, textos_app)):
        suite = md["suite"]
        pid = md["id"]

        for cond_name, rsp in [("A_A", a), ("A_Ap", ap), ("A_B", b), ("A_App", app)]:
            key = (suite, pid, cond_name)
            orig = tribunal_original.get(key)
            if orig is None:
                continue

            # Extraer scores del tribunal original
            lb = orig["score_lexical_baseline_score"]
            stg = orig["score_source_target_guard"]
            stg_fired = "source_target_guard" in orig["modulos_disparados"]
            flow = orig["score_flow_penalty"]
            flow_fired = "flow_penalty" in orig["modulos_disparados"]
            neg = orig["score_negation_penalty"]
            neg_fired = "negation_penalty" in orig["modulos_disparados"]
            arith = orig["score_arithmetic_penalty"]
            arith_fired = "arithmetic_penalty" in orig["modulos_disparados"]
            ref = orig["score_reference_penalty"]
            ref_fired = "reference_penalty" in orig["modulos_disparados"]
            cre = orig["score_cre_isi"]
            identicos = (cond_name == "A_A")

            # Evaluar guard con timing
            t_guard = time.perf_counter()
            guard_result = integrar_guard(
                source=a,
                response=rsp,
                lexical_baseline=lb,
                stg_val=stg,
                stg_fired=stg_fired,
                cre_val=cre,
                flow_val=flow,
                flow_fired=flow_fired,
                neg_val=neg,
                neg_fired=neg_fired,
                arith_val=arith,
                arith_fired=arith_fired,
                ref_val=ref,
                ref_fired=ref_fired,
                textos_identicos=identicos,
            )
            elapsed_us = (time.perf_counter() - t_guard) * 1_000_000
            tiempos_guard.append(elapsed_us)

            entry = {
                "suite": suite,
                "id": pid,
                "condicion": cond_name,
                "original": {
                    "isi_final": orig["isi_final"],
                    "isi_hard": orig["isi_hard"],
                    "zona": orig["zona"],
                },
                "con_guard": {
                    "isi_hard": guard_result["isi_hard"],
                    "isi_final": guard_result["isi_final"],
                    "zona": guard_result["zona"],
                },
                "guard": {
                    "opinó": guard_result["guard_opinó"],
                    "score": guard_result["guard_score"],
                    "equiv": guard_result["guard_equiv"],
                    "abstain_reason": guard_result["guard_abstain_reason"],
                },
                "latencia_us": round(elapsed_us, 1),
            }
            resultados_auditoria.append(entry)

        if (i + 1) % 200 == 0:
            print(f"  Procesados {i+1}/{len(metadatos)} pares...")

    # 4. Métricas
    print("\n[4/5] Calculando métricas...")

    # Ground truth por condición
    # A_A y A_Ap → equivalentes (negativos para detección de alucinación)
    # A_B y A_App → NO equivalentes (positivos para detección de alucinación)
    GT_EQUIV = {"A_A": True, "A_Ap": True, "A_B": False, "A_App": False}

    metricas_por_condicion = {}
    for cond in ["A_A", "A_Ap", "A_B", "A_App"]:
        entries = [r for r in resultados_auditoria if r["condicion"] == cond]
        n = len(entries)
        if n == 0:
            continue

        # Original
        n_equiv_orig = sum(1 for r in entries if r["original"]["zona"] == "A")
        # Con guard
        n_equiv_guard = sum(1 for r in entries if r["con_guard"]["zona"] == "A")
        # Abstenciones
        n_abstenciones = sum(1 for r in entries if not r["guard"]["opinó"])
        # Cambios de zona
        n_cambio = sum(1 for r in entries if r["original"]["zona"] != r["con_guard"]["zona"])
        # Correcciones (original mal, guard bien)
        n_correccion = sum(
            1 for r in entries
            if (r["original"]["zona"] == "A") != GT_EQUIV[cond]
            and (r["con_guard"]["zona"] == "A") == GT_EQUIV[cond]
        )
        # Regresiones (original bien, guard mal)
        n_regresion = sum(
            1 for r in entries
            if (r["original"]["zona"] == "A") == GT_EQUIV[cond]
            and (r["con_guard"]["zona"] == "A") != GT_EQUIV[cond]
        )

        metricas_por_condicion[cond] = {
            "n": n,
            "n_equiv_original": n_equiv_orig,
            "tasa_equiv_original": round(n_equiv_orig / n, 4),
            "n_equiv_guard": n_equiv_guard,
            "tasa_equiv_guard": round(n_equiv_guard / n, 4),
            "n_abstenciones": n_abstenciones,
            "tasa_abstenciones": round(n_abstenciones / n, 4),
            "n_cambios": n_cambio,
            "n_correcciones": n_correccion,
            "n_regresiones": n_regresion,
        }

    # Métricas globales de detección
    # Para FP/Recall, tratamos A_Ap como negativos y A_B como positivos
    neg_entries = [r for r in resultados_auditoria if r["condicion"] == "A_Ap"]
    pos_entries = [r for r in resultados_auditoria if r["condicion"] == "A_B"]

    # Original
    fp_orig = sum(1 for r in neg_entries if r["original"]["zona"] != "A")
    tp_orig = sum(1 for r in pos_entries if r["original"]["zona"] != "A")
    fn_orig = sum(1 for r in pos_entries if r["original"]["zona"] == "A")
    precision_orig = tp_orig / (tp_orig + fp_orig) if (tp_orig + fp_orig) > 0 else 0
    recall_orig = tp_orig / (tp_orig + fn_orig) if (tp_orig + fn_orig) > 0 else 0
    f1_orig = 2 * precision_orig * recall_orig / (precision_orig + recall_orig) if (precision_orig + recall_orig) > 0 else 0

    # Con guard
    fp_guard = sum(1 for r in neg_entries if r["con_guard"]["zona"] != "A")
    tp_guard = sum(1 for r in pos_entries if r["con_guard"]["zona"] != "A")
    fn_guard = sum(1 for r in pos_entries if r["con_guard"]["zona"] == "A")
    precision_guard = tp_guard / (tp_guard + fp_guard) if (tp_guard + fp_guard) > 0 else 0
    recall_guard = tp_guard / (tp_guard + fn_guard) if (tp_guard + fn_guard) > 0 else 0
    f1_guard = 2 * precision_guard * recall_guard / (precision_guard + recall_guard) if (precision_guard + recall_guard) > 0 else 0

    metricas_globales = {
        "original": {
            "fp": fp_orig,
            "tp": tp_orig,
            "fn": fn_orig,
            "precision": round(precision_orig, 4),
            "recall": round(recall_orig, 4),
            "f1": round(f1_orig, 4),
        },
        "con_guard": {
            "fp": fp_guard,
            "tp": tp_guard,
            "fn": fn_guard,
            "precision": round(precision_guard, 4),
            "recall": round(recall_guard, 4),
            "f1": round(f1_guard, 4),
        },
        "diferencia": {
            "fp": fp_guard - fp_orig,
            "tp": tp_guard - tp_orig,
            "fn": fn_guard - fn_orig,
            "precision": round(precision_guard - precision_orig, 4),
            "recall": round(recall_guard - recall_orig, 4),
            "f1": round(f1_guard - f1_orig, 4),
        },
    }

    # Latencia
    latencia_media_us = sum(tiempos_guard) / len(tiempos_guard) if tiempos_guard else 0

    # 5. Reporte
    print("\n[5/5] Generando reporte...")

    reporte = {
        "metadata": {
            "experimento": "Auditoría Differential Guard v3 sobre N1",
            "fecha": timestamp,
            "kappa_d": KAPPA_D,
            "kappa_r": KAPPA_R,
            "n_pares": len(metadatos),
            "n_evaluaciones": len(resultados_auditoria),
            "guard_version": "r3_1_differential.py v3 (grounding + compression abstention)",
            "tribunal_original_hash": "D6A8AB5CFEFF09B408FF945FF9F294BCA031DA2CCEEA7CEBC0CECEA4BDA154D0",
            "n1_json_hash": "267b7abbf241a75ceb4e6fbb3d073f9257bbcd9c09144a751864551ca94fa603",
            "runtime_segundos": round(time.time() - t_start, 1),
        },
        "metricas_por_condicion": metricas_por_condicion,
        "metricas_globales": metricas_globales,
        "latencia_media_us": round(latencia_media_us, 2),
        "resultados": resultados_auditoria,
    }

    # Guardar (archivo nuevo con timestamp, nunca sobrescribe el original)
    output_path = OUTPUT_DIR / f"audit_n1_guard_v3_{timestamp}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    # ── Reporte en consola ────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  REPORTE DE AUDITORÍA — DIFFERENTIAL GUARD v3")
    print("=" * 72)

    print(f"\n  Latencia media del guard: {latencia_media_us:.1f} µs/par")

    print(f"\n  ── Métricas por condición ──")
    for cond, m in metricas_por_condicion.items():
        gt = "EQUIV" if GT_EQUIV[cond] else "NO EQUIV"
        print(f"\n  {cond} (ground truth={gt}):")
        print(f"    n={m['n']}")
        print(f"    Original: {m['n_equiv_original']} eq ({m['tasa_equiv_original']:.1%})")
        print(f"    Con guard: {m['n_equiv_guard']} eq ({m['tasa_equiv_guard']:.1%})")
        print(f"    Abstenciones: {m['n_abstenciones']} ({m['tasa_abstenciones']:.1%})")
        print(f"    Correcciones: {m['n_correcciones']}  Regresiones: {m['n_regresiones']}")

    print(f"\n  ── Métricas globales (A_Ap como negativos, A_B como positivos) ──")
    print(f"  {'':30s} {'Original':>12s} {'Con guard':>12s} {'Δ':>8s}")
    print(f"  {'FP rate':30s} {metricas_globales['original']['fp']:>12d} {metricas_globales['con_guard']['fp']:>12d} {metricas_globales['diferencia']['fp']:>+8d}")
    print(f"  {'Recall':30s} {metricas_globales['original']['recall']:>12.4f} {metricas_globales['con_guard']['recall']:>12.4f} {metricas_globales['diferencia']['recall']:>+8.4f}")
    print(f"  {'Precision':30s} {metricas_globales['original']['precision']:>12.4f} {metricas_globales['con_guard']['precision']:>12.4f} {metricas_globales['diferencia']['precision']:>+8.4f}")
    print(f"  {'F1':30s} {metricas_globales['original']['f1']:>12.4f} {metricas_globales['con_guard']['f1']:>12.4f} {metricas_globales['diferencia']['f1']:>+8.4f}")

    print(f"\n  Resultados guardados en: {output_path}")
    print(f"  Runtime total: {reporte['metadata']['runtime_segundos']:.1f}s")

    print("\n" + "=" * 72)
    print("  AUDITORÍA COMPLETADA — NINGÚN ARCHIVO ORIGINAL FUE MODIFICADO")
    print("=" * 72)


if __name__ == "__main__":
    main()