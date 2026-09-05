#!/usr/bin/env python3
"""
scripts/28_construir_corpus_calibracion.py — Corpus real de calibración para reference_penalty
================================================================================================
Construye pares (source, response) desde Afrostnova/Hallucinated_Citation (MIT):
  - POSITIVOS: cita real en A (seed), mutada en B (year→same_author_diff_year,
    authors→same_year_diff_author). Son DATOS REALES con ground truth.
  - NEGATIVOS: cita real A=B idéntica (control) + cita real A vs cita real B
    distinta (sin relación — no debe disparar).

Separa en calibración (70%) / test (30%) ANTES de correr nada, con seed fijo.
Guarda split_manifest.json con el criterio. El test NO se toca.

Estructura de salida (igual a corpus_pilot_A_raw):
  {id, domain, source, response, expected_trigger, ground_truth, sas_result}
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
DATA = BASE / "research" / "cite_calibration"
OUT_DIR = BASE / "research" / "cite_calibration" / "corpus"

SEED = 20260902
CAL_RATIO = 0.70

EXPECTED_REF = [0, 0, 0, 0, 0, 0, 1]  # one-hot en reference_penalty


def autor_principal(authors):
    """Primer autor como 'Apellido' o nombre completo."""
    if not authors:
        return "Desconocido"
    return authors[0].split(",")[0].strip()


def fmt_cita_autor(texto_contexto, autor, anio):
    """Formato 'Autor (Año)' al final del contexto."""
    return f"{texto_contexto} {autor} ({anio})."


def fmt_cita_parentesis(texto_contexto, autor, anio):
    """Formato '(Autor, Año)' al inicio del contexto."""
    return f"({autor}, {anio}) {texto_contexto}."


def main():
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))

    # ── 1. Clasificar ítems ─────────────────────────────────────────────
    pos_author_year = []  # año O autor mutado (positivos)
    neg_by_absence = 0    # mutación en campos NO author/year
    reales = []           # citas reales (R) — negativos

    for cid, info in meta.items():
        campos = set(info.get("changed_fields", []))
        if info["label"] == "HALLUCINATED":
            if "year" in campos or "authors" in campos:
                mut_type = "same_author_diff_year" if "year" in campos and "authors" not in campos else \
                           ("same_year_diff_author" if "authors" in campos and "year" not in campos else "author_and_year")
                pos_author_year.append((cid, info, mut_type))
            else:
                neg_by_absence += 1
        elif info["label"] == "REAL":
            reales.append((cid, info))

    print(f"=== Clasificación ===")
    print(f"  Positivos (year o authors mutado): {len(pos_author_year)}")
    por_tipo = Counter(t for _, _, t in pos_author_year)
    for t, n in por_tipo.most_common():
        print(f"    {t}: {n}")
    print(f"  Negativos potenciales (mutación en otros campos): {neg_by_absence}")
    print(f"  Reales disponibles (R): {len(reales)}")

    # ── 2. Construir pares ──────────────────────────────────────────────
    pares = []

    # Positivos: seed (A) → cita mutada (B)
    for i, (cid, info, mut_type) in enumerate(pos_author_year):
        seed = info["seed"]
        # Cargar la cita mutada del archivo H*.json correspondiente
        subtype = info["subtype"]
        archivo = DATA / f"{subtype}.json"
        citas = json.loads(archivo.read_text(encoding="utf-8"))
        cita_b = next((c for c in citas if c.get("citation_id") == cid), None)
        if cita_b is None:
            continue

        autor_a = autor_principal(seed.get("authors", []))
        autor_b = autor_principal(cita_b.get("authors", []))
        anio_a = seed.get("year", "")
        anio_b = cita_b.get("year", "")

        contexto = f"In their work on {seed.get('_query_topic', 'this topic')}"
        # A: usar autores+y año del SEED (real)
        source = fmt_cita_autor(contexto, autor_a, anio_a)
        # B: usar autores+año de la CITA MUTADA
        response = fmt_cita_autor(contexto, autor_b, anio_b)

        gt = {
            "truth_factual": False,
            "coherence_structural": False,
            "plausibility_score": 0.3,
            "citation_mutation": mut_type,
            "changed_fields": info.get("changed_fields", []),
            "source_citation_id": cid,
        }
        pares.append({
            "id": f"CAL_{cid}",
            "domain": "academic_citations",
            "source": source,
            "response": response,
            "expected_trigger": EXPECTED_REF,
            "ground_truth": gt,
            "sas_result": None,
            "mutation_type": mut_type,
            "citation_id": cid,
            "split": None,  # se asigna abajo
        })

    # Negativos (controles): cita real A = B idéntica
    for i, (cid, info) in enumerate(reales[: len(pos_author_year)]):
        seed = info["seed"]
        autor = autor_principal(seed.get("authors", []))
        anio = seed.get("year", "")
        contexto = f"In their work on {seed.get('_query_topic', 'this topic')}"
        texto = fmt_cita_autor(contexto, autor, anio)
        gt = {
            "truth_factual": True,
            "coherence_structural": True,
            "plausibility_score": 0.95,
            "citation_mutation": "none",
            "source_citation_id": cid,
        }
        pares.append({
            "id": f"CAL_{cid}",
            "domain": "academic_citations",
            "source": texto,
            "response": texto,  # idéntica
            "expected_trigger": EXPECTED_REF,
            "ground_truth": gt,
            "sas_result": None,
            "mutation_type": "control",
            "citation_id": cid,
            "split": None,
        })

    print(f"\n=== Pares construidos: {len(pares)} ===")
    por_mut = Counter(p["mutation_type"] for p in pares)
    for t, n in por_mut.most_common():
        print(f"  {t}: {n}")

    # ── 3. Split ANTES de mirar nada (seed fija) ────────────────────────
    rng = random.Random(SEED)
    rng.shuffle(pares)
    n_cal = int(len(pares) * CAL_RATIO)
    for i, p in enumerate(pares):
        p["split"] = "calibracion" if i < n_cal else "test"

    cal = [p for p in pares if p["split"] == "calibracion"]
    test = [p for p in pares if p["split"] == "test"]
    print(f"\n=== SPLIT (seed={SEED}, ratio={CAL_RATIO}) ===")
    print(f"  Calibración: {len(cal)}")
    print(f"  Test: {len(test)}")

    # Verificar balance por tipo en cada split
    for nombre, split in [("calibración", cal), ("test", test)]:
        por_mut_split = Counter(p["mutation_type"] for p in split)
        print(f"  {nombre}: {dict(por_mut_split)}")

    # ── 4. Guardar ──────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "corpus_calibracion.jsonl", "w", encoding="utf-8") as f:
        for p in cal:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "corpus_test.jsonl", "w", encoding="utf-8") as f:
        for p in test:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    manifest = {
        "fuente": "Afrostnova/Hallucinated_Citation (CiteTracer, MIT license)",
        "descripcion": "Citas académicas reales con mutaciones LLM controladas + negativos reales",
        "split_criterio": {
            "metodo": "random shuffle con seed fija",
            "seed": SEED,
            "proporcion_calibracion": CAL_RATIO,
            "porcentaje_test": round(1 - CAL_RATIO, 2),
        },
        "n_total": len(pares),
        "n_calibracion": len(cal),
        "n_test": len(test),
        "ids_calibracion": [p["id"] for p in cal],
        "ids_test": [p["id"] for p in test],
        "nota": "El split se generó ANTES de correr el tribunal. El split de test NO se toca hasta que el autor lo pida.",
    }
    with open(DATA / "split_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Corpus y manifest guardados en {OUT_DIR}")


if __name__ == "__main__":
    main()