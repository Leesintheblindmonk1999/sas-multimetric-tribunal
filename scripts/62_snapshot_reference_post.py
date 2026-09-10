#!/usr/bin/env python3
"""scripts/62_snapshot_reference_post.py — Snapshot post-fix del regex de citas (v1.3)

Compara contra el snapshot pre-fix (t1_snapshot_reference_v12.json):
  1. 5 pares adversariales — los 3 FPs deben desaparecer
  2. 686 pares de calibración — recall/precision NO deben empeorar
  3. 1,600 pares de la matriz — reportar TODOS los cambios (suben/bajan/magnitud)
"""
import importlib.util
import json
import random
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
RC_PATH = BASE / "SAS" / "SAS" / "core" / "reference_check.py"
ADV_PATH = BASE / "reports" / "t1_adversariales_citas.json"
CAL_PATH = BASE / "research" / "cite_calibration" / "corpus" / "corpus_calibracion.jsonl"
PRE = BASE / "reports" / "t1_snapshot_reference_v12.json"
CORPUS_DIR = Path(r"C:\ProgramData\benchmark_corpus")
MAX_CHARS_PAIR = 25_000
SUITES = [
    "codehalu", "halubench", "halueval_dialogue", "halueval_general",
    "halueval_qa", "halueval_summarization", "legal_hallucinations", "truthfulqa",
]


def cargar_refcheck():
    spec = importlib.util.spec_from_file_location("core.reference_check", RC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["core.reference_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def cargar_pares_suite(suite: str, max_pairs: int, seed: int):
    suite_dir = CORPUS_DIR / suite
    if not suite_dir.exists():
        return []
    candidatos = []
    for clean_file in suite_dir.glob("*_A_clean.txt"):
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


def run_post():
    rc = cargar_refcheck()
    pre = json.loads(PRE.read_text("utf-8"))

    # ═══ 1: Adversariales ═══
    adv = json.loads(ADV_PATH.read_text("utf-8"))
    adv_result = []
    for d in adv["detalle"]:
        r = rc.detect_fabrications(d["source"], d["response"])
        adv_result.append({
            "id": d["id"],
            "fabricated_count": r.fabricated_count,
            "anachronistic_count": r.anachronistic_count,
            "penalty": r.penalty,
            "events": [{"type": e.event_type, "citation_a": e.citation_a, "citation_b": e.citation_b} for e in r.events],
        })
    print(f"\n[1] Adversariales post-fix:")
    for d in adv_result:
        print(f"    {d['id']}: fab={d['fabricated_count']} anac={d['anachronistic_count']} penalty={d['penalty']}")
    n_adv_fired = sum(1 for d in adv_result if d["fabricated_count"] > 0 or d["anachronistic_count"] > 0)
    print(f"    → {n_adv_fired}/5 disparan (esperado: 0/5)")

    # ═══ 2: Calibración ═══
    cal_pares = []
    with open(CAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cal_pares.append(json.loads(line))
    cal_result = []
    for p in cal_pares:
        r = rc.detect_fabrications(p.get("source", ""), p.get("response", ""))
        es_positivo = p.get("mutation_type", "") != "control"
        cal_result.append({
            "id": p.get("id", ""),
            "es_positivo": es_positivo,
            "fabricated_count": r.fabricated_count,
            "anachronistic_count": r.anachronistic_count,
            "penalty": r.penalty,
            "fired": r.penalty < 1.0,
        })
    n_cal_tp = sum(1 for d in cal_result if d["es_positivo"] and d["fired"])
    n_cal_fn = sum(1 for d in cal_result if d["es_positivo"] and not d["fired"])
    n_cal_fp = sum(1 for d in cal_result if not d["es_positivo"] and d["fired"])
    n_cal_tn = sum(1 for d in cal_result if not d["es_positivo"] and not d["fired"])
    recall = n_cal_tp / (n_cal_tp + n_cal_fn) if (n_cal_tp + n_cal_fn) > 0 else 0
    prec = n_cal_tp / (n_cal_tp + n_cal_fp) if (n_cal_tp + n_cal_fp) > 0 else 0
    pre_cal = pre["calibracion"]
    print(f"\n[2] Calibración post-fix: TP={n_cal_tp} FN={n_cal_fn} FP={n_cal_fp} TN={n_cal_tn}")
    print(f"    Recall={recall:.4f} (pre: {pre_cal['recall']}) Precision={prec:.4f} (pre: {pre_cal['precision']})")
    if n_cal_tp < pre_cal["n_tp"]:
        print(f"    ⚠️  SE PERDIERON TPs: {pre_cal['n_tp']} → {n_cal_tp} — DETENER")
    if n_cal_fp > pre_cal["n_fp"]:
        print(f"    ⚠️  NUEVOS FPs: {pre_cal['n_fp']} → {n_cal_fp}")

    # ═══ 3: Matriz 1,600 ═══
    matriz_pares = []
    for suite in SUITES:
        pares = cargar_pares_suite(suite, 200, 42)
        matriz_pares.extend(pares)
    matriz_result = []
    for source, response, pid in matriz_pares:
        r = rc.detect_fabrications(source, response)
        matriz_result.append({
            "pid": pid,
            "fabricated_count": r.fabricated_count,
            "anachronistic_count": r.anachronistic_count,
            "penalty": r.penalty,
            "fired": r.penalty < 1.0,
        })
    n_mat_fired = sum(1 for d in matriz_result if d["fired"])
    pre_mat = pre["matriz_1600"]
    pre_map = {d["pid"]: d for d in pre_mat["resultados"]}
    post_map = {d["pid"]: d for d in matriz_result}
    pids = set(pre_map) & set(post_map)
    suben = [p for p in pids if not pre_map[p]["fired"] and post_map[p]["fired"]]
    bajan = [p for p in pids if pre_map[p]["fired"] and not post_map[p]["fired"]]
    magnitud = [p for p in pids if pre_map[p]["fired"] and post_map[p]["fired"]
                and abs(pre_map[p]["penalty"] - post_map[p]["penalty"]) > 1e-6]
    print(f"\n[3] Matriz 1,600 post-fix: {n_mat_fired} fired (pre: {pre_mat['n_fired']})")
    print(f"    Suben (nuevo disparo): {len(suben)}")
    for p in suben[:10]:
        print(f"      {p}: pre penalty={pre_map[p]['penalty']} → post={post_map[p]['penalty']}")
    print(f"    Bajan (deja de disparar): {len(bajan)}")
    for p in bajan[:10]:
        print(f"      {p}: pre penalty={pre_map[p]['penalty']} → post={post_map[p]['penalty']}")
    print(f"    Cambio de magnitud (ya disparaban): {len(magnitud)}")
    for p in magnitud[:10]:
        print(f"      {p}: pre penalty={pre_map[p]['penalty']} → post={post_map[p]['penalty']}")

    # Guardar
    out = {
        "version": "v1.3 (post-fix)",
        "fecha": "2026-09-04",
        "adversariales": adv_result,
        "calibracion": {
            "n": len(cal_result),
            "n_tp": n_cal_tp,
            "n_fn": n_cal_fn,
            "n_fp": n_cal_fp,
            "n_tn": n_cal_tn,
            "recall": round(recall, 4),
            "precision": round(prec, 4),
            "resultados": cal_result,
        },
        "matriz_1600": {
            "n": len(matriz_result),
            "n_fired": n_mat_fired,
            "suben": suben,
            "bajan": bajan,
            "magnitud": magnitud,
            "resultados": matriz_result,
        },
    }
    out_path = BASE / "reports" / "t1_snapshot_reference_v13.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"\n[OK] Snapshot post-fix guardado en {out_path}")


if __name__ == "__main__":
    run_post()