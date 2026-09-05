"""
core/negation_probe.py — Negation & Quantifier Probe v1.3
═══════════════════════════════════════════════════════════════════════════════
Detects logical inversions and quantifier changes in binary assertions.

Target domain: rationalization_binary (recall 10.7% → target >60%)

Methodology:
  1. Extract binary assertion pairs from text A and text B using regex.
  2. Align sentences semantically via cosine similarity on BoW vectors,
     avoiding the fragile index-based alignment of v1.0.
  3. Compare polarity (affirmation vs negation) on aligned pairs.
  4. Compare quantifiers (all, none, some, every, etc.).
  5. Weight inversions by type (negation=1.0, quantifier=0.6) and
     apply a proportional penalty to ISI.

CHANGELOG v1.3 (2026-09-03) — comparación directa de marcadores de negación
--------------------------------------------------------------------------
[BUG][piloto R5 Subset A — confirmado por baseline con datos reales]
    detect_inversions() usaba _is_affirmative() para determinar la polaridad
    de cada oración. _is_affirmative() dependía de una whitelist cerrada de
    verbos (_AFFIRM_STRONG). Cuando el verbo del source NO estaba en la
    whitelist pero el verbo de la respuesta SÍ (o viceversa), se generaba
    una falsa inversión de polaridad, aunque no hubiera ninguna negación
    real. Esto causó 6 falsos positivos en el intento v1.2 (REVERTIDO).

    La causa real NO era alineación de oraciones (los 6 FP son pares de
    una sola oración, sin ambigüedad de alineación) sino asimetría de
    cobertura de la whitelist de verbos.

    Cambio: reemplazar _is_affirmative() por _tiene_negacion() en la
    detección de inversión de polaridad. _tiene_negacion() solo pregunta
    "¿hay marcador de negación en el texto?" mediante _NEGATION, sin
    depender de ningún verbo. La comparación de cuantificadores NO se tocó.

    _is_affirmative() y _AFFIRM_STRONG se mantienen en el archivo (sin
    uso en detect_inversions()) por si se necesitan para otra cosa.

    Antes/después (10 pares piloto Subset A): recall 4/10 → 10/10
    (remedido con el script 63 el 2026-09-04 — la única pieza que
    quedaba sin remedir tras el rediseño; ver reports/t1_negation_vs_piloto_A.json).
    6 FP históricos (impacto_fp_negation.json): 0/6 deben disparar.
    1,600 pares matriz: reportar todos los cambios (ver script 36).

Known limitations:
  - BoW alignment is approximate; paraphrased sentences may not align.
  - _tiene_negacion() is regex-based and may miss complex grammatical
    negations (e.g., "It is not the case that X holds").
  - Does not resolve negation scope across clause boundaries.
  - Negation markers are language-specific; the current set covers
    English and Spanish patterns. Other languages may need extension.

Registry: EX-2026-18792778
Author: Gonzalo Emir Durante — Project Manifold 0.56
License: Durante Invariance License v1.0
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

# ── Constants ──────────────────────────────────────────────────────────────────
KAPPA_D: float = 0.56

# Penalty multiplier per weighted inversion unit (compound exponential)
NEGATION_PENALTY_BASE: float = 0.45
MAX_PENALTY_FLOOR: float = 0.40  # ISI will never be pushed below this factor

# Inversion type weights
INVERSION_WEIGHTS: Dict[str, float] = {
    "negation":   1.0,   # "shall" → "shall not" — high confidence
    "quantifier": 0.6,   # "all" → "some" — medium confidence
}


# ── Pattern sets ───────────────────────────────────────────────────────────────

# Strong modal / auxiliary affirmations (deliberately excluding weak modals
# "may", "can", "could", "might" to reduce false positives)
#
# v1.2 (2026-09-02): INTENTO de ampliación con verbos de reporte/acción en
# español — REVERTIDO. El fix subió recall (4/10 → 10/10) pero generó 6
# falsos positivos NUEVOS que CAMBIAN el veredicto final del tribunal en
# pares de paráfrasis válida (zona A→B). Los verbos agregados (consumió,
# revisó, abrió, desactivó) aparecen en el source de pares que NO son
# negaciones, y al marcar el source como "afirmativo", cualquier negación
# en la respuesta dispara. Ver reports/comparacion_1600_negation.json y
# reports/impacto_fp_negation.json. Rediseño pendiente: alineación por
# oración + verificación de que la negación esté en la MISMA oración
# alineada, no en cualquier parte del texto.
_AFFIRM_STRONG = re.compile(
    r"\b(shall|will|must|is|are|was|were|has|have|had|does|do|did"
    r"|accepts|agrees|confirms|acknowledges|approves"
    r"|provides|grants|assigns|transfers|licenses"
    r"|holds|owns|possesses|retains"
    r"|redujo|aumentó|confirma|establece|demuestra|indica|prueba|verifica"
    r"|redujo|mejoró|empeoró|incrementó|disminuyó|publicó|reportó"
    r"|es|son|fue|fueron|ha|han|había|tiene|tienen|tenía)\b",
    re.IGNORECASE,
)

# Negation markers — order matters: longer phrases first
_NEGATION = re.compile(
    r"\b(shall not|will not|must not|cannot|is not|are not|was not|were not"
    r"|has not|have not|had not|does not|do not|did not"
    r"|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't"
    r"|declines|refuses|rejects|denies|disputes"
    r"|never|none|neither|nor"
    r"|no|nunca|jamás|ningún|ninguna|tampoco|ni)\b",
    re.IGNORECASE,
)

# Quantifier families
_Q_UNIVERSAL = re.compile(
    r"\b(all|every|each|any|both|entire|whole|always|invariably)\b",
    re.IGNORECASE,
)
_Q_EXISTENTIAL = re.compile(
    r"\b(some|several|few|many|most|often|sometimes|usually|generally)\b",
    re.IGNORECASE,
)
_Q_NEGATIVE = re.compile(
    r"\b(no|none|neither|nor|never|not any|not a single|nowhere)\b",
    re.IGNORECASE,
)


# ── Sentence extraction ─────────────────────────────────────────────────────────

def _split_sentences(text: str) -> List[str]:
    """Split text into non-trivial sentences (≥ 5 words)."""
    raw = re.split(r"(?<=[.!?;])\s+", text.strip())
    return [s.strip() for s in raw if len(s.split()) >= 5]


def _quantifier_class(sentence: str) -> str:
    """Return the dominant quantifier class of a sentence."""
    sl = sentence.lower()
    # Negative quantifiers take precedence
    if _Q_NEGATIVE.search(sl):
        return "negative"
    if _Q_UNIVERSAL.search(sl):
        return "universal"
    if _Q_EXISTENTIAL.search(sl):
        return "existential"
    return "neutral"


def _tiene_negacion(sentence: str) -> bool:
    """Return True if the sentence contains a negation marker.

    v1.3: reemplaza _is_affirmative() para la detección de inversión de
    polaridad. _is_affirmative() dependía de una whitelist cerrada de
    verbos (_AFFIRM_STRONG), lo que causaba falsos positivos cuando el
    verbo del source no estaba en la whitelist pero el de la respuesta
    sí (o viceversa). La comparación directa de marcadores de negación
    evita este problema por completo: solo pregunta "¿hay negación en A?"
    vs "¿hay negación en B?", sin depender de qué verbo se usó.
    """
    return bool(_NEGATION.search(sentence.lower()))


def _is_affirmative(sentence: str) -> bool:
    """Legacy function — kept for reference, NOT used in detect_inversions()."""
    sl = sentence.lower()
    return bool(_AFFIRM_STRONG.search(sl)) and not bool(_NEGATION.search(sl))


# ── BoW vectoriser (no external deps) ─────────────────────────────────────────

def _bow_vector(sentence: str, vocab: Dict[str, int]) -> List[float]:
    """Compute a normalised BoW vector over a fixed vocabulary."""
    tokens = re.findall(r"\b\w+\b", sentence.lower())
    vec = [0.0] * len(vocab)
    for t in tokens:
        if t in vocab:
            vec[vocab[t]] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(v1: List[float], v2: List[float]) -> float:
    """Cosine similarity between two vectors."""
    return sum(a * b for a, b in zip(v1, v2))


def _build_vocab(sentences: List[str]) -> Dict[str, int]:
    """Build a vocabulary index from a list of sentences."""
    vocab: Dict[str, int] = {}
    for s in sentences:
        for t in re.findall(r"\b\w+\b", s.lower()):
            if t not in vocab:
                vocab[t] = len(vocab)
    return vocab


def _align_sentences(
    sents_a: List[str],
    sents_b: List[str],
) -> List[Tuple[str, str]]:
    """
    Align sentences from A and B using greedy cosine-similarity matching.

    Each sentence in A is matched to its nearest unmatched sentence in B.
    This avoids the fragile index-based alignment of v1.0, which broke
    whenever B had an extra or missing sentence.

    Returns a list of (sentence_a, sentence_b) aligned pairs.
    """
    if not sents_a or not sents_b:
        return []

    combined = sents_a + sents_b
    vocab = _build_vocab(combined)

    vecs_a = [_bow_vector(s, vocab) for s in sents_a]
    vecs_b = [_bow_vector(s, vocab) for s in sents_b]

    used_b: set[int] = set()
    pairs: List[Tuple[str, str]] = []

    for i, va in enumerate(vecs_a):
        best_j, best_sim = -1, -1.0
        for j, vb in enumerate(vecs_b):
            if j in used_b:
                continue
            sim = _cosine(va, vb)
            if sim > best_sim:
                best_sim = sim
                best_j = j
        if best_j >= 0 and best_sim > 0.10:  # minimum similarity threshold
            pairs.append((sents_a[i], sents_b[best_j]))
            used_b.add(best_j)

    return pairs


# ── Inversion detection ─────────────────────────────────────────────────────────

@dataclass
class InversionDetail:
    """Single inversion event."""
    sentence_a: str
    sentence_b: str
    inversion_type: str   # "negation" | "quantifier"
    weight: float
    description: str


@dataclass
class NegationResult:
    """Aggregated result of the Negation & Quantifier Probe."""
    polarity_inverted: bool
    quantifier_changed: bool
    inversion_count: int
    weighted_inversion_score: float  # sum of weights
    penalty: float                   # ISI multiplier ∈ (0, 1]
    details: List[InversionDetail] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "polarity_inverted":        self.polarity_inverted,
            "quantifier_changed":       self.quantifier_changed,
            "inversion_count":          self.inversion_count,
            "weighted_inversion_score": round(self.weighted_inversion_score, 4),
            "penalty":                  round(self.penalty, 6),
            "details": [
                {
                    "type":        d.inversion_type,
                    "weight":      d.weight,
                    "description": d.description,
                }
                for d in self.details
            ],
        }


def detect_inversions(text_a: str, text_b: str) -> NegationResult:
    """
    Detect logical inversions between text_a (reference) and text_b (suspect).

    Returns a NegationResult with a penalty factor to apply to ISI.
    penalty = 1.0 means no change; values < 1.0 reduce ISI proportionally.
    """
    sents_a = _split_sentences(text_a)
    sents_b = _split_sentences(text_b)

    if not sents_a or not sents_b:
        return NegationResult(
            polarity_inverted=False,
            quantifier_changed=False,
            inversion_count=0,
            weighted_inversion_score=0.0,
            penalty=1.0,
        )

    aligned = _align_sentences(sents_a, sents_b)
    if not aligned:
        return NegationResult(
            polarity_inverted=False,
            quantifier_changed=False,
            inversion_count=0,
            weighted_inversion_score=0.0,
            penalty=1.0,
        )

    inversions: List[InversionDetail] = []

    for sa, sb in aligned:
        pol_a = _tiene_negacion(sa)
        pol_b = _tiene_negacion(sb)
        q_a   = _quantifier_class(sa)
        q_b   = _quantifier_class(sb)

        # Polarity inversion (strong signal)
        if pol_a != pol_b:
            inversions.append(InversionDetail(
                sentence_a=sa[:100],
                sentence_b=sb[:100],
                inversion_type="negation",
                weight=INVERSION_WEIGHTS["negation"],
                description=(
                    f"Polarity: {'affirm' if not pol_a else 'negate'}"
                    f" → {'affirm' if not pol_b else 'negate'}"
                ),
            ))

        # Quantifier change (weaker signal — non-neutral only)
        if q_a != q_b and q_a != "neutral" and q_b != "neutral":
            inversions.append(InversionDetail(
                sentence_a=sa[:100],
                sentence_b=sb[:100],
                inversion_type="quantifier",
                weight=INVERSION_WEIGHTS["quantifier"],
                description=f"Quantifier: {q_a} → {q_b}",
            ))

    total_weight = sum(inv.weight for inv in inversions)

    if total_weight == 0.0:
        penalty = 1.0
    else:
        # Exponential penalty proportional to total weighted inversions
        raw_penalty = NEGATION_PENALTY_BASE ** total_weight
        penalty = max(MAX_PENALTY_FLOOR, raw_penalty)

    return NegationResult(
        polarity_inverted=any(i.inversion_type == "negation" for i in inversions),
        quantifier_changed=any(i.inversion_type == "quantifier" for i in inversions),
        inversion_count=len(inversions),
        weighted_inversion_score=round(total_weight, 4),
        penalty=round(penalty, 6),
        details=inversions,
    )


def integrate_negation_penalty(
    isi_current: float,
    neg_result: NegationResult,
) -> float:
    """Apply the negation penalty to the current ISI value."""
    if neg_result.penalty >= 1.0:
        return isi_current
    return round(max(0.0, isi_current * neg_result.penalty), 6)
