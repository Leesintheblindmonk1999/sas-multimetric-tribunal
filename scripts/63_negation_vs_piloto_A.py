#!/usr/bin/env python3
"""scripts/63_negation_vs_piloto_A.py — negation v1.3 contra los 10 pares ORIGINALES del piloto Subset A

Este es el chequeo que quedó pendiente: el recall del piloto (4/10 original,
10/10 con el intento v1.2 revertido) nunca se remidió con el rediseño v1.3
(_tiene_negacion) sobre los MISMO 10 pares. Aquí se mide ahora.
"""
import importlib.util
import json
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
PILOT = BASE / "research" / "r5_module_pilot" / "outputs" / "corpus_pilot_A_raw.jsonl"
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"


def cargar_negation():
    spec = importlib.util.spec_from_file_location("core.negation_probe", NEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["core.negation_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


pilot = [json.loads(l) for l in PILOT.read_text("utf-8").splitlines() if l.strip()]
neg_pilot = [p for p in pilot if "negation_penalty" in p["id"]]
print(f"Pares piloto totales: {len(pilot)} | Pares negation: {len(neg_pilot)}")

np_mod = cargar_negation()
detectados = 0
print(f"\n{'='*80}")
print("negation v1.3 — detect_inversions sobre los 10 pares ORIGINALES del piloto Subset A")
print(f"{'='*80}")
for p in neg_pilot:
    r = np_mod.detect_inversions(p["source"], p["response"])
    fired = r.inversion_count > 0
    if fired:
        detectados += 1
    print(f"  {p['id'][:60]:<62} inv={r.inversion_count} penalty={r.penalty} {'✅' if fired else '❌'}")

print(f"\n  Recall piloto v1.3: {detectados}/{len(neg_pilot)} = {100*detectados/len(neg_pilot):.0f}%")

out = {
    "version_negation": "v1.3",
    "n_pares": len(neg_pilot),
    "detectados": detectados,
    "recall": detectados / len(neg_pilot),
    "detalle": [
        {
            "id": p["id"],
            "source": p["source"],
            "response": p["response"],
            "inversion_count": np_mod.detect_inversions(p["source"], p["response"]).inversion_count,
            "penalty": np_mod.detect_inversions(p["source"], p["response"]).penalty,
        }
        for p in neg_pilot
    ],
}
out_path = BASE / "reports" / "t1_negation_vs_piloto_A.json"
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
print(f"\n[OK] Guardado en {out_path}")