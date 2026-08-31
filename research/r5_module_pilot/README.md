# R5 — Controlled Module Pilot (Subset A)

**Status:** ✅ Complete — precision/recall per module measured (see report)

## Purpose

Validate each of the 7 tribunal modules **in isolation** using a **controlled corpus** with known ground-truth triggers. Each item in the corpus perturbs exactly ONE module's failure mode while keeping the rest intact, so we can measure:

- **Recall per module** — does the module fire when it should?
- **Precision per module** — does the module fire WITHOUT firing others (purity)?
- **Noise** — which modules contaminate each other?

## Design

5 domains × 7 modules × 2 perturbations = **70 unique items** (plus raw corpus with more variants):

| Domain | Description |
|--------|-------------|
| `finance` | Financial report statements |
| `legal` | Legal case summaries |
| `biomed` | Biomedical claims |
| `general` | General knowledge |
| `narrative` | Narrative prose |

Each domain anchors its entities/quantities in the **source** text (credit to Kimi H2 audit: originally, perturbations introduced NEW quantities not present in source, contaminating other modules — now all anchors are source-derived).

Module perturbations tested:
1. `lexical_baseline_score` — synonym substitution (should NOT trigger others)
2. `source_target_guard` — location swap (Buenos Aires → Madrid/Washington; Argentina → China/India — only names the core regex actually recognizes)
3. `cre_isi` — partial negation of the quantity clause (was: full-polarity negation — contaminated cre_isi)
4. `flow_penalty` — clause reordering / flow rupture
5. `negation_penalty` — partial negation preserving the rest
6. `arithmetic_penalty` — result change, quantities anchored in source
7. `reference_penalty` — fabricated citation

## Key Results

| Metric | Value (from `04_check_module_precision.py`) |
|--------|------|
| Items evaluated | 70 (10 per module, 5 domains) |
| Overall module-precision | **0.2143** (15/70 exact module matches) |
| **0 false positives on controls** | ✅ (unrelated homogeneously never fires) |

> ⚠️ **Important caveat:** `source_target_guard` fires on ANY loose-number change in the text (its "quantity mutation" branch), so it appears as an "extra" fired module on nearly every `arithmetic_penalty` item. This is a **core behavior**, not corpus contamination — see `04_check_module_precision.py` changelog for the full audit trail.

## Files

```
r5_module_pilot/
├── README.md
├── scripts/
│   ├── 01_generate_controlled.py      # Builds the controlled corpus (5×7×2=70)
│   ├── 02_validate_pilot.py           # Sanity-checks ground truth internally
│   ├── 03_run_pilot_inference.py      # Runs tribunal on each item
│   └── 04_check_module_precision.py   # Computes recall/precision/purity per module
└── outputs/
    ├── corpus_pilot_A_raw.jsonl       # Raw controlled corpus
    ├── results_pilot_A.jsonl          # Tribunal verdict per item
    └── precision_report.txt           # Per-module metrics
```

## Run

```bash
python scripts/01_generate_controlled.py
python scripts/02_validate_pilot.py
python scripts/03_run_pilot_inference.py
python scripts/04_check_module_precision.py
```

---
*SAS Multimetric Tribunal — Research Series. Registry: TAD EX-2026-18792778*