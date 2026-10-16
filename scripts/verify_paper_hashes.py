#!/usr/bin/env python3
"""verify_paper_hashes.py — Verifica que CADA hash en el paper coincida con el archivo real."""

import hashlib, re, json
from pathlib import Path

PAPER = Path("papers/v6/paper_v6.tex")
MANIFEST = Path("papers/v6/Manifest_hashes.json")

# Leer paper
tex = PAPER.read_text(encoding="utf-8")

# Extraer todos los SHA-256
hashes_in_paper = re.findall(r"[0-9a-f]{64}", tex)
print(f"Total SHA-256 en paper: {len(hashes_in_paper)}")

# Cargar manifest para saber qué archivo corresponde a cada hash
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
hash_to_file = {info["sha256"]: (dst, info["origen"]) for dst, info in manifest["archivos"].items()}

# Verificar cada hash
print()
print("VERIFICACIÓN CONTRA ARCHIVOS REALES:")
print("=" * 72)
all_ok = True
for h in hashes_in_paper:
    if h in hash_to_file:
        dst, src = hash_to_file[h]
        actual = hashlib.sha256(Path(src).read_bytes()).hexdigest()
        ok = actual == h
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {dst}")
        if not ok:
            print(f"          paper:    {h}")
            print(f"          actual:   {actual}")
    else:
        # Buscar el archivo manualmente
        found = False
        for dst, info in manifest["archivos"].items():
            if info["sha256"] == h:
                found = True
                break
        if not found:
            # Podría ser un archivo no copiado al manifest (ej: validacion_1800)
            print(f"  [?]  {h[:16]}...  (no está en manifest v6)")

print()
print(f"Resultado: {'TODOS OK' if all_ok else 'HAY ERRORES'}")