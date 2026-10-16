#!/usr/bin/env python3
"""list_manifest.py — List all files in v6 manifest."""
import json
m = json.load(open("papers/v6/Manifest_hashes.json", encoding="utf-8"))
print("Archivos en manifest v6:")
for dst, info in m["archivos"].items():
    print(f"  {info['origen']}  ->  {dst}")