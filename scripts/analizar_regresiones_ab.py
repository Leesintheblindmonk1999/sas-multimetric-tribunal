#!/usr/bin/env python3
"""analizar_regresiones_ab.py — Analiza las 802 regresiones de A_B.

Pregunta: ¿por qué el guard dice "equivalente" en respuestas alucinadas?
¿Es por compression ratio abstention, por grounding alto, o por polaridad?
"""

import json
from collections import Counter
from pathlib import Path

AUDIT = Path(r"c:\Users\conno\Downloads\SAS-Semántico\reports\audit_n1_guard_v3_20261012_222645.json")

audit = json.load(open(AUDIT, encoding="utf-8"))
resultados = audit["resultados"]

# A_B regressions: guard says equiv=True but should be False
regs = [r for r in resultados if r["condicion"] == "A_B" and r["guard"].get("equiv") is True]
print(f"Total regresiones A_B: {len(regs)}")

# Distribution of guard scores
gs_dist = Counter()
for r in regs:
    gs = r["guard"].get("score", 0)
    bucket = round(gs, 1)
    gs_dist[bucket] += 1

print("\nDistribución de guard_score en regresiones:")
for bucket in sorted(gs_dist):
    print(f"  {bucket:.1f}: {gs_dist[bucket]}")

# Distribution of abstain reasons
ar_dist = Counter()
for r in regs:
    ar = r["guard"].get("abstain_reason") or "directo"
    ar_dist[ar] += 1

print("\nDistribución de abstain_reason:")
for ar, n in ar_dist.most_common():
    print(f"  {ar}: {n}")

# Show first 15
print("\nPrimeros 15 ejemplos:")
for r in regs[:15]:
    g = r["guard"]
    print(f"  {r['suite']}/{r['id']}: score={g['score']:.4f} equiv={g['equiv']} abstain={g['abstain_reason']}")
