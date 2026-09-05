#!/usr/bin/env python3
"""scripts/67_rederivar_desglose_subtipos.py — TAREA 2: re-derivación del desglose por subtipo

Re-cuenta n y precisión por subtipo (primalidad/vuelos/senador) DIRECTAMENTE
desde las 45 clasificaciones individuales (a=negación real / b=espurio),
sin usar ningún total pre-sumado.

Fuente de los registros individuales:
  - IDs por tanda: reports/t1_desglose_subtipos.json (script 60, derivado del
    muestreo seed=42 reproducible)
  - Clasificación a/b: registros manuales de texto (transcript + reportes),
    hardcodeados aquí por ID — NO se re-clasifica de cero.
"""
import json
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
DESGLOSE = BASE / "reports" / "t1_desglose_subtipos.json"

# ── Clasificaciones individuales (a=real, b=espurio) por ID ──
# Tanda 1 (10, seed=42) — del transcript (clasificación manual con texto a la vista)
CLASIF_T1 = {
    "16937": "a", "19785": "a", "0212": "b", "19904": "a", "19959": "a",
    "1587": "a", "14819": "a", "19337": "a", "10999": "a", "11972": "b",
}
# Tanda 2 (15 siguientes) — del transcript
CLASIF_T2 = {
    "5959": "b", "13959": "a", "20119": "b", "11468": "a", "13936": "a",
    "9267": "a", "19874": "a", "13644": "a", "0235": "b", "11206": "a",
    "15332": "b", "16970": "a", "10757": "a", "11642": "a", "13802": "a",
}
# Tanda 3 (20 adicionales) — de la clasificación en pantalla
CLASIF_T3 = {
    "20553": "a", "6378": "a", "13722": "a", "16918": "a", "16987": "a",
    "11854": "a", "15083": "a", "20367": "b", "15016": "a", "18751": "b",
    "12916": "b", "20989": "a", "15914": "a", "5559": "b", "0018": "b",
    "2145": "b", "15784": "a", "16981": "a", "5403": "b", "7585": "a",
}

# Verificar que no haya IDs duplicados entre tandas
todas = {**CLASIF_T1, **CLASIF_T2, **CLASIF_T3}
assert len(todas) == 45, f"Esperaba 45 IDs únicos, hay {len(todas)}"

# Cargar el desglose con subtipos (derivado del texto A)
desglose = json.loads(DESGLOSE.read_text("utf-8"))

# Construir mapa base → subtipo desde las 3 tandas del desglose
base_a_subtipo = {}
for tanda in ["tanda1", "tanda2", "tanda3"]:
    for item in desglose[tanda]:
        base_a_subtipo[item["base"]] = item["subtipo"]

# Verificar que todos los IDs clasificados tienen subtipo
faltantes = [b for b in todas if b not in base_a_subtipo]
assert not faltantes, f"IDs sin subtipo: {faltantes}"

# ── Recontar por subtipo ──
print("=" * 80)
print("RECUENTO INDIVIDUAL — 45 clasificaciones por subtipo")
print("=" * 80)

por_subtipo = {}
for base, clasif in sorted(todas.items()):
    subtipo = base_a_subtipo[base]
    por_subtipo.setdefault(subtipo, []).append((base, clasif))

total_a = 0
total_n = 0
for subtipo in ["primalidad", "vuelos", "senador"]:
    items = por_subtipo.get(subtipo, [])
    n = len(items)
    n_a = sum(1 for _, c in items if c == "a")
    n_b = sum(1 for _, c in items if c == "b")
    prec = n_a / n if n else 0
    total_a += n_a
    total_n += n
    print(f"\n{subtipo.upper()}: n={n} | (a) real={n_a} | (b) espurio={n_b} | precisión={100*prec:.1f}%")
    for base, c in items:
        print(f"    {base}: {c}")

print(f"\n{'='*80}")
print(f"TOTAL: n={total_n} | (a) real={total_a} | (b) espurio={total_n-total_a} | precisión={100*total_a/total_n:.1f}%")
print(f"{'='*80}")

# ── Verificación contra lo reportado ──
print("\nVERIFICACIÓN contra lo publicado en CHANGELOG:")
reportado = {
    "primalidad": (27, 85.2),
    "vuelos": (8, 62.5),
    "senador": (10, 40.0),
}
ok = True
for subtipo, (n_rep, prec_rep) in reportado.items():
    items = por_subtipo.get(subtipo, [])
    n = len(items)
    n_a = sum(1 for _, c in items if c == "a")
    prec = 100 * n_a / n if n else 0
    match = (n == n_rep) and (abs(prec - prec_rep) < 0.1)
    ok = ok and match
    print(f"  {subtipo}: n={n} (reportado {n_rep}) {'✅' if n == n_rep else '❌'} | "
          f"precisión={prec:.1f}% (reportado {prec_rep}%) {'✅' if abs(prec-prec_rep) < 0.1 else '❌'}")

total_rep = 30 / 45 * 100
match_total = (total_a == 30) and (total_n == 45) and (abs(100 * total_a / total_n - total_rep) < 0.1)
ok = ok and match_total
print(f"  TOTAL: {total_a}/{total_n} = {100*total_a/total_n:.1f}% (reportado 30/45 = 66.7%) {'✅' if match_total else '❌'}")

print(f"\n{'CONFIRMADO, SIN CAMBIOS' if ok else '⚠️ DISCREPANCIA — revisar'}")

# Guardar
out = {
    "n_total": total_n,
    "n_a": total_a,
    "n_b": total_n - total_a,
    "precision_total": round(total_a / total_n, 4),
    "por_subtipo": {
        s: {
            "n": len(por_subtipo.get(s, [])),
            "n_a": sum(1 for _, c in por_subtipo.get(s, []) if c == "a"),
            "n_b": sum(1 for _, c in por_subtipo.get(s, []) if c == "b"),
            "precision": round(sum(1 for _, c in por_subtipo.get(s, []) if c == "a") / len(por_subtipo.get(s, [])), 4) if por_subtipo.get(s) else 0,
            "items": [{"base": b, "clasif": c} for b, c in por_subtipo.get(s, [])],
        }
        for s in ["primalidad", "vuelos", "senador"]
    },
    "confirmado": ok,
}
out_path = BASE / "reports" / "t1_rederivacion_desglose_subtipos.json"
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
print(f"\n[OK] Guardado en {out_path}")