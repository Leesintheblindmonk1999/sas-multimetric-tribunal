#!/usr/bin/env python3
"""explorar_finqa3.py — Emparejamiento exhaustivo y diseño alternativo para FinQA."""

import pandas as pd
from pathlib import Path
from collections import Counter

CSV = Path(r"C:\ProgramData\benchmark_corpus\financiero_finqa\finqa-hallucination-detection.csv")
df = pd.read_csv(CSV)

correct = df[df["is_correct"] == 1]
hallucinated = df[df["is_correct"] == 0]

print("=" * 60)
print("  financiero_finqa — Emparejamiento exhaustivo")
print("=" * 60)

# 1. Contextos completos idénticos entre correctas y alucinadas
c_ctx = correct["context"]
h_ctx = hallucinated["context"]
c_ctx_set = set(c_ctx)
h_ctx_set = set(h_ctx)
shared_full = c_ctx_set & h_ctx_set
print(f"\n1. Contextos COMPLETOS idénticos compartidos: {len(shared_full)}")

# Si hay contextos compartidos, ¿cuántas queries en cada contexto compartido?
if shared_full:
    for ctx in list(shared_full)[:3]:
        n_c = len(correct[correct["context"] == ctx])
        n_h = len(hallucinated[hallucinated["context"] == ctx])
        print(f"   contexto compartido: correctas={n_c} alucinadas={n_h}")
        if n_c and n_h:
            q_c = correct[correct["context"] == ctx]["query"].iloc[0][:100]
            q_h = hallucinated[hallucinated["context"] == ctx]["query"].iloc[0][:100]
            print(f"     queryC: {q_c}")
            print(f"     queryH: {q_h}")

# 2. Queries idénticas (normalizadas: minúsculas, sin puntuación)
def norm(s):
    import re
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower())

c_norm = set(correct["query"].apply(norm))
h_norm = set(hallucinated["query"].apply(norm))
shared_q = c_norm & h_norm
print(f"\n2. Queries NORMALIZADAS idénticas: {len(shared_q)}")

# 3. ¿Cuántas alucinadas tienen su misma query en correctas (normalizadas)?
matched_h = hallucinated["query"].apply(norm).isin(c_norm).sum()
print(f"   Alucinadas con query idéntica normalizada en correctas: {matched_h}")

# 4. Distribución de longitud de respuestas
print(f"\n3. Longitudes de respuesta:")
print(f"   correctas:   min={correct['llm_response'].str.len().min()}, "
      f"max={correct['llm_response'].str.len().max()}, "
      f"media={correct['llm_response'].str.len().mean():.1f}")
print(f"   alucinadas:  min={hallucinated['llm_response'].str.len().min()}, "
      f"max={hallucinated['llm_response'].str.len().max()}, "
      f"media={hallucinated['llm_response'].str.len().mean():.1f}")

# 5. ¿Cuántas respuestas tienen > 50 chars? (son las "largas")
n_long_c = (correct["llm_response"].str.len() > 50).sum()
n_long_h = (hallucinated["llm_response"].str.len() > 50).sum()
print(f"\n4. Respuestas largas (>50 chars):")
print(f"   correctas: {n_long_c} ({n_long_c/len(correct):.1%})")
print(f"   alucinadas: {n_long_h} ({n_long_h/len(hallucinated):.1%})")

# 6. Muestras de respuestas
print(f"\n5. Muestras de respuestas:")
print(f"   Correcta típica (is_correct=1):")
for _, r in correct.head(3).iterrows():
    print(f"     [{r['llm_response'][:60]}]")
print(f"   Alucinada típica (is_correct=0):")
for _, r in hallucinated.head(3).iterrows():
    print(f"     [{r['llm_response'][:60]}]")
