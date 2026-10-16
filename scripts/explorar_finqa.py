#!/usr/bin/env python3
"""explorar_finqa.py — Explora financiero_finqa y diseña la conversión a 4-variante."""

import pandas as pd
from pathlib import Path

CSV = Path(r"C:\ProgramData\benchmark_corpus\financiero_finqa\finqa-hallucination-detection.csv")
df = pd.read_csv(CSV)

print("=" * 60)
print("  financiero_finqa — Exploración")
print("=" * 60)
print(f"\nShape: {df.shape}")
print(f"Columnas: {list(df.columns)}")

print(f"\nDistribución de is_correct:")
print(df["is_correct"].value_counts())

# Queries con ambas variantes
correct = df[df["is_correct"] == 1]
hallucinated = df[df["is_correct"] == 0]
correct_queries = set(correct["query"])
hallucinated_queries = set(hallucinated["query"])
paired = correct_queries & hallucinated_queries

print(f"\nQueries con ambas variantes: {len(paired)}")
print(f"  Correctas: {len(correct_queries)}")
print(f"  Alucinadas: {len(hallucinated_queries)}")
print(f"  Pares posibles: {len(paired)}")

# Para cada query pareada, ver cuántas respuestas correctas/alucinadas tiene
print(f"\nAnálisis de pares por query:")
multi_correct = 0
multi_halluc = 0
for q in list(paired)[:10]:
    n_c = len(correct[correct["query"] == q])
    n_h = len(hallucinated[hallucinated["query"] == q])
    print(f"  query={q[:60]}...  correctas={n_c}  alucinadas={n_h}")
    if n_c > 1:
        multi_correct += 1
    if n_h > 1:
        multi_halluc += 1

print(f"\nQueries con múltiples respuestas correctas: {multi_correct}")
print(f"Queries con múltiples respuestas alucinadas: {multi_halluc}")

# Mostrar un ejemplo completo
print(f"\n--- Ejemplo completo (primera fila) ---")
for col in df.columns:
    val = str(df.iloc[0][col])
    print(f"  {col}: {val[:300]}")

# Diseño de conversión
print(f"\n--- Diseño de conversión ---")
print(f"  A  = context + query + correct answer")
print(f"  A' = correct answer sola")
print(f"  B  = hallucinated answer sola")
print(f"  A'' = context + query + hallucinated answer")
print(f"\n  Marcador: 'Correct answer: '")
print(f"  Para queries sin par (correcta sin alucinada o viceversa):")
print(f"    - Se descartan (no se puede construir A'' o A')")
print(f"  Pares esperados: ~{len(paired)}")