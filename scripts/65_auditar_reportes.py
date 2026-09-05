#!/usr/bin/env python3
"""Auditoría de cierre — verifica estructura y estado de los reportes del ciclo"""
import json
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")

checks = [
    "reports/impacto_fp_negation.json",
    "reports/negation_resultado_despues.json",
    "reports/t2_spotcheck_negation.json",
    "reports/cambios_1600_negation_v3.json",
    "reports/nuevos_disparos_negation_v3.json",
    "reports/analisis_decisivo_negation_v3.json",
    "reports/t1_sobrecaptura_citas.json",
    "reports/regresion_1600_despues_v2.json",
    "reports/regresion_1600_negation_v3.json",
    "reports/comparacion_1600_negation.json",
]

for rel in checks:
    f = BASE / rel
    if not f.exists():
        print(f"{rel}: NO EXISTE")
        continue
    try:
        d = json.loads(f.read_text("utf-8"))
    except Exception as e:
        print(f"{rel}: ERROR DE PARSEO {e}")
        continue
    if isinstance(d, dict):
        n = len(d)
        k = list(d.keys())[:6]
        print(f"{rel}: dict ({n} keys) {k}")
    elif isinstance(d, list):
        n = len(d)
        k = list(d[0].keys()) if d else []
        print(f"{rel}: lista de {n} items; keys = {k}")
    else:
        print(f"{rel}: tipo {type(d).__name__}")