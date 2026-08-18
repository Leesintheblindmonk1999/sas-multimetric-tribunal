#!/usr/bin/env python3
"""
SAS Multimetric Tribunal — Validation Runner
=============================================
Evaluates all (source, response) pairs in a benchmark dataset directory
and produces a structured validation report.

Usage:
    python scripts/run_validation.py --data-dir ./data/benchmark_sample --output ./reports/validation_report.json
    python scripts/run_validation.py --data-dir ./data/benchmark_sample --verbose
"""

import os
import sys
import json
import argparse
import glob
from pathlib import Path
from typing import List, Tuple, Dict

# Add parent to path so we can import core
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.tribunal_multimetrico import TribunalMultimetrico


def load_pairs(data_dir: str) -> List[Tuple[str, str, str, str]]:
    """
    Load (source, response, label, source_file) pairs from a benchmark directory.
    
    Expected structure:
        data_dir/
            suite_name/
                XXXX_A_clean.txt          # Source text (ground truth)
                XXXX_B_hallucination.txt  # Hallucinated response
    
    For each pair:
      - Control pair: (source, source, "CONTROL") — should be COHERENT
      - Hallucination pair: (source, hallucination, "HALLUCINATION") — should be COLLAPSE/RUPTURE
    
    Returns:
        List of (source, response, label, source_file) tuples
    """
    pairs = []
    suites = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
    
    if not suites:
        suites = [""]  # Flat structure
    
    for suite in suites:
        suite_path = os.path.join(data_dir, suite) if suite else data_dir
        suite_name = suite if suite else os.path.basename(data_dir)
        
        # Find all clean files (source texts)
        clean_files = sorted(glob.glob(os.path.join(suite_path, "*_A_clean.txt")))
        
        for clean_file in clean_files:
            base = os.path.basename(clean_file).replace("_A_clean.txt", "")
            hall_file = os.path.join(suite_path, f"{base}_B_hallucination.txt")
            
            if not os.path.exists(hall_file):
                continue
            
            try:
                with open(clean_file, "r", encoding="utf-8", errors="replace") as f:
                    source_text = f.read().strip()
                
                with open(hall_file, "r", encoding="utf-8", errors="replace") as f:
                    hall_text = f.read().strip()
            except Exception:
                continue
            
            if not source_text or not hall_text:
                continue
            
            # Control pair: source → source (should be COHERENT)
            pairs.append((source_text, source_text, "CONTROL", f"{suite_name}/{base}_A"))
            # Hallucination pair: source → hallucinated response (should be COLLAPSE/RUPTURE)
            pairs.append((source_text, hall_text, "HALLUCINATION", f"{suite_name}/{base}_B"))
    
    return pairs


def compute_metrics(results: List[Dict]) -> Dict:
    """Compute confusion matrix and derived metrics."""
    tp = sum(1 for r in results if r["label"] == "HALLUCINATION" and r["zone"] in ("F-S", "B"))
    fp = sum(1 for r in results if r["label"] == "CONTROL" and r["zone"] in ("F-S", "B"))
    fn = sum(1 for r in results if r["label"] == "HALLUCINATION" and r["zone"] == "A")
    tn = sum(1 for r in results if r["label"] == "CONTROL" and r["zone"] == "A")
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
    
    return {
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn
        },
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4)
        },
        "total_pairs": len(results)
    }


def main():
    parser = argparse.ArgumentParser(
        description="SAS Multimetric Tribunal — Validation Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_validation.py --data-dir ./data/benchmark_sample
  python scripts/run_validation.py --data-dir ./data/benchmark_sample --verbose
  python scripts/run_validation.py --data-dir ./data/benchmark_sample --output ./reports/validation_report.json
        """
    )
    parser.add_argument("--data-dir", required=True, help="Path to benchmark dataset directory")
    parser.add_argument("--output", default=None, help="Path to output JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-pair results")
    parser.add_argument("--max-pairs", type=int, default=None, help="Limit number of pairs to evaluate")
    args = parser.parse_args()
    
    print("=" * 60)
    print("SAS Multimetric Tribunal — Validation")
    print("=" * 60)
    
    # Load pairs
    print(f"\n📂 Loading pairs from: {args.data_dir}")
    pairs = load_pairs(args.data_dir)
    print(f"   Found {len(pairs)} pairs ({sum(1 for p in pairs if p[2]=='CONTROL')} control, {sum(1 for p in pairs if p[2]=='HALLUCINATION')} hallucination)")
    
    if args.max_pairs:
        pairs = pairs[:args.max_pairs]
        print(f"   Limited to {len(pairs)} pairs")
    
    # Initialize tribunal
    print("\n⚙️  Initializing TribunalMultimetrico...")
    tribunal = TribunalMultimetrico()
    
    # Evaluate
    print(f"\n🔍 Evaluating {len(pairs)} pairs...\n")
    results = []
    
    for i, (source, response, label, source_file) in enumerate(pairs, 1):
        verdict = tribunal.evaluar(source, response)
        
        result = {
            "pair_id": i,
            "source_file": source_file,
            "label": label,
            "isi_final": round(verdict.isi_final, 4),
            "zone": verdict.codigo_zona,
            "risk": verdict.riesgo,
            "modules_fired": [m.nombre for m in verdict.modulos_disparados] if verdict.modulos_disparados else [],
            "isi_hard": round(verdict.isi_hard, 4) if hasattr(verdict, 'isi_hard') else None
        }
        results.append(result)
        
        if args.verbose:
            is_control = label == "CONTROL"
            is_coherent = verdict.codigo_zona == "A"
            is_collapse_or_rupture = verdict.codigo_zona in ("F-S", "B")
            status = "✅" if (is_control and is_coherent) or (not is_control and is_collapse_or_rupture) else "❌"
            print(f"  [{i:4d}/{len(pairs)}] {status} {source_file:40s} ISI={verdict.isi_final:.4f} → {verdict.codigo_zona:10s} (expected: {label})")
    
    # Compute metrics
    metrics = compute_metrics(results)
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    
    cm = metrics["confusion_matrix"]
    print(f"\n  Confusion Matrix:")
    print(f"                    ┌──────────────┬──────────────┐")
    print(f"                    │  Detected    │  Not detected│")
    print(f"    ───────────────┼──────────────┼──────────────┤")
    print(f"    Hallucination  │   TP={cm['true_positive']:<4d}    │   FN={cm['false_negative']:<4d}    │")
    print(f"    Control        │   FP={cm['false_positive']:<4d}    │   TN={cm['true_negative']:<4d}    │")
    print(f"                    └──────────────┴──────────────┘")
    
    m = metrics["metrics"]
    print(f"\n  Metrics:")
    print(f"    F1 Score:       {m['f1']:.4f}")
    print(f"    Precision:      {m['precision']:.4f}")
    print(f"    Recall:         {m['recall']:.4f}")
    print(f"    Accuracy:       {m['accuracy']:.4f}")
    print(f"    Total pairs:    {metrics['total_pairs']}")
    
    # Zone distribution
    zones = {}
    for r in results:
        zone = r["zone"]
        zones[zone] = zones.get(zone, 0) + 1
    print(f"\n  Zone Distribution:")
    for zone, count in sorted(zones.items()):
        print(f"    {zone}: {count}")
    
    # Save report
    if args.output:
        output_path = args.output
        report = {
            "metadata": {
                "tool": "SAS Multimetric Tribunal",
                "version": "1.0.0",
                "kappa_D": 0.56,
                "kappa_R": 0.15
            },
            "results": results,
            "summary": metrics
        }
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Report saved to: {output_path}")
    
    print("\n" + "=" * 60)
    return 0 if m["f1"] > 0.95 else 1


if __name__ == "__main__":
    sys.exit(main())
