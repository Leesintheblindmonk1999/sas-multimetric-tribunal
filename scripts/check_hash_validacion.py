#!/usr/bin/env python3
"""check_hash_validacion.py — Verify validacion_1800_stratified_v3.py hash."""
import hashlib
f = "papers/SAS_v5_Supplements/validacion_1800_stratified_v3.py"
h = hashlib.sha256(open(f, "rb").read()).hexdigest()
expected = "65415c53c7032b529664a5a9c2cb51cb5cd9d5093b252d0c38eba884484ab939"
print(f"Hash real:     {h}")
print(f"Hash esperado: {expected}")
print(f"Coinciden: {h == expected}")