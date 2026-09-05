#!/usr/bin/env python3
"""scripts/64_integracion_tribunal.py — Test de integración: tribunal con reference_check v1.3"""
import importlib.util
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
TRIBUNAL = BASE / "SAS" / "SAS" / "core" / "tribunal_multimetrico.py"

# El paquete "core" está en SAS/SAS/ — ese directorio padre debe estar en sys.path
sys.path.insert(0, str(TRIBUNAL.parent.parent))
spec = importlib.util.spec_from_file_location("tribunal_multimetrico", TRIBUNAL)
m = importlib.util.module_from_spec(spec)
sys.modules["tribunal_multimetrico"] = m
spec.loader.exec_module(m)
t = m.TribunalMultimetrico()

# ADV_CITA_03: cita correcta, no debe disparar reference_penalty
v = t.evaluar(
    'Como señala el autor: "Los resultados son concluyentes" (Chen, 2021).',
    "Chen (2021) demostró que los resultados son concluyentes en su estudio original.",
)
print("ADV_CITA_03 (correcto): fired =", [x.nombre for x in v.modulos_disparados], "| isi_final =", v.isi_final)

# Cita mutada: García et al. (2019) → García (2020) — debe disparar reference_penalty
v2 = t.evaluar(
    "García et al. (2019) establecieron el marco teórico.",
    "Según García (2020), el marco teórico se aplica también a sistemas sociales.",
)
print("Cita mutada (debe disparar): fired =", [x.nombre for x in v2.modulos_disparados], "| isi_final =", v2.isi_final)

# Cita mutada same_year_diff_author: Thompson (2020) → Martínez (2020)
v3 = t.evaluar(
    "El equipo liderado por Thompson (2020) reportó una correlación significativa.",
    "El abogado defensor citó a Martínez (2020) como precedente en su alegato.",
)
print("Cita mutada autor (debe disparar): fired =", [x.nombre for x in v3.modulos_disparados], "| isi_final =", v3.isi_final)