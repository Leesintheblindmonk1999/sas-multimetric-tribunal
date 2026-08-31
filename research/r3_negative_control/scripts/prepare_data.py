"""
prepare_data.py — Prepara datos desde benchmark_corpus para ablation y A→C
═══════════════════════════════════════════════════════════════════════════════

Soporta múltiples formatos y suites:
  1. TruthfulQA: archivos .txt emparejados (000N_A_clean.txt + 000N_B_hallucination.txt)
  2. HaluEval-Dialogue: puede ser .txt emparejados, .json, o .csv
  3. HaluEval-QA: idem

Genera:
  1. pares_ablation.json — para ablation_study.py
  2. pares_clean.json   — para pilot_ac.py

Uso:
  python prepare_data.py \
    --truthfulqa-dir "C:/Users/conno/Downloads/SAS-Semantico/benchmark_corpus/truthfulqa" \
    --halu-eval-dialogue-dir "C:/Users/conno/Downloads/SAS-Semantico/benchmark_corpus/halueval_dialogue" \
    --halu-eval-qa-dir "C:/Users/conno/Downloads/SAS-Semantico/benchmark_corpus/halueval_qa" \
    --output-dir ./prepared
"""

from __future__ import annotations

import json
import argparse
import re
from pathlib import Path
from typing import List, Dict, Optional


def parse_truthfulqa_clean(filepath: Path) -> Dict[str, str]:
    """Parsea TruthfulQA *_A_clean.txt"""
    text = filepath.read_text(encoding="utf-8")
    question_match = re.search(r"Question:\s*(.+?)(?=\n\n|Correct answer:|$)", text, re.DOTALL | re.IGNORECASE)
    answer_match = re.search(r"Correct answer:\s*(.+)$", text, re.DOTALL | re.IGNORECASE)
    return {
        "question": question_match.group(1).strip() if question_match else "",
        "correct_answer": answer_match.group(1).strip() if answer_match else "",
    }


def parse_hallucination_file(filepath: Path) -> str:
    """Lee un archivo *_B_hallucination.txt"""
    return filepath.read_text(encoding="utf-8").strip()


def detect_format(directory: Path) -> str:
    """Detecta el formato de archivos en un directorio."""
    files = list(directory.iterdir())

    # Formato 1: pares de archivos .txt (000N_A_clean.txt + 000N_B_hallucination.txt)
    has_clean = any(f.name.endswith("_A_clean.txt") for f in files)
    has_hall = any(f.name.endswith("_B_hallucination.txt") for f in files)
    if has_clean and has_hall:
        return "paired_txt"

    # Formato 2: archivos JSON
    json_files = [f for f in files if f.suffix == ".json"]
    if json_files:
        return "json"

    # Formato 3: archivos CSV
    csv_files = [f for f in files if f.suffix == ".csv"]
    if csv_files:
        return "csv"

    # Formato 4: archivos .txt genéricos (uno por línea o uno por par)
    txt_files = [f for f in files if f.suffix == ".txt"]
    if txt_files:
        return "generic_txt"

    return "unknown"


def load_paired_txt(directory: Path, suite_name: str) -> List[dict]:
    """Carga archivos en formato emparejado .txt"""
    clean_files = sorted(directory.glob("*_A_clean.txt"))

    if not clean_files:
        return []

    all_pares = []

    for clean_file in clean_files:
        match = re.match(r"(\d+)_A_clean\.txt", clean_file.name)
        if not match:
            continue

        idx = match.group(1)
        hallucination_file = directory / f"{idx}_B_hallucination.txt"

        if not hallucination_file.exists():
            continue

        # Parsear según suite
        if "truthfulqa" in suite_name.lower():
            clean_data = parse_truthfulqa_clean(clean_file)
            source = clean_data["question"]
            correct = clean_data["correct_answer"]
        else:
            # HaluEval genérico: asumir que A_clean tiene source + correct answer
            text = clean_file.read_text(encoding="utf-8")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            if len(lines) >= 2:
                source = lines[0]
                correct = lines[1]
            elif len(lines) == 1:
                source = lines[0]
                correct = lines[0]
            else:
                continue

        hallucinated = parse_hallucination_file(hallucination_file)

        if not source or not correct:
            continue

        # A→A
        all_pares.append({
            "source": source, "response": source,
            "label": "sanity", "suite": suite_name, "variant": "A→A",
            "id": f"{suite_name}_{idx}",
        })

        # A→A_clean
        all_pares.append({
            "source": source, "response": correct,
            "label": "sanity", "suite": suite_name, "variant": "A→A_clean",
            "id": f"{suite_name}_{idx}_clean",
        })

        # A→B
        all_pares.append({
            "source": source, "response": hallucinated,
            "label": "hallucination", "suite": suite_name, "variant": "A→B",
            "id": f"{suite_name}_{idx}_hall",
        })

    return all_pares


def load_json_files(directory: Path, suite_name: str) -> List[dict]:
    """Carga archivos JSON"""
    all_pares = []

    for json_file in sorted(directory.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))

            # Intentar detectar estructura
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "data" in data:
                items = data["data"]
            else:
                items = [data]

            for i, item in enumerate(items):
                # Intentar extraer campos comunes
                source = item.get("source") or item.get("question") or item.get("input") or ""
                correct = item.get("correct_answer") or item.get("answer") or item.get("clean") or item.get("response") or ""
                hallucinated = item.get("hallucinated") or item.get("incorrect_answer") or item.get("wrong") or ""

                if not source:
                    continue

                idx = item.get("id", f"{i:04d}")

                # A→A
                all_pares.append({
                    "source": source, "response": source,
                    "label": "sanity", "suite": suite_name, "variant": "A→A",
                    "id": f"{suite_name}_{idx}",
                })

                # A→A_clean
                if correct:
                    all_pares.append({
                        "source": source, "response": correct,
                        "label": "sanity", "suite": suite_name, "variant": "A→A_clean",
                        "id": f"{suite_name}_{idx}_clean",
                    })

                # A→B
                if hallucinated:
                    all_pares.append({
                        "source": source, "response": hallucinated,
                        "label": "hallucination", "suite": suite_name, "variant": "A→B",
                        "id": f"{suite_name}_{idx}_hall",
                    })
        except Exception as e:
            print(f"  [ERROR] {json_file.name}: {e}")

    return all_pares


def load_csv_files(directory: Path, suite_name: str) -> List[dict]:
    """Carga archivos CSV usando pandas si está disponible"""
    try:
        import pandas as pd
    except ImportError:
        print("  [WARN] pandas no instalado, saltando CSV")
        return []

    all_pares = []

    for csv_file in sorted(directory.glob("*.csv")):
        try:
            df = pd.read_csv(csv_file)

            # Detectar columnas
            cols_lower = [c.lower().strip() for c in df.columns]
            col_map = {}
            for c in df.columns:
                cl = c.lower().strip()
                if any(x in cl for x in ["source", "question", "input", "context"]):
                    col_map["source"] = c
                elif any(x in cl for x in ["correct", "clean", "answer", "ground", "best"]):
                    col_map["correct"] = c
                elif any(x in cl for x in ["hallucinat", "incorrect", "wrong", "false"]):
                    col_map["hallucinated"] = c

            if "source" not in col_map:
                print(f"  [SKIP] {csv_file.name}: no columna source/question")
                continue

            for i, row in df.iterrows():
                source = str(row[col_map["source"]]) if pd.notna(row[col_map["source"]]) else ""
                correct = str(row[col_map["correct"]]) if "correct" in col_map and pd.notna(row[col_map["correct"]]) else ""
                hallucinated = str(row[col_map["hallucinated"]]) if "hallucinated" in col_map and pd.notna(row[col_map["hallucinated"]]) else ""

                if not source:
                    continue

                idx = f"{i:04d}"

                all_pares.append({
                    "source": source, "response": source,
                    "label": "sanity", "suite": suite_name, "variant": "A→A",
                    "id": f"{suite_name}_{idx}",
                })

                if correct:
                    all_pares.append({
                        "source": source, "response": correct,
                        "label": "sanity", "suite": suite_name, "variant": "A→A_clean",
                        "id": f"{suite_name}_{idx}_clean",
                    })

                if hallucinated:
                    all_pares.append({
                        "source": source, "response": hallucinated,
                        "label": "hallucination", "suite": suite_name, "variant": "A→B",
                        "id": f"{suite_name}_{idx}_hall",
                    })
        except Exception as e:
            print(f"  [ERROR] {csv_file.name}: {e}")

    return all_pares


def load_generic_txt(directory: Path, suite_name: str) -> List[dict]:
    """Carga archivos .txt genéricos"""
    txt_files = sorted(directory.glob("*.txt"))
    all_pares = []

    for txt_file in txt_files:
        text = txt_file.read_text(encoding="utf-8").strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        if len(lines) >= 3:
            source = lines[0]
            correct = lines[1]
            hallucinated = lines[2]

            idx = txt_file.stem

            all_pares.append({
                "source": source, "response": source,
                "label": "sanity", "suite": suite_name, "variant": "A→A",
                "id": f"{suite_name}_{idx}",
            })
            all_pares.append({
                "source": source, "response": correct,
                "label": "sanity", "suite": suite_name, "variant": "A→A_clean",
                "id": f"{suite_name}_{idx}_clean",
            })
            all_pares.append({
                "source": source, "response": hallucinated,
                "label": "hallucination", "suite": suite_name, "variant": "A→B",
                "id": f"{suite_name}_{idx}_hall",
            })

    return all_pares


def load_suite(directory: Path, suite_name: str) -> List[dict]:
    """Carga un suite detectando automáticamente el formato."""
    if not directory.exists():
        print(f"  [SKIP] Directorio no existe: {directory}")
        return []

    fmt = detect_format(directory)
    print(f"  Formato detectado: {fmt}")

    if fmt == "paired_txt":
        return load_paired_txt(directory, suite_name)
    elif fmt == "json":
        return load_json_files(directory, suite_name)
    elif fmt == "csv":
        return load_csv_files(directory, suite_name)
    elif fmt == "generic_txt":
        return load_generic_txt(directory, suite_name)
    else:
        print(f"  [WARN] Formato desconocido en {directory}")
        print(f"  Archivos encontrados: {[f.name for f in directory.iterdir()][:10]}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Prepara datos para ablation y A→C")
    parser.add_argument("--truthfulqa-dir", type=Path, default=None,
                        help="Directorio con archivos de TruthfulQA")
    parser.add_argument("--halu-eval-dialogue-dir", type=Path, default=None,
                        help="Directorio con archivos de HaluEval-Dialogue")
    parser.add_argument("--halu-eval-qa-dir", type=Path, default=None,
                        help="Directorio con archivos de HaluEval-QA")
    parser.add_argument("--output-dir", type=Path, default=Path("./prepared"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_pares = []
    suites = [
        (args.truthfulqa_dir, "truthfulqa"),
        (args.halu_eval_dialogue_dir, "halu_eval_dialogue"),
        (args.halu_eval_qa_dir, "halu_eval_qa"),
    ]

    for directory, suite_name in suites:
        if directory and directory.exists():
            print(f"\n[{suite_name}]")
            pares = load_suite(directory, suite_name)
            all_pares.extend(pares)
            print(f"  → {len(pares)} pares generados")

    if not all_pares:
        print("\nERROR: No se generaron pares. Verificá las rutas.")
        return

    # Guardar pares para ablation
    ablation_path = args.output_dir / "pares_ablation.json"
    with open(ablation_path, "w", encoding="utf-8") as f:
        json.dump(all_pares, f, indent=2, ensure_ascii=False)
    print(f"\n  → Ablation: {ablation_path} ({len(all_pares)} pares)")

    # Guardar pares limpios para A→C
    clean_pares = [p for p in all_pares if p["label"] == "sanity" and p.get("variant") != "A→A"]
    aa_pares = [p for p in all_pares if p["variant"] == "A→A"]
    clean_pares = clean_pares + aa_pares[:min(len(aa_pares), 50)]

    ac_path = args.output_dir / "pares_clean.json"
    with open(ac_path, "w", encoding="utf-8") as f:
        json.dump(clean_pares, f, indent=2, ensure_ascii=False)
    print(f"  → A→C piloto: {ac_path} ({len(clean_pares)} pares limpios)")

    # Estadísticas
    by_suite = {}
    for p in all_pares:
        s = p["suite"]
        if s not in by_suite:
            by_suite[s] = {"sanity": 0, "hallucination": 0}
        by_suite[s][p["label"]] += 1

    print(f"\n  Estadísticas por suite:")
    for suite, counts in by_suite.items():
        print(f"    {suite}: {counts['sanity']} sanity + {counts['hallucination']} hallucination = {counts['sanity'] + counts['hallucination']} total")

    print(f"\n  TOTAL: {len(all_pares)} pares")
    print("\n" + "=" * 70)
    print("LISTO. Ahora podés correr:")
    print(f"  python ablation_study.py --input {ablation_path}")
    print(f"  python pilot_ac.py --input {ac_path} --n 100")


if __name__ == "__main__":
    main()