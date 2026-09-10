#!/usr/bin/env python3
"""scripts/69_rederivar_317_193.py — TAREA 3: re-derivación del split 317/193 con detect_inversions() real

Llama DIRECTAMENTE a detect_inversions() de negation_probe.py v1.3 sobre los
510 pares True→False de la matriz de 1,600 (identificados desde los snapshots
regresion_1600_despues_v2.json → regresion_1600_negation_v3.json).

Criterio (equivalente al del script 37 pero con el módulo real):
  - El par tiene asimetría de negación REAL según detect_inversions()
    (inversion_count > 0 con tipo negation) → el nuevo módulo PERDIÓ una
    detección genuina = REGRESIÓN.
  - Sin inversión detectada → el viejo disparaba por asimetría de whitelist
    = FP eliminado.

Además: si el split cambia >5%, recalcular cuántos de las "regresiones"
son legal_hallucinations.
"""
import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
ANTES = BASE / "reports" / "regresion_1600_despues_v2.json"
DESPUES = BASE / "reports" / "regresion_1600_negation_v3.json"
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"
CORPUS_DIR = Path(r"C:\ProgramData\benchmark_corpus")
MAX_CHARS_PAIR = 25_000
SUITES = [
    "codehalu", "halubench", "halueval_dialogue", "halueval_general",
    "halueval_qa", "halueval_summarization", "legal_hallucinations", "truthfulqa",
]


def cargar_negation():
    spec = importlib.util.spec_from_file_location("core.negation_probe", NEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["core.negation_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def cargar_pares_suite(suite: str, max_pairs: int, seed: int):
    suite_dir = CORPUS_DIR / suite
    if not suite_dir.exists():
        return []
    candidatos = []
    for clean_file in sorted(suite_dir.glob("*_A_clean.txt")):
        hall_file = clean_file.with_name(clean_file.name.replace("_A_clean.txt", "_B_hallucination.txt"))
        if not hall_file.exists():
            continue
        try:
            sz = clean_file.stat().st_size + hall_file.stat().st_size
        except OSError:
            continue
        if sz > MAX_CHARS_PAIR:
            continue
        candidatos.append((clean_file, hall_file))
    if not candidatos:
        return []
    n_muestra = min(max_pairs, len(candidatos))
    muestra = random.Random(seed).sample(candidatos, n_muestra)
    pares = []
    for clean_file, hall_file in muestra:
        base = clean_file.name.replace("_A_clean.txt", "")
        try:
            source = clean_file.read_text(encoding="utf-8", errors="replace").strip()
            response = hall_file.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if not source or not response:
            continue
        pares.append((source, response, f"{suite}/{base}"))
    return pares


def main():
    antes = json.loads(ANTES.read_text("utf-8"))
    despues = json.loads(DESPUES.read_text("utf-8"))
    mapa_antes = {a["pid"]: a for a in antes}
    mapa_despues = {d["pid"]: d for d in despues}

    # Identificar los 510 True→False (negation disparaba antes, no después)
    bajan = []
    for pid in mapa_despues:
        a = mapa_antes.get(pid)
        if not a:
            continue
        fa = set(a["fired"])
        fd = set(mapa_despues[pid]["fired"])
        if "negation_penalty" in fa and "negation_penalty" not in fd:
            bajan.append(pid)
    print(f"Pares True→False: {len(bajan)}")

    # Cargar textos de los 1,600
    textos = {}
    for suite in SUITES:
        for src, rsp, pid in cargar_pares_suite(suite, 200, 42):
            textos[pid] = (src, rsp)
    print(f"Textos cargados: {len(textos)}")

    np_mod = cargar_negation()

    # Clasificar cada uno con detect_inversions() REAL
    regresiones = []      # detect_inversions encuentra inversión de negación real
    fp_eliminados = []    # sin inversión detectada
    sin_texto = 0
    detalle = []

    for pid in bajan:
        if pid not in textos:
            sin_texto += 1
            continue
        A, B = textos[pid]
        r = np_mod.detect_inversions(A, B)
        # ¿Hay inversión de polaridad (negación) real?
        tiene_inv_neg = any(d.inversion_type == "negation" for d in r.details)
        detalle.append({
            "pid": pid,
            "inversion_count": r.inversion_count,
            "weighted_score": r.weighted_inversion_score,
            "tiene_inv_negacion": tiene_inv_neg,
            "penalty": r.penalty,
        })
        if tiene_inv_neg:
            regresiones.append(pid)
        else:
            fp_eliminados.append(pid)

    print(f"\n=== RESULTADO CON detect_inversions() REAL (v1.3) ===")
    print(f"  REGRESIONES (inversión real que el nuevo pierde): {len(regresiones)}")
    print(f"  FP eliminados (sin inversión):                    {len(fp_eliminados)}")
    print(f"  Sin texto disponible:                             {sin_texto}")
    print(f"  Total: {len(regresiones) + len(fp_eliminados) + sin_texto} (esperado {len(bajan)})")

    # Comparar con el split publicado (317/193)
    print(f"\n=== COMPARACIÓN con lo publicado (317/193) ===")
    n_publicado_fp = 317
    n_publicado_reg = 193
    diff_fp = len(fp_eliminados) - n_publicado_fp
    diff_reg = len(regresiones) - n_publicado_reg
    print(f"  FP eliminados: {len(fp_eliminados)} (publicado {n_publicado_fp}, diff {diff_fp:+d})")
    print(f"  Regresiones:   {len(regresiones)} (publicado {n_publicado_reg}, diff {diff_reg:+d})")
    pct_diff = abs(diff_reg) / n_publicado_reg * 100
    print(f"  Diferencia %: {pct_diff:.1f}% (>5% = recalcular legal_hallucinations)")

    # Por suite
    print(f"\n=== Por suite ===")
    cnt_reg = Counter(pid.split("/")[0] for pid in regresiones)
    cnt_fp = Counter(pid.split("/")[0] for pid in fp_eliminados)
    print("  Regresiones por suite:")
    for s, n in cnt_reg.most_common():
        print(f"    {s}: {n}")
    print("  FP eliminados por suite:")
    for s, n in cnt_fp.most_common():
        print(f"    {s}: {n}")

    # Si cambió >5%, recalcular legal_hallucinations en regresiones
    if pct_diff > 5:
        n_legal_reg = sum(1 for pid in regresiones if pid.startswith("legal_hallucinations/"))
        n_legal_fp = sum(1 for pid in fp_eliminados if pid.startswith("legal_hallucinations/"))
        print(f"\n=== RECÁLCULO legal_hallucinations (por cambio >5%) ===")
        print(f"  Regresiones que son legal_hallucinations: {n_legal_reg}/{len(regresiones)}")
        print(f"  FP eliminados que son legal_hallucinations: {n_legal_fp}/{len(fp_eliminados)}")

    # Guardar
    out = {
        "fecha": "2026-09-05",
        "metodo": "detect_inversions() real (negation_probe.py v1.3)",
        "n_true_false": len(bajan),
        "n_regresiones": len(regresiones),
        "n_fp_eliminados": len(fp_eliminados),
        "n_sin_texto": sin_texto,
        "publicado_anterior": {"n_regresiones": 193, "n_fp_eliminados": 317},
        "regresiones": regresiones,
        "fp_eliminados": fp_eliminados,
        "detalle": detalle,
    }
    out_path = BASE / "reports" / "t1_rederivacion_317_193.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"\n[OK] Guardado en {out_path}")


if __name__ == "__main__":
    main()