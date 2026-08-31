"""
Compute per-module precision/recall/purity from results_pilot_A.jsonl.
Mirrors 04_check_module_precision.py logic and writes precision_report.txt.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "outputs" / "results_pilot_A.jsonl"
OUT = Path(__file__).resolve().parent.parent / "outputs" / "precision_report.txt"

MODULES = [
    "lexical_baseline_score",
    "source_target_guard",
    "cre_isi",
    "flow_penalty",
    "negation_penalty",
    "arithmetic_penalty",
    "reference_penalty",
]

items = []
with open(RESULTS, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))

# expected module per item (index of the 1 in expected_trigger)
expected_of = {}
for it in items:
    et = it.get("expected_trigger", [])
    idx = et.index(1) if 1 in et else -1
    expected_of[it["id"]] = MODULES[idx] if idx >= 0 else None

# per-module counts
tp = defaultdict(int)       # fired the expected module
expected_count = defaultdict(int)
fired_count = defaultdict(int)
pure = defaultdict(int)     # fired modules == {expected} exactly
purity_denom = 0
tot_expected = 0

for it in items:
    exp = expected_of[it["id"]]
    if exp is None:
        continue
    tot_expected += 1
    expected_count[exp] += 1
    fired = it.get("sas_result", {}).get("fired_modules", []) or []
    fired = [m for m in fired if m in MODULES]
    for m in fired:
        fired_count[m] += 1
    if exp in fired:
        tp[exp] += 1
    if set(fired) == {exp}:
        pure[exp] += 1
        purity_denom += 1

lines = []
lines.append("=" * 70)
lines.append("SAS MULTIMETRIC TRIBUNAL - R5 MODULE PRECISION REPORT")
lines.append("=" * 70)
lines.append(f"Items evaluated: {len(items)}")
lines.append(f"Items with expected trigger: {tot_expected}")
lines.append("")

lines.append(f"{'Module':<28}{'Exp':>5}{'TP':>5}{'Recall':>9}{'Fired':>7}{'Prec':>9}{'Pure':>6}{'Purity':>9}")
lines.append("-" * 70)
tot_tp, tot_fired, tot_exp = 0, 0, 0
for m in MODULES:
    e = expected_count[m]
    t = tp[m]
    f = fired_count[m]
    p = pure[m]
    recall = t / e if e else 0.0
    prec = t / f if f else 0.0
    pur = p / e if e else 0.0
    tot_tp += t; tot_fired += f; tot_exp += e
    lines.append(f"{m:<28}{e:>5}{t:>5}{recall:>9.3f}{f:>7}{prec:>9.3f}{p:>6}{pur:>9.3f}")
lines.append("-" * 70)
g_recall = tot_tp / tot_exp if tot_exp else 0.0
g_prec = tot_tp / tot_fired if tot_fired else 0.0
g_purity = purity_denom / tot_exp if tot_exp else 0.0
lines.append(f"{'TOTAL':<28}{tot_exp:>5}{tot_tp:>5}{g_recall:>9.3f}{tot_fired:>7}{g_prec:>9.3f}{purity_denom:>6}{g_purity:>9.3f}")
lines.append("")

# fires that were NOT expected (contamination)
lines.append("CONTAMINATION (fired without being expected)")
lines.append("-" * 70)
for m in MODULES:
    extra = fired_count[m] - tp[m]
    if extra > 0:
        lines.append(f"  {m}: fired extra {extra} times")
lines.append("")
lines.append("NOTE: source_target_guard fires on ANY loose-number change (its quantity-")
lines.append("mutation branch). arithmetic_penalty items change a number, so STG is an")
lines.append("expected 'extra' there - core behavior, not corpus contamination.")
lines.append("")
lines.append("STATUS: PILOT CLEAN" if tot_fired > 0 and tot_fired == tot_tp else "STATUS: PILOT IN REVIEW (extras detected)")

report = "\n".join(lines)
print(report)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(report + "\n")
print(f"\nWrote: {OUT}")