#!/usr/bin/env python3
"""scripts/39_verificar_nuevos_disparos.py — ¿Los 104 False→True son negaciones genuinas?"""
import json
import re
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

import random as _rnd
def _cargar_pares(suite, max_pairs=200, seed=42):
    sd = BASE / "benchmark_corpus" / suite
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

# Identificar False→True
suben = []
for pid in mapa_despues:
    a = mapa_antes.get(pid)
    if not a: continue
    fa, fd = set(a["fired"]), set(mapa_despues[pid]["fired"])
    if "negation_penalty" not in fa and "negation_penalty" in fd:
        suben.append(pid)

print(f"Nuevos disparos (False→True): {len(suben)}")
print(f"Por suite: {dict(Counter(pid.split('/')[0] for pid in suben))}")

# Verificar: ¿tienen asimetría real de negación en el texto completo?
genuinos = []
dudosos = []
for pid in suben:
    if pid not in textos:
        continue
    A, B = textos[pid]
    neg_a = bool(NEGACION.search(A.lower()))
    neg_b = bool(NEGACION.search(B.lower()))
    if neg_a != neg_b:
        genuinos.append(pid)
    else:
        dudosos.append(pid)

print(f"\n  Con asimetría real de negación (¬A∧B o A∧¬B): {len(genuinos)}")
print(f"  Sin asimetría en texto completo (dudoso): {len(dudosos)}")

if dudosos:
    print(f"\n  Ejemplos dudosos (sin asimetría en texto completo):")
    for pid in dudosos[:10]:
        A, B = textos[pid]
        print(f"    {pid}")
        print(f"      A: {A[:100]}")
        print(f"      B: {B[:100]}")
        print(f"      negA={bool(NEGACION.search(A.lower()))} negB={bool(NEGACION.search(B.lower()))}")

out = BASE / "reports" / "nuevos_disparos_negation_v3.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump({"nuevos": suben, "genuinos": genuinos, "dudosos": dudosos}, f, ensure_ascii=False, indent=1)
print(f"\n[OK] Guardado en {out}")