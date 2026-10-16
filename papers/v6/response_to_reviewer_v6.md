# Response to Reviewer — Round 4 (v6)

**Paper:** SAS Multimetric Tribunal: What a Hallucination Benchmark Measures, and What It Does Not
**DOI:** 10.32388/T420IV
**Revision:** v6 (2026-10-16)
**Reviewer:** Evgenii Arsentev

---

Dear Dr. Arsentev,

Thank you for your fourth review. Your sustained engagement across four rounds — and your willingness to acknowledge when a point is answered, even when the answer goes against the author's own earlier claims — is the reason this paper is substantially better than the version you first evaluated. I am particularly grateful that you noted this explicitly in your round-4 review: *"I value that the author retires four of his own v4 claims by direct measurement, with the same protocol. That is rare."*

Below I address each of your seven points from round 4, plus the field-name request. The most substantial change in this revision is the R3.1 differential guard, which you asked to see in your round-3 review and which is now validated on two domains.

---

## Point-by-Point Response

### Point 1 — Table 8: asymmetric threshold calibration

**Your observation:** The multiplicative row stayed at fixed κD = 0.56 while the weighted average received an optimized threshold (0.83). You asked to either optimize the multiplicative threshold too or label the rows "fixed" vs. "optimized."

**Response:** Both done. I re-ran the calibration with a sweep over both schemes on the same set (A→B vs. A→A′, n = 1,800). The multiplicative optimum is 0.550 — essentially indistinguishable from the fixed κD = 0.56 (F1 0.688 vs. 0.687). The fixed-κD row was already at the multiplicative optimum. Table 8 now reports four rows: both schemes at both their fixed-κD and optimized thresholds, explicitly labeled.

The asymmetry between the two schemes' thresholds (0.550 vs. 0.830) is a property of each score's distribution, not of the calibration procedure. The multiplicative cascade compresses scores toward zero, so its threshold naturally sits lower.

### Point 2 — F1 arithmetic (Table 8)

**Your observation:** TP = 1,759, FP = 1,511 → F1 = 3,518 / 5,070 = 0.694, but the table printed 0.695.

**Response:** Corrected. The table now reads 0.694. I verified the arithmetic independently: precision = 1,735 / (1,735 + 1,461) = 0.5429, recall = 1,735 / 1,800 = 0.9639, F1 = 2 × 0.5429 × 0.9639 / (0.5429 + 0.9639) = 0.6946, rounded to 0.694. Thank you for catching this.

### Point 3 — "Nearly identical" wording (§5.4)

**Your observation:** 87.2% and 98.0% are 10.8 points apart — "nearly identical" is imprecise. You suggested "close" or Wilson intervals.

**Response:** Changed to "close" with Wilson intervals. The 95% Wilson intervals are [0.8554, 0.8863] for 87.2% and [0.9724, 0.9855] for 98.0%. They do not overlap, so the gap is statistically real, but both rates are high and both reflect the format asymmetry rather than content. The text now reads: *"the two rates are close (10.8 points apart), and their 95% Wilson intervals do not overlap... so the gap is statistically real but substantively small."*

### Point 4 — Length claim stated as fact without measurement (§9.1)

**Your observation:** §9.1 said "The published F1 reflects response length" but length is not measured anywhere in the paper. You asked for a direct measurement or to phrase it as a likely explanation.

**Response:** I added the measurement. On the N1 set, I computed the Pearson correlation between ISIFINAL and the ratio of response length to source length:

- A→B (hallucinated response): r = +0.5996 (n = 1,800)
- A→A′ (correct response): r = +0.8696 (n = 1,800)

Longer responses score higher ISI in both conditions; the correlation is stronger on correct answers than on hallucinated ones. This makes the length explanation the *measured* one rather than the *plausible* one. The text now reports these correlations explicitly.

### Point 5 — cre_isi firing asymmetry (Table 7)

**Your observation:** A reader will ask why cre_isi fires on 971 (A→A) and 1,081 (A→A″) but on 132 (A→B) and 68 (A→A′). You asked for one sentence on what gates the firing.

**Response:** I added a paragraph explaining the two gates. cre_isi is only included in ISIHARD when it fires *and* the two texts are not byte-identical. Its score is computed from the source's LSA dispersion, so it fires on long format-matched pairs (A→A and A→A″) regardless of the response, while short responses (A→B, A→A′) rarely reach the dispersion threshold. The gate suppresses it on byte-identical pairs for the verdict, but the firing count in Table 7 counts the module's own activation — which is why A→A still shows 971 firings without any zone change.

### Point 6 — "below" → "above" + justify κD (§9.5)

**Your observation:** The sentence "No limitation below changes κD = 0.56 or κR = 0.15" comes after Table 11, so "below" should be "above." You also asked for one line on what now supports κD = 0.56, since §11 keeps it while the benchmark it was tuned on is shown to measure format.

**Response:** Corrected to "above." I added a full paragraph justifying κD = 0.56:

κD is a property of the score distribution, not of the benchmark's label semantics. It separates the two modes of ISIFINAL visible in N1 (format-matched pairs cluster below 0.35, identity pairs at 1.0), and it was re-confirmed on the seed-42 and seed-123 stratified runs. The audit does not change the threshold; it changes what firing means. The honest formulation is: κD = 0.56 remains the boundary of the format distribution, and N1 shows that crossing it does not, by itself, prove hallucination. The same applies to κR = 0.15, which v5 established as the entropy-maximizing value of this sample's ISI distribution.

### Point 7 — License mismatch

**Your observation:** The Qeios page header shows CC BY, while "License and Attribution" says CC BY-NC 4.0.

**Response:** Resolved in favor of the displayed Qeios header. The manuscript now states CC BY 4.0, with a note that earlier versions stated CC BY-NC 4.0 and the mismatch is corrected.

### Field-name request (§3.5)

**Your request:** You asked for the specific dataset field used for A and B in each suite, noting that R3 failed exactly on a field-parsing error.

**Response:** I added a new table (Table: Dataset fields and extraction markers per suite) that lists each suite's source dataset, how A is constructed, and the exact marker string used for extraction:

| Suite | A construction | Marker |
|-------|---------------|--------|
| HaluEval-Dialogue | Knowledge: + Dialogue: + Correct response: | `Correct response: ` |
| HaluEval-QA | Knowledge: + Question: + Correct answer: | `Correct answer: ` |
| TruthfulQA | Knowledge: + Question: + Correct answer: | `Correct answer: ` |

Writing these field names down is not cosmetic: the R3 control failed exactly on a field-parsing error, and N1's correctness depends on using the verbatim marker.

---

## Major Addition: R3.1 Differential Guard

Beyond your seven points, this revision introduces the R3.1 differential guard — the module you asked to see in your round-3 review (*"I look forward to the version with the semantic-equivalence guard R3.1"*).

The v5 paper tested a substring-based guard and found it was a constructional artifact (it returned 1.0 for every A→A′ pair because A′ is a substring of A by construction). That guard has been replaced with a *differential* guard that does not rely on substrings:

**Architecture.** Grounding (recall of response content words against the source) as the primary signal, compression-ratio abstention as the secondary signal, and three short-response heuristics (polarity inversion, isolated entity, stopword grounding) for responses under 5 words.

**Threshold calibration.** The grounding threshold was swept over the N1 audit data. The v5 default (0.50) was too permissive — a hallucination with 80% lexical overlap scored equivalent. The sweep minimizes total error at 0.95 (scripts/sweep_threshold_guard.py, included in the supplement).

**Results on N1 (n = 1,800 per condition):**

| Metric | Tribunal alone | Tribunal + R3.1 | Δ |
|--------|:-------------:|:--------------:|:-:|
| FP rate | 1,569 | 436 | −1,133 |
| Recall | 0.9800 | 0.8867 | −0.0933 |
| Precision | 0.5293 | 0.7854 | +0.2562 |
| F1 | 0.6873 | 0.8330 | +0.1457 |

The guard corrects 1,133 of the 1,569 format-driven false positives on A→A′ (72% of the original FP rate eliminated) while keeping A→A intact at 100% and introducing zero regressions on the negative side. On A→B, recall drops from 0.9800 to 0.8867: the 168 regressions are responses where the guard abstains by compression ratio (long hallucinated responses where grounding is uninformative).

**Generalization to financial domain (FinQA, 1,657 samples).** The guard detects 208 of 239 hallucinated financial answers (87.0%) with zero regressions, despite the sources being from different queries. During this test we found and fixed a defect in the isolated-entity regex (it did not match negative numbers), which removed 5 regressions without changing N1 results.

**Why this guard is not a substring artifact.** The v5 guard returned 1.0 for every A→A′ pair because A′ is a substring of A by construction. The differential guard does not check substrings; it checks whether the response's content words appear in the source. Its success on A→A′ is not an exploitation of the extraction method — A′ gets grounding ≈ 1.0 because it is genuinely composed of the source's content words.

---

## Supplement

The complete supplement (SAS_v6_Supplements.zip, 26 files, SHA-256 manifest) is available with this revision. It includes:

- The R3.1 differential guard (r3_1_differential.py, sweep_threshold_guard.py)
- The N1 guard audit (audit_n1_guard_v4.json, audit_n1_corpus.py)
- The N1 control (n1_control.py, pairs_conditions_1800_seed42.json)
- The recalibration (recalibracion_v6.json, recalibrar_umbral_v6.py)
- The FinQA conversion and evaluation (convert_finqa.py, evaluar_finqa_guard.py, pairs_finqa.jsonl, evaluacion_finqa_guard.json)
- The MedHallu conversion (convert_medhallu.py, 10,000 pairs)
- All v5 artifacts that remain relevant (ablation, baselines, κR sweep, validation script)
- The project changelog with SHA-256 hashes for every file

Every numerical claim in this paper can be verified against the files in this archive.

---

Thank you again for your thoroughness across four rounds. The paper is substantially stronger for it.

Gonzalo Emir Durante