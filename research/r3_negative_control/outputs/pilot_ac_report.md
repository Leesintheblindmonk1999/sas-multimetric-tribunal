# R3 — Negative Control Pilot Report (A→C Paraphrase)

**Date:** 2026-08-31
**Registry:** TAD EX-2026-18792778
**Status:** ⚠️ Open issue — high false-positive rate on paraphrases

---

## 1. Motivation

The SAS Multimetric Tribunal was validated on **A→B** pairs (source → hallucinated response), achieving F1=99.16% with 0 false positives. However, the validation protocol used **A→A** pairs as the control condition (source → identical response).

Reviewer #1 correctly identified that this does not test the case where a model produces a **correct but non-identical** response (paraphrase, summary, reformulation). This pilot closes that gap.

## 2. Protocol

- **Source of pairs:** `benchmark_corpus` (TruthfulQA, HaluEval-Dialogue, HaluEval-QA)
- **Paraphrase methods:**
  - `synonym`: NLTK WordNet synonym replacement
  - `backtranslation`: EN → ES → EN via `deep_translator`
- **Sample:** n=100 (synonym), n=27 (backtranslation — limited by API availability)
- **Thresholds:** κD=0.56, κR=0.15
- **Expected:** All paraphrases should be classified **COHERENT (A)** — they preserve meaning

## 3. Results

| Method | n | FP | FP rate | A | B | F-S | Mean ISI |
|--------|---|----|---------|---|---|-----|----------|
| synonym | 100 | 100 | 100% | 0 | 15 | 85 | 0.0554 |
| backtranslation | 27 | 26 | 96.3% | 1 | 10 | 16 | 0.1725 |
| **Total** | **127** | **126** | **99.2%** | **1** | **25** | **101** | — |

## 4. Analysis

### 4.1 Why does this happen?

The tribunal's `lexical_baseline_score` (Jaccard overlap) is the dominant signal in `ISI_HARD`:

```
ISI_HARD = min(lexical_baseline, source_target_guard, cre_isi)
```

A paraphrase shares few **surface tokens** with the source, so Jaccard similarity collapses to ~0.05–0.17, pushing the pair into **F-S (structural collapse)** even though the meaning is preserved.

### 4.2 Is this a bug or a design limitation?

**Design limitation.** The tribunal was designed to detect *structural* rupture between a source and a response that should be *derived* from it. When the response is a paraphrase, the lexical layer is blind to semantic equivalence.

### 4.3 Impact

| Scenario | Impact |
|----------|--------|
| Hallucination detection (A→B) | ✅ Unaffected — F1=99.16% holds |
| Deployment as content filter | ❌ Blocked — would reject valid paraphrases |
| RAG verification | ⚠️ Partial — only verbatim extractions pass |

## 5. Recommended Fix (R3.1)

Add a **semantic-equivalence guard** before applying lexical penalties:

```
IF semantic_similarity(source, response) > θ_semantic:
    SKIP lexical penalties (treat as paraphrase-safe)
    ISI_FINAL = max(ISI_HARD, semantic_similarity)
```

Candidate implementations (zero-LLM, zero-GPU):
- TF-IDF cosine similarity (already available in the codebase)
- LSA embeddings (already used by CRE module)
- Sentence-transformer (optional, adds ~80MB model)

**Target:** FP rate < 5% on this pilot after the guard.

## 6. Conclusion

The A→C negative control **exposes the lexical layer's blindness to paraphrase equivalence**. This is the top-priority open issue for the tribunal. The hallucination-detection results remain valid, but the system cannot be deployed as a general-purpose coherence filter until R3.1 is implemented.

---
*SAS Multimetric Tribunal — Research Series. Registry: TAD EX-2026-18792778*