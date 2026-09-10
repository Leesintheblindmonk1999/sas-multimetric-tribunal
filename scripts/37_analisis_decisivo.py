#!/usr/bin/env python3
"""scripts/37_analisis_decisivo.py — Análisis decisivo de los 510 True→False

Para cada par que dejó de disparar negation (v1.1 → v1.3):
  - Si B tenía marcador de negación real y A no (¬A∧B) → el nuevo módulo
    PERDIÓ una detección genuina = REGRESIÓN (malo).
  - Si A y B tienen el mismo estado de negación (ambos sin, o ambos con)
    → el viejo disparaba por asimetría de whitelist = FP eliminado (bien).

Esto determina mantener el fix o revertirlo.
"""
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
ANTES = BASE / "reports" / "regresion_1600_despues_v2.json"
DESPUES = BASE / "reports" / "regresion_1600_negation_v3.json"

NEGACION = re.compile(
    r"\b(shall not|will not|must not|cannot|is not|are not|was not|were not"
    r"|has not|have not|had not|does not|do not|did not"
    r"|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|declines|refuses|rejects|denies|disputes"
    r"|never|none|neither|nor"
    r"|no|nunca|jamás|ningún|ninguna|tampoco|ni)\b",
    re.IGNORECASE,
)

antes = json.loads(ANTES.read_text("utf-8"))
despues = json.loads(DESPUES.read_text("utf-8"))
mapa_antes = {a["pid"]: a for a in antes}
mapa_despues = {d["pid"]: d for d in despues}

# Cargo helper para lecturas de texto
sys.path.insert(0, str(BASE / "scripts"))
import random as _rnd

def _leer(suite, base):
    sd = Path(r"C:\ProgramData\benchmark_corpus") / suite
    cf = sd / f"{base}_A_clean.txt"
    hf = sd / f"{base}_B_hallucination.txt"
    try:
        return cf.read_text("utf-8", errors="replace"), hf.read_text("utf-8", errors="replace")
    except Exception:
        return None, None

# Recomponer la muestra (seed 42, filtro 25k) para tener los textos
def _cargar_pares(suite, max_pairs=200, seed=42):
    sd = Path(r"C:\ProgramData\benchmark_corpus") / suite
    if not sd.exists(): return []
    cand = []
    for cf in sorted(sd.glob("*_A_clean.txt")):
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

# Identificar los 510 True→False
bajan = []
for pid in mapa_despues:
    a = mapa_antes.get(pid)
    if not a: continue
    fa, fd = set(a["fired"]), set(mapa_despues[pid]["fired"])
    if "negation_penalty" in fa and "negation_penalty" not in fd:
        bajan.append(pid)

print(f"Pares True→False: {len(bajan)}")

# Clasificar cada uno
regresiones = []      # ¬A∧B pero no dispara = perdió detección genuina
fp_eliminados = []    # mismo estado de negación = FP del whitelist eliminado
sin_texto = 0
otros = []

for pid in bajan:
    if pid not in textos:
        sin_texto += 1
        continue
    A, B = textos[pid]
    neg_a = bool(NEGACION.search(A.lower()))
    neg_b = bool(NEGACION.search(B.lower()))
    if neg_a != neg_b:
        # Debería haber detectado (asimetría real) pero no dispara
        regresiones.append(pid)
    else:
        fp_eliminados.append(pid)

print(f"\n=== RESULTADO DECISIVO ===")
print(f"  REGRESIONES (¬A∧B real que el nuevo pierde): {len(regresiones)}")
print(f"  FP eliminados (whitelist spurious):          {len(fp_eliminados)}")
print(f"  Sin texto disponible:                        {sin_texto}")

if regresiones:
    print(f"\n  Ejemplos de regresión (el nuevo debería disparar):")
    for pid in regresiones[:10]:
        A, B = textos[pid]
        print(f"    {pid}")
        print(f"      A: {A[:80]}")
        print(f"      B: {B[:80]}")
        print(f"      negA={bool(NEGACION.search(A.lower()))} negB={bool(NEGACION.search(B.lower()))}")

print(f"\n  FPs eliminados por suite:")
cnt = Counter(pid.split("/")[0] for pid in fp_eliminados)
for s, n in cnt.most_common():
    print(f"    {s}: {n}")

out = BASE / "reports" / "analisis_decisivo_negation_v3.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({
        "n_true_false": len(bajan),
        "n_regresiones": len(regresiones),
        "n_fp_eliminados": len(fp_eliminados),
        "regresiones": regresiones,
        "fp_eliminados": fp_eliminados,
    }, f, ensure_ascii=False, indent=1)
print(f"\n[OK] Guardado en {out}")