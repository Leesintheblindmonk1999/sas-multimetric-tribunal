#!/usr/bin/env python3
"""Diagnóstico: ¿por qué detect_inversions() da 0 inversiones en los 510 True→False?

Examina algunos de los 193 "regresiones" del análisis original (script 37) y
muestra el detalle del módulo: split de oraciones, alineación, marcadores.
"""
import importlib.util
import json
import random
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"
ANALISIS = BASE / "reports" / "analisis_decisivo_negation_v3.json"
CORPUS_DIR = Path(r"C:\ProgramData\benchmark_corpus")
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


def cargar_pares_suite(suite, max_pairs=200, seed=42):
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
        if sz > 25000:
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
        pares.append((source, response, f"{suite}/{base}"))
    return pares


data = json.loads(ANALISIS.read_text("utf-8"))
regresiones = data["regresiones"]  # los 193
print(f"Regresiones originales (193): {len(regresiones)}")

# Por suite
from collections import Counter
cnt = Counter(pid.split("/")[0] for pid in regresiones)
print("Por suite:", dict(cnt))

# Cargar textos
textos = {}
for suite in SUITES:
    for src, rsp, pid in cargar_pares_suite(suite, 200, 42):
        textos[pid] = (src, rsp)

np_mod = cargar_negation()

# Para cada regresión original: ¿qué dice detect_inversions? ¿cuántas oraciones?
n_con_oraciones = 0
n_con_align = 0
n_con_inv = 0
ejemplos = []
for pid in regresiones[:40]:
    if pid not in textos:
        continue
    A, B = textos[pid]
    sa = np_mod._split_sentences(A)
    sb = np_mod._split_sentences(B)
    aligned = np_mod._align_sentences(sa, sb)
    r = np_mod.detect_inversions(A, B)
    n_neg_a = sum(1 for s in sa if np_mod._tiene_negacion(s))
    n_neg_b = sum(1 for s in sb if np_mod._tiene_negacion(s))
    if len(sa) > 0 and len(sb) > 0:
        n_con_oraciones += 1
    if aligned:
        n_con_align += 1
    if r.inversion_count > 0:
        n_con_inv += 1
    ejemplos.append({
        "pid": pid,
        "n_sents_a": len(sa),
        "n_sents_b": len(sb),
        "n_neg_sents_a": n_neg_a,
        "n_neg_sents_b": n_neg_b,
        "n_aligned": len(aligned),
        "inv_count": r.inversion_count,
        "A[:120]": A[:120],
        "B[:120]": B[:120],
    })

print(f"\nDe los primeros 40 regresiones originales:")
print(f"  Con oraciones (≥5 palabras) en A y B: {n_con_oraciones}")
print(f"  Con pares alineados: {n_con_align}")
print(f"  Con inversión detectada: {n_con_inv}")

print("\n=== Ejemplos (primeros 10) ===")
for e in ejemplos[:10]:
    print(f"\n--- {e['pid']}: sentsA={e['n_sents_a']} sentsB={e['n_sents_b']} "
          f"negSentsA={e['n_neg_sents_a']} negSentsB={e['n_neg_sents_b']} "
          f"aligned={e['n_aligned']} inv={e['inv_count']}")
    print(f"  A: {e['A[:120]']!r}")
    print(f"  B: {e['B[:120]']!r}")