#!/usr/bin/env python3
"""
scripts/convert_finqa.py — Conversión determinista de financiero_finqa a formato evaluable
═══════════════════════════════════════════════════════════════════════════════

Contexto del dataset:
  financiero_finqa (1,657 filas, MIT) NO tiene queries pareadas entre
  correctas y alucinadas (0 queries idénticas, 0 contextos idénticos).
  Cada fila tiene: query, context, llm_response, is_correct.

  Por lo tanto NO se puede construir el formato 4-variante con el MISMO
  ID (A, A', B, A'' del mismo par). En su lugar construimos:

    correctas (is_correct=1):
      A   = context + query + correct answer  (formato completo)
      A'  = correct answer sola                (negativo limpio)

    alucinadas (is_correct=0):
      A'' = context + query + hallucinated answer (mismo formato, contenido alucinado)
      B   = hallucinated answer sola               (positivo limpio)

Esto da un corpus con control de formato por FILA:
  - Mismo formato: A (correcta completa) vs A'' (alucinada completa)
  - Respuesta sola: A' (correcta) vs B (alucinada)
  - Permite medir: ¿el tribunal distingue contenido cuando el formato es igual?

Salida: reports/pairs_finqa.jsonl (JSON Lines, 1,657 líneas)
Auditoría: reports/metadata_finqa.json

Uso:
    python scripts/convert_finqa.py

Requiere: pandas
"""

from __future__ import annotations

import hashlib
import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import pandas as pd

# ── Rutas ─────────────────────────────────────────────────────────────────
CORPUS = Path(r"C:\ProgramData\benchmark_corpus")
INPUT_CSV = CORPUS / "financiero_finqa" / "finqa-hallucination-detection.csv"
OUTPUT_DIR = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports")
OUTPUT_JSONL = OUTPUT_DIR / "pairs_finqa.jsonl"
OUTPUT_META = OUTPUT_DIR / "metadata_finqa.json"

# Marcador exacto (como N1)
MARCADOR = "Correct answer: "


def construir_a(context: str, query: str, answer: str) -> str:
    """Construye A = context + query + answer (formato completo)."""
    return f"Context:\n{context}\n\nQuestion: {query}\n\n{MARCADOR}{answer}"


def construir_a_pp(context: str, query: str, hallucinated: str) -> str:
    """Construye A'' = context + query + hallucinated answer."""
    return f"Context:\n{context}\n\nQuestion: {query}\n\n{MARCADOR}{hallucinated}"


def generar_id(query: str, response: str) -> str:
    """ID determinista: SHA-256 de query + response, primeros 16 chars."""
    raw = f"{query}|||{response}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def procesar(df: pd.DataFrame) -> Tuple[List[dict], List[str], List[str]]:
    """Procesa el DataFrame completo.

    Returns:
        (pares, errores, warnings)
    """
    pares = []
    errores = []
    warnings = []

    for idx, row in df.iterrows():
        query = str(row["query"] or "").strip()
        context = str(row["context"] or "").strip()
        response = str(row["llm_response"] or "").strip()
        is_correct = bool(row["is_correct"])

        if not query or not context or not response:
            warnings.append(f"fila {idx}: campo vacío (query={len(query)}, "
                            f"context={len(context)}, response={len(response)})")
            continue

        pair_id = generar_id(query, response)

        if is_correct:
            # Correcta: A (completa) + A' (sola)
            a = construir_a(context, query, response)
            a_prime = response
            pares.append({
                "id": pair_id,
                "tipo": "correcta",
                "is_correct": True,
                "query": query,
                "A": a,
                "A_prime": a_prime,
            })
        else:
            # Alucinada: A'' (completa) + B (sola)
            a_pp = construir_a_pp(context, query, response)
            b = response
            pares.append({
                "id": pair_id,
                "tipo": "alucinada",
                "is_correct": False,
                "query": query,
                "A_pp": a_pp,
                "B": b,
            })

    return pares, errores, warnings


def main():
    global OUTPUT_JSONL, OUTPUT_META
    t0 = time.time()

    print("=" * 72)
    print("  CONVERSIÓN — financiero_finqa a formato evaluable")
    print("=" * 72)

    if not INPUT_CSV.exists():
        print(f"  [ERROR] No existe: {INPUT_CSV}")
        sys.exit(1)

    print(f"\n[1/4] Leyendo CSV...")
    df = pd.read_csv(INPUT_CSV)
    print(f"  {len(df)} filas")
    print(f"  correctas: {(df['is_correct'] == 1).sum()}")
    print(f"  alucinadas: {(df['is_correct'] == 0).sum()}")

    print(f"\n[2/4] Procesando...")
    pares, errores, warnings = procesar(df)
    print(f"  {len(pares)} pares generados")
    print(f"  {len(errores)} errores")
    print(f"  {len(warnings)} warnings")

    print(f"\n[3/4] Guardando JSONL...")
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for par in pares:
            f.write(json.dumps(par, ensure_ascii=False) + "\n")

    print(f"[4/4] Auditoría...")
    raw_bytes = OUTPUT_JSONL.read_bytes()
    sha = hashlib.sha256(raw_bytes).hexdigest()
    fingerprint = hashlib.sha256(
        "\n".join(sorted(p["id"] for p in pares)).encode()
    ).hexdigest()[:16]

    n_correctas = sum(1 for p in pares if p["is_correct"])
    n_alucinadas = sum(1 for p in pares if not p["is_correct"])

    metadata = {
        "dataset": "financiero_finqa",
        "fuente": str(INPUT_CSV),
        "n_total": len(pares),
        "n_correctas": n_correctas,
        "n_alucinadas": n_alucinadas,
        "formato": "por fila (sin pares query-idénticos)",
        "marcador": MARCADOR,
        "sha256_jsonl": sha,
        "fingerprint_ids": fingerprint,
        "warnings": warnings[:20],
        "errores": errores[:10],
        "runtime_segundos": round(time.time() - t0, 2),
    }

    with open(OUTPUT_META, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n  JSONL: {OUTPUT_JSONL}")
    print(f"  SHA-256: {sha}")
    print(f"  Fingerprint IDs: {fingerprint}")
    print(f"  Metadata: {OUTPUT_META}")
    print(f"  Runtime: {metadata['runtime_segundos']}s")
    print("=" * 72)


if __name__ == "__main__":
    main()
