#!/usr/bin/env python3
"""verify_zip.py — Verify SAS_v6_Supplements.zip internal consistency."""
import zipfile, hashlib, json

with zipfile.ZipFile("papers/SAS_v6_Supplements.zip", "r") as zf:
    names = zf.namelist()
    print(f"Archivos en zip: {len(names)}")

    manifest = json.loads(zf.read("Manifest_hashes.json"))
    print(f"Manifest interno: {len(manifest['archivos'])} archivos")

    all_ok = True
    for name in names:
        if name.startswith("Manifest_"):
            continue
        data = zf.read(name)
        h = hashlib.sha256(data).hexdigest()
        expected = manifest["archivos"][name]["sha256"]
        ok = h == expected
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {name}")

    print()
    print(f"Verificación: {'TODOS OK' if all_ok else 'HAY ERRORES'}")
    print(f"Tamaño total: {sum(zf.getinfo(n).file_size for n in names) / 1024:.0f} KB (comprimido)")
    print(f"Tamaño zip:   {zf.getinfo(names[0]).file_size / 1024:.0f} KB (primer archivo)")