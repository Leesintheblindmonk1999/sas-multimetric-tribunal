#!/usr/bin/env python3
"""
SAS Multimetric Tribunal — Dataset Sampler
===========================================
Samples a balanced subset of (source, response) pairs from the full benchmark
corpus for use in validation and testing.

Usage:
    python scripts/sample_dataset.py \
        --input-dir ../benchmark_corpus \
        --output-dir ./data/benchmark_sample \
        --pairs-per-suite 100
"""

import os
import sys
import json
import argparse
import glob
import random
import shutil
from pathlib import Path


def sample_pairs(input_dir: str, output_dir: str, pairs_per_suite: int = 100, seed: int = 42):
    """
    Sample balanced pairs from each benchmark suite.
    
    For each suite, selects `pairs_per_suite` pairs (one clean + one hallucination each),
    ensuring balanced representation across all suites.
    """
    random.seed(seed)
    
    # Discover suites
    suites = []
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isdir(item_path):
            # Check if it contains pair files
            clean_files = glob.glob(os.path.join(item_path, "*_A_clean.txt"))
            if clean_files:
                suites.append(item)
    
    if not suites:
        # Try flat structure
        clean_files = sorted(glob.glob(os.path.join(input_dir, "*_A_clean.txt")))
        if clean_files:
            suites = [""]
    
    print(f"Found {len(suites)} suites: {suites}")
    
    total_copied = 0
    
    for suite in suites:
        suite_input = os.path.join(input_dir, suite) if suite else input_dir
        suite_output = os.path.join(output_dir, suite) if suite else output_dir
        
        os.makedirs(suite_output, exist_ok=True)
        
        # Find all clean files
        clean_files = sorted(glob.glob(os.path.join(suite_input, "*_A_clean.txt")))
        
        # Extract base names
        all_bases = []
        for cf in clean_files:
            base = os.path.basename(cf).replace("_A_clean.txt", "")
            hall_file = os.path.join(suite_input, f"{base}_B_hallucination.txt")
            if os.path.exists(hall_file):
                all_bases.append(base)
        
        print(f"\n  Suite '{suite or '(root)'}': {len(all_bases)} complete pairs available")
        
        # Sample
        sample_size = min(pairs_per_suite, len(all_bases))
        sampled_bases = random.sample(all_bases, sample_size)
        
        for base in sampled_bases:
            for suffix, label in [("_A_clean.txt", "clean"), ("_B_hallucination.txt", "hallucination")]:
                src = os.path.join(suite_input, f"{base}{suffix}")
                dst = os.path.join(suite_output, f"{base}{suffix}")
                shutil.copy2(src, dst)
                total_copied += 1
        
        print(f"  → Sampled {sample_size} pairs → {suite_output}")
    
    print(f"\n✅ Total: {total_copied} files copied to {output_dir}")
    print(f"   ({total_copied // 2} pairs: {total_copied // 4} control + {total_copied // 4} hallucination per suite)")


def main():
    parser = argparse.ArgumentParser(
        description="SAS Multimetric Tribunal — Dataset Sampler",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input-dir", required=True, help="Path to full benchmark corpus")
    parser.add_argument("--output-dir", required=True, help="Path to output sampled dataset")
    parser.add_argument("--pairs-per-suite", type=int, default=100, help="Number of pairs per suite (default: 100)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()
    
    print("=" * 60)
    print("SAS Multimetric Tribunal — Dataset Sampler")
    print("=" * 60)
    print(f"\nInput:  {args.input_dir}")
    print(f"Output: {args.output_dir}")
    print(f"Pairs per suite: {args.pairs_per_suite}")
    print(f"Seed:   {args.seed}")
    
    sample_pairs(args.input_dir, args.output_dir, args.pairs_per_suite, args.seed)


if __name__ == "__main__":
    main()
