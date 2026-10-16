#!/usr/bin/env python3
"""
r3_1_signals.py — R3.1 Semantic-Equivalence Guard: 4 independent signals
═══════════════════════════════════════════════════════════════════════════════

Each signal implements the same interface:
    signal(source: str, response: str) -> dict {"score": float, "fires": bool}

- score ∈ [0.0, 1.0]:  higher means the two texts are semantically equivalent
  along the dimension measured by this signal.
- fires:  True when the signal has enough information to produce a meaningful
  score; False when the signal abstains (e.g. no entities found in either text).

Usage:
    from r3_1_signals import EntityCore, NegationMatch, QuantMatch, ContentWordOverlap

    result = EntityCore(source_text, response_text)
    print(result["score"], result["fires"])
"""

from __future__ import annotations

import re
from typing import Dict, List, Set


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL 1 — EntityCore
# ═══════════════════════════════════════════════════════════════════════════

# Pattern for proper names: two or more capitalized words in a row
_RE_NAME = re.compile(r"\b[A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+){1,3}\b")

# Clinical key terms (common medical entities, procedures, conditions)
_CLINICAL_TERMS: Set[str] = {
    # Diseases & conditions
    "cancer", "diabetes", "hypertension", "asthma", "arthritis", "pneumonia",
    "tuberculosis", "malaria", "hiv", "aids", "covid", "stroke", "infarction",
    "ischemia", "necrosis", "apoptosis", "fibrosis", "cirrhosis", "sepsis",
    "anemia", "leukemia", "lymphoma", "melanoma", "carcinoma", "sarcoma",
    "obesity", "anorexia", "depression", "schizophrenia", "autism",
    "alzheimer", "parkinson", "epilepsy", "migraine", "insomnia",
    # Procedures & techniques
    "biopsy", "autopsy", "angiography", "electrocardiogram", "echocardiogram",
    "colonoscopy", "endoscopy", "laparoscopy", "dialysis", "transfusion",
    "vaccination", "immunization", "chemotherapy", "radiotherapy",
    "hemodialysis", "catheterization", "intubation", "amputation",
    # Anatomy & physiology
    "mitochondria", "ribosome", "nucleus", "cytoplasm", "membrane",
    "epithelium", "endothelium", "myocardium", "neurona", "synapse",
    "dendrite", "axon", "cortex", "cerebellum", "hippocampus",
    "hypothalamus", "pituitary", "thyroid", "pancreas", "hepatocyte",
    "nephron", "alveolus", "bronchus", "trachea", "esophagus",
    # Pharmacology
    "ibuprofen", "paracetamol", "acetaminophen", "metformin", "insulin",
    "atorvastatin", "omeprazole", "amoxicillin", "azithromycin",
    "ciprofloxacin", "warfarin", "heparin", "morphine", "fentanyl",
    # Molecular biology
    "dna", "rna", "mrna", "trna", "ribosomal", "polymerase", "ligase",
    "helicase", "primase", "nuclease", "protease", "kinase", "phosphatase",
    "methylation", "acetylation", "phosphorylation", "ubiquitination",
    "transcription", "translation", "replication", "recombination",
    # Immunology
    "antibody", "antigen", "cytokine", "chemokine", "interleukin",
    "interferon", "immunoglobulin", "lymphocyte", "macrophage",
    "neutrophil", "eosinophil", "basophil", "monocyte", "dendritic",
    # Genetics
    "genotype", "phenotype", "allele", "locus", "gene", "chromosome",
    "telomere", "centromere", "karyotype", "mutation", "polymorphism",
    "deletion", "insertion", "duplication", "translocation", "inversion",
}

_RE_CLINICAL = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(_CLINICAL_TERMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def EntityCore(source: str, response: str) -> Dict:
    """Signal 1 — EntityCore: proper-name and clinical-term overlap.

    Extracts proper names (consecutive capitalized words) and clinical key
    terms from both texts, then computes:
        score = |intersection| / max(|response_entities|, 1)

    Fires only when at least one entity is found in *both* texts.
    """
    # Proper names
    names_src: Set[str] = set(_RE_NAME.findall(source))
    names_rsp: Set[str] = set(_RE_NAME.findall(response))

    # Clinical terms
    clin_src: Set[str] = set(m.group(0).lower() for m in _RE_CLINICAL.finditer(source))
    clin_rsp: Set[str] = set(m.group(0).lower() for m in _RE_CLINICAL.finditer(response))

    entities_src: Set[str] = names_src | clin_src
    entities_rsp: Set[str] = names_rsp | clin_rsp

    if not entities_src or not entities_rsp:
        return {"score": 0.0, "fires": False}

    intersection = entities_src & entities_rsp
    score = len(intersection) / max(len(entities_rsp), 1)
    return {"score": round(min(score, 1.0), 6), "fires": True}


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL 2 — NegationMatch
# ═══════════════════════════════════════════════════════════════════════════

_RE_NEGATION = re.compile(
    r"\b(?:"
    r"no|not|never|none|neither|nor|nobody|nothing|nowhere|"
    r"without|lack|lacking|absence|absent of|"
    r"isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|"
    r"doesn't|don't|didn't|won't|wouldn't|shouldn't|couldn't|can't|cannot|"
    r"unable|unlikely|unnecessary|unsuccessful|"
    r"denies|denied|refuses|refused|rejects|rejected|disputes|disputed|"
    r"declines|declined|fails|failed to|"
    r"sin|nunca|jamás|tampoco|ni|ningún|ninguna"
    r")\b",
    re.IGNORECASE,
)


def NegationMatch(source: str, response: str) -> Dict:
    """Signal 2 — NegationMatch: polarity consistency check.

    Counts negation markers in both texts.
    - score = 1.0 if both have negations or both lack them.
    - score = 0.0 if one has negations and the other does not.
    - fires = False only when *neither* text contains any negation marker
      (neutral case, no opinion).
    """
    has_neg_src = bool(_RE_NEGATION.search(source))
    has_neg_rsp = bool(_RE_NEGATION.search(response))

    if not has_neg_src and not has_neg_rsp:
        return {"score": 0.0, "fires": False}

    score = 1.0 if has_neg_src == has_neg_rsp else 0.0
    return {"score": score, "fires": True}


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL 3 — QuantMatch
# ═══════════════════════════════════════════════════════════════════════════

_RE_QUANTITY = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|ml|g|kg|mcg|µg|ui|IU|cm|mm|µm|nm|"
    r"l|dl|cl|fl\s*oz|oz|lb|kg|%|percent|mmhg|"
    r"cells?/µl|units?/l|g/dl|mg/dl|mmol/l|meq/l)\b",
    re.IGNORECASE,
)

# Fallback: bare numbers when no unit-carrying quantity is found
_RE_BARE_NUMBER = re.compile(r"\b(\d+)\b")


def QuantMatch(source: str, response: str) -> Dict:
    """Signal 3 — QuantMatch: numerical-quantity overlap.

    Extracts numbers with units (preferred) and bare numbers (fallback).
    Score = |intersection| / max(|response_numbers|, 1).

    Fires only when at least one number is present in *both* texts.
    """
    # Prefer quantities with units
    nums_src: Set[str] = set(_RE_QUANTITY.findall(source))
    nums_rsp: Set[str] = set(_RE_QUANTITY.findall(response))

    # Fallback to bare numbers if neither side has unit-carrying quantities
    if not nums_src and not nums_rsp:
        nums_src = set(_RE_BARE_NUMBER.findall(source))
        nums_rsp = set(_RE_BARE_NUMBER.findall(response))

    if not nums_src or not nums_rsp:
        return {"score": 0.0, "fires": False}

    intersection = nums_src & nums_rsp
    score = len(intersection) / max(len(nums_rsp), 1)
    return {"score": round(min(score, 1.0), 6), "fires": True}


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL 4 — ContentWordOverlap (baseline floor)
# ═══════════════════════════════════════════════════════════════════════════

_STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "can", "could", "shall", "should",
    "may", "might", "must", "need", "dare", "ought", "used",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "out", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "each", "every",
    "both", "little", "much", "many", "some", "any", "no", "none", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "because",
    "as", "until", "while", "about", "across", "after", "along", "among",
    "around", "at", "before", "between", "beyond", "but", "by", "despite",
    "down", "during", "except", "for", "from", "in", "inside", "into",
    "near", "of", "off", "on", "out", "outside", "over", "past", "since",
    "through", "throughout", "to", "toward", "under", "underneath", "until",
    "up", "upon", "with", "within", "without",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "would", "should", "could", "might", "must",
    "the", "a", "an", "and", "or", "but", "if", "because", "as", "until",
    "while", "of", "at", "by", "for", "with", "about", "against",
    "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "in", "out", "on", "off",
    "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "just", "because", "as", "until", "while",
}

_RE_TOKEN = re.compile(r"\b[a-záéíóúñ]+\b", re.IGNORECASE)


def ContentWordOverlap(source: str, response: str) -> Dict:
    """Signal 4 — ContentWordOverlap: Jaccard on content words only.

    Tokenises both texts, lowercases, removes stopwords, and computes:
        score = |intersection| / |union|

    Always fires (baseline floor).  When the two texts share few content
    words, this signal returns a low score, which is the honest answer.
    """
    tokens_src: Set[str] = set(
        m.group(0).lower() for m in _RE_TOKEN.finditer(source)
        if m.group(0).lower() not in _STOPWORDS
    )
    tokens_rsp: Set[str] = set(
        m.group(0).lower() for m in _RE_TOKEN.finditer(response)
        if m.group(0).lower() not in _STOPWORDS
    )

    if not tokens_src or not tokens_rsp:
        return {"score": 0.0, "fires": True}

    intersection = tokens_src & tokens_rsp
    union = tokens_src | tokens_rsp
    score = len(intersection) / max(len(union), 1)
    return {"score": round(min(score, 1.0), 6), "fires": True}


# ═══════════════════════════════════════════════════════════════════════════
# Quick self-test when run directly
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  R3.1 Signals — Self-Test")
    print("=" * 60)

    # Test pair: semantically equivalent, lexically different
    src = "The patient was diagnosed with diabetes and hypertension."
    rsp = "Diabetes and hypertension were diagnosed in the patient."

    for name, fn in [
        ("EntityCore", EntityCore),
        ("NegationMatch", NegationMatch),
        ("QuantMatch", QuantMatch),
        ("ContentWordOverlap", ContentWordOverlap),
    ]:
        result = fn(src, rsp)
        print(f"  {name:20s}  score={result['score']:.4f}  fires={result['fires']}")

    # Test pair: different content
    src2 = "The patient has cancer."
    rsp2 = "The patient has diabetes."

    print()
    for name, fn in [
        ("EntityCore", EntityCore),
        ("NegationMatch", NegationMatch),
        ("QuantMatch", QuantMatch),
        ("ContentWordOverlap", ContentWordOverlap),
    ]:
        result = fn(src2, rsp2)
        print(f"  {name:20s}  score={result['score']:.4f}  fires={result['fires']}")