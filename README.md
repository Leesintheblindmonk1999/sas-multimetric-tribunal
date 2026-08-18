# SAS Multimetric Tribunal

**Structural Coherence Auditing for AI-Generated Text — 3-Zone Classification**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19702379.svg)](https://doi.org/10.5281/zenodo.19702379)
[![SAS Standard](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.19702379-blue)](https://doi.org/10.5281/zenodo.19702379)
[![R0 Audit](https://img.shields.io/badge/R0%20Audit-Zenodo%2020647532-blueviolet)](https://zenodo.org/records/20647532)
[![License](https://img.shields.io/badge/license-Durante--Invariance--1.0-blue)](LICENSE)

---

## Overview

The **SAS Multimetric Tribunal** is an open-source structural auditing system that classifies (source, response) text pairs into **3 structural zones** using 7 detection modules with **cascading multiplicative penalty**.

It detects hallucinations, factual mutations, and structural ruptures in AI-generated text — **without GPU, without external LLM APIs, and without training data**.

### Key Results

| Metric | Value |
|--------|-------|
| **F1 Score** | **99.16%** |
| **Precision** | **100.00%** (0 false positives) |
| **Recall** | **98.33%** |
| **Accuracy** | **99.17%** |
| **ISI Separation** | **0.8323** |
| **Pairs Evaluated** | 600 (300 control + 300 hallucination) |

### Thresholds

| Threshold | Value | Meaning |
|-----------|-------|---------|
| **κD** | **0.56** | Structural coherence (TAD EX-2026-18792778) |
| **κR** | **0.15** | Structural collapse (experimentally validated) |

---

## Structural Zones

| Zone | Code | ISI Range | Risk | Action |
|------|------|-----------|------|--------|
| **STRUCTURAL COLLAPSE** | **F-S** | ISI < 0.15 | CRITICAL | Block / Escalate |
| **RECOVERABLE RUPTURE** | **B** | 0.15 ≤ ISI < 0.56 | HIGH | Review / Flag |
| **COHERENT** | **A** | ISI ≥ 0.56 | LOW | Pass |

---

## Architecture

```
ISI_HARD  = min(lexical_baseline, source_target_guard, cre_isi)
ISI_FINAL = ISI_HARD × Π(penalties from fired modules)
```

### 7 Detection Modules

| # | Module | Function | Weight |
|---|--------|----------|--------|
| 1 | `lexical_baseline_score` | Jaccard lexical overlap | 0.35 |
| 2 | `source_target_guard` | Critical entity mutation detection | 0.25 |
| 3 | `flow_penalty` | Semantic flow rupture | 0.12 |
| 4 | `negation_penalty` | Logical inversions | 0.08 |
| 5 | `cre_isi` | Ricci semantic curvature | 0.12 |
| 6 | `arithmetic_penalty` | Arithmetic errors | 0.04 |
| 7 | `reference_penalty` | Reference fabrication | 0.04 |

### Combination Strategy

The tribunal uses **cascading multiplicative penalty**: only modules that **fire** (detect an anomaly) apply a penalty. Silent modules (returning 1.0) do not dilute the signal. This prevents false negatives from modules that are irrelevant to the specific input.

---

## Quick Start

### Requirements

- Python 3.10+
- No GPU required
- No external LLM API required

### Installation

```bash
git clone https://github.com/Leesintheblindmonk1999/sas-multimetric-tribunal.git
cd sas-multimetric-tribunal
pip install -r requirements.txt
```

### Run on a Single Pair

```python
from core.tribunal_multimetrico import TribunalMultimetrico

tribunal = TribunalMultimetrico()

source = "The Eiffel Tower is located in Paris, France. It was built in 1889."
response = "The Eiffel Tower is located in Berlin, Germany. It was built in 1950."

verdict = tribunal.evaluar(source, response)

print(f"ISI: {verdict.isi_final:.4f}")
print(f"Zone: {verdict.zona}")
print(f"Risk: {verdict.riesgo}")
print(verdict.summary)
```

### Run from CLI

```bash
python -m core.tribunal_multimetrico \
  --source "The Eiffel Tower is in Paris." \
  --response "The Eiffel Tower is in Berlin." \
  --json
```

### Run Validation

```bash
python scripts/run_validation.py \
  --data-dir ./data/benchmark_sample \
  --output ./reports/validation_report.json
```

---

## Dataset

The validation was performed on the **benchmark_corpus** containing:

| Corpus | Domain | Pairs |
|--------|--------|-------|
| `halueval_dialogue` | Dialogue | 10,000 |
| `halueval_qa` | Question answering | 10,000 |
| `truthfulqa` | Factual QA | 790 |

A pre-sampled set of **600 pairs** (100 per suite × 3 suites, split into control and hallucination) is included in `./data/benchmark_sample/`.

To run on the full corpus, download the original datasets from:
- [HaluEval](https://github.com/RUCAIBox/HaluEval)
- [TruthfulQA](https://github.com/sylinrl/TruthfulQA)

---

## Validation Results

### Confusion Matrix

```
                    ┌──────────────┬──────────────┐
                    │  Detected    │  Not detected│
    ───────────────┼──────────────┼──────────────┤
    Hallucination  │   TP=295     │   FN=5       │
    Control        │   FP=0       │   TN=300     │
                    └──────────────┴──────────────┘
```

### κR Sweep

| κR | Collapse | Rupture | Coherent | Signal | F1 |
|----|----------|---------|----------|--------|-----|
| 0.15 | 30.0% | 19.2% | 50.8% | 98.3% | **99.2%** |
| 0.20 | 35.2% | 14.0% | 50.8% | 98.3% | 99.2% |
| 0.25 | 39.5% | 9.7% | 50.8% | 98.3% | 99.2% |
| 0.30 | 41.0% | 8.2% | 50.8% | 98.3% | 99.2% |

### ISI Distribution

| ISI Range | Control | Hallucination |
|-----------|---------|---------------|
| [0.00-0.10) | 0 | 30 |
| [0.10-0.20) | 0 | 13 |
| [0.20-0.30) | 0 | 5 |
| [0.30-0.40) | 0 | 2 |
| [0.40-0.56) | 0 | 0 |
| [0.56-1.00) | 50 | 0 |

### Module Firing Frequency

| Module | Times | % |
|--------|-------|---|
| lexical_baseline_score | 294 | 49.0% |
| cre_isi | 171 | 28.5% |
| negation_penalty | 123 | 20.5% |
| source_target_guard | 98 | 16.3% |
| flow_penalty | 46 | 7.7% |

---

## Repository Structure

```
sas-multimetric-tribunal/
├── core/
│   ├── tribunal_multimetrico.py   # Main tribunal implementation (7 modules, 3 zones)
│   ├── flow_coherence.py          # Semantic flow rupture detection
│   ├── negation_probe.py          # Logical inversion detection
│   ├── ricci_enhanced_cre.py      # Ricci semantic curvature analysis
│   ├── arithmetic_detector.py     # Arithmetic error detection
│   └── reference_check.py         # Reference fabrication detection
├── scripts/
│   ├── run_validation.py          # Run validation on benchmark data
│   └── sample_dataset.py          # Sample pairs from corpus
├── data/
│   └── benchmark_sample/          # 600 pre-sampled pairs for validation
│       ├── halueval_dialogue/
│       ├── halueval_qa/
│       └── truthfulqa/
├── reports/
│   └── validation_report.json     # Full validation results
├── tests/
│   └── test_tribunal.py           # Unit tests
├── README.md                      # This file
├── LICENSE                        # Durante Invariance License v1.0
└── requirements.txt               # Python dependencies
```

---

## Background & Research Line

This tribunal is the result of the SAS / κD=0.56 research program:

| Milestone | Description | DOI |
|-----------|-------------|-----|
| SAS Standard | Main structural coherence standard | [10.5281/zenodo.19702379](https://doi.org/10.5281/zenodo.19702379) |
| R0 | Infrastructure & baseline stability audit | [10.5281/zenodo.20647532](https://zenodo.org/records/20647532) |
| R0-bis | Nonlinear dependence & redundancy audit | [10.5281/zenodo.20671824](https://zenodo.org/records/20671824) |
| R1 | Real local structural evaluation | [10.5281/zenodo.21034155](https://zenodo.org/records/21034155) |
| R1-D | Structural evaluation over declarative corpus | [10.5281/zenodo.21282332](https://doi.org/10.5281/zenodo.21282332) |
| R2.1 | Code hallucination detection via AST | [10.5281/zenodo.21365707](https://doi.org/10.5281/zenodo.21365707) |
| **Tribunal** | **Multimetric 3-zone classification** | **This repository** |

---

## Citation

```bibtex
@software{durante_2026_sas_tribunal,
  author    = {Durante, Gonzalo Emir},
  title     = {SAS — Multimetric Tribunal: 3-Zone Structural Classification},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19702379},
  note      = {Cascading multiplicative penalty, F1=99.16%, 0 false positives}
}
```

---

## Links

- **SAS (active implementation):** https://github.com/Leesintheblindmonk1999/SAS
- **Project Manifold 0.56 (historical):** https://github.com/Leesintheblindmonk1999/Project_Manifold_056
- **Public API:** https://sas-api.onrender.com
- **Landing page:** https://leesintheblindmonk1999.github.io/sas-landing/

---

## License

**Durante Invariance License v1.0** — See [LICENSE](LICENSE) for details.

Registry: TAD EX-2026-18792778 (Argentina)

© 2026 Gonzalo Emir Durante