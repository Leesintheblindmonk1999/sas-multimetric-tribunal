#!/usr/bin/env python3
"""verify_manifest.py — Verifica integridad del manifest v6."""
import hashlib, json, sys

manifest = json.load(open("papers/v6/Manifest_hashes.json", encoding="utf-8"))
print("=" * 60)
print("  MANIFEST v6 — VERIFICACIÓN")
print("=" * 60)
all_ok = True
for dst, info in manifest["archivos"].items():
    src = info["origen"]
    with open(src, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    expected = info["sha256"]
    ok = actual == expected
    status = "OK" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(f"  [{status}] {dst}")
    if not ok:
        print(f"         esperado: {expected}")
        print(f"         actual:   {actual}")

print()
print(f"Total archivos: {len(manifest['archivos'])}")
print(f"Todo OK: {all_ok}")
sys.exit(0 if all_ok else 1)