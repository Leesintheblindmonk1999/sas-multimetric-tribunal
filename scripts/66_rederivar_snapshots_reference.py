#!/usr/bin/env python3
"""scripts/66_rederivar_snapshots_reference.py — TAREA 1: re-derivación desde cero de los snapshots v12/v13

Re-corré desde cero (sin reusar t1_snapshot_reference_v12.json ni v13.json):
  1. 5 pares adversariales — ANTES (regex viejo v1.2) y DESPUÉS (regex nuevo v1.3),
     con el resultado crudo de detect_fabrications() (fabricated_count, events).
  2. 686 pares de calibración CiteTracer — TP/FN/FP/TN item por item.
  3. 1,600 de la matriz — diff directo pre vs post.

El regex viejo se reconstruye EN EL SCRIPT (no se toca reference_check.py).
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
CORPUS_DIR = BASE / "benchmark_corpus"
MAX_CHARS_PAIR = 25_000
SUITES = [
    "codehalu", "halubench", "halueval_dialogue", "halueval_general",
    "halueval_qa", "halueval_summarization", "legal_hallucinations", "truthfulqa",
]

# ── Regex viejo (v1.2) — patrón 4 original, reconstruido aquí ──
import re as _re
_PATRON_4_VIEJO = _re.compile(
    r'([\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF][\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF\s\-\.]{2,40}?)'
    r'\s+\((\d{4}[a-z]?)\)',
    _re.UNICODE,
)


def cargar_refcheck():
    spec = importlib.util.spec_from_file_location("core.reference_check", RC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["core.reference_check"] = mod
    spec.loader.exec_module(mod)
    return mod


def cargar_refcheck_viejo():
    """Carga el módulo pero con el patrón 4 reemplazado por el regex v1.2."""
    mod = cargar_refcheck()
    # Reemplazar el 4to patrón (índice 3) por el viejo
    mod._CITATION_PATTERNS = list(mod._CITATION_PATTERNS)
    mod._CITATION_PATTERNS[3] = _PATRON_4_VIEJO
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


def run_detect(rc, source, response):
    r = rc.detect_fabrications(source, response)
    return {
        "fabricated_count": r.fabricated_count,
        "anachronistic_count": r.anachronistic_count,
        "penalty": r.penalty,
        "events": [
            {"type": e.event_type, "citation_a": e.citation_a, "citation_b": e.citation_b}
            for e in r.events
        ],
    }


def main():
    rc_viejo = cargar_refcheck_viejo()
    rc_nuevo = cargar_refcheck()

    # ═══ 1: Adversariales ═══
    adv = json.loads(ADV_PATH.read_text("utf-8"))
    print("=" * 80)
    print("[1] ADVERSARIALES — detect_fabrications() crudo, ANTES vs DESPUÉS")
    print("=" * 80)
    adv_antes, adv_despues = [], []
    for d in adv["detalle"]:
        antes = run_detect(rc_viejo, d["source"], d["response"])
        despues = run_detect(rc_nuevo, d["source"], d["response"])
        adv_antes.append({"id": d["id"], **antes})
        adv_despues.append({"id": d["id"], **despues})
        print(f"  {d['id']}: ANTES fab={antes['fabricated_count']} anac={antes['anachronistic_count']} "
              f"penalty={antes['penalty']} | DESPUÉS fab={despues['fabricated_count']} "
              f"anac={despues['anachronistic_count']} penalty={despues['penalty']}")
        if antes["events"]:
            for e in antes["events"]:
                print(f"      ANTES evt: {e['type']} | A='{e['citation_a'][:50]}' | B='{e['citation_b'][:50]}'")
        if despues["events"]:
            for e in despues["events"]:
                print(f"      DESPUÉS evt: {e['type']} | A='{e['citation_a'][:50]}' | B='{e['citation_b'][:50]}'")
    n_adv_antes = sum(1 for d in adv_antes if d["fabricated_count"] > 0 or d["anachronistic_count"] > 0)
    n_adv_despues = sum(1 for d in adv_despues if d["fabricated_count"] > 0 or d["anachronistic_count"] > 0)
    print(f"  → ANTES: {n_adv_antes}/5 disparan | DESPUÉS: {n_adv_despues}/5 disparan")

    # ═══ 2: Calibración ═══
    print("\n" + "=" * 80)
    print("[2] CALIBRACIÓN CiteTracer (686) — TP/FN/FP/TN item por item")
    print("=" * 80)
    cal_pares = []
    with open(CAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cal_pares.append(json.loads(line))
    print(f"  Pares cargados: {len(cal_pares)}")

    def contar(rc, label):
        tp = fn = fp = tn = 0
        detalle = []
        for p in cal_pares:
            es_pos = p.get("mutation_type", "") != "control"
            r = rc.detect_fabrications(p.get("source", ""), p.get("response", ""))
            fired = r.penalty < 1.0
            if es_pos and fired:
                tp += 1
            elif es_pos and not fired:
                fn += 1
            elif not es_pos and fired:
                fp += 1
            else:
                tn += 1
            detalle.append({
                "id": p.get("id", ""),
                "es_positivo": es_pos,
                "fired": fired,
                "fabricated_count": r.fabricated_count,
                "anachronistic_count": r.anachronistic_count,
                "penalty": r.penalty,
            })
        recall = tp / (tp + fn) if (tp + fn) else 0
        prec = tp / (tp + fp) if (tp + fp) else 0
        print(f"  [{label}] TP={tp} FN={fn} FP={fp} TN={tn} | recall={recall:.4f} precision={prec:.4f}")
        return {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "recall": recall, "precision": prec, "detalle": detalle}

    cal_antes = contar(rc_viejo, "ANTES (v1.2)")
    cal_despues = contar(rc_nuevo, "DESPUÉS (v1.3)")

    # Verificar que los IDs de TP/FN/FP/TN coinciden entre antes y después
    ids_antes = {d["id"]: d for d in cal_antes["detalle"]}
    ids_despues = {d["id"]: d for d in cal_despues["detalle"]}
    diffs = []
    for pid in ids_antes:
        a, b = ids_antes[pid], ids_despues[pid]
        if a["fired"] != b["fired"] or a["fabricated_count"] != b["fabricated_count"]:
            diffs.append({"id": pid, "antes": a, "despues": b})
    print(f"  Diffs item-level entre ANTES y DESPUÉS: {len(diffs)}")
    for d in diffs[:10]:
        print(f"    {d['id']}: antes fired={d['antes']['fired']} fab={d['antes']['fabricated_count']} "
              f"| despues fired={d['despues']['fired']} fab={d['despues']['fabricated_count']}")

    # ═══ 3: Matriz 1,600 ═══
    print("\n" + "=" * 80)
    print("[3] MATRIZ 1,600 — diff directo pre vs post")
    print("=" * 80)
    matriz_pares = []
    for suite in SUITES:
        pares = cargar_pares_suite(suite, 200, 42)
        matriz_pares.extend(pares)
        print(f"  [{suite}] {len(pares)} pares")
    print(f"  Total: {len(matriz_pares)}")

    pre_map, post_map = {}, {}
    for source, response, pid in matriz_pares:
        r_pre = rc_viejo.detect_fabrications(source, response)
        r_post = rc_nuevo.detect_fabrications(source, response)
        pre_map[pid] = {
            "fired": r_pre.penalty < 1.0,
            "fabricated_count": r_pre.fabricated_count,
            "anachronistic_count": r_pre.anachronistic_count,
            "penalty": r_pre.penalty,
        }
        post_map[pid] = {
            "fired": r_post.penalty < 1.0,
            "fabricated_count": r_post.fabricated_count,
            "anachronistic_count": r_post.anachronistic_count,
            "penalty": r_post.penalty,
        }

    n_pre = sum(1 for v in pre_map.values() if v["fired"])
    n_post = sum(1 for v in post_map.values() if v["fired"])
    suben = [p for p in pre_map if not pre_map[p]["fired"] and post_map[p]["fired"]]
    bajan = [p for p in pre_map if pre_map[p]["fired"] and not post_map[p]["fired"]]
    magnitud = [p for p in pre_map if pre_map[p]["fired"] and post_map[p]["fired"]
                and abs(pre_map[p]["penalty"] - post_map[p]["penalty"]) > 1e-6]
    print(f"  ANTES fired: {n_pre} | DESPUÉS fired: {n_post}")
    print(f"  Suben (nuevo disparo): {len(suben)}")
    for p in suben[:10]:
        print(f"    {p}: pre={pre_map[p]['penalty']} → post={post_map[p]['penalty']}")
    print(f"  Bajan (deja de disparar): {len(bajan)}")
    for p in bajan[:10]:
        print(f"    {p}: pre={pre_map[p]['penalty']} → post={post_map[p]['penalty']}")
    print(f"  Cambio de magnitud (ya disparaban): {len(magnitud)}")
    for p in magnitud[:10]:
        print(f"    {p}: pre={pre_map[p]['penalty']} → post={post_map[p]['penalty']}")

    # Guardar
    out = {
        "fecha": "2026-09-05",
        "adversariales": {"antes": adv_antes, "despues": adv_despues},
        "calibracion": {
            "antes": {k: v for k, v in cal_antes.items() if k != "detalle"},
            "despues": {k: v for k, v in cal_despues.items() if k != "detalle"},
            "diffs_item_level": diffs,
        },
        "matriz_1600": {
            "n": len(matriz_pares),
            "antes_fired": n_pre,
            "despues_fired": n_post,
            "suben": suben,
            "bajan": bajan,
            "magnitud": magnitud,
        },
    }
    out_path = BASE / "reports" / "t1_rederivacion_snapshots_reference.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"\n[OK] Guardado en {out_path}")


if __name__ == "__main__":
    main()