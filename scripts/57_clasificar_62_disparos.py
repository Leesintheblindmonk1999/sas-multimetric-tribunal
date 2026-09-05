#!/usr/bin/env python3
"""scripts/57_clasificar_62_disparos.py — Clasifica los 62 pares que dispararon negation en rationalization_binary"""
import importlib.util
import json
import re
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
RATBIN = BASE / "benchmark_corpus" / "halogen" / "rationalization_binary"
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"
RESULT = BASE / "reports" / "t1_rationalization_binary.json"

NEGACION = re.compile(
    r"\b(shall not|will not|must not|cannot|is not|are not|was not|were not"
    r"|has not|have not|had not|does not|do not|did not"
    r"|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|declines|refuses|rejects|denies|disputes"
    r"|never|none|neither|nor"
    r"|no|nunca|jamás|ningún|ninguna|tampoco|ni)\b",
    re.IGNORECASE,
)

# Cargar el resultado con los 200 pares detallados
detalles = json.loads(RESULT.read_text("utf-8"))
print(f"Total pares en el archivo: {len(detalles)}")

# Los que dispararon (fired=true)
dispararon = [d for d in detalles if d["fired"]]
print(f"Dispararon: {len(dispararon)}")

# Confirmar cuántos tienen ¬A∧B real
asimetria = [d for d in dispararon if not d["negA"] and d["negB"]]
ambos_neg = [d for d in dispararon if d["negA"] and d["negB"]]
print(f"  De los que dispararon: ¬A∧B (asimetría): {len(asimetria)} | negA∧negB (ambos): {len(ambos_neg)}")
print(f"  negA={sum(1 for d in dispararon if d['negA'])} negB={sum(1 for d in dispararon if d['negB'])}")

# Tomar 10 al azar de los 62 (seed=42)
import random
rng = random.Random(42)
muestra = rng.sample(dispararon, 10)

print(f"\n{'='*80}")
print("10 PAres que dispararon (seed=42) — texto completo + tokens")
print(f"{'='*80}")

for d in muestra:
    A, B = d["A"], d["B"]
    neg_a_tokens = [m.group(0) for m in NEGACION.finditer(A.lower())]
    neg_b_tokens = [m.group(0) for m in NEGACION.finditer(B.lower())]
    print(f"\n{'─'*80}")
    print(f"BASE: {d['base']} | inv={d['inv']} | negA={d['negA']} negB={d['negB']}")
    print(f"  Tokens _NEGATION en A: {neg_a_tokens if neg_a_tokens else '(ninguno)'}")
    print(f"  Tokens _NEGATION en B: {neg_b_tokens if neg_b_tokens else '(ninguno)'}")
    print(f"  [A]: {A}")
    print(f"  [B]: {B}")