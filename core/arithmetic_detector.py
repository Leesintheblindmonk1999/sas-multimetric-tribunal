"""
core/arithmetic_detector.py — Arithmetic Error Detector v1.1
═══════════════════════════════════════════════════════════════════════════════
Validates arithmetic operations mentioned explicitly in natural language text.

Target domain: rationalization_numerical (recall 24.0% → target >80%)

Methodology:
  1. Scan text for arithmetic statements in natural language:
       "X is twice Y", "X plus Y equals Z", "half of X is Y", etc.
  2. Parse the numeric operands from each match.
  3. Verify mathematical correctness using a tolerance of 1e-9 to avoid
     float-precision false negatives (fix from v1.0 which used == on floats).
  4. Division by zero is explicitly guarded — no exception propagates.
  5. Each confirmed error reduces ISI by a graduated penalty.

Correction from v1.0:
  - Float comparison used == → changed to abs(a - b) < _FLOAT_TOL
  - Division-by-zero unguarded → wrapped in try/except with pre-check
  - Lambda validators were inline → moved to named _Validator callables
    for testability and clarity.

Known limitations:
  - Only detects explicitly stated arithmetic (e.g., "twice X is Y").
    Implicit calculations embedded in narrative prose are not captured.
  - Number parsing uses simple regex; does not handle commas in large
    numbers (e.g., "1,000") — stripped before parsing.
  - Percentage calculations use exact equality; rounding differences
    in the source text may cause false positives.

Registry: EX-2026-18792778
Author: Gonzalo Emir Durante — Project Manifold 0.56
License: Durante Invariance License v1.0
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Callable, Optional

# ── Constants ──────────────────────────────────────────────────────────────────
KAPPA_D: float = 0.56

ARITHMETIC_PENALTY_BASE: float = 0.60   # per confirmed error (exponential)
MAX_PENALTY_FLOOR: float = 0.50         # ISI floor from this module alone

_FLOAT_TOL: float = 1e-9   # tolerance for float equality checks


# ── Number parsing ─────────────────────────────────────────────────────────────

_NUM_RE = re.compile(r'(\d[\d,]*(?:\.\d+)?)')


def _parse_num(s: str) -> float:
    """
    Parse a numeric string, removing commas (e.g. "1,000" → 1000.0).
    Raises ValueError if the string is not a valid number.
    """
    return float(s.replace(',', ''))


# ── Arithmetic rule definitions ────────────────────────────────────────────────
# Each rule is (compiled_pattern, validator_function).
# The validator receives the re.Match object and returns True if the
# arithmetic is correct, False if it is an error.

def _safe_eq(a: float, b: float) -> bool:
    """Approximately equal within _FLOAT_TOL."""
    return abs(a - b) < _FLOAT_TOL


def _safe_divide(numerator: float, denominator: float) -> Optional[float]:
    """Return numerator / denominator or None if denominator is zero."""
    if abs(denominator) < _FLOAT_TOL:
        return None
    return numerator / denominator


# ── Validator builders (return True = CORRECT, False = ERROR) ──────────────────

def _v_twice_a_is_b(m: re.Match) -> bool:
    a, b = _parse_num(m.group(1)), _parse_num(m.group(2))
    return _safe_eq(a * 2, b)


def _v_a_is_twice_b(m: re.Match) -> bool:
    a, b = _parse_num(m.group(1)), _parse_num(m.group(2))
    return _safe_eq(a, b * 2)


def _v_a_plus_b_eq_c(m: re.Match) -> bool:
    a, b, c = _parse_num(m.group(1)), _parse_num(m.group(2)), _parse_num(m.group(3))
    return _safe_eq(a + b, c)


def _v_a_minus_b_eq_c(m: re.Match) -> bool:
    a, b, c = _parse_num(m.group(1)), _parse_num(m.group(2)), _parse_num(m.group(3))
    return _safe_eq(a - b, c)


def _v_a_times_b_eq_c(m: re.Match) -> bool:
    a, b, c = _parse_num(m.group(1)), _parse_num(m.group(2)), _parse_num(m.group(3))
    return _safe_eq(a * b, c)


def _v_a_div_b_eq_c(m: re.Match) -> bool:
    a, b, c = _parse_num(m.group(1)), _parse_num(m.group(2)), _parse_num(m.group(3))
    result = _safe_divide(a, b)
    if result is None:
        return True  # Can't verify — don't penalise
    return _safe_eq(result, c)


def _v_half_of_a_is_b(m: re.Match) -> bool:
    a, b = _parse_num(m.group(1)), _parse_num(m.group(2))
    return _safe_eq(a / 2, b)


def _v_pct_of_b_is_c(m: re.Match) -> bool:
    pct, base, result = _parse_num(m.group(1)), _parse_num(m.group(2)), _parse_num(m.group(3))
    expected = _safe_divide(pct * base, 100.0)
    if expected is None:
        return True
    return _safe_eq(expected, result)


def _v_a_cubed_eq_b(m: re.Match) -> bool:
    a, b = _parse_num(m.group(1)), _parse_num(m.group(2))
    return _safe_eq(a ** 3, b)


def _v_a_squared_eq_b(m: re.Match) -> bool:
    a, b = _parse_num(m.group(1)), _parse_num(m.group(2))
    return _safe_eq(a ** 2, b)


# Number token pattern (no commas inside the group — stripped separately)
_N = r'([\d,]+(?:\.\d+)?)'  # numeric token, possibly with commas
_IS = r'(?:is|equals|=|amounts\s+to|comes\s+to)'
_PLUS = r'(?:plus|added\s+to|\+)'
_MINUS = r'(?:minus|subtracted\s+from|\-)'
_TIMES = r'(?:times|multiplied\s+by|×|\*)'
_DIV = r'(?:divided\s+by|over|÷)'

_RULES: List[Tuple[re.Pattern, Callable[[re.Match], bool]]] = [
    # "twice 5 is 10" / "double 5 is 10"
    (re.compile(rf'(?:twice|double)\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_twice_a_is_b),
    # "5 is twice 2.5"
    (re.compile(rf'{_N}\s+{_IS}\s+twice\s+{_N}', re.IGNORECASE), _v_a_is_twice_b),
    # "3 plus 4 is 7"
    (re.compile(rf'{_N}\s+{_PLUS}\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_a_plus_b_eq_c),
    # "10 minus 3 is 7"
    (re.compile(rf'{_N}\s+{_MINUS}\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_a_minus_b_eq_c),
    # "3 times 4 is 12"
    (re.compile(rf'{_N}\s+{_TIMES}\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_a_times_b_eq_c),
    # "12 divided by 4 is 3"
    (re.compile(rf'{_N}\s+{_DIV}\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_a_div_b_eq_c),
    # "half of 10 is 5"
    (re.compile(rf'half\s+of\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_half_of_a_is_b),
    # "50% of 200 is 100"
    (re.compile(rf'{_N}%\s+of\s+{_N}\s+{_IS}\s+{_N}', re.IGNORECASE), _v_pct_of_b_is_c),
    # "2 cubed is 8" / "2 to the power of 3 is 8" (simplified)
    (re.compile(rf'{_N}\s+cubed\s+{_IS}\s+{_N}', re.IGNORECASE), _v_a_cubed_eq_b),
    # "3 squared is 9"
    (re.compile(rf'{_N}\s+squared\s+{_IS}\s+{_N}', re.IGNORECASE), _v_a_squared_eq_b),
]


# ── Result dataclass ────────────────────────────────────────────────────────────

@dataclass
class ArithmeticError:
    """A single arithmetic error detected in the text."""
    matched_text: str
    description: str


@dataclass
class ArithmeticResult:
    """Aggregated result of arithmetic validation."""
    error_count: int
    penalty: float
    errors: List[ArithmeticError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "error_count": self.error_count,
            "penalty":     round(self.penalty, 6),
            "errors": [
                {"text": e.matched_text, "description": e.description}
                for e in self.errors[:10]
            ],
        }


# ── Main detector ───────────────────────────────────────────────────────────────

def detect_arithmetic_errors(text: str) -> ArithmeticResult:
    """
    Scan text for arithmetic statements and verify their correctness.

    Each matched statement is evaluated by its corresponding validator.
    Statements that cannot be parsed (e.g., overflow, non-numeric tokens)
    are silently skipped — errors never propagate to the caller.

    Returns an ArithmeticResult with a penalty factor.
    penalty = 1.0 means no errors detected.
    """
    errors: List[ArithmeticError] = []
    seen_spans: set = set()   # avoid double-counting overlapping matches

    for pattern, validator in _RULES:
        for match in pattern.finditer(text):
            span = (match.start(), match.end())
            if span in seen_spans:
                continue

            try:
                is_correct = validator(match)
            except (ValueError, OverflowError, ZeroDivisionError):
                # Parsing failed — skip gracefully
                continue

            if not is_correct:
                seen_spans.add(span)
                errors.append(ArithmeticError(
                    matched_text=match.group(0).strip(),
                    description=f"Arithmetic error: '{match.group(0).strip()}'",
                ))

    n = len(errors)
    if n == 0:
        penalty = 1.0
    else:
        raw_penalty = ARITHMETIC_PENALTY_BASE ** min(n, 4)
        penalty = max(MAX_PENALTY_FLOOR, raw_penalty)

    return ArithmeticResult(
        error_count=n,
        penalty=round(penalty, 6),
        errors=errors,
    )


def integrate_arithmetic_penalty(
    isi_current: float,
    arith_result: ArithmeticResult,
) -> float:
    """Apply the arithmetic penalty to the current ISI value."""
    if arith_result.penalty >= 1.0:
        return isi_current
    return round(max(0.0, isi_current * arith_result.penalty), 6)
