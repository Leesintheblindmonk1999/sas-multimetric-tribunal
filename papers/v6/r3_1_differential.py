#!/usr/bin/env python3
"""
r3_1_differential.py — R3.1 Differential Structural Guard (Opción A, v4)
═══════════════════════════════════════════════════════════════════════════════

Núcleo rediseñado tras auditoría. El self-test de v1 mostró que el perfil
estructural NO puede distinguir A_Ap (equivalente) de A_App (no equivalente)
porque el contexto compartido domina todas las métricas de densidad.

v4 (2026-10-13): threshold de grounding recalibrado de 0.50 → 0.95.
  El barrido sobre N1 (1,800 pares × 4 condiciones) mostró que 0.95
  minimiza el error total: A_B regresiones 1,349 → 215 (−1,134),
  A_Ap regresiones se mantienen en 22. El threshold anterior (0.50)
  era demasiado permisivo para respuestas alucinadas con alto
  solapamiento léxico.

Señal principal — GROUNDING CHECK:
  Mide qué fracción de las palabras de contenido de la RESPONSE aparecen
  en el SOURCE. Una respuesta válida (A') solo contiene palabras del source.
  Una alucinación (B) introduce palabras nuevas. Esto NO es Jaccard (que
  penaliza palabras del source ausentes en la response) — es RECALL de
  la response contra el source.

Señal secundaria — COMPRESSION RATIO:
  Una respuesta válida típicamente comprime el source dentro de un rango
  esperado. Una alucinación puede ser desproporcionadamente larga o corta.

Regla de decisión:
  - Si GROUNDING > 0.50 → estructuralmente equivalente (la response no
    introduce contenido nuevo).
  - Si GROUNDING < 0.95 → NO equivalente (la response introduce
    contenido o entidades nuevas).

Uso:
    from r3_1_differential import compute_structural_delta
    result = compute_structural_delta(source_text, response_text)
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════════

GROUNDING_THRESHOLD: float = 0.95
MIN_COMPRESSION: float = 0.01
MAX_COMPRESSION: float = 3.00


# ═══════════════════════════════════════════════════════════════════════════
# PATRONES
# ═══════════════════════════════════════════════════════════════════════════

_RE_TOKEN = re.compile(r"\b\w+\b", re.UNICODE)

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


def _content_words(texto: str) -> Set[str]:
    """Extrae palabras de contenido (no stopwords) de un texto."""
    return {
        m.group(0).lower() for m in _RE_TOKEN.finditer(texto)
        if m.group(0).lower() not in _STOPWORDS
    }


# ═══════════════════════════════════════════════════════════════════════════
# SEÑAL PRINCIPAL — GROUNDING CHECK
# ═══════════════════════════════════════════════════════════════════════════

def compute_grounding(source: str, response: str) -> Dict:
    """Mide qué fracción de la response está "groundeada" en el source.

    NO es Jaccard. Jaccard = |intersection| / |union| penaliza cuando el
    source tiene palabras adicionales (siempre es así porque el source
    incluye contexto). En su lugar, usamos:

        grounding = |response_content_words ∩ source_content_words|
                   / |response_content_words|

    Esto mide: ¿cuánto del contenido NUEVO de la response aparece en el
    source? Una respuesta válida (A') obtiene grounding ≈ 1.0 porque solo
    contiene palabras del source. Una alucinación (B) obtiene grounding
    más bajo porque introduce palabras nuevas.

    Args:
        source: Texto fuente completo (contexto + respuesta correcta).
        response: Texto respuesta a evaluar.

    Returns:
        Dict con grounding_score (0..1) y métricas auxiliares.
    """
    src_words = _content_words(source)
    rsp_words = _content_words(response)

    if not rsp_words:
        return {
            "grounding_score": 0.0,
            "n_response_words": 0,
            "n_grounded_words": 0,
            "n_source_words": len(src_words),
        }

    grounded = rsp_words & src_words
    score = len(grounded) / len(rsp_words)

    return {
        "grounding_score": round(min(score, 1.0), 6),
        "n_response_words": len(rsp_words),
        "n_grounded_words": len(grounded),
        "n_source_words": len(src_words),
    }


# ═══════════════════════════════════════════════════════════════════════════
# SEÑAL SECUNDARIA — COMPRESSION RATIO
# ═══════════════════════════════════════════════════════════════════════════

def compute_compression_ratio(source: str, response: str) -> Dict:
    """Mide el ratio de compresión/expansión de la response respecto al source.

    Una respuesta válida típicamente comprime el source (ratio < 1.0).
    Una alucinación puede expandirse desproporcionadamente.

    Returns:
        Dict con compression_ratio y compression_score (0..1).
    """
    len_src = len(source)
    len_rsp = len(response)

    if len_src == 0:
        return {"compression_ratio": 0.0, "compression_score": 0.0}

    ratio = len_rsp / len_src

    # Score: pico en 0.3 (compresión típica), decae hacia los bordes
    if ratio <= 0.3:
        score = ratio / 0.3
    elif ratio <= 1.0:
        score = 1.0 - (ratio - 0.3) * 0.5
    else:
        score = max(0.0, 1.0 - (ratio - 1.0) * 0.2)

    return {
        "compression_ratio": round(ratio, 6),
        "compression_score": round(min(score, 1.0), 6),
    }


# ═══════════════════════════════════════════════════════════════════════════
# PARCHES PARA RESPUESTAS BREVES (< 5 palabras)
# ═══════════════════════════════════════════════════════════════════════════

# Inversores de polaridad — palabras que invierten el significado
_RE_POLARITY_INVERSION = re.compile(
    r"\b(?:"
    r"no|not|never|none|neither|nor|nobody|nothing|"
    r"without|lack|lacking|absence|absent|"
    r"isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|"
    r"doesn't|don't|didn't|won't|wouldn't|shouldn't|couldn't|can't|cannot|"
    r"denies|denied|refuses|refused|rejects|rejected|"
    r"sin|nunca|jamás|tampoco|ni|ningún|ninguna"
    r")\b",
    re.IGNORECASE,
)

# Números sueltos (incluyendo negativos, decimales, porcentajes)
_RE_BARE_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?%?$")

# Números con símbolo monetario: "$8.6 billion", "20%", "934,243"
_RE_MONEY_NUMBER = re.compile(
    r"^[\$£€]?-?\d+[\.\d,]*\s*(?:million|billion|thousand|%|percent)?$",
    re.IGNORECASE,
)

# Fechas en formato numérico (1944, 2001, etc.)
_RE_YEAR = re.compile(r"^(1[4-9]\d{2}|20[0-2]\d)$")


def _es_inversion_polaridad(source: str, response: str) -> bool:
    """Detecta si la response invierte la polaridad del source.

    Una respuesta corta como "no" o "yes" puede tener grounding=1.0
    pero ser semánticamente opuesta al source. Esta función detecta
    si la response contiene un inversor de polaridad que contradice
    el contexto inmediato del source.

    Returns:
        True si la response invierte la polaridad del source.
    """
    rsp_lower = response.lower().strip()

    # Detectar inversores en la response
    tiene_inversor = bool(_RE_POLARITY_INVERSION.search(rsp_lower))

    if not tiene_inversor:
        return False

    # Buscar en el source si hay una afirmación/negación correspondiente
    # Extraer las últimas 200 caracteres del source (contexto inmediato)
    ctx = source[-200:].lower()

    # Si la response es negativa y el source es afirmativo → inversión
    # Si la response es afirmativa y el source es negativo → inversión
    source_has_neg = bool(_RE_POLARITY_INVERSION.search(ctx))

    # Palabras afirmativas en la response
    es_afirmativo = bool(re.search(r"\b(yes|true|correct|affirm|always|does)\b", rsp_lower))

    if tiene_inversor and not source_has_neg and not es_afirmativo:
        return True  # response negativa, source no negativo → inversión
    if es_afirmativo and source_has_neg:
        return True  # response afirmativa, source negativo → inversión

    return False


# Palabras comunes cortas que NO deben activar la verificación de entidad
_SHORT_WORDS_SAFE: Set[str] = {
    "yes", "no", "true", "false", "none", "all", "some", "any",
    "si", "no", "sí", "n/a", "ok", "okay", "maybe", "never",
    "always", "both", "each", "every", "few", "many", "much",
    "several", "sí", "no sé",
}


def _es_entidad_aislada(response: str) -> bool:
    """Detecta si la response es una entidad aislada (número, año, nombre propio).

    Una respuesta como "1944", "Paris", "American" puede tener grounding=1.0
    pero ser semánticamente incorrecta si no responde a la pregunta.

    Palabras comunes como "yes", "no", "true" NO se consideran entidades
    aisladas.

    Returns:
        True si la response es una entidad aislada.
    """
    rsp_stripped = response.strip()
    rsp_lower = rsp_stripped.lower()

    # Palabras comunes seguras → no es entidad aislada
    if rsp_lower in _SHORT_WORDS_SAFE:
        return False

    # Número suelto (incluye negativos, decimales, porcentajes)
    if _RE_BARE_NUMBER.match(rsp_stripped):
        return True

    # Año
    if _RE_YEAR.match(rsp_stripped):
        return True

    # Palabra única capitalizada (nombre propio)
    if re.match(r"^[A-Z][a-záéíóú]+$", rsp_stripped):
        return True

    # Fecha corta: "October 1960", "25 May", etc.
    if re.match(r"^\d+\s+[A-Z][a-z]+$", rsp_stripped) or \
       re.match(r"^[A-Z][a-z]+\s+\d+$", rsp_stripped):
        return True

    # Número con símbolo monetario
    if _RE_MONEY_NUMBER.match(rsp_stripped):
        return True

    return False


def _handle_short_response(source: str, response: str, grounding_score: float, threshold: float = GROUNDING_THRESHOLD) -> Dict:
    """Evalúa respuestas breves (< 5 palabras) con heurísticas estrictas.

    Las respuestas cortas son estadísticamente inestables bajo grounding
    porque un único token coincidente puede dar grounding=1.0 aunque
    el significado sea opuesto.

    Heurísticas:
      1. Inversión de polaridad: si la response invierte la negación del
         source → NO equivalente.
      2. Entidad aislada: si la response es un número/año/nombre suelto
         y no hay suficiente contexto de verificación → ABSTIENE.
      3. Si pasa ambas verificaciones → equivalente (grounding confiable).

    Args:
        source: Texto fuente.
        response: Texto respuesta (corto).
        grounding_score: Score de grounding precalculado.

    Returns:
        Dict con is_structurally_equivalent (bool o None) y razón.
    """
    # Contar palabras reales (tokens)
    n_words = len(response.split())

    # Solo aplicar a respuestas muy cortas
    if n_words >= 5:
        return {"is_structurally_equivalent": grounding_score >= threshold,
                "reason": "not_short_response"}

    # 1. Verificación de polaridad
    if _es_inversion_polaridad(source, response):
        return {"is_structurally_equivalent": False,
                "reason": "polarity_inversion"}

    # 1b. Respuesta compuesta solo de stopwords (ej: "No", "None" como respuesta válida)
    #     El grounding normal da 0 porque filtra stopwords, pero la palabra
    #     puede ser la respuesta correcta.
    if n_words <= 3 and all(w.lower() in _STOPWORDS for w in response.split()):
        rsp_tokens = set(w.lower() for w in response.split())
        src_tokens = set(m.group(0).lower() for m in _RE_TOKEN.finditer(source))
        if rsp_tokens.issubset(src_tokens):
            return {"is_structurally_equivalent": True,
                    "reason": "stopword_response_grounded"}

    # 2. Verificación de entidad aislada
    # Si grounding es alto pero la response es una entidad aislada,
    # el grounding no es confiable → abstenerse
    if grounding_score >= GROUNDING_THRESHOLD and _es_entidad_aislada(response):
        return {"is_structurally_equivalent": None,
                "reason": "isolated_entity_abstain"}

    # 3. Si pasa ambas verificaciones, grounding es confiable
    return {"is_structurally_equivalent": grounding_score >= threshold,
            "reason": "short_response_grounding_ok"}
# ═══════════════════════════════════════════════════════════════════════════

def compute_structural_delta(
    source: str,
    response: str,
    grounding_threshold: float = GROUNDING_THRESHOLD,
) -> Dict:
    """Computa el delta estructural diferencial entre source y response.

    Estrategia (v2, post-auditoría):
      1. COMPRESSION CHECK — si la response es larga (ratio > 0.5),
         el grounding no es informativo (la response incluye el contexto).
         El guard se ABSTIENE: is_structurally_equivalent = None.
      2. GROUNDING CHECK — señal principal. Mide qué fracción de la
         response está groundeada en el source. Solo aplica cuando la
         response es corta (ratio ≤ 0.5).
      3. Decisión: si grounding > threshold → equivalente.
         Si no → no equivalente.

    Args:
        source: Texto fuente (A, contexto + respuesta correcta).
        response: Texto respuesta a evaluar (A', B, o A'').
        grounding_threshold: Umbral de grounding (default: 0.95).

    Returns:
        Dict con differential_score, is_structurally_equivalent, y señales.
        is_structurally_equivalent = None significa que el guard se
        abstiene (response demasiado larga para grounding informativo).
    """
    # 0. Byte-identical check (fast path)
    if source == response:
        return {
            "differential_score": 1.0,
            "is_structurally_equivalent": True,
            "grounding": {"grounding_score": 1.0, "n_response_words": 0, "n_grounded_words": 0, "n_source_words": 0},
            "compression": {"compression_ratio": 1.0, "compression_score": 1.0},
            "abstain_reason": None,
        }

    # 1. COMPRESSION CHECK
    compression = compute_compression_ratio(source, response)
    cr = compression["compression_ratio"]

    # Si la response es larga (incluye contexto), el guard se abstiene
    if cr > 0.5:
        return {
            "differential_score": 0.0,
            "is_structurally_equivalent": None,  # abstiene
            "grounding": None,
            "compression": compression,
            "abstain_reason": "response_too_long_for_grounding",
        }

    # 2. GROUNDING CHECK (solo para responses cortas)
    grounding = compute_grounding(source, response)
    gs = grounding["grounding_score"]

    # 3. Short-response handler (< 5 palabras)
    n_words = len(response.split())
    if n_words < 5:
        # Umbral más estricto para respuestas cortas
        short_threshold = max(GROUNDING_THRESHOLD, 0.75) if n_words <= 2 else GROUNDING_THRESHOLD
        short_result = _handle_short_response(source, response, gs, threshold=short_threshold)
        equiv = short_result["is_structurally_equivalent"]
        reason = short_result["reason"]

        if equiv is None:
            # Abstenerse
            return {
                "differential_score": 0.0,
                "is_structurally_equivalent": None,
                "grounding": grounding,
                "compression": compression,
                "abstain_reason": f"short_response_{reason}",
            }
        elif equiv:
            differential_score = round(min(max(gs, 0.0), 1.0), 6)
            return {
                "differential_score": differential_score,
                "is_structurally_equivalent": True,
                "grounding": grounding,
                "compression": compression,
                "abstain_reason": None,
                "short_response_reason": reason,
            }
        else:
            differential_score = round(min(max(gs * 0.3, 0.0), 1.0), 6)
            return {
                "differential_score": differential_score,
                "is_structurally_equivalent": False,
                "grounding": grounding,
                "compression": compression,
                "abstain_reason": None,
                "short_response_reason": reason,
            }

    # 4. Para responses de 5+ palabras, grounding directo
    differential_score = round(min(max(gs, 0.0), 1.0), 6)

    return {
        "differential_score": differential_score,
        "is_structurally_equivalent": differential_score >= grounding_threshold,
        "grounding": grounding,
        "compression": compression,
        "abstain_reason": None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 72)
    print("  R3.1 Differential Guard v4 — Self-Test (threshold 0.95, con parche respuestas cortas)")
    print("=" * 72)

    casos = [
        ("A_A (idéntico)",
         "The patient was diagnosed with diabetes and hypertension.",
         "The patient was diagnosed with diabetes and hypertension."),
        ("A_Ap (respuesta correcta sola, diálogo)",
         "Knowledge: Iron Man is starring Robert Downey Jr.\nDialogue:\n[Human]: Do you like Iron Man?\n\nCorrect response: I like crime fiction!",
         "I like crime fiction!"),
        ("A_Ap (respuesta factual corta, QA)",
         "Knowledge: Paris is the capital of France.\n\nQuestion: What is the capital of France?\nCorrect answer: Paris",
         "Paris"),
        ("A_B (alucinación, respuesta distinta)",
         "Knowledge: Paris is the capital of France.\n\nQuestion: What is the capital of France?\nCorrect answer: Paris",
         "London is the capital of the United Kingdom."),
        ("A_App (mismo formato, distinto contenido)",
         "Knowledge: Paris is the capital of France.\n\nQuestion: What is the capital of France?\nCorrect answer: Paris",
         "Knowledge: Paris is the capital of France.\n\nQuestion: What is the capital of France?\nCorrect answer: London"),
        ("A_B (alucinación médica)",
         "Question: Do mitochondria play a role in PCD?\nKnowledge: Programmed cell death (PCD) is the regulated death of cells.\nGround Truth: Mitochondria are involved in PCD.",
         "Mitochondria regulate the formation of perforations through calcium channels."),
        # ── Casos cortos (< 5 palabras) ──────────────────────────────
        ("SHORT: A_Ap (yes afirmativo)",
         "Question: Is Paris the capital of France?\nCorrect answer: Yes",
         "Yes"),
        ("SHORT: A_B (no inversión de polaridad)",
         "Question: Is Paris the capital of France?\nCorrect answer: Yes",
         "No"),
        ("SHORT: A_B (none inversión)",
         "Question: Does the patient have diabetes?\nCorrect answer: Yes",
         "None"),
        ("SHORT: A_Ap (año correcto)",
         "Question: When did WWII end?\nCorrect answer: 1945",
         "1945"),
        ("SHORT: A_B (año incorrecto)",
         "Question: When did WWII end?\nCorrect answer: 1945",
         "1944"),
        ("SHORT: A_Ap (entidad correcta)",
         "Question: Who directed Psycho?\nCorrect answer: Alfred Hitchcock",
         "Alfred Hitchcock"),
        ("SHORT: A_B (entidad incorrecta)",
         "Question: Who directed Psycho?\nCorrect answer: Alfred Hitchcock",
         "Alfred Molina"),
        ("SHORT: A_B (negación en source, afirmación en response)",
         "Question: Does the patient have cancer?\nCorrect answer: No, the patient does not have cancer.",
         "Yes"),
    ]

    for nombre, src, rsp in casos:
        r = compute_structural_delta(src, rsp)
        g = r["grounding"]
        c = r["compression"]
        equiv_str = {True: "SI", False: "NO", None: "ABSTIENE"}[r["is_structurally_equivalent"]]
        print(f"\n  {nombre}:")
        print(f"    differential_score={r['differential_score']:.4f}  equiv={equiv_str}")
        if r.get("short_response_reason"):
            print(f"    short_response_reason={r['short_response_reason']}")
        if g is not None:
            print(f"    grounding={g['grounding_score']:.4f}  ({g['n_grounded_words']}/{g['n_response_words']} words)")
        else:
            print(f"    grounding=ABSTIENE  (razón: {r['abstain_reason']})")
        print(f"    compression={c['compression_ratio']:.4f}  score={c['compression_score']:.4f}")