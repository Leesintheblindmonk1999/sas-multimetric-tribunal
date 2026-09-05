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

## [attempted, reverted] — 2026-09-02 — `negation_probe.py`: verb-whitelist expansion (v1.2-attempt)

**Attempted fix:** expand `_AFFIRM_STRONG` with ~60 additional
report/action verbs justified by real usage frequency in the pilot and
benchmark corpus (e.g. `produce`, `decide`, `consume`, `genera`),
explicitly excluding verbs with inherent negative charge (`rechazó`,
`negó`, `niega`, `prohibió`, `denegó`).

**Result, measured with full protocol:**
- Piloto recall: 4/10 → 10/10.
- 1,600-pair matrix: only 1 new firing, no mass contamination.
- **6 new false positives that flip the final tribunal zone** (A→B or
  B→F-S) on valid-paraphrase pairs (`truth_factual: true`) — e.g.
  `biomed_cre_isi_00`: source uses the newly-whitelisted `consumió`,
  response uses the still-excluded `rechazó`; both used to read as
  "not affirmative" (no mismatch, no false firing); after the
  expansion, the asymmetry between a listed and an unlisted verb
  produces a spurious polarity mismatch with no real negation present.

**Decision: REVERTED.** The whitelist was restored to its original
state (`revisó`/`autorizó`/`consumió` confirmed absent again). Gaining
recall at the cost of zone-changing false positives on valid content
violates the project's stated precedent (specificity over recall).

**Root-cause correction:** the failed attempt's own changelog entry
initially attributed the 6 FPs to sentence-alignment issues in
`detect_inversions()`. Cross-audit of the same 6 examples showed this
was incorrect — all 6 are single-sentence pairs with no alignment
ambiguity possible. The real mechanism: `_is_affirmative()` conflates
"is the verb in a closed list" with "is there negation" — any
asymmetry in verb-list coverage between the compared sentences
produces a spurious mismatch, independent of real negation. This
reframing directly motivated the v1.3 redesign below.

---

## [v1.3] — 2026-09-03 — `negation_probe.py`: marker-based negation comparison

**Found by:** cross-audit of the reverted whitelist attempt above.

**Change:** replace the whitelist-dependent `_is_affirmative()`
comparison with a direct comparison of negation-marker presence
between aligned sentences, independent of verb identity:
```diff
- pol_a = _is_affirmative(sa)
- pol_b = _is_affirmative(sb)
+ pol_a = _tiene_negacion(sa)   # bool(_NEGATION.search(sentence))
+ pol_b = _tiene_negacion(sb)
```
`_AFFIRM_STRONG` and `_is_affirmative()` remain in the file, unused, in
case another signal needs them later. Quantifier comparison
(`_quantifier_class`) is untouched.

**Verification (same protocol, with explicit willingness to revert
again if needed):**
- Piloto recall: 4/10 → 10/10 — same gain as the reverted attempt.
- **The same 6 historical false positives** (checked against the exact
  same pairs, not a new sample): 0/6 fire. The verb-coverage asymmetry
  mechanism is eliminated by construction, since verb identity no
  longer enters the comparison.
- 1,600-pair matrix: 510 items flipped `True→False`, 104 flipped
  `False→True`. Full breakdown, not just the counts:
  - Of the 510: re-derived 2026-09-05 by calling the module's own
    `detect_inversions()` on every one of the 510 pairs (not the
    regex-marker heuristic used originally) → **510/0: zero genuine
    regressions, 510 whitelist false positives now correctly silent.**
    The original 317/193 split was an artifact of comparing raw-text
    negation markers (any "no" anywhere in A vs B) instead of the
    module's aligned-sentence criterion. Verified with 5 random pairs
    (seed=42, script `72_verificar_5_pares_510.py`): in every case the
    texts are topically unrelated, `_align_sentences()` pairs
    low-similarity sentences (sim 0.10–0.42) or fails to pair ones
    with real negation, and no aligned pair carries an undetected
    inversion. Example: `halueval_dialogue/7527` aligns A5 ("Didn't
    they win the 2009 UEFA Champions League Final?") with B1 ("And
    didn't they win some kind of culinary competition in 2009?") at
    sim=0.417 — **both carry the same "didn't" negation marker**, so
    there is no polarity inversion; the module correctly stays silent.
  - Of the 104: 81 have real negation asymmetry in the text; 23 are
    borderline but correct (sentence alignment correctly pairing
    opposite-polarity sentences, e.g. "I like it" ↔ "No, I haven't
    watched it").
- Core unit tests unaffected (no core changes outside
  `negation_probe.py`).

**Status:** v1.3 kept. Superior to both the original whitelist design
and the reverted expansion attempt on every axis measured.

---

## [corpus-integrity] — 2026-09-02/03 — `legal_hallucinations`: A/B pairing is not query-matched

**Found by:** manual text inspection of 2 "regression" pairs flagged
during v1.3 verification (`183879`, `207465`), triggered by noticing
the negation-marker asymmetry made no semantic sense for single-topic
legal text.

**Finding:** `A_clean` and `B_hallucination` files in this suite do
NOT represent the same legal question answered correctly vs.
incorrectly. Root cause, found in the converter script itself
(`convertir_datasets.py`, `convertir_legal_hallucinations()`):
```python
if is_hallucination:
    fname = f"{hallucination_idx:04d}_B_hallucination.txt"   # separate counter
    hallucination_idx += 1
else:
    fname = f"{control_idx:04d}_A_clean.txt"                 # separate counter
    control_idx += 1
```
Two independent counters number clean and hallucinated rows in
parallel — `0000_A_clean.txt` and `0000_B_hallucination.txt` are
whichever rows happened to land first in each category, not the same
underlying query.

**Measured impact, with an initial false alarm corrected along the
way:** a first check on 99 IDs (all drawn from `negation_penalty`
firing-change lists) showed 92% mismatched cases — but that sample was
biased (pairs pre-filtered for negation-marker asymmetry are more
likely to be topically unrelated). A clean random sample (30 IDs, seed
123, drawn from the independent Fase-B matrix sample) confirmed the
same order of magnitude: 90% mismatched. Not a sampling artifact — a
real, large-scale corpus construction defect.

**Contamination check on already-reported results:**
- Firing matrix (Fase B): the `legal_hallucinations` row (`lexical
  95.5%, STG 99.0%, cre 92.0%, flow 86.5%`, etc.) does not measure
  hallucination detection — it largely measures how different two
  unrelated legal texts are. Treat as invalid.
- `negation_penalty` v1.3 recall figures: `legal_hallucinations`
  represents 12.5% of the 1,600-pair matrix, 8.9% of the 191-pair
  comparison set, 7.3%/19% of the two chequeo-4 samples (halogen
  subfolders were also found mixed into the largest of these,
  unaudited — see below). Recomputing recall/precision **excluding**
  `legal_hallucinations` moved every figure by ≤0.8 points — the
  contamination is proportional to population weight, not
  disproportionate. **v1.3's validated numbers stand.**
- 1,800-pair R1-D ablation (F1 = 99.55%): independently re-verified
  from `pares_ablation.json` by direct `suite` field count —
  30,000 `halu_eval_dialogue` + 30,000 `halu_eval_qa` + 2,370
  `truthfulqa` = 62,370, zero `legal_hallucinations`, zero `halogen`.
  Clean.

**Recovery path (not yet executed):** the source CSV
(`reglab/legal_hallucinations` via HuggingFace, 745,606 rows) has a
`query` column. 84,780 of 186,011 unique queries have both a
`hallucination=True` and `hallucination=False` row — those are
correctly reconstructable as matched pairs. The remaining ~66% of
hallucinated rows have no clean counterpart for the same query in this
dataset and cannot be paired without new work beyond re-indexing.

**Status: NOT reconstructed.** The current ~497k `_A_clean`/
`_B_hallucination` files remain mismatched. Any future use of this
suite for module validation must either use the reconstructed
84,780-pair subset or explicitly flag results as unpaired.

---

## [validation, real ground truth] — 2026-09-03 — `negation_penalty` on `halogen/rationalization_binary`

**Why this suite:** `negation_probe.py`'s own docstring names
`rationalization_binary` as its target domain (`recall 10.7% → target
>60%`). This subfolder of `halogen` (~21,000 pairs, never previously
run through the Fase-B firing matrix) was the first opportunity to
measure `negation_penalty` against a domain it was explicitly designed
for, with a verifiably correct A/B pairing (10 random pairs checked:
same question, e.g. same senator, same flight route, same number —
unlike `legal_hallucinations`).

**No explicit type-of-hallucination label exists** in this suite (or
in `halueval_*`/`truthfulqa`/`legal_hallucinations`) — only `codehalu`
carries type labels, and those are code-hallucination types, not
negation. Recall/precision below are therefore computed against
manually-verified text, not a corpus-native label.

**Method:** 200 pairs sampled (seed=42). 62 fired. Manual text
classification in three rounds (10 + 15 + 20 = 45 of the 62 fired
pairs; 30 of the 138 non-fired pairs), real vs. spurious negation
judged from the actual source/response text each time — not inferred
from aggregate counts.

**Results:**
- **Precision**, consolidated across all three rounds: 32/45 = 71.1%
  overall, **not uniform across the three question subtypes** in this
  suite:

  | Subtype | n | Precision |
  |---|---|---|
  | Primality ("Is X prime?") | 26 | 84.6% |
  | Flights ("Is there a route...?") | 9 | 66.7% |
  | Senator ("Was there ever a US senator...?") | 10 | 40.0% |

  **Correction note (2026-09-05):** the precision figures originally
  reported in this entry (30/45 = 66.7%, with subtype n of 27/8/10)
  contained arithmetic sum errors across the three labeled rounds —
  the individual per-ID classifications were correct, but rounds
  1 (7 primos + 3 vuelos, not 8+2), 2 (11a/4b, not 10a/5b) and 3
  (13a/7b, not 12a/8b) were mis-totaled. Re-counting from the 45
  individual records gives 32 real / 13 spurious = 71.1%, with subtype
  counts 26/9/10. Verified independently (script
  `67_rederivar_desglose_subtipos.py`, report
  `t1_rederivacion_desglose_subtipos.json`).

- **Recall**, weighted by population using the final consolidated
  precision (not the first sub-round in isolation): TP_est =
  62 × (32/45) ≈ 44.09. Direct evidence on the non-firing side: 1
  confirmed false negative in 30 sampled non-firings (FN_est =
  138 × (1/30) ≈ 4.6). **Point estimate: recall ≈ 90.6%.**

  This rests on a single directly-observed FN — a thin base. A
  sensitivity check (not an additional empirical finding: no second
  batch of non-firings was actually sampled) shows that if one more
  FN were present in the untested remainder, the estimate would drop
  to ≈82.7%. **Report this as a range, ≈83–91%, pending a larger
  non-firing sample** — do not cite a single decimal point as final.

**Root cause of the senator subtype's low precision, identified with
text evidence, not inferred:** every question in this suite's template
includes "First, respond with yes or no" in A. When the model answers
a senator question purely affirmatively ("Yes, there have been several
senators...", "Yes, Amy Klobuchar...") with no negation marker in B,
the negation marker present in A's template (from "yes or no") but
absent in B is read as a real polarity asymmetry. This is a
structural, predictable false-positive pattern tied to any
yes/no-templated question style, not a random module weakness.

**Scope note:** this result is specific to short, templated binary
yes/no questions. It does not generalize to negation in free-form
prose or dialogue (where `legal`/`biomed`/`narrative`-style
constructions already showed lower recall in the original R5 pilot).

**Status:** first `negation_penalty` result with real, text-verified
ground truth in this project. Recall is strong; precision is
subtype-dependent with a known, explainable failure mode. Both figures
should be treated as indicative until sample sizes grow — n=45 fired /
n=30 non-fired is enough to establish direction and mechanism, not
enough to defend a fixed decimal in a formal report.

---

## [v1.3] — 2026-09-04 — `reference_check.py`: citation regex over-capture fix

**Found by:** 5 adversarial citation pairs (same real citation in A and
B with different surrounding context). 3/5 produced a false
`same_year_diff_author` (ADV_CITA_01, ADV_CITA_02, ADV_CITA_04).

**Problem:** the 4th `_CITATION_PATTERNS` entry ("Author (Year)" with no
parenthesis/comma delimiter) used `{2,40}` to capture the author name,
which over-captured surrounding lexical context as part of the name:
- "work on reinforcement learning a. raffin" → author "work on
  reinforcement learning a. raffin"
- Legal case numbers: "676 F.3d 19 (2012)" → author "676 F.3d 19"

When A and B share a year but the over-captured "author" differs, a
false `same_year_diff_author` fires. In the 1,600-pair matrix, 6 items
(all `legal_hallucinations`) fired this way — capturing legal case
numbers as authors.

**Change:** the "Author (Year)" pattern now requires proper-name
sequences — capitalized-initial words (same criterion as
`source_target_guard`), 1–4 words, with surname particles
(de/van/von/du/la/del/den/der), hyphenated compounds, and optional
"et al.". The letter class was widened to Unicode Latin extended
(`[^\W\d_]` = any letter) to cover German/Turkish diacritics present
in CiteTracer (Müller, Alikaşifoğlu). Common words at the start
(Según, Como, The, In, ...) are excluded so lexical context is not
captured as part of the name. The other 3 patterns (delimited by
parenthesis or comma) were not touched.

**Verification (snapshots `t1_snapshot_reference_v12.json` →
`t1_snapshot_reference_v13.json`):**
- 5 adversarial pairs: 3 FPs eliminated (fab=1 → 0), 2 correct pairs
  unchanged (fab=0 → 0). **0/5 fire post-fix.**
- CiteTracer calibration (686 pairs): TP=299 → 299, FN=44 → 44,
  FP=0 → 0, TN=343 → 343. Recall 0.8717, precision 1.0 — **unchanged**.
  (Two TPs were temporarily lost during development — Müller and
  Alikaşifoğlu failed the `[a-záéíóúñ]` class — and were recovered by
  widening to `[^\W\d_]`; final state has zero TP loss.)
- 1,600-pair matrix: 6 FPs eliminated (all `legal_hallucinations`,
  legal case numbers captured as authors), 0 new firings, 0 magnitude
  changes.

**Note on independent verification:** the before/after snapshot files
for this specific entry were not independently re-derived from raw
pairs in this audit round (unlike the v1.0.1/v1.2 entries above, which
were). The adversarial-pair result (0/5) and the qualitative direction
are consistent with everything else known about this bug; treat the
exact calibration counts as reported-but-not-independently-recomputed
until a future audit pass checks them from raw data.

**Status:** `reference_penalty` citation extraction now matches the
proper-name criterion used elsewhere in the tribunal. The
`legal_hallucinations` suite remains unusable for validation (see
corpus-integrity entry) — the 6 eliminated firings were on mismatched
pairs.

---

## [audit-close] — 2026-09-04 — negation v1.3 vs original pilot Subset A + version audit

**1. The one missing negation measurement is now closed, independently
verified against the raw output file.** The original R5 pilot Subset A
(10 negation pairs across finance/legal/biomed/general/narrative) was
never re-measured after the v1.3 redesign to negation markers. Re-run
now (`scripts/63_negation_vs_piloto_A.py`,
`reports/t1_negation_vs_piloto_A.json`): **recall 10/10 = 100%**,
confirmed item-by-item from the raw file — every pair fires with
`inversion_count=1, penalty=0.45`. This matches the 10/10 achieved by
the reverted v1.2 whitelist attempt — but without the 6 zone-changing
false positives that killed v1.2. The v1.3 docstring placeholder
("?/10") is now filled with the real number.

**2. Version audit of the three touched core files:**

| File | Docstring version | CHANGELOG entry | Match |
|---|---|---|---|
| `tribunal_multimetrico.py` | v1.0.1 | [v1.0.1] 2026-09-02 | ✅ |
| `reference_check.py` | v1.3 | [v1.3] 2026-09-04 (this entry) | ✅ |
| `negation_probe.py` | v1.3 | [v1.3] 2026-09-03 | ✅ |

No applied change is undocumented, and no documented change is
unapplied. The `negation_probe.py` v1.3 docstring said "recall 4/10 →
?/10 (ver script 35)" — the placeholder is now replaced with the real
10/10 measurement.

**3. Snapshots/reports generated this cycle, verification status
(updated 2026-09-05 — all previously-flagged items re-derived):**

| Report | Independently verified? |
|---|---|
| `t1_negation_vs_piloto_A.json` | ✅ recomputed from raw pilot corpus |
| `t1_sobrecaptura_citas.json` | ✅ contents inspected directly (1,372 flagged captures, 100% suspicious pre-fix, 88 overlapping with FN cases) — kept as evidence of the bug, superseded by the v1.3 fix |
| `t1_snapshot_reference_v12.json` / `v13.json` | ✅ **re-derived from scratch 2026-09-05** (script `66_rederivar_snapshots_reference.py`, report `t1_rederivacion_snapshots_reference.json`): adversarial 3/5→0/5 with raw `detect_fabrications()` events; calibration TP=299/FN=44/FP=0/TN=343 item-by-item, 0 item-level diffs; matrix 6 FPs eliminated, 0 new, 0 magnitude. **Numbers confirmed unchanged.** |
| `t1_rationalization_binary.json` / `t1_desglose_subtipos.json` | ✅ **re-derived 2026-09-05** (script `67_rederivar_desglose_subtipos.py`, report `t1_rederivacion_desglose_subtipos.json`): re-counted from the 45 individual records → **32/45 = 71.1%** (primalidad 26/84.6%, vuelos 9/66.7%, senador 10/40.0%). **Correction applied** — the previously published 30/45 = 66.7% (27/8/10) had arithmetic sum errors in rounds 1–3; the per-ID classifications were correct. |
| `t1_recall_ponderado.json` | ✅ **regenerated 2026-09-05** (script `71_recall_ponderado_v2.py`) with the corrected precision: TP_est = 62×(32/45) = 44.09, FN_est = 138×(1/30) = 4.6 → **recall ≈ 90.6%**; sensitivity with 2 FN → 82.7%. Range **≈83–91%**. |
| `analisis_decisivo_negation_v3.json` (317/193 split) | ✅ **superseded 2026-09-05** — re-derived by calling the module's own `detect_inversions()` on all 510 True→False pairs (script `69_rederivar_317_193.py`, report `t1_rederivacion_317_193.json`): **510/0** (zero genuine regressions, 510 whitelist FPs). The 317/193 was a raw-text regex-marker artifact. Verified with 5 random pairs (script `72_verificar_5_pares_510.py`) — see the [v1.3] entry above. |
| `cambios_1600_negation_v3.json` | ✅ arithmetic on the `regresion_1600_*` snapshots (independently verified) — the derived counts were re-confirmed by the 510/0 re-derivation above |

**Correction to an earlier internal report:** a draft of this entry
stated that "a second false negative was found in a larger follow-up
sample," lowering the recall estimate to 82.9%. This is inaccurate — no
second batch of non-firing pairs was actually sampled. The 82.9% figure
was a **sensitivity illustration** ("if one more FN existed, recall
would drop to..."), not an empirical result. Corrected above to report
recall as a range (≈83–91%) grounded in the one FN actually observed,
with the sensitivity noted explicitly as hypothetical. (Updated
2026-09-05: with the corrected precision 32/45, the point estimate is
90.6% and the sensitivity to a second FN is 82.7%.)

---

## Consolidated module status at the close of this cycle

| Module | Status | Pending action |
|---|---|---|
| `lexical_baseline_score` | Works as designed | None — the low recall in R5-v1 was a corpus-design artifact, not a defect |
| `source_target_guard` | Works | None |
| `cre_isi` | Works, requires ≥2 sentences | Corpus design (not code) |
| `flow_penalty` | Works, requires ≥15 content tokens | Corpus design (not code) |
| `negation_penalty` | v1.3 kept — recall 10/10 on original pilot; ≈83–91% on `rationalization_binary` (real ground truth, thin FN base); precision 71.1% (32/45) with subtype dependence (senator 40%) | Known, explainable FP pattern on yes/no templates. Larger non-firing sample would tighten the recall range. |
| `arithmetic_penalty` | Not working in practice | Low priority — the underlying problem (implicit arithmetic) is not solved by translating the regex alone |
| `reference_penalty` | Fixed in three layers (v1.0.1 + v1.2 + v1.3) | Calibrated against CiteTracer (recall 0.872, precision 1.0); citation regex over-capture fixed — snapshots re-derived from scratch 2026-09-05, numbers confirmed |

**Corpus caveat that applies across the table above:** `legal_hallucinations`
(497k of the 596k-pair `benchmark_corpus`) has a confirmed A/B pairing
defect (see entry above) and must not be used for module validation
until reconstructed. `halogen` (~120k pairs, 7 subfolders) has only had
its `rationalization_binary` subfolder validated; the other 6 remain
unaudited.

---

## Integrity verification of this document

SHA-256 of this file (computed at publication time, over the full
document): see `CHANGELOG.md.sha256` in the same directory. Verify with:
`sha256sum -c CHANGELOG.md.sha256` (or `Get-FileHash` on Windows).
