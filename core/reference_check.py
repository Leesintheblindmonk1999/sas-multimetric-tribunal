"""
core/reference_check.py — Reference Entity Cross-Check v1.1
═══════════════════════════════════════════════════════════════════════════════
Detects fabricated or modified citations in text B relative to text A.

Target domain: references (recall 68.1% → target >85%)

Methodology:
  1. Extract citation patterns from both texts: Author (Year), et al., etc.
  2. Build a citation map for text A (the reference/clean document).
  3. For each citation in text B, check whether:
       a. The same author appears with a DIFFERENT year  → fabrication signal
       b. The same year appears with a DIFFERENT author  → fabrication signal
       c. The year is anachronistic (< 1800 or > 2030)  → anachronism signal
  4. Citations that appear only in B (no overlap with A at all) are NOT
     penalised — they may be legitimate additions to the narrative.
  5. Apply a graduated penalty for confirmed fabrications.

Correction from v1.0:
  - v1.0 penalised ALL citations in B not in A — causing high false positives
    when A and B cover different aspects of a topic.
  - v1.1 only penalises citations that are MODIFICATIONS of existing A citations
    (same key field changed), which is the true hallucination signal.
  - Author name validation now uses Unicode character classes to support
    Asian, Arabic, and hyphenated names.

Known limitations:
  - Citation extraction relies on regex patterns and may miss uncommon formats
    (e.g., footnote-style, numbered references, or non-Latin scripts in titles).
  - No external knowledge base is queried; verification is structural only.

Registry: EX-2026-18792778
Author: Gonzalo Emir Durante — Project Manifold 0.56
License: Durante Invariance License v1.0
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set

# ── Constants ──────────────────────────────────────────────────────────────────
KAPPA_D: float = 0.56

REFERENCE_PENALTY_BASE: float = 0.75  # per confirmed fabrication
MAX_PENALTY_FLOOR: float = 0.50       # ISI floor from this module alone

MIN_YEAR: int = 1800
MAX_YEAR: int = 2030   # allows preprints slightly ahead of current year


# ── Citation extraction ─────────────────────────────────────────────────────────

# Ordered from most specific to least specific to avoid partial overlaps
_CITATION_PATTERNS: List[re.Pattern] = [
    # "Author et al. (Year)" — e.g. Smith et al. (2023)
    re.compile(
        r'([\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF][\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF\s\-\.]+?)'
        r'\s+et\s+al\.\s*\((\d{4}[a-z]?)\)',
        re.UNICODE,
    ),
    # "(Author et al., Year)"
    re.compile(
        r'\('
        r'([\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF][\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF\s\-\.]+?)'
        r'\s+et\s+al\.,?\s*(\d{4}[a-z]?)'
        r'\)',
        re.UNICODE,
    ),
    # "(Author, Year)"
    re.compile(
        r'\('
        r'([\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF][\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF\s\-\.]+?)'
        r',\s*(\d{4}[a-z]?)'
        r'\)',
        re.UNICODE,
    ),
    # "Author (Year)"
    re.compile(
        r'([\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF][\w\u00C0-\u024F\u4E00-\u9FFF\u0600-\u06FF\s\-\.]{2,40}?)'
        r'\s+\((\d{4}[a-z]?)\)',
        re.UNICODE,
    ),
]


def _normalise_author(author: str) -> str:
    """
    Normalise an author name for comparison:
    strip excess whitespace, lowercase, remove trailing punctuation.
    """
    author = author.strip().lower()
    author = re.sub(r'[\.,;]+$', '', author)
    author = re.sub(r'\s+', ' ', author)
    return author


def _is_plausible_year(year_str: str) -> bool:
    """
    Return True if the year (possibly with suffix like '2023a') is plausible.
    Strips letter suffix before checking range.
    """
    try:
        year_int = int(re.match(r'\d{4}', year_str).group())
        return MIN_YEAR <= year_int <= MAX_YEAR
    except (AttributeError, ValueError):
        return False


def _is_plausible_author(author: str) -> bool:
    """
    Return True if the author string looks like a plausible person or
    organisation name.

    Accepts:
      - Latin (including accented), CJK, Arabic characters
      - Hyphens, dots, and spaces
      - Minimum 2 characters after stripping

    Rejects:
      - Pure numeric strings
      - Strings that are clearly not names (e.g. "Figure 3")
    """
    stripped = author.strip()
    if len(stripped) < 2:
        return False
    if stripped.isdigit():
        return False
    # At least one Unicode letter
    return any(unicodedata.category(c).startswith('L') for c in stripped)


def extract_citations(text: str) -> List[Tuple[str, str, str]]:
    """
    Extract citations from text.

    Returns a list of (normalised_author, year_str, full_match_string).
    Deduplicates by (author, year).
    """
    seen: Set[Tuple[str, str]] = set()
    citations: List[Tuple[str, str, str]] = []

    for pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(text):
            author_raw = match.group(1)
            year_str   = match.group(2)
            full       = match.group(0)

            author_norm = _normalise_author(author_raw)

            if not _is_plausible_author(author_norm):
                continue

            key = (author_norm, year_str)
            if key in seen:
                continue
            seen.add(key)

            citations.append((author_norm, year_str, full))

    return citations


# ── Fabrication detection ───────────────────────────────────────────────────────

@dataclass
class FabricationEvent:
    """A single fabrication or anachronism event."""
    event_type: str       # "same_author_diff_year" | "same_year_diff_author" | "anachronistic"
    citation_a: str       # matched citation in A (or empty for anachronisms)
    citation_b: str       # citation in B that triggered the event
    description: str


@dataclass
class ReferenceResult:
    """Aggregated result of the Reference Cross-Check."""
    fabricated_count: int
    anachronistic_count: int
    penalty: float
    events: List[FabricationEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fabricated_count":    self.fabricated_count,
            "anachronistic_count": self.anachronistic_count,
            "penalty":             round(self.penalty, 6),
            "events": [
                {
                    "type":        e.event_type,
                    "citation_a":  e.citation_a,
                    "citation_b":  e.citation_b,
                    "description": e.description,
                }
                for e in self.events[:10]  # cap output size
            ],
        }


def detect_fabrications(text_a: str, text_b: str) -> ReferenceResult:
    """
    Compare citations in text_b against those in text_a (the reference).

    Only flags citations in B that are MODIFICATIONS of citations already
    present in A (same author → different year, or same year → different
    author). Pure additions to B are not penalised.

    Also flags anachronistic years regardless of A.
    """
    citations_a = extract_citations(text_a)
    citations_b = extract_citations(text_b)

    if not citations_b:
        return ReferenceResult(
            fabricated_count=0,
            anachronistic_count=0,
            penalty=1.0,
        )

    # Build lookup structures for A
    # author_norm → set of years seen in A
    a_by_author: Dict[str, Set[str]] = {}
    # year → set of authors seen in A
    a_by_year: Dict[str, Set[str]] = {}

    for auth, year, _ in citations_a:
        a_by_author.setdefault(auth, set()).add(year)
        a_by_year.setdefault(year, set()).add(auth)

    events: List[FabricationEvent] = []

    for auth_b, year_b, full_b in citations_b:
        # ── Anachronistic year ────────────────────────────────
        if not _is_plausible_year(year_b):
            events.append(FabricationEvent(
                event_type="anachronistic",
                citation_a="",
                citation_b=full_b,
                description=f"Year '{year_b}' outside plausible range {MIN_YEAR}–{MAX_YEAR}",
            ))

        # ── Same author, different year ───────────────────────
        # Signal: author appears in A but with a different year
        if auth_b in a_by_author and year_b not in a_by_author[auth_b]:
            years_in_a = sorted(a_by_author[auth_b])
            events.append(FabricationEvent(
                event_type="same_author_diff_year",
                citation_a=f"{auth_b} ({', '.join(years_in_a)})",
                citation_b=full_b,
                description=(
                    f"Author '{auth_b}' appears in A with year(s) "
                    f"{years_in_a} but in B with year '{year_b}'"
                ),
            ))

        # ── Same year, different author ───────────────────────
        # Signal: year appears in A but with different author(s)
        if year_b in a_by_year and auth_b not in a_by_year[year_b]:
            authors_in_a = sorted(a_by_year[year_b])
            events.append(FabricationEvent(
                event_type="same_year_diff_author",
                citation_a=f"({', '.join(authors_in_a)}, {year_b})",
                citation_b=full_b,
                description=(
                    f"Year '{year_b}' appears in A with author(s) "
                    f"{authors_in_a} but in B attributed to '{auth_b}'"
                ),
            ))

    fabricated  = [e for e in events if e.event_type != "anachronistic"]
    anachronistic = [e for e in events if e.event_type == "anachronistic"]

    n_fab = len(fabricated)
    if n_fab == 0:
        penalty = 1.0
    else:
        raw_penalty = REFERENCE_PENALTY_BASE ** min(n_fab, 4)
        penalty = max(MAX_PENALTY_FLOOR, raw_penalty)

    return ReferenceResult(
        fabricated_count=n_fab,
        anachronistic_count=len(anachronistic),
        penalty=round(penalty, 6),
        events=events,
    )


def integrate_reference_penalty(
    isi_current: float,
    ref_result: ReferenceResult,
) -> float:
    """Apply the reference penalty to the current ISI value."""
    if ref_result.penalty >= 1.0:
        return isi_current
    return round(max(0.0, isi_current * ref_result.penalty), 6)
