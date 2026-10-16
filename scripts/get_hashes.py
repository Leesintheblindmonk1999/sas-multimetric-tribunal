#!/usr/bin/env python3
"""get_hashes.py — Print real hashes for paper manifest."""
import json
m = json.load(open("papers/v6/Manifest_hashes.json", encoding="utf-8"))
targets = ["convert_finqa.py", "evaluar_finqa_guard.py", "r3_1_differential.py", "audit_n1_guard_v4.json", "evaluacion_finqa_guard.json", "pairs_finqa.jsonl"]
for dst, info in m["archivos"].items():
    if dst in targets:
        print(f"{info['sha256']}  {dst}")