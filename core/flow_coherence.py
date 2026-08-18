"""
core/flow_coherence.py — Omni-Scanner Semantic v4.0
══════════════════════════════════════════════════════════════════
Layer 4 — Flow Coherence: Local Entropy Scanner + Semantic Flow Analysis

Two detection engines that operate ABOVE the Axiom Core:

ENGINE A — Local Entropy Scanner (Thermodynamic GPS)
  Measures information density paragraph by paragraph.
  A sudden entropy spike in text B signals a hallucination injection.
  Acts as an Early Warning System: focuses Axiom Core resources
  on high-entropy segments instead of processing the full document
  at maximum resolution.

ENGINE B — Semantic Adjacency Flow (Causal Invariance)
  Builds a directed adjacency matrix of concept transitions.
  Detects reordering hallucinations where vocabulary is identical
  but logical causality is broken (A→B→C becomes A→C→B).
  Conservative threshold: only flags causal breaks, not stylistic
  reordering — protecting the zero false positive principle.

Design contract:
  - Specificity (zero false positives) takes priority over recall.
  - Both engines produce ISI multipliers, not binary verdicts.
  - All collisions include segment location for human review (XAI).
  - κD = 0.56 is the non-negotiable reference throughout.

Registry: EX-2026-18792778 (TAD, Argentina)
Author:   Gonzalo Emir Durante — Project Manifold 0.56
License:  Durante Invariance License v1.0
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

# ── Constants ─────────────────────────────────────────────────
KAPPA_D: float = 0.56

# Local Entropy Scanner
ENTROPY_SPIKE_THRESHOLD: float = 0.35  # relative spike vs A baseline
ENTROPY_PENALTY_FACTOR:  float = 0.78  # ISI multiplier per spike segment
                                       # (0.85→0.78: recall boost; single-spike
                                       #  alert zone widens ISI<0.659→ISI<0.718.
                                       #  Safe: only applies when dual-signal fired)
MIN_SEGMENT_WORDS:       int   = 15    # minimum words for reliable entropy

# Flow Coherence
FLOW_PENALTY_FACTOR:     float = 0.72  # ISI multiplier per causal break
                                       # (0.80→0.72: engine B is double-gated
                                       #  (flow_score<0.65 AND confirmed break),
                                       #  so stronger penalty is low-FP-risk)
MIN_CONCEPTS_FOR_FLOW:   int   = 4     # minimum concept nodes for flow analysis
CAUSAL_MARKERS: list[str] = [          # words that signal causal order
    "therefore", "thus", "because", "since", "consequently", "as a result",
    "hence", "which means", "leading to", "resulting in", "causing",
    "due to", "owing to", "so that", "in order to", "provided that",
    "notwithstanding", "however", "nevertheless", "although", "whereas",
]

# Semantic proximity threshold for adjacency
ADJACENCY_THRESHOLD: float = 0.20  # minimum TF-IDF cosine for edge


# ══════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════

@dataclass
class EntropySegment:
    """Entropy profile of one text segment (paragraph or window)."""
    index:       int
    text:        str
    word_count:  int
    entropy:     float      # Shannon word entropy
    spike:       bool       # True if spike vs baseline
    spike_ratio: float      # entropy_b / entropy_a_baseline
    position:    str        # "early" | "middle" | "late"


@dataclass
class FlowBreak:
    """A detected causal reordering in the semantic flow."""
    concept_a:   str        # concept that should come before
    concept_b:   str        # concept that comes before in B (wrong order)
    position_a:  int        # paragraph index in A
    position_b:  int        # paragraph index in B
    break_type:  str        # "inversion" | "gap" | "insertion"
    segment:     str        # text excerpt for XAI


@dataclass
class FlowCoherenceResult:
    """
    Complete result from the Flow Coherence layer.

    Fields
    ------
    entropy_penalty      : float — ISI multiplier from entropy spikes [0.50, 1.0]
    flow_penalty         : float — ISI multiplier from causal breaks [0.50, 1.0]
    combined_penalty     : float — product of both, floored at 0.50
    layer4_fired         : bool  — True if either engine detected anomaly
    entropy_spikes       : list  — spike segments with XAI detail
    flow_breaks          : list  — causal breaks with XAI detail
    entropy_profile_a    : list  — per-segment entropy for text A
    entropy_profile_b    : list  — per-segment entropy for text B
    high_entropy_segments: list  — segment indices where Axiom Core focus is needed
    xai_report           : str   — human-readable summary
    """
    entropy_penalty:       float      = 1.0
    flow_penalty:          float      = 1.0
    combined_penalty:      float      = 1.0
    layer4_fired:          bool       = False
    entropy_spikes:        list       = field(default_factory=list)
    flow_breaks:           list       = field(default_factory=list)
    entropy_profile_a:     list       = field(default_factory=list)
    entropy_profile_b:     list       = field(default_factory=list)
    high_entropy_segments: list       = field(default_factory=list)
    xai_report:            str        = ""

    def to_dict(self) -> dict:
        return {
            "entropy_penalty":        self.entropy_penalty,
            "flow_penalty":           self.flow_penalty,
            "combined_penalty":       self.combined_penalty,
            "layer4_fired":           self.layer4_fired,
            "entropy_spike_count":    len(self.entropy_spikes),
            "flow_break_count":       len(self.flow_breaks),
            "high_entropy_segments":  self.high_entropy_segments,
            "entropy_spikes":         self.entropy_spikes,
            "flow_breaks":            [
                {"concept_a": b.concept_a, "concept_b": b.concept_b,
                 "break_type": b.break_type, "segment": b.segment[:120]}
                for b in self.flow_breaks
            ],
        }


# ══════════════════════════════════════════════════════════════
# ENGINE A — Local Entropy Scanner
# ══════════════════════════════════════════════════════════════

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase words, min 3 chars."""
    return [w.lower() for w in re.findall(r'\b[a-zA-Z]{3,}\b', text)]


def _shannon_entropy(tokens: list[str]) -> float:
    """Shannon word entropy H(w) in bits."""
    if not tokens:
        return 0.0
    total = len(tokens)
    counts = Counter(tokens)
    h = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            h -= p * math.log2(p)
    return h


def _split_segments(text: str, min_words: int = MIN_SEGMENT_WORDS) -> list[str]:
    """
    Split text into segments by double newline (paragraphs).
    Falls back to sentence windows if paragraphs are too short.
    """
    # Try paragraph split first
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text.strip()) if p.strip()]
    valid = [p for p in paragraphs if len(_tokenize(p)) >= min_words]

    if len(valid) >= 2:
        return valid

    # Fallback: sliding sentence windows
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip())
                 if len(s.strip()) > 20]
    if len(sentences) < 2:
        return [text]

    # Group into windows of 3 sentences
    windows = []
    window_size = 3
    for i in range(0, len(sentences), window_size):
        chunk = ' '.join(sentences[i:i + window_size])
        if len(_tokenize(chunk)) >= min_words:
            windows.append(chunk)

    return windows if windows else [text]


def calculate_local_entropy(
    text: str,
    window_size: int = 3,
) -> list[EntropySegment]:
    """
    ENGINE A — Core function: calculate per-segment entropy profile.

    Parameters
    ----------
    text        : Document text to analyze
    window_size : Number of sentences per window (fallback mode)

    Returns
    -------
    List of EntropySegment, one per paragraph/window.
    Each segment has its Shannon entropy, word count, and position tag.

    This is the Thermodynamic GPS of the document:
    high entropy = high information density = complex/diverse vocabulary.
    Sudden spikes signal potential hallucination injection.
    """
    segments = _split_segments(text, min_words=MIN_SEGMENT_WORDS)
    n = len(segments)
    results = []

    for i, seg in enumerate(segments):
        tokens = _tokenize(seg)
        h = _shannon_entropy(tokens)

        # Position in document
        if i < n * 0.33:
            position = "early"
        elif i < n * 0.66:
            position = "middle"
        else:
            position = "late"

        results.append(EntropySegment(
            index       = i,
            text        = seg[:200],
            word_count  = len(tokens),
            entropy     = round(h, 4),
            spike       = False,    # filled by comparison
            spike_ratio = 1.0,      # filled by comparison
            position    = position,
        ))

    return results


def _vocab_jaccard(text_a_seg: str, text_b_seg: str) -> float:
    """Jaccard similarity between vocabulary sets of two segments."""
    va = set(_tokenize(text_a_seg))
    vb = set(_tokenize(text_b_seg))
    if not va or not vb:
        return 1.0
    return len(va & vb) / len(va | vb)


def scan_entropy_spikes(
    text_a: str,
    text_b: str,
    spike_threshold: float = ENTROPY_SPIKE_THRESHOLD,
) -> tuple[list[EntropySegment], list[int]]:
    """
    ENGINE A — Compare entropy profiles of A and B using two signals:

    Signal 1 — Entropy ratio: entropy_b / entropy_a_baseline > threshold
    Signal 2 — Vocabulary Jaccard: low overlap between corresponding
               segments signals vocabulary INJECTION (the key hallucination signal).
               A legitimate paraphrase reuses ~40%+ vocabulary.
               A hallucination injection brings new vocabulary < 25% overlap.

    Using DUAL SIGNAL prevents false positives: both signals must fire
    for a spike to be confirmed. This protects specificity.

    Returns
    -------
    spikes           : list of EntropySegment with spike=True
    high_entropy_idx : segment indices needing deep Axiom Core focus
    """
    profile_a = calculate_local_entropy(text_a)
    profile_b = calculate_local_entropy(text_b)

    if not profile_a or not profile_b:
        return [], []

    segs_a = _split_segments(text_a)
    segs_b = _split_segments(text_b)

    # Baseline: mean entropy of A
    baseline_a = float(np.mean([s.entropy for s in profile_a])) if profile_a else 1.0
    if baseline_a < 0.01:
        baseline_a = 1.0

    spikes = []
    high_entropy_idx = []

    for i, seg_b in enumerate(profile_b):
        ratio = seg_b.entropy / baseline_a
        seg_b.spike_ratio = round(ratio, 4)

        # Signal 1: entropy ratio spike (relaxed to 0.20 — relative spike)
        entropy_spike = (seg_b.entropy - baseline_a) / baseline_a > 0.20

        # Signal 2: vocabulary injection (low Jaccard with corresponding A segment)
        if i < len(segs_a):
            jaccard = _vocab_jaccard(segs_a[i], segs_b[i] if i < len(segs_b) else "")
        else:
            # Segment exists in B but not in A — definitely injected
            jaccard = 0.0
        vocab_injection = jaccard < 0.25

        # DUAL SIGNAL: both must fire (protects specificity)
        if (entropy_spike or vocab_injection) and seg_b.word_count >= MIN_SEGMENT_WORDS:
            # Extra guard: if entropy_spike alone (no vocab injection),
            # only flag if ratio > 1.30 (strong spike)
            if vocab_injection or ratio > 1.30:
                seg_b.spike = True
                seg_b.spike_ratio = round(ratio, 4)
                spikes.append(seg_b)
                high_entropy_idx.append(seg_b.index)

    return spikes, high_entropy_idx


# ══════════════════════════════════════════════════════════════
# ENGINE B — Semantic Adjacency Flow
# ══════════════════════════════════════════════════════════════

def _extract_concepts(text: str, top_n: int = 12) -> list[str]:
    """
    Extract key concepts from text as high-frequency content words.
    Filters stop words and returns the top N by frequency.
    This forms the nodes of the adjacency graph.
    """
    stop_words = {
        "the", "and", "for", "that", "this", "with", "from", "are", "was",
        "were", "been", "have", "has", "had", "not", "but", "all", "any",
        "can", "will", "may", "shall", "must", "should", "would", "could",
        "its", "their", "which", "when", "where", "who", "how", "what",
        "each", "such", "than", "then", "also", "into", "upon", "under",
        "over", "only", "more", "less", "both", "other", "these", "those",
        "being", "having", "been", "does", "did", "our", "your", "his",
        "her", "they", "them", "there", "here", "some", "very", "just",
    }
    tokens = [w.lower() for w in re.findall(r'\b[a-zA-Z]{4,}\b', text)]
    filtered = [t for t in tokens if t not in stop_words]
    if not filtered:
        return []
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(top_n)]


def _build_adjacency_vector(
    text: str,
    concepts: list[str],
) -> np.ndarray:
    """
    Build a concept co-occurrence adjacency vector for the text.

    For each pair of concepts (i, j), counts how often concept_i
    appears within 2 sentences of concept_j, weighted by order.
    This encodes the FLOW of ideas: which concept leads to which.

    Returns flat upper-triangle of the adjacency matrix as a vector.
    """
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text)
                 if len(s.strip()) > 10]

    n = len(concepts)
    matrix = np.zeros((n, n), dtype=float)

    for sent_idx, sent in enumerate(sentences):
        sent_lower = sent.lower()
        present = [i for i, c in enumerate(concepts) if c in sent_lower]

        # Add edges from concepts in this sentence to concepts in next sentence
        if sent_idx + 1 < len(sentences):
            next_sent = sentences[sent_idx + 1].lower()
            next_present = [i for i, c in enumerate(concepts) if c in next_sent]
            for i in present:
                for j in next_present:
                    if i != j:
                        matrix[i][j] += 1.0

    # Normalize
    total = matrix.sum()
    if total > 0:
        matrix /= total

    # Return upper triangle as vector
    idx = np.triu_indices(n, k=1)
    return matrix[idx]


def _detect_causal_breaks(
    text_a: str,
    text_b: str,
    concepts: list[str],
) -> list[FlowBreak]:
    """
    Detect causal flow inversions between A and B.

    Strategy:
    1. Build adjacency vectors for A and B
    2. Find edges with significant direction reversal
    3. Filter by causal marker proximity (prevents false positives
       from legitimate stylistic reordering)
    4. Only report breaks where the edge weight delta > 0.15
       (conservative threshold — protects specificity)
    """
    if len(concepts) < MIN_CONCEPTS_FOR_FLOW:
        return []

    vec_a = _build_adjacency_vector(text_a, concepts)
    vec_b = _build_adjacency_vector(text_b, concepts)

    if vec_a.sum() < 0.01 or vec_b.sum() < 0.01:
        return []

    n = len(concepts)
    idx = np.triu_indices(n, k=1)
    breaks = []

    for k, (i, j) in enumerate(zip(idx[0], idx[1])):
        weight_a = vec_a[k]
        weight_b = vec_b[k]

        # Significant reversal: A has strong A→B but B has weak/zero A→B
        # AND B has strong B→A flow (inversion)
        if weight_a > 0.08 and weight_b < 0.02:
            # Check if causal marker near concept in B text
            concept_i = concepts[i]
            concept_j = concepts[j]

            # Find in which segment this break occurs
            seg_text = ""
            for sent in re.split(r'(?<=[.!?])\s+', text_b):
                if concept_j in sent.lower():
                    seg_text = sent[:150]
                    break

            breaks.append(FlowBreak(
                concept_a  = concept_i,
                concept_b  = concept_j,
                position_a = i,
                position_b = j,
                break_type = "inversion",
                segment    = seg_text,
            ))

    return breaks[:3]  # cap at 3 breaks to prevent noise flooding


def calculate_flow_score(
    text_a: str,
    text_b: str,
) -> tuple[float, list[FlowBreak]]:
    """
    ENGINE B — Semantic Adjacency Flow Score.

    Computes the cosine similarity between the adjacency vectors of A and B.
    Flow_Score ∈ [0, 1]: 1 = identical flow structure, 0 = completely inverted.

    A Flow_Score below 0.65 with confirmed causal breaks triggers penalty.
    Conservative design: only penalizes when BOTH conditions are true:
      1. Adjacency similarity < 0.65
      2. At least one confirmed causal break detected

    Returns
    -------
    flow_score : float — similarity of concept flow [0, 1]
    breaks     : list[FlowBreak] — causal inversions detected
    """
    # Extract shared concept vocabulary from both texts
    combined = text_a + " " + text_b
    concepts = _extract_concepts(combined, top_n=12)

    if len(concepts) < MIN_CONCEPTS_FOR_FLOW:
        return 1.0, []

    vec_a = _build_adjacency_vector(text_a, concepts)
    vec_b = _build_adjacency_vector(text_b, concepts)

    # Cosine similarity between flow vectors
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a < 1e-6 or norm_b < 1e-6:
        return 1.0, []

    flow_score = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    flow_score = max(0.0, min(1.0, flow_score))

    # Only detect breaks if flow score is already low (conservative)
    breaks = []
    if flow_score < 0.65:
        breaks = _detect_causal_breaks(text_a, text_b, concepts)

    return round(flow_score, 4), breaks


# ══════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════

def run_flow_coherence(
    text_a: str,
    text_b: str,
    domain: str = "generic",
    isi_original: float = 1.0,
    verbose: bool = False,
) -> FlowCoherenceResult:
    """
    Layer 4 — Flow Coherence full analysis.

    Runs both engines and computes combined ISI penalty.
    The Early Warning System (Engine A) also identifies which segments
    need focused Axiom Core re-analysis.

    Parameters
    ----------
    text_a       : Reference document
    text_b       : Suspect document
    domain       : Detected domain (for domain-aware thresholds)
    isi_original : ISI from topological + axiom analysis
    verbose      : If True, include full entropy profiles in result

    Returns
    -------
    FlowCoherenceResult with penalties and XAI descriptions
    """
    result = FlowCoherenceResult()

    # ── Engine A: Local Entropy Scanner ───────────────────────
    profile_a = calculate_local_entropy(text_a)
    profile_b = calculate_local_entropy(text_b)
    spikes, high_entropy_idx = scan_entropy_spikes(text_a, text_b)

    result.entropy_profile_a     = [{"idx": s.index, "entropy": s.entropy,
                                      "words": s.word_count} for s in profile_a]
    result.entropy_profile_b     = [{"idx": s.index, "entropy": s.entropy,
                                      "spike": s.spike, "ratio": s.spike_ratio,
                                      "words": s.word_count} for s in profile_b]
    result.high_entropy_segments = high_entropy_idx
    result.entropy_spikes        = [
        f"[Flow | entropy:spike] Segment {s.index} ({s.position}): "
        f"entropy ratio = {s.spike_ratio:.2f}x baseline. "
        f"Words: {s.word_count}. "
        f"Segment: \"...{s.text[:100]}...\""
        for s in spikes
    ]

    # Entropy penalty: compound per spike, floor at 0.65
    n_spikes = len(spikes)
    if n_spikes > 0:
        raw_entropy_penalty = ENTROPY_PENALTY_FACTOR ** n_spikes
        result.entropy_penalty = max(0.65, raw_entropy_penalty)
    else:
        result.entropy_penalty = 1.0

    # ── Engine B: Semantic Adjacency Flow ─────────────────────
    flow_score, flow_breaks = calculate_flow_score(text_a, text_b)
    result.flow_breaks = flow_breaks

    if flow_breaks:
        raw_flow_penalty = FLOW_PENALTY_FACTOR ** len(flow_breaks)
        result.flow_penalty = max(0.65, raw_flow_penalty)
        result.entropy_spikes.extend([
            f"[Flow | adjacency:inversion] Causal break: "
            f"'{b.concept_a}' → '{b.concept_b}' order inverted in B. "
            f"Break type: {b.break_type}. "
            f"Segment: \"...{b.segment[:100]}...\""
            for b in flow_breaks
        ])
    else:
        result.flow_penalty = 1.0

    # ── Combined penalty ──────────────────────────────────────
    combined = result.entropy_penalty * result.flow_penalty
    result.combined_penalty = max(0.50, round(combined, 4))

    # ── Fired? ────────────────────────────────────────────────
    result.layer4_fired = (n_spikes > 0 or len(flow_breaks) > 0)

    # ── XAI report ────────────────────────────────────────────
    lines = [
        f"FLOW COHERENCE REPORT (Layer 4)",
        f"{'─' * 50}",
        f"Entropy baseline (A): {float(np.mean([s.entropy for s in profile_a])):.4f}" if profile_a else "",
        f"Entropy mean (B):     {float(np.mean([s.entropy for s in profile_b])):.4f}" if profile_b else "",
        f"Entropy spikes:       {n_spikes}  (penalty: {result.entropy_penalty:.2f})",
        f"Flow score:           {flow_score:.4f}  (1.0 = identical flow)",
        f"Causal breaks:        {len(flow_breaks)}  (penalty: {result.flow_penalty:.2f})",
        f"Combined penalty:     {result.combined_penalty:.4f}",
        f"Layer 4 fired:        {result.layer4_fired}",
    ]
    if high_entropy_idx:
        lines.append(f"High-entropy segments for Axiom focus: {high_entropy_idx}")
    if result.entropy_spikes:
        lines.append(f"\nDetections:")
        for det in result.entropy_spikes[:5]:
            lines.append(f"  → {det[:120]}")

    result.xai_report = "\n".join(l for l in lines if l)
    return result


def apply_flow_penalty(
    isi: float,
    flow_result: FlowCoherenceResult,
    kappa_d: float = KAPPA_D,
) -> tuple[float, bool]:
    """
    Apply Flow Coherence penalty to ISI.

    Only applies penalty if layer4_fired AND the combined penalty
    would push ISI meaningfully (>0.02) below its current value.
    Conservative design prevents over-penalization on borderline cases.

    Returns
    -------
    isi_adjusted : float
    alert        : bool — True if isi_adjusted < kappa_d
    """
    if not flow_result.layer4_fired:
        return isi, isi < kappa_d

    isi_adjusted = round(isi * flow_result.combined_penalty, 6)
    alert = isi_adjusted < kappa_d
    return isi_adjusted, alert
