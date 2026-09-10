#!/usr/bin/env python3
"""scripts/38_revisar_regresiones.py — ¿Las 193 regresiones son negaciones semánticas reales?"""
import json
import re
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
DATA = json.loads((BASE / "reports" / "analisis_decisivo_negation_v3.json").read_text("utf-8"))
regresiones = DATA["regresiones"]

NEGACION = re.compile(
    r"\b(shall not|will not|must not|cannot|is not|are not|was not|were not"
    r"|has not|have not|had not|does not|do not|did not"
    r"|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|declines|refuses|rejects|denies|disputes"
    r"|never|none|neither|nor"
    r"|no|nunca|jamás|ningún|ninguna|tampoco|ni)\b",
    re.IGNORECASE,
)

# Cargar textos
import random as _rnd
def _cargar_pares(suite, max_pairs=200, seed=42):
    sd = Path(r"C:\ProgramData\benchmark_corpus") / suite
    if not sd.exists(): return []
    cand = []
    for cf in sd.glob("*_A_clean.txt"):
        hf = cf.with_name(cf.name.replace("_A_clean.txt", "_B_hallucination.txt"))
        if not hf.exists(): continue
        try: sz = cf.stat().st_size + hf.stat().st_size
        except: continue
        if sz > 25000: continue
        cand.append((cf, hf))
    if not cand: return []
    nm = min(max_pairs, len(cand))
    rng = _rnd.Random(seed)
    m = rng.sample(cand, nm)
    res = []
    for cf, hf in m:
        base = cf.name.replace("_A_clean.txt", "")
        try:
            src = cf.read_text("utf-8", errors="replace").strip()
            rsp = hf.read_text("utf-8", errors="replace").strip()
        except: continue
        if not src or not rsp: continue
        res.append((src, rsp, f"{suite}/{base}"))
    return res

SUITES = ["codehalu","halubench","halueval_dialogue","halueval_general",
          "halueval_qa","halueval_summarization","legal_hallucinations","truthfulqa"]
textos = {}
for suite in SUITES:
    for src, rsp, pid in _cargar_pares(suite, 200, 42):
        textos[pid] = (src, rsp)

# Clasificar regresiones por suite y por tipo de negación
from collections import Counter
por_suite = Counter(pid.split("/")[0] for pid in regresiones)
print("Regresiones por suite:")
for s, n in por_suite.most_common():
    print(f"  {s}: {n}")

# Para las suites de TEXTO (no codehalu), mostrar ejemplos con el marcador
print(f"\n=== Ejemplos de regresión en suites de texto (no codehalu) ===")
mostrados = 0
for pid in regresiones:
    suite = pid.split("/")[0]
    if suite == "codehalu":
        continue
    if pid not in textos:
        continue
    A, B = textos[pid]
    neg_a = bool(NEGACION.search(A.lower()))
    neg_b = bool(NEGACION.search(B.lower()))
    if neg_a != neg_b and mostrados < 12:
        print(f"\n  {pid} (negA={neg_a} negB={neg_b})")
        print(f"    A: {A[:150]}")
        print(f"    B: {B[:150]}")
        # Mostrar el marcador encontrado
        m_a = NEGACION.search(A.lower())
        m_b = NEGACION.search(B.lower())
        print(f"    marcador A: {m_a.group(0) if m_a else '-'} | marcador B: {m_b.group(0) if m_b else '-'}")
        mostrados += 1