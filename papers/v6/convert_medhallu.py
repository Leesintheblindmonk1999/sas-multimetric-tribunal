#!/usr/bin/env python3
"""
scripts/convert_medhallu.py — Conversión determinista de medico_medhallu a 4 variantes
═══════════════════════════════════════════════════════════════════════════════

Lee los archivos Parquet de medico_medhallu (pqa_labeled + pqa_artificial,
10,000 muestras totales) y genera para cada muestra 4 variantes:

  A   : Question + Knowledge + Ground Truth  (formato completo, respuesta correcta)
  A'  : Ground Truth sola                     (negativo limpio)
  B   : Hallucinated Answer sola              (positivo limpio)
  A'' : Question + Knowledge + Hallucinated Answer  (mismo contexto, contenido alucinado)

Salida: pairs_medico_medhallu_10k.jsonl (JSON Lines, 10,000 líneas)
Auditoría: metadata_medhallu.json (manifiesto con SHA-256, conteos, warnings)

Uso:
    python scripts/convert_medhallu.py

Requiere: pyarrow (para leer Parquet)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ── Rutas ─────────────────────────────────────────────────────────────────
CORPUS = Path(r"C:\ProgramData\benchmark_corpus")
INPUT_DIR = CORPUS / "medico_medhallu"
OUTPUT_DIR = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports")
OUTPUT_JSONL = OUTPUT_DIR / "pairs_medico_medhallu_10k.jsonl"
OUTPUT_META = OUTPUT_DIR / "metadata_medhallu.json"

# Splits
SPLITS = [
    ("pqa_labeled", INPUT_DIR / "pqa_labeled" / "train-00000-of-00001.parquet"),
    ("pqa_artificial", INPUT_DIR / "pqa_artificial" / "train-00000-of-00001.parquet"),
]

# Marcador exacto (como en N1)
MARCADOR = "Ground Truth: "


def construir_a(question: str, knowledge: str, ground_truth: str) -> str:
    """Construye A = Question + Knowledge + Ground Truth (formato completo)."""
    ctx = f"Question: {question}\n\nKnowledge: {knowledge}"
    return f"{ctx}\n\n{MARCADOR}{ground_truth}"


def construir_a_pp(question: str, knowledge: str, hallucinated: str) -> str:
    """Construye A'' = Question + Knowledge + Hallucinated Answer (mismo formato que A)."""
    ctx = f"Question: {question}\n\nKnowledge: {knowledge}"
    return f"{ctx}\n\n{MARCADOR}{hallucinated}"


def generar_id(ground_truth: str, hallucinated: str) -> str:
    """ID determinista: SHA-256 de A' + B, primeros 16 chars."""
    raw = f"{ground_truth}|||{hallucinated}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def knowledge_to_str(knowledge) -> str:
    """Convierte el campo Knowledge (lista o string) a string plano."""
    if isinstance(knowledge, list):
        return " ".join(str(k) for k in knowledge)
    return str(knowledge or "")


def procesar_split(split_name: str, parquet_path: Path) -> List[dict]:
    """Procesa un split de Parquet y devuelve lista de pares."""
    import pyarrow.parquet as pq

    print(f"  Leyendo {split_name} desde {parquet_path}...")
    t = pq.read_table(str(parquet_path))
    rows = t.num_rows
    print(f"    {rows} filas, columnas: {t.column_names}")

    pares = []
    for i in range(rows):
        question = str(t.column("Question")[i].as_py() or "")
        knowledge = knowledge_to_str(t.column("Knowledge")[i].as_py())
        ground_truth = str(t.column("Ground Truth")[i].as_py() or "")
        hallucinated = str(t.column("Hallucinated Answer")[i].as_py() or "")
        difficulty = str(t.column("Difficulty Level")[i].as_py() or "")
        category = str(t.column("Category of Hallucination")[i].as_py() or "")

        pair_id = generar_id(ground_truth, hallucinated)

        a = construir_a(question, knowledge, ground_truth)
        a_prime = ground_truth
        b = hallucinated
        a_pp = construir_a_pp(question, knowledge, hallucinated)

        pares.append({
            "id": pair_id,
            "split": split_name,
            "difficulty": difficulty,
            "category": category,
            "A": a,
            "A_prime": a_prime,
            "B": b,
            "A_pp": a_pp,
        })

    return pares


def audit_dataset_pairs(pares: List[dict]) -> Tuple[bool, List[str], List[str]]:
    """Auditoría forense previa a la ejecución.

    Returns:
        (paso_ok, errores, warnings)
    """
    print("\n" + "=" * 72)
    print("  AUDITORÍA FORENSE — medico_medhallu")
    print("=" * 72)

    errores: List[str] = []
    warnings: List[str] = []
    ids_vistos: set = set()
    a_prime_vistos: set = set()
    b_vistos: set = set()

    for i, par in enumerate(pares):
        lineno = i + 1
        pid = par["id"]

        # a) No vacíos
        for campo in ["A", "A_prime", "B", "A_pp"]:
            val = par.get(campo)
            if val is None:
                errores.append(f"  Línea {lineno} [{pid}]: {campo} es None")
            elif not val.strip():
                errores.append(f"  Línea {lineno} [{pid}]: {campo} está vacío")

        if errores:
            continue  # no seguir auditando si falta contenido

        # b) Consistencia estructural: A' debe ser subcadena de A
        if par["A_prime"] not in par["A"]:
            errores.append(
                f"  Línea {lineno} [{pid}]: A' NO es subcadena de A"
            )

        # A'' debe contener el mismo contexto que A (Question + Knowledge)
        # y terminar con MARCADOR + B
        ctx_a = par["A"].split(f"\n\n{MARCADOR}")[0] if MARCADOR in par["A"] else ""
        ctx_app = par["A_pp"].split(f"\n\n{MARCADOR}")[0] if MARCADOR in par["A_pp"] else ""
        if ctx_a != ctx_app:
            errores.append(
                f"  Línea {lineno} [{pid}]: el contexto de A y A'' difiere"
            )

        # Verificar que A'' termine con MARCADOR + B
        expected_suffix = f"{MARCADOR}{par['B']}"
        if not par["A_pp"].endswith(expected_suffix):
            errores.append(
                f"  Línea {lineno} [{pid}]: A'' no termina con MARCADOR + B"
            )

        # c) Anomalías de longitud
        len_a = len(par["A"])
        len_ap = len(par["A_prime"])
        len_b = len(par["B"])
        len_app = len(par["A_pp"])

        if len_ap > 0 and len_a / len_ap > 10:
            warnings.append(
                f"  Línea {lineno} [{pid}]: relación A/A' = {len_a}/{len_ap} = {len_a/len_ap:.1f}x (> 10x)"
            )
        if len_b > 0 and len_app / len_b > 10:
            warnings.append(
                f"  Línea {lineno} [{pid}]: relación A''/B = {len_app}/{len_b} = {len_app/len_b:.1f}x (> 10x)"
            )

        # d) Unicidad
        if pid in ids_vistos:
            errores.append(f"  Línea {lineno} [{pid}]: ID duplicado")
        ids_vistos.add(pid)

        ap_normalized = par["A_prime"].strip().lower()
        b_normalized = par["B"].strip().lower()
        if ap_normalized in b_vistos:
            warnings.append(f"  Línea {lineno} [{pid}]: A' duplicado (contenido idéntico a otro par)")
        if b_normalized in a_prime_vistos:
            warnings.append(f"  Línea {lineno} [{pid}]: B duplicado (contenido idéntico a otro par)")
        a_prime_vistos.add(ap_normalized)
        b_vistos.add(b_normalized)

    # Reporte
    print(f"\n  Total pares auditados: {len(pares)}")
    print(f"  IDs únicos: {len(ids_vistos)}")
    print(f"  Errores: {len(errores)}")
    print(f"  Warnings: {len(warnings)}")

    if errores:
        print(f"\n  ❌ AUDITORÍA FALLÓ — {len(errores)} error(es):")
        for e in errores[:20]:
            print(e)
        if len(errores) > 20:
            print(f"  ... y {len(errores) - 20} más")
        return False, errores, warnings
    else:
        print(f"\n  ✅ AUDITORÍA PASÓ — 0 errores")
        return True, errores, warnings


def main():
    print("=" * 72)
    print("  CONVERSIÓN — medico_medhallu → 4 variantes (A, A', B, A'')")
    print(f"  Splits: pqa_labeled (1,000) + pqa_artificial (9,000) = 10,000")
    print("=" * 72)

    t_start = time.time()

    # 1. Verificar que los archivos existen
    print("\n[1/4] Verificando archivos fuente...")
    for name, path in SPLITS:
        if not path.exists():
            print(f"  ❌ No encontrado: {path}")
            sys.exit(1)
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  ✅ {name}: {path.name} ({size_mb:.1f} MB)")

    # 2. Cargar y convertir
    print("\n[2/4] Cargando y convirtiendo...")
    todos_pares: List[dict] = []
    for name, path in SPLITS:
        pares = procesar_split(name, path)
        todos_pares.extend(pares)
        print(f"    → {len(pares)} pares generados")

    print(f"\n  Total pares: {len(todos_pares)}")

    # 3. Auditoría forense
    print("\n[3/4] Ejecutando auditoría forense...")
    paso_ok, errores, warnings = audit_dataset_pairs(todos_pares)

    if not paso_ok:
        print(f"\n  ❌ ABORTANDO — {len(errores)} errores de auditoría")
        sys.exit(1)

    # 4. Guardar JSONL
    print("\n[4/4] Guardando resultados...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for par in todos_pares:
            f.write(json.dumps(par, ensure_ascii=False) + "\n")

    # SHA-256 del JSONL
    sha256_hash = hashlib.sha256()
    with open(OUTPUT_JSONL, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    sha256_hex = sha256_hash.hexdigest()

    # Metadata
    metadata = {
        "dataset": "medico_medhallu",
        "total_samples": len(todos_pares),
        "splits": {
            "pqa_labeled": sum(1 for p in todos_pares if p["split"] == "pqa_labeled"),
            "pqa_artificial": sum(1 for p in todos_pares if p["split"] == "pqa_artificial"),
        },
        "passed_checks": paso_ok,
        "total_errors": len(errores),
        "total_warnings": len(warnings),
        "sha256_hash": sha256_hex,
        "output_file": str(OUTPUT_JSONL),
        "timestamp": "2026-10-12",
        "runtime_segundos": round(time.time() - t_start, 1),
        "campos": {
            "A": "Question + Knowledge + Ground Truth (formato completo)",
            "A_prime": "Ground Truth sola (negativo limpio)",
            "B": "Hallucinated Answer sola (positivo limpio)",
            "A_pp": "Question + Knowledge + Hallucinated Answer (mismo contexto, contenido alucinado)",
        },
    }

    with open(OUTPUT_META, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Resumen final
    print(f"\n  JSONL guardado: {OUTPUT_JSONL}")
    print(f"  SHA-256: {sha256_hex}")
    print(f"  Metadata: {OUTPUT_META}")
    print(f"  Runtime: {metadata['runtime_segundos']:.1f}s")

    print("\n" + "=" * 72)
    print("  RESUMEN DE CONVERSIÓN")
    print("=" * 72)
    print(f"  Total muestras: {metadata['total_samples']}")
    print(f"    pqa_labeled:    {metadata['splits']['pqa_labeled']}")
    print(f"    pqa_artificial: {metadata['splits']['pqa_artificial']}")
    print(f"  Auditoría: {'✅ PASÓ' if paso_ok else '❌ FALLÓ'}")
    print(f"  Errores: {metadata['total_errors']}")
    print(f"  Warnings: {metadata['total_warnings']}")
    print(f"  SHA-256: {sha256_hex}")
    print(f"  Runtime: {metadata['runtime_segundos']:.1f}s")
    print("=" * 72)


if __name__ == "__main__":
    main()