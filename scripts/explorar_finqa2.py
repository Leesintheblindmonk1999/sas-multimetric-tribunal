#!/usr/bin/env python3
"""explorar_finqa2.py — Analiza si financiero_finqa tiene contexto compartido para emparejar."""

import pandas as pd
from pathlib import Path
from difflib import SequenceMatcher

CSV = Path(r"C:\ProgramData\benchmark_corpus\financiero_finqa\finqa-hallucination-detection.csv")
df = pd.read_csv(CSV)

correct = df[df["is_correct"] == 1]
hallucinated = df[df["is_correct"] == 0]

print("=" * 60)
print("  financiero_finqa — ¿Se puede emparejar por contexto?")
print("=" * 60)

# ¿Hay contextos compartidos entre correctas y alucinadas?
correct_contexts = set(correct["context"].str[:100])
hallucinated_contexts = set(hallucinated["context"].str[:100])
shared = correct_contexts & hallucinated_contexts
print(f"\nContextos (primeros 100 chars) compartidos: {len(shared)}")

# ¿Hay queries similares (fuzzy)?
print(f"\nAnálisis de similitud de queries:")
best_matches = []
for _, h_row in hallucinated.iterrows():
    h_query = h_row["query"]
    best_score = 0
    best_q = None
    for _, c_row in correct.iterrows():
        q = c_row["query"]
        score = SequenceMatcher(None, h_query, q).ratio()
        if score > best_score:
            best_score = score
            best_q = q
    best_matches.append((h_row["query"], best_q, best_score))

best_matches.sort(key=lambda x: -x[2])
print(f"\nTop 10 coincidencias query (correcta más similar a cada alucinada):")
for h_q, c_q, score in best_matches[:10]:
    print(f"  sim={score:.3f}")
    print(f"    H: {h_q[:80]}")
    print(f"    C: {c_q[:80]}")

# Distribución de scores
import numpy as np
scores = [s for _, _, s in best_matches]
print(f"\nDistribución de similitud máxima:")
print(f"  media={np.mean(scores):.3f}  mediana={np.median(scores):.3f}  max={np.max(scores):.3f}")
print(f"  >= 0.90: {sum(1 for s in scores if s >= 0.90)}")
print(f"  0.70-0.90: {sum(1 for s in scores if 0.70 <= s < 0.90)}")
print(f"  0.50-0.70: {sum(1 for s in scores if 0.50 <= s < 0.70)}")
print(f"  < 0.50: {sum(1 for s in scores if s < 0.50)}")

# Check longitudes
print(f"\nLongitudes de respuesta:")
print(f"  correctas: media={correct['llm_response'].str.len().mean():.0f} chars")
print(f"  alucinadas: media={hallucinated['llm_response'].str.len().mean():.0f} chars")
