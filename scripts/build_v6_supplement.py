#!/usr/bin/env python3
"""build_v6_supplement.py — Construye SAS_v6_Supplements.zip con todo.

Incluye:
  - Paper (paper_v6.tex)
  - R3.1 Differential Guard (r3_1_differential.py, sweep_threshold_guard.py)
  - N1 audit (audit_n1_guard_v4.json, audit_n1_corpus.py)
  - N1 control (n1_control.py, pairs_conditions_1800_seed42.json)
  - Recalibración v6 (recalibracion_v6.json, recalibrar_umbral_v6.py)
  - FinQA (convert_finqa.py, evaluar_finqa_guard.py, pairs_finqa.jsonl, evaluacion_finqa_guard.json)
  - MedHallu (convert_medhallu.py)
  - Tribunal (tribunal_multimetrico.py)
  - Validación (validacion_1800_stratified_v3.py)
  - Ablaciones v5 (ablation_averaging_vs_multiplicative.json, ablation_stg_disabled.json)
  - Baselines (baselines_triviales.json, guard_jaccard.py)
  - κR sweep (sweep_kr_extendido_1800.json)
  - ISI per-pair (isi_por_par_1800_seed42.json)
  - verificar_cre.py
  - CHANGELOG.md
  - Manifest_hashes.txt + Manifest_hashes.json
"""

import hashlib, json, os, shutil, zipfile
from pathlib import Path
from datetime import datetime

BASE = Path(r"C:\Users\conno\Downloads\SAS-Semántico")
V6 = BASE / "papers" / "v6"
V5_SUPP = BASE / "papers" / "SAS_v5_Supplements"
OUTPUT_ZIP = BASE / "papers" / "SAS_v6_Supplements.zip"
TEMP = V6 / "_temp_supplement"

# ── Archivos a incluir (origen -> nombre en zip) ─────────────────────
FILES = [
    # Paper
    (V6 / "paper_v6.tex", "paper_v6.tex"),
    # R3.1 Guard
    (BASE / "scripts" / "r3_1_differential.py", "r3_1_differential.py"),
    (BASE / "scripts" / "sweep_threshold_guard.py", "sweep_threshold_guard.py"),
    # N1 audit
    (BASE / "reports" / "audit_n1_guard_v3_20261013_123506.json", "audit_n1_guard_v4.json"),
    (BASE / "scripts" / "audit_n1_corpus.py", "audit_n1_corpus.py"),
    # N1 control
    (BASE / "scripts" / "n1_control.py", "n1_control.py"),
    (BASE / "reports" / "pairs_conditions_1800_seed42.json", "pairs_conditions_1800_seed42.json"),
    # Recalibración v6
    (BASE / "reports" / "recalibracion_v6.json", "recalibracion_v6.json"),
    (BASE / "scripts" / "recalibrar_umbral_v6.py", "recalibrar_umbral_v6.py"),
    # FinQA
    (BASE / "scripts" / "convert_finqa.py", "convert_finqa.py"),
    (BASE / "scripts" / "evaluar_finqa_guard.py", "evaluar_finqa_guard.py"),
    (BASE / "reports" / "pairs_finqa.jsonl", "pairs_finqa.jsonl"),
    (BASE / "reports" / "evaluacion_finqa_guard.json", "evaluacion_finqa_guard.json"),
    # MedHallu
    (BASE / "scripts" / "convert_medhallu.py", "convert_medhallu.py"),
    # Tribunal
    (BASE / "SAS" / "SAS" / "core" / "tribunal_multimetrico.py", "tribunal_multimetrico.py"),
    # Validación v3
    (V5_SUPP / "validacion_1800_stratified_v3.py", "validacion_1800_stratified_v3.py"),
    # Ablaciones v5
    (V5_SUPP / "ablation_averaging_vs_multiplicative.json", "ablation_averaging_vs_multiplicative.json"),
    (V5_SUPP / "ablation_stg_disabled.json", "ablation_stg_disabled.json"),
    # Baselines
    (V5_SUPP / "baselines_triviales.json", "baselines_triviales.json"),
    (V5_SUPP / "guard_jaccard.py", "guard_jaccard.py"),
    # κR sweep
    (V5_SUPP / "sweep_kr_extendido_1800.json", "sweep_kr_extendido_1800.json"),
    # ISI per-pair
    (V5_SUPP / "isi_por_par_1800_seed42.json", "isi_por_par_1800_seed42.json"),
    # verificar_cre
    (V5_SUPP / "verificar_cre.py", "verificar_cre.py"),
    # Recalibrar umbral v5 (referencia)
    (V5_SUPP / "recalibrar_umbral.py", "recalibrar_umbral_v5.py"),
    # R3.1 signals (referencia)
    (BASE / "scripts" / "r3_1_signals.py", "r3_1_signals.py"),
    # CHANGELOG
    (BASE / "CHANGELOG.md", "CHANGELOG.md"),
]

print("=" * 72)
print("  CONSTRUCCIÓN — SAS_v6_Supplements.zip")
print("=" * 72)

# ── 1. Verificar que todos los archivos existen ──────────────────────
print("\n[1/4] Verificando archivos fuente...")
missing = []
for src, dst in FILES:
    if not src.exists():
        missing.append(str(src))
        print(f"  [MISSING] {src}")
if missing:
    print(f"\n  ERROR: {len(missing)} archivo(s) faltante(s).")
    for m in missing:
        print(f"    {m}")
    exit(1)
print(f"  {len(FILES)} archivos encontrados.")

# ── 2. Calcular hashes ──────────────────────────────────────────────
print("\n[2/4] Calculando SHA-256...")
manifest = {
    "titulo": "SAS Multimetric Tribunal — v6 Supplementary Materials",
    "fecha": "2026-10-16",
    "autor": "Gonzalo Emir Durante — Project Manifold 0.56",
    "registry": "TAD EX-2026-18792778",
    "archivos": {},
}
for src, dst in FILES:
    data = src.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    manifest["archivos"][dst] = {
        "sha256": h,
        "tamano_bytes": len(data),
    }
    print(f"  {h[:16]}...  {dst}")

# ── 3. Crear zip ────────────────────────────────────────────────────
print("\n[3/4] Creando zip...")
with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for src, dst in FILES:
        zf.write(src, dst)
    # Agregar manifest como JSON
    zf.writestr("Manifest_hashes.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    # Agregar manifest como TXT
    txt_lines = [
        "=" * 72,
        "  MANIFEST — SAS v6 Supplementary Materials",
        f"  Fecha: {manifest['fecha']}",
        f"  Autor: {manifest['autor']}",
        f"  Registry: {manifest['registry']}",
        "=" * 72,
        "",
    ]
    for dst, info in manifest["archivos"].items():
        txt_lines.append(f"{info['sha256']}  {dst}")
    txt_lines.append("")
    txt_lines.append(f"Generado: {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    txt_lines.append("=" * 72)
    zf.writestr("Manifest_hashes.txt", "\n".join(txt_lines))

zip_size = OUTPUT_ZIP.stat().st_size
print(f"  ZIP creado: {OUTPUT_ZIP}")
print(f"  Tamaño: {zip_size:,} bytes ({zip_size/1024:.0f} KB)")

# ── 4. Verificar integridad del zip ──────────────────────────────────
print("\n[4/4] Verificando integridad...")
with zipfile.ZipFile(OUTPUT_ZIP, "r") as zf:
    names = zf.namelist()
    print(f"  Archivos en zip: {len(names)}")
    all_ok = True
    for name in names:
        data = zf.read(name)
        if name in manifest["archivos"]:
            expected = manifest["archivos"][name]["sha256"]
            actual = hashlib.sha256(data).hexdigest()
            ok = actual == expected
            status = "OK" if ok else "FAIL"
            if not ok:
                all_ok = False
            print(f"  [{status}] {name}")
        elif name.startswith("Manifest_"):
            print(f"  [META] {name}")
        else:
            print(f"  [?]   {name}")

print()
if all_ok:
    print("  ✅ ZIP VERIFICADO — TODOS LOS ARCHIVOS COINCIDEN CON SUS HASHES")
else:
    print("  ❌ ERROR: ALGUNOS ARCHIVOS NO COINCIDEN")
print("=" * 72)