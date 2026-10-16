#!/usr/bin/env python3
"""build_v6_papers.py — Copia archivos clave a papers/v6/ con SHA-256 manifest."""

import hashlib, os, shutil, json
from datetime import datetime

v6_dir = "papers/v6"
os.makedirs(v6_dir, exist_ok=True)

files = [
    ("scripts/r3_1_differential.py", "r3_1_differential.py"),
    ("scripts/audit_n1_corpus.py", "audit_n1_corpus.py"),
    ("SAS/SAS/core/tribunal_multimetrico.py", "tribunal_multimetrico.py"),
    ("reports/audit_n1_guard_v3_20261012_222645.json", "audit_n1_guard_v3.json"),
    ("CHANGELOG.md", "CHANGELOG.md"),
    ("scripts/n1_control.py", "n1_control.py"),
    ("scripts/convert_medhallu.py", "convert_medhallu.py"),
    ("reports/pairs_conditions_1800_seed42.json", "pairs_conditions_1800_seed42.json"),
    ("scripts/r3_1_signals.py", "r3_1_signals.py"),
    ("scripts/recalibrar_umbral.py", "recalibrar_umbral.py"),
    ("reports/recalibracion_v6.json", "recalibracion_v6.json"),
    ("scripts/recalibrar_umbral_v6.py", "recalibrar_umbral_v6.py"),
    ("reports/audit_n1_guard_v3_20261013_123506.json", "audit_n1_guard_v4.json"),
    ("scripts/sweep_threshold_guard.py", "sweep_threshold_guard.py"),
    ("scripts/convert_finqa.py", "convert_finqa.py"),
    ("scripts/evaluar_finqa_guard.py", "evaluar_finqa_guard.py"),
    ("reports/pairs_finqa.jsonl", "pairs_finqa.jsonl"),
    ("reports/evaluacion_finqa_guard.json", "evaluacion_finqa_guard.json"),
    ("papers/SAS_v6_Supplements.zip", "SAS_v6_Supplements.zip"),
]

manifest = {
    "titulo": "SAS Multimetric Tribunal — v6 Supplementary Materials",
    "fecha": "2026-10-12",
    "autor": "Gonzalo Emir Durante — Project Manifold 0.56",
    "registry": "TAD EX-2026-18792778",
    "archivos": {},
    "notas": "Copia de seguridad para Qeios v6. Los hashes permiten verificar integridad.",
}

for src, dst in files:
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(v6_dir, dst))
        with open(src, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        manifest["archivos"][dst] = {
            "origen": src,
            "sha256": h,
            "tamano_bytes": os.path.getsize(src),
        }
        print(f"  OK  {src} -> {dst}  [{h[:16]}...]")
    else:
        print(f"  MISSING  {src}")

# Write TXT manifest
manifest_path = os.path.join(v6_dir, "Manifest_hashes.txt")
with open(manifest_path, "w", encoding="utf-8") as f:
    f.write("=" * 72 + "\n")
    f.write("  MANIFEST — SAS v6 Supplementary Materials\n")
    f.write(f"  Fecha: {manifest['fecha']}\n")
    f.write(f"  Autor: {manifest['autor']}\n")
    f.write(f"  Registry: {manifest['registry']}\n")
    f.write("=" * 72 + "\n\n")
    for dst, info in manifest["archivos"].items():
        f.write(f"{info['sha256']}  {dst}  ({info['origen']})\n")
    f.write("\n")
    f.write(f"Generado: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
    f.write("=" * 72 + "\n")

# Write JSON manifest
with open(os.path.join(v6_dir, "Manifest_hashes.json"), "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"\nManifest escrito: {manifest_path}")
print(f"Total archivos: {len(manifest['archivos'])}")