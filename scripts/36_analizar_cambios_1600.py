#!/usr/bin/env python3
"""scripts/36_analizar_cambios_1600.py — Cuantifica y explica los cambios de negation v1.3 en 1,600 pares"""
import json
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
ANTES = BASE / "reports" / "regresion_1600_despues_v2.json"      # negation v1.1 (whitelist original)
DESPUES = BASE / "reports" / "regresion_1600_negation_v3.json"   # negation v1.3 (_tiene_negacion)

antes = json.loads(ANTES.read_text("utf-8"))
despues = json.loads(DESPUES.read_text("utf-8"))

mapa_antes = {a["pid"]: a for a in antes}
mapa_despues = {d["pid"]: d for d in despues}
pids = set(mapa_antes) & set(mapa_despues)
print(f"Antes: {len(antes)}, Después: {len(despues)}, PIDs común: {len(pids)}")

suben, bajan, isi_cambia = [], [], []
zona_flips = {"A→B": [], "A→F-S": [], "B→A": [], "F-S→A": [], "B→F-S": [], "F-S→B": [], "A→A": [], "B→B": [], "F-S→F-S": []}

for pid in sorted(pids):
    a, d = mapa_antes[pid], mapa_despues[pid]
    fa, fd = set(a["fired"]), set(d["fired"])
    neg_a, neg_d = "negation_penalty" in fa, "negation_penalty" in fd
    neg_cambio = neg_a != neg_d
    isi_a = a.get("isi_final", a.get("isi"))
    isi_d = d.get("isi_final", d.get("isi"))
    isi_cambio = abs(isi_a - isi_d) > 1e-6

    if neg_a and not neg_d:
        bajan.append(pid)
    elif not neg_a and neg_d:
        suben.append(pid)
    if isi_cambio:
        isi_cambia.append(pid)
    # Zona flips
    clave = f"{a['zona']}→{d['zona']}"
    if clave in zona_flips:
        zona_flips[clave].append(pid)

print(f"\n=== RESUMEN ===")
print(f"  negation True→False (deja de disparar): {len(bajan)}")
print(f"  negation False→True (nuevo disparo):    {len(suben)}")
print(f"  ISI cambió: {len(isi_cambia)}")
print(f"  Zona cambió: {sum(len(v) for k,v in zona_flips.items() if k not in ('A→A','B→B','F-S→F-S'))}")

print(f"\n=== ZONE FLIPS ===")
for k in ["A→B", "A→F-S", "B→A", "F-S→A", "B→F-S", "F-S→B"]:
    v = zona_flips[k]
    if v:
        print(f"  {k}: {len(v)}")
        for pid in v[:8]:
            print(f"      {pid}")

print(f"\n=== Por suite (True→False) ===")
cnt_bajan = Counter(pid.split("/")[0] for pid in bajan)
for s, n in cnt_bajan.most_common():
    print(f"  {s}: {n}")

print(f"\n=== Por suite (False→True) ===")
cnt_suben = Counter(pid.split("/")[0] for pid in suben)
for s, n in cnt_suben.most_common():
    print(f"  {s}: {n}")

# Guardar
with open(BASE / "reports" / "cambios_1600_negation_v3.json", "w", encoding="utf-8") as f:
    json.dump({
        "n_pares": len(pids),
        "negation_true_false": len(bajan),
        "negation_false_true": len(suben),
        "isi_cambio": len(isi_cambia),
        "bajan": bajan,
        "suben": suben,
        "zona_flips": {k: v for k, v in zona_flips.items()},
    }, f, ensure_ascii=False, indent=1)
print(f"\n[OK] Guardado en reports/cambios_1600_negation_v3.json")