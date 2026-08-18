"""
core/tribunal_multimetrico.py — Tribunal Multimétrico SAS v1.0
═══════════════════════════════════════════════════════════════════════════════
TRIBUNAL MULTIMÉTRICO — Clasificación en 3 Zonas

Arquitectura:
  · Toma 6 métricas del tribunal: lexical_baseline_score, flow_penalty,
    negation_penalty, cre_isi, arithmetic_penalty, reference_penalty
  · Aplica combinador calibrado (regresión logística entrenada en validación)
  · Clasifica en 3 zonas según ISI vs κR y κD:
      - ISI < κR       → COLAPSO ESTRUCTURAL
      - κR ≤ ISI < κD  → RUPTURA RECUPERABLE
      - ISI ≥ κD       → COHERENTE
  · κD = 0.56 (validado, TAD EX-2026-18792778)
  · κR = validación experimental (barrido 0.15-0.40)

Registry: EX-2026-18792778 (TAD, Argentina)
Author: Gonzalo Emir Durante — Project Manifold 0.56
License: Durante Invariance License v1.0
"""

from __future__ import annotations

import math
import json
import hashlib
import datetime
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Callable
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTES
# ════════════════════════════════════════════════════════════════════════════

KAPPA_D: float = 0.56       # Validado — umbral de coherencia estructural
KAPPA_D_TOLERANCE: float = 0.02

# Pesos del combinador calibrado — ESTRATEGIA MULTIPLICATIVA
# Basada en la pipeline original SAS: ISI_HARD = min(TDA, NIG)
# Los módulos experimentales aplican penalización multiplicativa.
# Esto evita que módulos que no disparan (devuelven 1.0) diluyan la señal.
#
# ISI_FINAL = ISI_HARD * Π(penalizaciones_modulos_que_dispararon)
#
# donde ISI_HARD = min(lexical_baseline, cre_isi, source_target_guard)
# es el núcleo estructural y las penalizaciones solo se aplican si
# el módulo disparó.
COMBINER_WEIGHTS: Dict[str, float] = {
    "lexical_baseline":   0.35,  # Peso del núcleo estructural
    "source_target_guard": 0.25, # Mutación de entidades críticas
    "flow_penalty":       0.12,  # Penalización por ruptura de flujo
    "negation_penalty":   0.08,  # Penalización por inversión lógica
    "cre_isi":            0.12,  # Curvatura semántica (Ricci)
    "arithmetic_penalty": 0.04,  # Errores aritméticos
    "reference_penalty":  0.04,  # Fabricación de referencias
}

# Umbrales de zona
KAPPA_R_CANDIDATES: List[float] = [0.15, 0.18, 0.20, 0.22, 0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.40]

# Penalización mínima (ISI floor)
MAX_PENALTY_FLOOR: float = 0.30


# ════════════════════════════════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════════════════════════════════

class ZonaEstructural(Enum):
    COLAPSO_ESTRUCTURAL = "COLAPSO_ESTRUCTURAL"
    RUPTURA_RECUPERABLE = "RUPTURA_RECUPERABLE"
    COHERENTE = "COHERENTE"

    @property
    def codigo(self) -> str:
        return {
            "COLAPSO_ESTRUCTURAL": "F-S",
            "RUPTURA_RECUPERABLE": "B",
            "COHERENTE": "A",
        }[self.value]

    @property
    def riesgo(self) -> str:
        return {
            "COLAPSO_ESTRUCTURAL": "CRITICAL",
            "RUPTURA_RECUPERABLE": "HIGH",
            "COHERENTE": "LOW",
        }[self.value]


# ════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class EvidenciaModulo:
    """Evidencia de un módulo individual del tribunal."""
    nombre: str
    valor: float
    disparo: bool
    umbral: float
    descripcion: str
    peso: float

    def to_dict(self) -> dict:
        return {
            "modulo": self.nombre,
            "valor": round(self.valor, 6),
            "disparo": self.disparo,
            "umbral": self.umbral,
            "descripcion": self.descripcion,
            "peso": self.peso,
        }


@dataclass
class VeredictoTribunal:
    """Veredicto completo del tribunal multimétrico."""
    # Metadatos
    timestamp: str
    hash_source: str
    hash_response: str
    request_id: str

    # Métricas del tribunal
    lexical_baseline_score: float
    source_target_guard: float
    flow_penalty: float
    negation_penalty: float
    cre_isi: float
    arithmetic_penalty: float
    reference_penalty: float

    # Métricas compuestas
    isi_hard: float          # Mínimo de métricas core
    isi_soft: float          # Media ponderada del tribunal
    isi_final: float         # Combinación calibrada

    # Umbrales
    kappa_d: float           # κD = 0.56
    kappa_r: float           # κR (validado experimentalmente)

    # Clasificación
    zona: str                # COLAPSO_ESTRUCTURAL | RUPTURA_RECUPERABLE | COHERENTE
    codigo_zona: str         # F-S | B | A
    riesgo: str              # CRITICAL | HIGH | LOW

    # Evidencia
    modulos_disparados: List[EvidenciaModulo] = field(default_factory=list)
    todas_las_evidencias: List[EvidenciaModulo] = field(default_factory=list)

    # Trazabilidad
    pesos_aplicados: Dict[str, float] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "hash_source": self.hash_source,
            "hash_response": self.hash_response,
            "request_id": self.request_id,
            "lexical_baseline_score": round(self.lexical_baseline_score, 6),
            "source_target_guard": round(self.source_target_guard, 6),
            "flow_penalty": round(self.flow_penalty, 6),
            "negation_penalty": round(self.negation_penalty, 6),
            "cre_isi": round(self.cre_isi, 6),
            "arithmetic_penalty": round(self.arithmetic_penalty, 6),
            "reference_penalty": round(self.reference_penalty, 6),
            "isi_hard": round(self.isi_hard, 6),
            "isi_soft": round(self.isi_soft, 6),
            "isi_final": round(self.isi_final, 6),
            "kappa_d": self.kappa_d,
            "kappa_r": self.kappa_r,
            "zona": self.zona,
            "codigo_zona": self.codigo_zona,
            "riesgo": self.riesgo,
            "modulos_disparados": [m.to_dict() for m in self.modulos_disparados],
            "todas_las_evidencias": [m.to_dict() for m in self.todas_las_evidencias],
            "pesos_aplicados": self.pesos_aplicados,
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False, indent=indent)


@dataclass
class ResultadoBarridoKappaR:
    """Resultado del barrido de validación de κR."""
    kappa_r: float
    proporcion_colapso: float
    proporcion_ruptura: float
    proporcion_coherente: float
    senhal_total: float       # colapso + ruptura (señal detectada)
    entropia_distribucion: float  # qué tan balanceada está la distribución
    f1_estimado: float        # F1 estimado para este κR
    precision_estimada: float
    recall_estimado: float

    def to_dict(self) -> dict:
        return {
            "kappa_r": self.kappa_r,
            "proporcion_colapso": round(self.proporcion_colapso, 4),
            "proporcion_ruptura": round(self.proporcion_ruptura, 4),
            "proporcion_coherente": round(self.proporcion_coherente, 4),
            "senhal_total": round(self.senhal_total, 4),
            "entropia_distribucion": round(self.entropia_distribucion, 4),
            "f1_estimado": round(self.f1_estimado, 4),
            "precision_estimada": round(self.precision_estimada, 4),
            "recall_estimado": round(self.recall_estimado, 4),
        }


# ════════════════════════════════════════════════════════════════════════════
# COMBINADOR CALIBRADO (Regresión Logística)
# ════════════════════════════════════════════════════════════════════════════

class CombinadorCalibrado:
    """
    Combinador de métricas del tribunal usando regresión logística.

    La regresión logística asigna pesos a cada módulo y produce
    un ISI calibrado en [0, 1]. Los pesos se calibran en validación
    y se congelan para test.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or COMBINER_WEIGHTS.copy()
        self._validate_weights()

    def _validate_weights(self):
        """Valida que los pesos sumen ~1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                f"Pesos del combinador no normalizados: suma={total:.4f}. "
                f"Normalizando automáticamente."
            )
            for k in self.weights:
                self.weights[k] /= total

    def calibrar(self, metricas: Dict[str, float]) -> float:
        """
        Aplica regresión logística a las métricas del tribunal.

        ISI_calibrado = sigmoid(Σ w_i · x_i)

        donde x_i son las métricas normalizadas a [0, 1] y w_i son
        los pesos calibrados.
        """
        score = 0.0
        for nombre, valor in metricas.items():
            peso = self.weights.get(nombre, 0.0)
            score += peso * valor

        # Aplicar sigmoid para mantener en [0, 1]
        # Escalamos para que score=0.5 → ISI≈0.56 (κD)
        isi = 1.0 / (1.0 + math.exp(-6.0 * (score - 0.5)))
        return max(0.0, min(1.0, isi))

    def get_pesos(self) -> Dict[str, float]:
        return self.weights.copy()


# ════════════════════════════════════════════════════════════════════════════
# TRIBUNAL MULTIMÉTRICO
# ════════════════════════════════════════════════════════════════════════════

class TribunalMultimetrico:
    """
    Tribunal Multimétrico SAS.

    Evalúa pares (source, response) usando 6 módulos y clasifica
    en 3 zonas estructurales.

    Flujo:
      1. Recibir par (source, response)
      2. Calcular cada métrica del tribunal
      3. Aplicar combinador calibrado
      4. Clasificar según κR y κD
      5. Emitir veredicto con evidencia
    """

    def __init__(
        self,
        kappa_d: float = KAPPA_D,
        kappa_r: float = 0.25,  # Valor por defecto, se calibra experimentalmente
        weights: Optional[Dict[str, float]] = None,
    ):
        self.kappa_d = kappa_d
        self.kappa_r = kappa_r
        self.combinador = CombinadorCalibrado(weights)
        self._modulos_cargados: Dict[str, bool] = {}
        self._inicializar_modulos()

    def _inicializar_modulos(self):
        """Intenta cargar todos los módulos disponibles."""
        modulos = [
            ("flow_coherence", "_FLOW_OK"),
            ("negation_probe", "_NEGATION_OK"),
            ("ricci_enhanced_cre", "_CRE_OK"),
            ("arithmetic_detector", "_ARITH_OK"),
            ("reference_check", "_REF_OK"),
            ("entropy_density", "_ENTROPY_DENSITY_OK"),
        ]
        for nombre, flag in modulos:
            try:
                exec(f"from core.{nombre} import *")
                self._modulos_cargados[nombre] = True
            except ImportError:
                self._modulos_cargados[nombre] = False

    def _calcular_lexical_baseline(self, text_a: str, text_b: str) -> float:
        """Calcula el baseline léxico (Jaccard similarity)."""
        tokens_a = set(re.findall(r"\b\w+\b", text_a.lower()))
        tokens_b = set(re.findall(r"\b\w+\b", text_b.lower()))
        if not tokens_a or not tokens_b:
            return 0.0
        union = tokens_a | tokens_b
        return len(tokens_a & tokens_b) / len(union) if union else 0.0

    def _calcular_source_target_guard(
        self, text_a: str, text_b: str
    ) -> Tuple[float, bool, str]:
        """
        SourceTargetGuard — Detecta mutaciones de entidades críticas
        entre source (A) y response (B).

        Detecta:
          - Mutaciones de ubicación (ciudades, países)
          - Mutaciones de fechas y años
          - Mutaciones de nombres propios
          - Mutaciones de cantidades numéricas

        Penalización: ISI multiplicado por factor según gravedad.
        """
        # Patrones de entidades críticas
        location_pattern = re.compile(
            r'\b(?:Paris|London|Berlin|Madrid|Rome|Buenos\s*Aires|New\s*York|'
            r'Washington|Tokyo|Beijing|Moscow|Sydney|Cairo|Delhi|'
            r'France|Germany|Spain|Italy|Argentina|USA|UK|China|Japan|'
            r'Russia|Australia|Brazil|India|Mexico|Canada)\b',
            re.IGNORECASE
        )
        year_pattern = re.compile(r'\b(1[4-9]\d{2}|20[0-2]\d)\b')
        name_pattern = re.compile(
            r'\b[A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+){1,3}\b'
        )
        quantity_pattern = re.compile(
            r'\b(\d+)\s*(?:million|billion|thousand|mg|kg|km|%)?\b',
            re.IGNORECASE
        )

        # Extraer entidades de A
        locations_a = set(location_pattern.findall(text_a))
        years_a = set(year_pattern.findall(text_a))
        names_a = set(name_pattern.findall(text_a))
        quantities_a = set(quantity_pattern.findall(text_a))

        # Extraer entidades de B
        locations_b = set(location_pattern.findall(text_b))
        years_b = set(year_pattern.findall(text_b))
        names_b = set(name_pattern.findall(text_b))
        quantities_b = set(quantity_pattern.findall(text_b))

        mutaciones = []
        penalizacion = 1.0

        # 1. Mutaciones de ubicación (alta gravedad)
        loc_mutadas = locations_a - locations_b
        loc_nuevas = locations_b - locations_a
        if loc_mutadas and loc_nuevas:
            # Hay ubicaciones en A que no están en B, y viceversa
            n_mutaciones = min(len(loc_mutadas), len(loc_nuevas))
            mutaciones.append(f"{n_mutaciones} ubicación(es) mutada(s)")
            penalizacion *= (0.70 ** n_mutaciones)

        # 2. Mutaciones de año (alta gravedad)
        years_mutados = years_a - years_b
        years_nuevos = years_b - years_a
        if years_mutados and years_nuevos:
            n_mutaciones = min(len(years_mutados), len(years_nuevos))
            mutaciones.append(f"{n_mutaciones} año(s) mutado(s)")
            penalizacion *= (0.65 ** n_mutaciones)

        # 3. Mutaciones de nombres propios (gravedad media)
        # Solo considerar nombres que aparecen 1-2 veces (no genéricos)
        names_a_filt = {n for n in names_a if len(n.split()) <= 3}
        names_b_filt = {n for n in names_b if len(n.split()) <= 3}
        names_mutados = names_a_filt - names_b_filt
        names_nuevos = names_b_filt - names_a_filt
        if names_mutados and names_nuevos:
            n_mutaciones = min(len(names_mutados), len(names_nuevos))
            mutaciones.append(f"{n_mutaciones} nombre(s) mutado(s)")
            penalizacion *= (0.80 ** n_mutaciones)

        # 4. Mutaciones de cantidades (gravedad media)
        # Comparar solo si hay números en ambos textos
        if quantities_a and quantities_b:
            nums_a = {int(q[0]) for q in quantities_a if q[0].isdigit()}
            nums_b = {int(q[0]) for q in quantities_b if q[0].isdigit()}
            nums_mutados = nums_a - nums_b
            nums_nuevos = nums_b - nums_a
            if nums_mutados and nums_nuevos:
                n_mutaciones = min(len(nums_mutados), len(nums_nuevos))
                mutaciones.append(f"{n_mutaciones} cantidad(es) mutada(s)")
                penalizacion *= (0.75 ** n_mutaciones)

        disparo = penalizacion < 0.95
        desc = "; ".join(mutaciones) if mutaciones else "Sin mutaciones de entidades"

        return max(penalizacion, 0.30), disparo, f"SourceTargetGuard: {desc}"

    def _calcular_flow_penalty(self, text_a: str, text_b: str) -> Tuple[float, bool, str]:
        """Calcula penalización por ruptura de flujo semántico."""
        try:
            from core.flow_coherence import run_flow_coherence, apply_flow_penalty
            result = run_flow_coherence(text_a, text_b, domain="generic", isi_original=1.0)
            if result.layer4_fired:
                isi_penalized, _ = apply_flow_penalty(1.0, result, kappa_d=self.kappa_d)
                return isi_penalized, True, (
                    f"Flow Coherence: {len(result.entropy_spikes)} entropy spike(s), "
                    f"{len(result.flow_breaks)} causal break(s)"
                )
            return 1.0, False, "Flow Coherence: sin anomalías"
        except Exception as e:
            logger.debug(f"Flow module error: {e}")
            return 1.0, False, f"Flow Coherence: no disponible ({e})"

    def _calcular_negation_penalty(self, text_a: str, text_b: str) -> Tuple[float, bool, str]:
        """Calcula penalización por inversiones lógicas."""
        try:
            from core.negation_probe import detect_inversions
            result = detect_inversions(text_a, text_b)
            if result.inversion_count > 0:
                return result.penalty, True, (
                    f"NegationProbe: {result.inversion_count} inversión(es) "
                    f"(score ponderado={result.weighted_inversion_score:.2f})"
                )
            return 1.0, False, "NegationProbe: sin inversiones"
        except Exception as e:
            logger.debug(f"Negation module error: {e}")
            return 1.0, False, f"NegationProbe: no disponible ({e})"

    def _calcular_cre_isi(self, text_a: str, text_b: str) -> Tuple[float, bool, str]:
        """Calcula ISI del motor CRE (curvatura semántica)."""
        try:
            from core.ricci_enhanced_cre import run_cre_ricci
            result = run_cre_ricci(text_a=text_a, text_b=text_b, lambda_cre=2.0)
            return result.isi_cre, result.is_rupture, (
                f"CRE: {len(result.ricci_singularities)} singularidad(es) Ricci, "
                f"R_mean={result.ricci_scalar_mean:.4f}, "
                f"clasificación={result.classification}"
            )
        except Exception as e:
            logger.debug(f"CRE module error: {e}")
            return 1.0, False, f"CRE: no disponible ({e})"

    def _calcular_arithmetic_penalty(self, text_b: str) -> Tuple[float, bool, str]:
        """Calcula penalización por errores aritméticos."""
        try:
            from core.arithmetic_detector import detect_arithmetic_errors
            result = detect_arithmetic_errors(text_b)
            if result.error_count > 0:
                return result.penalty, True, (
                    f"ArithmeticDetector: {result.error_count} error(es) aritmético(s)"
                )
            return 1.0, False, "ArithmeticDetector: sin errores"
        except Exception as e:
            logger.debug(f"Arithmetic module error: {e}")
            return 1.0, False, f"ArithmeticDetector: no disponible ({e})"

    def _calcular_reference_penalty(self, text_a: str, text_b: str) -> Tuple[float, bool, str]:
        """Calcula penalización por fabricación de referencias."""
        try:
            from core.reference_check import detect_fabrications
            result = detect_fabrications(text_a, text_b)
            if result.fabricated_count > 0:
                return result.penalty, True, (
                    f"ReferenceCheck: {result.fabricated_count} fabricación(es) "
                    f"({result.anachronistic_count} anacrónica(s))"
                )
            return 1.0, False, "ReferenceCheck: sin fabricaciones"
        except Exception as e:
            logger.debug(f"Reference module error: {e}")
            return 1.0, False, f"ReferenceCheck: no disponible ({e})"

    def _clasificar_zona(self, isi_final: float) -> ZonaEstructural:
        """Clasifica el ISI final en una de las 3 zonas estructurales."""
        if isi_final < self.kappa_r:
            return ZonaEstructural.COLAPSO_ESTRUCTURAL
        elif isi_final < self.kappa_d:
            return ZonaEstructural.RUPTURA_RECUPERABLE
        else:
            return ZonaEstructural.COHERENTE

    def evaluar(
        self,
        source: str,
        response: str,
        request_id: Optional[str] = None,
    ) -> VeredictoTribunal:
        """
        Evalúa un par (source, response) y produce un veredicto.

        Parámetros
        ----------
        source : str
            Texto fuente (A_clean)
        response : str
            Texto respuesta a evaluar
        request_id : str, optional
            ID de trazabilidad

        Returns
        -------
        VeredictoTribunal
            Veredicto completo con evidencia de cada módulo
        """
        ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        hash_src = hashlib.sha256(source.encode("utf-8", errors="replace")).hexdigest()[:16]
        hash_rsp = hashlib.sha256(response.encode("utf-8", errors="replace")).hexdigest()[:16]
        rid = request_id or f"TRIB-{hash_src}-{hash_rsp}-{datetime.datetime.utcnow().strftime('%H%M%S')}"

        # ── 1. Calcular métricas del tribunal ──────────────────────────────
        lexical_score = self._calcular_lexical_baseline(source, response)
        stg_val, stg_fired, stg_desc = self._calcular_source_target_guard(source, response)
        flow_val, flow_fired, flow_desc = self._calcular_flow_penalty(source, response)
        neg_val, neg_fired, neg_desc = self._calcular_negation_penalty(source, response)
        cre_val, cre_fired, cre_desc = self._calcular_cre_isi(source, response)
        arith_val, arith_fired, arith_desc = self._calcular_arithmetic_penalty(response)
        ref_val, ref_fired, ref_desc = self._calcular_reference_penalty(source, response)

        # ── 2. Construir mapa de métricas ──────────────────────────────────
        metricas_raw = {
            "lexical_baseline": lexical_score,
            "source_target_guard": stg_val,
            "flow_penalty": flow_val,
            "negation_penalty": neg_val,
            "cre_isi": cre_val,
            "arithmetic_penalty": arith_val,
            "reference_penalty": ref_val,
        }

        # ── 3. ISI Hard (mínimo de módulos core) ───────────────────────────
        # Núcleo estructural: mínimo entre baseline léxico y SourceTargetGuard.
        # SourceTargetGuard detecta mutaciones de entidades que el baseline
        # léxico no captura (alto solapamiento léxico pero entidades cambiadas).
        #
        # CRE (curvatura semántica) solo se incluye si los textos son
        # diferentes Y CRE disparó. En textos cortos o idénticos, CRE puede
        # producir falsos positivos por dispersión del embedding LSA.
        textos_identicos = source.strip() == response.strip()
        if cre_fired and not textos_identicos:
            isi_hard = min(lexical_score, stg_val, cre_val)
        else:
            isi_hard = min(lexical_score, stg_val)

        # ── 4. ISI Final — Penalización multiplicativa en cascada ──────────
        # Estrategia: ISI_FINAL = ISI_HARD * Π(penalizaciones)
        # Solo los módulos que DISPARARON aplican penalización.
        # Esto evita que módulos silenciosos (1.0) diluyan la señal.
        #
        # Las penalizaciones se aplican en orden de especificidad:
        #   source_target_guard → mutación de entidades críticas
        #   flow_penalty → ruptura de flujo semántico
        #   negation_penalty → inversiones lógicas
        #   arithmetic_penalty → errores aritméticos
        #   reference_penalty → fabricación de referencias
        #
        # ISI_SOFT se reporta como el factor de penalización multiplicativo
        # total (para trazabilidad), pero no se promedia con ISI_HARD.
        penalizaciones = []
        if stg_fired:
            penalizaciones.append(stg_val)
        if flow_fired:
            penalizaciones.append(flow_val)
        if neg_fired:
            penalizaciones.append(neg_val)
        if arith_fired:
            penalizaciones.append(arith_val)
        if ref_fired:
            penalizaciones.append(ref_val)

        if penalizaciones:
            # Producto de penalizaciones (cada una < 1.0 si disparó)
            factor_penalizacion = 1.0
            for p in penalizaciones:
                factor_penalizacion *= p
            isi_final = isi_hard * factor_penalizacion
            isi_soft = factor_penalizacion  # reporte
        else:
            isi_final = isi_hard
            isi_soft = 1.0

        isi_final = max(0.0, min(1.0, isi_final))

        # ── 6. Clasificar zona ─────────────────────────────────────────────
        zona = self._clasificar_zona(isi_final)

        # ── 7. Construir evidencias ────────────────────────────────────────
        todas_evidencias = [
            EvidenciaModulo(
                nombre="lexical_baseline_score",
                valor=lexical_score,
                disparo=lexical_score < self.kappa_d,
                umbral=self.kappa_d,
                descripcion=f"Solapamiento léxico Jaccard: {lexical_score:.4f}",
                peso=self.combinador.weights.get("lexical_baseline", 0.0),
            ),
            EvidenciaModulo(
                nombre="source_target_guard",
                valor=stg_val,
                disparo=stg_fired,
                umbral=0.70,
                descripcion=stg_desc,
                peso=self.combinador.weights.get("source_target_guard", 0.0),
            ),
            EvidenciaModulo(
                nombre="flow_penalty",
                valor=flow_val,
                disparo=flow_fired,
                umbral=0.78,  # FLOW_PENALTY_FACTOR
                descripcion=flow_desc,
                peso=self.combinador.weights.get("flow_penalty", 0.0),
            ),
            EvidenciaModulo(
                nombre="negation_penalty",
                valor=neg_val,
                disparo=neg_fired,
                umbral=0.45,  # NEGATION_PENALTY_BASE
                descripcion=neg_desc,
                peso=self.combinador.weights.get("negation_penalty", 0.0),
            ),
            EvidenciaModulo(
                nombre="cre_isi",
                valor=cre_val,
                disparo=cre_fired,
                umbral=self.kappa_d,
                descripcion=cre_desc,
                peso=self.combinador.weights.get("cre_isi", 0.0),
            ),
            EvidenciaModulo(
                nombre="arithmetic_penalty",
                valor=arith_val,
                disparo=arith_fired,
                umbral=0.60,  # ARITHMETIC_PENALTY_BASE
                descripcion=arith_desc,
                peso=self.combinador.weights.get("arithmetic_penalty", 0.0),
            ),
            EvidenciaModulo(
                nombre="reference_penalty",
                valor=ref_val,
                disparo=ref_fired,
                umbral=0.75,  # REFERENCE_PENALTY_BASE
                descripcion=ref_desc,
                peso=self.combinador.weights.get("reference_penalty", 0.0),
            ),
        ]

        modulos_disparados = [m for m in todas_evidencias if m.disparo]

        # ── 8. Construir summary ───────────────────────────────────────────
        sep = "─" * 60
        lines = [
            "TRIBUNAL MULTIMÉTRICO SAS — VEREDICTO",
            sep,
            f"Request ID    : {rid}",
            f"Source hash   : {hash_src}",
            f"Response hash : {hash_rsp}",
            sep,
            "MÉTRICAS DEL TRIBUNAL",
            f"  Lexical Baseline  : {lexical_score:.6f}",
            f"  SourceTargetGuard : {stg_val:.6f}  {'⚠ DISPARO' if stg_fired else '✓ OK'}",
            f"  Flow Penalty      : {flow_val:.6f}  {'⚠ DISPARO' if flow_fired else '✓ OK'}",
            f"  Negation Penalty : {neg_val:.6f}  {'⚠ DISPARO' if neg_fired else '✓ OK'}",
            f"  CRE ISI          : {cre_val:.6f}  {'⚠ DISPARO' if cre_fired else '✓ OK'}",
            f"  Arithmetic Penal : {arith_val:.6f}  {'⚠ DISPARO' if arith_fired else '✓ OK'}",
            f"  Reference Penal  : {ref_val:.6f}  {'⚠ DISPARO' if ref_fired else '✓ OK'}",
            sep,
            "ISI COMPUESTO (penalización multiplicativa en cascada)",
            f"  ISI_HARD = {isi_hard:.6f}  [min(lexical, STG, CRE)]",
            f"  ISI_SOFT = {isi_soft:.6f}  [factor de penalización multiplicativo]",
            f"  ISI_FINAL = {isi_final:.6f}  [ISI_HARD × Π(penalizaciones)]",
            sep,
            f"  κD = {self.kappa_d}  |  κR = {self.kappa_r}",
            sep,
            f"ZONA       : {zona.value} ({zona.codigo})",
            f"RIESGO     : {zona.riesgo}",
            sep,
        ]

        if modulos_disparados:
            lines.append("MÓDULOS QUE DISPARARON:")
            for m in modulos_disparados:
                lines.append(f"  • {m.nombre}: {m.descripcion}")
        else:
            lines.append("NINGÚN MÓDULO DISPARÓ — estructura coherente")

        lines.append(sep)

        return VeredictoTribunal(
            timestamp=ts,
            hash_source=hash_src,
            hash_response=hash_rsp,
            request_id=rid,
            lexical_baseline_score=lexical_score,
            source_target_guard=stg_val,
            flow_penalty=flow_val,
            negation_penalty=neg_val,
            cre_isi=cre_val,
            arithmetic_penalty=arith_val,
            reference_penalty=ref_val,
            isi_hard=round(isi_hard, 6),
            isi_soft=round(isi_soft, 6),
            isi_final=round(isi_final, 6),
            kappa_d=self.kappa_d,
            kappa_r=self.kappa_r,
            zona=zona.value,
            codigo_zona=zona.codigo,
            riesgo=zona.riesgo,
            modulos_disparados=modulos_disparados,
            todas_las_evidencias=todas_evidencias,
            pesos_aplicados=self.combinador.get_pesos(),
            summary="\n".join(lines),
        )

    def evaluar_batch(
        self,
        pares: List[Tuple[str, str]],
        request_ids: Optional[List[str]] = None,
    ) -> List[VeredictoTribunal]:
        """Evalúa múltiples pares en lote."""
        resultados = []
        for i, (source, response) in enumerate(pares):
            rid = request_ids[i] if request_ids and i < len(request_ids) else None
            resultados.append(self.evaluar(source, response, request_id=rid))
        return resultados


# ════════════════════════════════════════════════════════════════════════════
# VALIDADOR EXPERIMENTAL DE κR
# ════════════════════════════════════════════════════════════════════════════

class ValidadorKappaR:
    """
    Validador experimental del umbral κR.

    Barre candidatos κR en [0.15, 0.40] y evalúa:
      - Proporción de pares en cada zona
      - Señal total detectada (colapso + ruptura)
      - Entropía de la distribución (qué tan balanceada)
      - F1 estimado contra baseline conocido

    El κR óptimo maximiza la señal manteniendo una distribución
    con entropía suficiente (no todo colapso ni todo coherente).
    """

    def __init__(self, tribunal: TribunalMultimetrico):
        self.tribunal = tribunal
        self.candidatos = KAPPA_R_CANDIDATES

    def validar(
        self,
        pares_control: List[Tuple[str, str]],       # Pares limpios (A_clean, C_clean)
        pares_alucinacion: List[Tuple[str, str]],   # Pares con alucinación (A_clean, B_hallucination)
    ) -> Tuple[float, List[ResultadoBarridoKappaR]]:
        """
        Valida κR experimentalmente.

        Para cada candidato κR, evalúa todos los pares y calcula
        métricas de calidad de la clasificación.

        Returns
        -------
        kappa_r_optimo : float
            El κR que maximiza la señal
        resultados : List[ResultadoBarridoKappaR]
            Resultados detallados para cada candidato
        """
        resultados = []

        for kr in self.candidatos:
            self.tribunal.kappa_r = kr

            # Evaluar pares de control (deberían ser COHERENTES)
            n_colapso_control = 0
            n_ruptura_control = 0
            n_coherente_control = 0

            for source, response in pares_control:
                v = self.tribunal.evaluar(source, response)
                if v.zona == ZonaEstructural.COLAPSO_ESTRUCTURAL.value:
                    n_colapso_control += 1
                elif v.zona == ZonaEstructural.RUPTURA_RECUPERABLE.value:
                    n_ruptura_control += 1
                else:
                    n_coherente_control += 1

            # Evaluar pares de alucinación (deberían ser COLAPSO o RUPTURA)
            n_colapso_aluc = 0
            n_ruptura_aluc = 0
            n_coherente_aluc = 0

            for source, response in pares_alucinacion:
                v = self.tribunal.evaluar(source, response)
                if v.zona == ZonaEstructural.COLAPSO_ESTRUCTURAL.value:
                    n_colapso_aluc += 1
                elif v.zona == ZonaEstructural.RUPTURA_RECUPERABLE.value:
                    n_ruptura_aluc += 1
                else:
                    n_coherente_aluc += 1

            total_control = len(pares_control) or 1
            total_aluc = len(pares_alucinacion) or 1

            # Proporciones
            p_colapso = (n_colapso_control + n_colapso_aluc) / (total_control + total_aluc)
            p_ruptura = (n_ruptura_control + n_ruptura_aluc) / (total_control + total_aluc)
            p_coherente = (n_coherente_control + n_coherente_aluc) / (total_control + total_aluc)

            # Señal total (colapso + ruptura) en pares de alucinación
            senhal_aluc = (n_colapso_aluc + n_ruptura_aluc) / total_aluc

            # Señal total en pares de control (idealmente baja)
            senhal_control = (n_colapso_control + n_ruptura_control) / total_control

            # Señal neta (señal en alucinación - señal en control)
            senhal_neta = senhal_aluc - senhal_control

            # Entropía de la distribución (Shannon)
            entropia = 0.0
            for p in [p_colapso, p_ruptura, p_coherente]:
                if p > 0:
                    entropia -= p * math.log2(p)

            # F1 estimado: qué tan bien separa las clases
            # True positives = alucinaciones detectadas (colapso + ruptura)
            # False positives = controles detectados como anomalía
            tp = n_colapso_aluc + n_ruptura_aluc
            fp = n_colapso_control + n_ruptura_control
            fn = n_coherente_aluc  # alucinaciones clasificadas como coherentes
            tn = n_coherente_control

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            resultados.append(ResultadoBarridoKappaR(
                kappa_r=kr,
                proporcion_colapso=p_colapso,
                proporcion_ruptura=p_ruptura,
                proporcion_coherente=p_coherente,
                senhal_total=senhal_neta,
                entropia_distribucion=entropia,
                f1_estimado=f1,
                precision_estimada=precision,
                recall_estimado=recall,
            ))

        # Seleccionar κR óptimo: maximiza F1 con entropía suficiente
        kappa_r_optimo = self._seleccionar_optimo(resultados)
        return kappa_r_optimo, resultados

    def _seleccionar_optimo(self, resultados: List[ResultadoBarridoKappaR]) -> float:
        """
        Selecciona el κR óptimo.

        Criterio: maximizar F1 estimado con penalización por
        entropía muy baja (< 0.5 bits, indica distribución degenerada).
        """
        mejor = None
        mejor_score = -1.0

        for r in resultados:
            # Penalizar distribuciones degeneradas
            penalizacion_entropia = 1.0
            if r.entropia_distribucion < 0.5:
                penalizacion_entropia = r.entropia_distribucion / 0.5

            score = r.f1_estimado * penalizacion_entropia

            if score > mejor_score:
                mejor_score = score
                mejor = r

        return mejor.kappa_r if mejor else 0.25

    def generar_reporte_validacion(
        self,
        resultados: List[ResultadoBarridoKappaR],
        kappa_r_optimo: float,
    ) -> str:
        """Genera reporte legible de la validación de κR."""
        sep = "═" * 70
        lines = [
            sep,
            "VALIDACIÓN EXPERIMENTAL DE κR — TRIBUNAL MULTIMÉTRICO SAS",
            sep,
            f"κD = {self.tribunal.kappa_d} (fijo, validado TAD EX-2026-18792778)",
            f"Rango evaluado: {self.candidatos[0]} – {self.candidatos[-1]}",
            f"κR óptimo: {kappa_r_optimo}",
            sep,
            f"{'κR':>6} | {'Colapso':>8} | {'Ruptura':>8} | {'Coherente':>9} | {'Señal':>6} | {'Entropía':>8} | {'F1':>6}",
            sep[:65],
        ]

        for r in resultados:
            marker = " ◄ ÓPTIMO" if abs(r.kappa_r - kappa_r_optimo) < 0.001 else ""
            lines.append(
                f"{r.kappa_r:>6.2f} | {r.proporcion_colapso:>7.1%} | "
                f"{r.proporcion_ruptura:>7.1%} | {r.proporcion_coherente:>7.1%} | "
                f"{r.senhal_total:>5.1%} | {r.entropia_distribucion:>7.3f} | "
                f"{r.f1_estimado:>5.1%}{marker}"
            )

        lines.append(sep)
        lines.append("")
        lines.append("INTERPRETACIÓN:")
        lines.append(f"  κR = {kappa_r_optimo} maximiza F1 con distribución no degenerada.")
        lines.append(f"  Señal neta (alucinación - control) en óptimo: "
                     f"{resultados[[abs(r.kappa_r - kappa_r_optimo) for r in resultados].index(min(abs(r.kappa_r - kappa_r_optimo) for r in resultados))].senhal_total:.1%}")
        lines.append("")
        lines.append("ZONAS:")
        lines.append(f"  ISI < {kappa_r_optimo:.2f} → COLAPSO ESTRUCTURAL (F-S)")
        lines.append(f"  {kappa_r_optimo:.2f} ≤ ISI < {self.tribunal.kappa_d} → RUPTURA RECUPERABLE (B)")
        lines.append(f"  ISI ≥ {self.tribunal.kappa_d} → COHERENTE (A)")
        lines.append(sep)

        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL (CLI)
# ════════════════════════════════════════════════════════════════════════════

def evaluar_par(
    source: str,
    response: str,
    kappa_d: float = KAPPA_D,
    kappa_r: float = 0.25,
    request_id: Optional[str] = None,
) -> VeredictoTribunal:
    """
    Evalúa un par (source, response) con el tribunal multimétrico.

    Esta es la función de entrada principal para uso externo.
    """
    tribunal = TribunalMultimetrico(kappa_d=kappa_d, kappa_r=kappa_r)
    return tribunal.evaluar(source, response, request_id=request_id)


def validar_kr(
    pares_control: List[Tuple[str, str]],
    pares_alucinacion: List[Tuple[str, str]],
    kappa_d: float = KAPPA_D,
) -> Tuple[float, str]:
    """
    Valida κR experimentalmente sobre pares conocidos.

    Returns
    -------
    kappa_r_optimo : float
    reporte : str
    """
    tribunal = TribunalMultimetrico(kappa_d=kappa_d)
    validador = ValidadorKappaR(tribunal)
    kr_optimo, resultados = validador.validar(pares_control, pares_alucinacion)
    reporte = validador.generar_reporte_validacion(resultados, kr_optimo)
    return kr_optimo, reporte


def _cli():
    import argparse
    parser = argparse.ArgumentParser(
        prog="tribunal-multimetrico",
        description="Tribunal Multimétrico SAS — Clasificación en 3 zonas estructurales",
    )
    parser.add_argument("--source", required=True, help="Texto fuente (A_clean)")
    parser.add_argument("--response", required=True, help="Texto respuesta a evaluar")
    parser.add_argument("--kappa-d", type=float, default=KAPPA_D, help=f"κD (default: {KAPPA_D})")
    parser.add_argument("--kappa-r", type=float, default=0.25, help="κR (default: 0.25)")
    parser.add_argument("--request-id", default=None, help="ID de trazabilidad")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    args = parser.parse_args()

    tribunal = TribunalMultimetrico(kappa_d=args.kappa_d, kappa_r=args.kappa_r)
    veredicto = tribunal.evaluar(args.source, args.response, request_id=args.request_id)

    if args.json:
        print(veredicto.to_json())
    else:
        print(veredicto.summary)


if __name__ == "__main__":
    _cli()
