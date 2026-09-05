#!/usr/bin/env python3
"""Verifica/regenera CHANGELOG.md.sha256 — hash del CHANGELOG excluyendo la sección de integridad"""
import hashlib
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
CHANGELOG = BASE / "CHANGELOG.md"
HASH_FILE = BASE / "CHANGELOG.md.sha256"

text = CHANGELOG.read_text("utf-8")

# La sección de integridad empieza en "## Integrity verification of this document"
# El hash se computa sobre el contenido ANTES de esa sección (excluyendo esta sección)
marker = "## Integrity verification of this document"
idx = text.find(marker)
if idx == -1:
    print("[ERROR] No se encontró la sección de integridad en CHANGELOG.md")
    raise SystemExit(1)

content = text[:idx].rstrip("\n") + "\n"
h = hashlib.sha256(content.encode("utf-8")).hexdigest()

print(f"Longitud total CHANGELOG: {len(text)} chars")
print(f"Contenido hasheado (antes de la sección de integridad): {len(content)} chars")
print(f"SHA-256 calculado: {h}")

# Comparar con el archivo existente
if HASH_FILE.exists():
    actual = HASH_FILE.read_text("utf-8").strip()
    print(f"SHA-256 en archivo:  {actual}")
    if actual == h:
        print("\n✅ COINCIDE — el archivo existente es válido para el CHANGELOG actual")
    else:
        print("\n⚠️ NO COINCIDE — el archivo está desactualizado (el CHANGELOG cambió)")
        print("   Regenerando...")
        HASH_FILE.write_text(h + "\n", "utf-8")
        print(f"   [OK] {HASH_FILE} actualizado a {h}")
else:
    print("\nEl archivo no existe — creándolo...")
    HASH_FILE.write_text(h + "\n", "utf-8")
    print(f"[OK] {HASH_FILE} creado con {h}")