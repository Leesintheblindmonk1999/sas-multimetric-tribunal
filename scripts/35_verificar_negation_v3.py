#!/usr/bin/env python3
"""scripts/35_verificar_negation_v3.py — Protocolo completo v1.3"""
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
PILOT = BASE / "research" / "r5_module_pilot" / "outputs" / "corpus_pilot_A_raw.jsonl"
CORPUS_1600 = BASE / "reports" / "regresion_1600_despues_negation.json"
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"
TRIBUNAL = BASE / "SAS" / "SAS" / "core" / "tribunal_multimetrico.py"
BENCH_DIR = BASE / "benchmark_corpus"

def cargar_negation():
    spec = importlib.util.spec_from_file_location("core.negation_probe", NEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["core.negation_probe"] = mod
    spec.loader.exec_module(mod)
    return mod

def cargar_tribunal():
    spec_n = importlib.util.spec_from_file_location("core.negation_probe", NEG_PATH)
    mod_n = importlib.util.module_from_spec(spec_n)
    sys.modules["core.negation_probe"] = mod_n
    spec_n.loader.exec_module(mod_n)
    core_dir = TRIBUNAL.parent
    sys.path.insert(0, str(core_dir.parent))
    spec = importlib.util.spec_from_file_location("tribunal_multimetrico", TRIBUNAL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.TribunalMultimetrico()

# ── Cargar datos ───────────────────────────────────────────────
pilot = [json.loads(l) for l in PILOT.read_text("utf-8").splitlines() if l.strip()]
mapa_pilot = {p["id"]: p for p in pilot}
neg_pilot = [p for p in pilot if "negation_penalty" in p["id"]]
otros_pilot = [p for p in pilot if "negation_penalty" not in p["id"]]

fp_ids = ["SAS_PILOT_A_biomed_cre_isi_00","SAS_PILOT_A_biomed_cre_isi_01",
          "SAS_PILOT_A_biomed_lexical_baseline_score_00","SAS_PILOT_A_biomed_lexical_baseline_score_01",
          "SAS_PILOT_A_legal_lexical_baseline_score_00","SAS_PILOT_A_narrative_lexical_baseline_score_00"]

# ── 3a: Recall en 10 pares piloto ──────────────────────────────
print("="*70)
print("PASO 3a — Recall en 10 pares del piloto")
print("="*70)
np_mod = cargar_negation()
for p in neg_pilot:
    r = np_mod.detect_inversions(p["source"], p["response"])
    print(f"  {p['id'][:58]:<60} inv={r.inversion_count} penalty={r.penalty}")

recall = sum(1 for p in neg_pilot if
             np_mod.detect_inversions(p["source"], p["response"]).inversion_count > 0)
print(f"\n  Recall: {recall}/{len(neg_pilot)} = {100*recall/len(neg_pilot):.0f}%")

# ── 3b: Los 6 FP históricos ────────────────────────────────────
print(f"\n{'='*70}")
print("PASO 3b — 6 FP históricos (impacto_fp_negation.json)")
print("="*70)
fp_fired = []
for pid in fp_ids:
    p = mapa_pilot[pid]
    r = np_mod.detect_inversions(p["source"], p["response"])
    fired = r.inversion_count > 0
    print(f"  {pid:<58} {'🔴 DISPARA (FP)' if fired else '✅ OK'}")
    if fired:
        fp_fired.append(pid)

if fp_fired:
    print(f"\n  ⚠️  {len(fp_fired)} FP aún disparan — DETENIDO")
    sys.exit(1)
else:
    print(f"\n  ✅ 0/6 FP disparan")

# ── 3c: 1,600 pares matriz (con cambios de magnitud) ───────────
print(f"\n{'='*70}")
print("PASO 3c — 1,600 pares matriz (cambios completos)")
print("="*70)

# Helper inline para cargar pares (misma lógica que 06_matriz_disparo.py)
import random as _rnd
def _cargar_pares(suite, max_pairs=200, seed=42):
    sd = BENCH_DIR / suite
    if not sd.exists(): return []
    cand = []
    for cf in sd.glob("*_A_clean.txt"):
        hf = cf.with_name(cf.name.replace("_A_clean.txt", "_B_hallucination.txt"))
        if not hf.exists(): continue
        try:
            sz = cf.stat().st_size + hf.stat().st_size
        except: continue
        if sz > 25000: continue
        cand.append((cf, hf))
    if not cand: return []
    nm = min(max_pairs, len(cand))
    rng = _rnd.Random(seed)
    m = rng.sample(cand, nm)
    res = []
    for cf, hf in m:
        base = cf.name.replace("_A_clean.txt", "")
        try:
            src = cf.read_text("utf-8", errors="replace").strip()
            rsp = hf.read_text("utf-8", errors="replace").strip()
        except: continue
        if not src or not rsp: continue
        res.append((src, rsp, f"{suite}/{base}"))
    return res

tribunal = cargar_tribunal()
SUITES = ["codehalu","halubench","halueval_dialogue","halueval_general",
          "halueval_qa","halueval_summarization","legal_hallucinations","truthfulqa"]
items = []
for suite in SUITES:
    pares = _cargar_pares(suite, 200, 42)
    for src, rsp, pid in pares:
        v = tribunal.evaluar(src, rsp)
        fired = sorted(m.nombre for m in v.modulos_disparados)
        items.append({"pid": pid, "suite": suite, "fired": fired,
                       "isi": round(v.isi_final, 6), "zona": v.codigo_zona})
    print(f"  {suite}: {len(pares)}")

# Guardar
with open(BASE / "reports" / "regresion_1600_negation_v3.json", "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=1)
print("  [OK] guardado")

# Comparar contra el estado pre-fix (antes del intento v1.2 que se revirtió)
# El estado base es regresion_1600_despues_v2.json (reference fix applied, negation v1.1)
ANTES = BASE / "reports" / "regresion_1600_despues_v2.json"
if ANTES.exists():
    antes = json.loads(ANTES.read_text("utf-8"))
    mapa_antes = {a["pid"]: a for a in antes}
    cambios = []
    for d in items:
        a = mapa_antes.get(d["pid"])
        if not a: continue
        fa = set(a["fired"])
        fd = set(d["fired"])
        if fa != fd:
            cambios.append({
                "pid": d["pid"], "suite": d["suite"],
                "antes_fired": sorted(fa), "despues_fired": sorted(fd),
                "antes_isi": a["isi_final"], "despues_isi": d["isi"],
            })
    print(f"\n  Cambios en fired: {len(cambios)}")
    for c in cambios:
        print(f"    {c['suite']}/{c['pid']:<30} {c['antes_fired']} → {c['despues_fired']}  ISI: {c['antes_isi']} → {c['despues_isi']}")

# ── 4: Benchmark corpus negation pairs ─────────────────────────
print(f"\n{'='*70}")
print("PASO 4 — Pares de negación real del benchmark_corpus")
print("="*70)
# Buscar pares que contengan negación en B pero no en A
NEGACION = re.compile(
    r"\b(shall not|will not|must not|cannot|is not|are not|was not|were not"
    r"|has not|have not|had not|does not|do not|did not"
    r"|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|declines|refuses|rejects|denies|disputes"
    r"|never|none|neither|nor"
    r"|no|nunca|jamás|ningún|ninguna|tampoco|ni)\b",
    re.IGNORECASE,
)
encontrados = 0
detectados = 0
for suite_dir in sorted(BENCH_DIR.iterdir()):
    if not suite_dir.is_dir(): continue
    clean = sorted(suite_dir.glob("*_A_clean.txt"))
    import random
    rng = random.Random(42)
    muestra = rng.sample(clean, min(100, len(clean)))
    for cf in muestra:
        base = cf.name.replace("_A_clean.txt", "")
        hf = cf.with_name(f"{base}_B_hallucination.txt")
        if not hf.exists(): continue
        try:
            A = cf.read_text("utf-8", errors="replace").strip()
            B = hf.read_text("utf-8", errors="replace").strip()
        except: continue
        neg_a = bool(NEGACION.search(A.lower()))
        neg_b = bool(NEGACION.search(B.lower()))
        if not neg_a and neg_b:
            encontrados += 1
            r = np_mod.detect_inversions(A, B)
            if r.inversion_count > 0:
                detectados += 1
    if encontrados > 0:
        print(f"  {suite_dir.name}: {encontrados} con ¬A∧B, {detectados} detectados")
print(f"\n  Total benchmark: {encontrados} pares con negación real, {detectados} detectados ({100*detectados/encontrados:.0f}% de los muestreados)")
