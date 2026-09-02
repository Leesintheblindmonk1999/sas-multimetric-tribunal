# CHANGELOG — SAS Multimetric Tribunal

Registry: TAD EX-2026-18792778
Author: Gonzalo Emir Durante — Project Manifold 0.56
License: Durante Invariance License v1.0

This changelog documents the diagnosis and correction cycle of the
per-module validation pilot (R5) for the Multimetric Tribunal, from the
initial finding to final verification. Each entry states who/what found
it, what was changed (or explicitly not changed), and how it was
verified.

κD = 0.56 and κR remained fixed throughout this cycle — no finding in
this changelog modified either threshold.

---

## [R5-v1] — 2026-08-27 — Controlled pilot Subset A (70 items)

First per-module validation pilot: 5 domains × 7 modules × 2 variants,
single-sentence perturbations designed to activate exactly one module
per item.

**Cross-audit** (internal + Kimi) of the 4 pilot scripts
(`01_generate_controlled.py` through `04_check_module_precision.py`)
before the first real run:
- `coherence_structural` ground truth inverted for `arithmetic_penalty`.
- `arithmetic_penalty` perturbations introduced new numbers not anchored
  in the source (cross-contamination with `source_target_guard`).
- Exact duplicates between the 2 variants per module/domain.
- The metric labeled "precision" in `04` actually measured recall.
- No purity metric (hits with zero extra firings) was computed.

All corrected before the first run against the real core.

**Result of the first real run** (`precision_report.txt`, 2026-08-28):
global recall 21.4% (15/70). Four modules at exactly 0.000: `cre_isi`,
`flow_penalty`, `arithmetic_penalty`, `reference_penalty`.

---

## [R5-diag] — 2026-08-29/30 — Root-cause diagnosis by direct execution

Instead of inferring the cause from reading the code, the 6 submodules
(`core/*.py`) were imported and executed directly against the pilot
corpus. Findings below, each confirmed by execution, not by inspection:

| Module | Confirmed root cause |
|---|---|
| `arithmetic_penalty` | Detection regex is 100% English (`plus`, `twice`, `% of`...). Zero Spanish coverage. |
| `reference_penalty` | v1.1 only penalizes citations that MODIFY a citation already present in A. Citations added only in B (no counterpart in A) are excluded by design. |
| `cre_isi` | Explicit guard `if n < 2 (sentences in B): return classification="INSUFFICIENT_DATA"`. Confirmed by execution: `n_nodes=1` in 100% of pilot items. |
| `flow_penalty` | Engine A (entropy) requires ≥15 content tokens per segment; Engine B (causal adjacency) requires ≥2 sentences — with 1 sentence, the adjacency matrix is zero by construction. |
| `negation_penalty` (recall 40%) | A closed whitelist of ~25 "affirmative" verbs (`indica`, `aumentó`, `fue/fueron`...) decides whether the source sentence counts as affirmative. Verbs like `revisó`, `autorizó`, `consumió` are not on the list → there is never a polarity to invert. |
| `lexical_baseline_score` (recall 10%) | Not a bug: the module fires on LOW Jaccard overlap; a faithful paraphrase naturally keeps Jaccard high. We were measuring the opposite of what the module measures. |

---

## [R5-matrix] — 2026-08-31 — Module × domain firing matrix (1,600 pairs)

Sample of 200 pairs per suite (seed=42) across 8 suites of the
`benchmark_corpus/` (596k pairs total), with length metadata (sentence
count, content-token count, apparent language) per item.

**Length hypothesis — confirmed, with an important nuance:**
- `cre_isi`: 0.0% firing rate in absolutely every "1 sentence" row,
  across the 5 suites that had them. Fully consistent with the `n<2`
  guard.
- `flow_penalty`: the simple hypothesis "needs 2+ sentences" was
  **incomplete** — `halueval_general` (61.9%) and
  `halueval_summarization` (91.7%) fire with a single sentence. A finer
  cut against content-token count (`flow_penalty_vs_tokens.csv`)
  confirmed a near-binary step at tokens=15, matching exactly the
  Engine A `MIN_SEGMENT_WORDS` threshold — firing depends on token
  density, not sentence count.
- `arithmetic_penalty`: the 596k corpus is already 92-99.5% English
  (`pct_texto_ingles`), and recall still sits at 0-7%. The cause is not
  (only) language — the detector only recognizes explicit arithmetic
  ("A plus B is C"), and real numeric hallucinations rarely take that
  syntactic form.

**Operational conclusion:** `cre_isi` and `flow_penalty` are not
broken — they are calibrated for multi-sentence documents. The pending
action is corpus design, not code.

---

## [v1.0.1] — 2026-09-02 — `tribunal_multimetrico.py`: anachronistic firing-decision fix

**Found by:** controlled `reference_penalty` corpus (65 pairs: 20
`same_author_diff_year`, 20 `same_year_diff_author`, 20 control, 5
anachronistic).

**Problem:** `_calcular_reference_penalty()` only fired on
`result.fabricated_count > 0`, ignoring `result.anachronistic_count`.
A pure anachronism (year < 1800 or > 2030, without being a modification
of an existing citation) never activated the module at the tribunal
level, even though `reference_check.py` detected it correctly.

**Change:**
```diff
- if result.fabricated_count > 0:
+ if result.fabricated_count > 0 or result.anachronistic_count > 0:
```

**Verification (using before/after snapshot files, not just the diff):**
- 5 anachronistic pairs: 3 pure ones flipped from `fired=False` to
  `fired=True`.
- 60 non-anachronistic pairs: 0 differences.
- 1,600 pairs from the matrix: 0 differences in `fired`/`isi_final` for
  the other 6 modules.

**Limitation found during that same verification** (see next entry):
the `isi_final` of the 3 pure pairs did NOT change even though `fired`
flipped to `True` — a signal that the fix was necessary but not
sufficient.

---

## [v1.2] — 2026-09-02 — `reference_check.py`: anachronistic severity fix

**Found by:** cross-audit of the v1.0.1 fix — `isi_final` of the 3 pure
anachronistic pairs was recomputed before/after the decision fix, and
came out identical (`0.500000 → 0.500000`, `0.642857 → 0.642857`,
`0.538462 → 0.538462`). Root cause: `penalty` in
`detect_fabrications()` was computed solely from `n_fab`
(fabricated_count); a pure anachronism (`n_fab=0`) always returned
`penalty=1.0` regardless of `anachronistic_count`. The v1.0.1 fix
corrected the firing decision but not the penalty magnitude.

**Change:**
```diff
- n_fab = len(fabricated)
- if n_fab == 0:
+ n_total = len(fabricated) + len(anachronistic)
+ if n_total == 0:
      penalty = 1.0
  else:
-     raw_penalty = REFERENCE_PENALTY_BASE ** min(n_fab, 4)
+     raw_penalty = REFERENCE_PENALTY_BASE ** min(n_total, 4)
      penalty = max(MAX_PENALTY_FLOOR, raw_penalty)
```

`fabricated_count` and `anachronistic_count` are still reported
separately in `ReferenceResult` (for evidence/XAI purposes); only what
feeds into `penalty` changes.

**Verification — independently recomputed, not just taken from the
run report** (`isi_final = isi_hard × penalty`, recomputed item by item
from the raw JSON files):

| Pair | isi_hard | penalty before → after | isi_final before → after |
|---|---|---|---|
| pure_00 | 0.500000 | 1.00 → 0.75 | 0.500000 → 0.375000 |
| pure_01 | 0.642857 | 1.00 → 0.75 | 0.642857 → 0.482143 |
| pure_02 | 0.538462 | 1.00 → 0.75 | 0.538462 → 0.403846 |
| mixed_03 | 0.777778 | 0.75 → 0.5625 | 0.583333 → 0.437500 |
| mixed_04 | 0.461538 | 0.75 → 0.5625 | 0.346154 → 0.259615 |

All 5 post-fix `isi_final` values match `isi_hard × penalty` recomputed
independently (not merely compared against the delivered table).

- 60 non-anachronistic pairs: 0 differences (`n_total == n_fab` when
  there are no anachronisms).
- 1,600 pairs from the matrix: 0 differences (independent diff; the
  empty comparison file delivered was not taken on faith).
- Core unit tests: 11/11 PASS.

**Status:** `reference_penalty` now has correct firing and severity
mechanisms in both layers. Pending: calibration against a real citation
corpus (not just the synthetic 65-pair corpus used for diagnosis).

---

## Consolidated module status at the close of this cycle

| Module | Status | Pending action |
|---|---|---|
| `lexical_baseline_score` | Works as designed | None — the low recall in R5-v1 was a corpus-design artifact, not a defect |
| `source_target_guard` | Works | None |
| `cre_isi` | Works, requires ≥2 sentences | Corpus design (not code) |
| `flow_penalty` | Works, requires ≥15 content tokens | Corpus design (not code) |
| `negation_penalty` | Works partially (recall ~40%) | Expand affirmative-verb whitelist |
| `arithmetic_penalty` | Not working in practice | Low priority — the underlying problem (implicit arithmetic) is not solved by translating the regex alone |
| `reference_penalty` | Fixed in two layers (v1.0.1 + v1.2) | Calibrate against a real citation corpus |

---

## Integrity verification of this document

SHA-256 of this file (computed at publication time, excluding this
section): see `CHANGELOG.md.sha256` in the same directory.
