"""
prepare_data.py — Prepara datos desde benchmark_corpus para ablation y A→C
═══════════════════════════════════════════════════════════════════════════════

Lee archivos del benchmark (CSV/JSON) y genera:
  1. pares_ablation.json — para ablation_study.py
  2. pares_clean.json   — para pilot_ac.py

Uso:
  python prepare_data.py --truthfulqa-dir "C:/Users/conno/Downloads/SAS-Semántico/benchmark_corpus/truthfulqa"                          --output-dir ./prepared

Soporta:
  - TruthfulQA: busca archivos con columnas Question, Best Answer, Incorrect Answers
  - HaluEval: busca archivos con columnas source, hallucinated, clean (o similares)
"""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas no instalado. Ejecutá: pip install pandas")
    sys.exit(1)


def load_truthfulqa(directory: Path) -> List[dict]:
    """Carga pares de TruthfulQA desde CSV/JSON."""
    files = list(directory.glob("*.csv")) + list(directory.glob("*.json"))
    if not files:
        print(f"  [WARN] No se encontraron archivos en {directory}")
        return []

    all_pares = []
    for f in files:
        print(f"  Leyendo {f.name} ...")
        if f.suffix == ".csv":
            df = pd.read_csv(f)
        else:
            df = pd.read_json(f)

        # Detectar columnas
        cols = [c.lower().strip() for c in df.columns]
        col_map = {}
        for c in df.columns:
            cl = c.lower().strip()
            if "question" in cl or "source" in cl:
                col_map["source"] = c
            elif "best" in cl and "answer" in cl:
                col_map["clean"] = c
            elif "incorrect" in cl or "wrong" in cl or "hallucinat" in cl:
                col_map["incorrect"] = c
            elif "correct" in cl and "answer" in cl and "best" not in cl:
                col_map["clean"] = c

        if "source" not in col_map:
            print(f"    [SKIP] No se detectó columna 'source/question' en {f.name}")
            print(f"    Columnas disponibles: {list(df.columns)}")
            continue

        source_col = col_map["source"]
        clean_col = col_map.get("clean", None)
        incorrect_col = col_map.get("incorrect", None)

        for _, row in df.iterrows():
            source = str(row[source_col])

            # Par sanity (A→A): source con sí mismo
            all_pares.append({
                "source": source,
                "response": source,
                "label": "sanity",
                "suite": "truthfulqa",
                "variant": "A→A",
            })

            # Par sanity con respuesta limpia (A→A_clean)
            if clean_col and pd.notna(row[clean_col]):
                clean = str(row[clean_col])
                all_pares.append({
                    "source": source,
                    "response": clean,
                    "label": "sanity",
                    "suite": "truthfulqa",
                    "variant": "A→A_clean",
                })

            # Par alucinación (A→B)
            if incorrect_col and pd.notna(row[incorrect_col]):
                incorrect = str(row[incorrect_col])
                all_pares.append({
                    "source": source,
                    "response": incorrect,
                    "label": "hallucination",
                    "suite": "truthfulqa",
                    "variant": "A→B",
                })

    print(f"  → {len(all_pares)} pares generados de TruthfulQA")
    return all_pares


def load_halu_eval(directory: Path) -> List[dict]:
    """Carga pares de HaluEval desde CSV/JSON."""
    files = list(directory.glob("*.csv")) + list(directory.glob("*.json"))
    all_pares = []

    for f in files:
        print(f"  Leyendo {f.name} ...")
        if f.suffix == ".csv":
            df = pd.read_csv(f)
        else:
            df = pd.read_json(f)

        cols = [c.lower().strip() for c in df.columns]
        col_map = {}
        for c in df.columns:
            cl = c.lower().strip()
            if "source" in cl or "input" in cl or "question" in cl:
                col_map["source"] = c
            elif "clean" in cl or "correct" in cl or "ground" in cl:
                col_map["clean"] = c
            elif "hallucinat" in cl or "incorrect" in cl or "wrong" in cl:
                col_map["hallucinated"] = c
            elif "response" in cl and "clean" not in cl and "hallucinat" not in cl:
                col_map["response"] = c

        if "source" not in col_map:
            print(f"    [SKIP] No se detectó columna 'source' en {f.name}")
            continue

        source_col = col_map["source"]
        clean_col = col_map.get("clean", col_map.get("response", None))
        hallucinated_col = col_map.get("hallucinated", None)

        suite_name = "halu_eval"
        if "dialogue" in f.name.lower():
            suite_name = "halu_eval_dialogue"
        elif "qa" in f.name.lower() or "question" in f.name.lower():
            suite_name = "halu_eval_qa"

        for _, row in df.iterrows():
            source = str(row[source_col])

            # Sanity A→A
            all_pares.append({
                "source": source,
                "response": source,
                "label": "sanity",
                "suite": suite_name,
                "variant": "A→A",
            })

            # A→A_clean
            if clean_col and pd.notna(row[clean_col]):
                clean = str(row[clean_col])
                all_pares.append({
                    "source": source,
                    "response": clean,
                    "label": "sanity",
                    "suite": suite_name,
                    "variant": "A→A_clean",
                })

            # A→B
            if hallucinated_col and pd.notna(row[hallucinated_col]):
                hallucinated = str(row[hallucinated_col])
                all_pares.append({
                    "source": source,
                    "response": hallucinated,
                    "label": "hallucination",
                    "suite": suite_name,
                    "variant": "A→B",
                })

    print(f"  → {len(all_pares)} pares generados de HaluEval")
    return all_pares


def main():
    parser = argparse.ArgumentParser(description="Prepara datos para ablation y A→C")
    parser.add_argument("--truthfulqa-dir", type=Path, default=None,
                        help="Directorio con archivos de TruthfulQA")
    parser.add_argument("--halu-eval-dir", type=Path, default=None,
                        help="Directorio con archivos de HaluEval")
    parser.add_argument("--output-dir", type=Path, default=Path("./prepared"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_pares = []

    if args.truthfulqa_dir and args.truthfulqa_dir.exists():
        print("\n[TruthfulQA]")
        all_pares.extend(load_truthfulqa(args.truthfulqa_dir))

    if args.halu_eval_dir and args.halu_eval_dir.exists():
        print("\n[HaluEval]")
        all_pares.extend(load_halu_eval(args.halu_eval_dir))

    if not all_pares:
        print("\nERROR: No se generaron pares. Verificá las rutas.")
        sys.exit(1)

    # Guardar pares para ablation (todos: sanity + hallucination)
    ablation_path = args.output_dir / "pares_ablation.json"
    with open(ablation_path, "w", encoding="utf-8") as f:
        json.dump(all_pares, f, indent=2, ensure_ascii=False)
    print(f"\n  → Ablation: {ablation_path} ({len(all_pares)} pares)")

    # Guardar pares limpios para A→C (solo sanity, con respuesta limpia)
    clean_pares = [p for p in all_pares if p["label"] == "sanity" and p.get("variant") != "A→A"]
    # También incluir algunos A→A para comparación
    aa_pares = [p for p in all_pares if p["variant"] == "A→A"]
    clean_pares = clean_pares + aa_pares[:min(len(aa_pares), 50)]

    ac_path = args.output_dir / "pares_clean.json"
    with open(ac_path, "w", encoding="utf-8") as f:
        json.dump(clean_pares, f, indent=2, ensure_ascii=False)
    print(f"  → A→C piloto: {ac_path} ({len(clean_pares)} pares limpios)")

    print("\n" + "=" * 70)
    print("LISTO. Ahora podés correr:")
    print(f"  python ablation_study.py --input {ablation_path}")
    print(f"  python pilot_ac.py --input {ac_path} --n 100")


if __name__ == "__main__":
    main()