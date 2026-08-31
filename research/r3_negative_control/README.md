# R3 — Negative Control: A→C Paraphrase Pilot

**Status:** ⚠️ Pilot complete — **high false-positive rate detected** (open issue)

## Purpose

This study responds to **Reviewer #1 (Prateek Srivastava)**:

> *"Without evaluation on correct but non-identical responses, including paraphrases, summaries, and semantically equivalent reformulations, this conclusion remains premature."*

The tribunal was validated on pairs where the response is **identical** to the source (A→A). This pilot evaluates the **A→C** case: responses that are **semantically equivalent but not identical** (paraphrases). If the tribunal flags correct paraphrases as hallucinations, it has a false-positive problem.

## Design (conservative, n=100)

1. Take pairs `(source, clean_response)` where `source != response`
2. Generate paraphrases of the clean response using lightweight methods:
   - **a)** Back-translation (EN → ES → EN) via `deep_translator`
   - **b)** Synonym replacement via NLTK WordNet
3. Evaluate `(source, paraphrase)` with the tribunal
4. Report zone distribution and false positives

## Results (from `outputs/results_ac_pilot.jsonl`)

| Method | n evaluated | False positives | FP rate | Zone A | Zone B | Zone F-S | Mean ISI |
|--------|-------------|-----------------|---------|--------|--------|----------|----------|
| **synonym** | 100 | 100 | **1.000** | 0 | 15 | 85 | 0.0554 |
| **backtranslation** | 27 | 26 | **0.963** | 1 | 10 | 16 | 0.1725 |

## Interpretation

- **The tribunal currently flags ~96–100% of correct paraphrases as structural collapse (F-S).**
- This is the **expected behavior of the lexical baseline** (Jaccard overlap): paraphrases share few surface tokens, so lexical ISI collapses even though semantics are preserved.
- **This is the single most important open limitation** of the current architecture. It does not invalidate the hallucination-detection results (F1=99.16% on A→B), but it **blocks deployment** in any setting where the response is not expected to be verbatim.

## Next Steps

- [ ] **R3.1**: Add a semantic-equivalence guard (embedding-based) before applying lexical penalties
- [ ] **R3.2**: Re-run pilot with the guard; target FP rate < 5%
- [ ] **R3.3**: Extend to summaries (A→S) and reformulations (A→R)

## Files

```
r3_negative_control/
├── README.md
├── scripts/
│   ├── pilot_ac.py          # Paraphrase generation + tribunal evaluation
│   └── prepare_data.py      # Builds pares_clean.json from benchmark_corpus
└── outputs/
    ├── results_ac_pilot.jsonl   # Full per-pair results
    └── pilot_ac_report.md       # This report
```

## Run

```bash
pip install deep-translator nltk
python scripts/prepare_data.py --output-dir ./prepared
python scripts/pilot_ac.py --input prepared/pares_clean.json --output outputs/results_ac_pilot.jsonl --n 100 --methods synonym backtranslation
```

---
*SAS Multimetric Tribunal — Research Series. Registry: TAD EX-2026-18792778*