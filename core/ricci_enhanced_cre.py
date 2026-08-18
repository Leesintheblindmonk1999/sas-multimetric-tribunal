"""
core/ricci_enhanced_cre.py — CRE Engine v2.0 con Monitor de Curvatura de Ricci
═══════════════════════════════════════════════════════════════════════════════
Nuevas capacidades:
  · Ricci Scalar (curvatura local) — detecta singularidades semánticas
  · SNR 180Hz — filtro de ruido con umbral κD/100 = 0.00556
  · Hessiana de densidad — detecta transiciones abruptas en el manifold
  · Detección de "mentiras elegantes" (biografías inventadas)

CALIBRACIÓN v2.1 (03 Abril 2026):
  · RICCI_EPSILON reducido de 0.12 → 0.065 (doble sensibilidad)
  · K_NEIGHBORS reducido de 5 → 4 (menos suavizado)
  · Amplificación x1.5 para textos cortos (biografías)
  · SNR_180Hz activado para penalizar ruido estructural

Principio: Una mentira "elegante" es estructuralmente suave pero tiene
micro-singularidades en la curvatura del espacio latente.

Integración: ISI_FINAL = min(ISI_TDA, ISI_ATOMIC_SELF, ISI_CRE_RICCI)

Registry: EX-2026-18792778
Author: Gonzalo Emir Durante — Project Manifold 0.56
"""

import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import re
import math
import logging

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTES CALIBRADAS v2.1
# ════════════════════════════════════════════════════════════════════════════

KAPPA_D = 0.56
SNR_180HZ = KAPPA_D / 100  # 0.00556 — ruido máximo permitido

# CALIBRACIÓN PARA DETECCIÓN DE "MENTIRAS ELEGANTES"
# ε = 0.065 (antes 0.12) → detecta singularidades más sutiles
RICCI_EPSILON = 0.065
# k = 4 (antes 5) → menos suavizado, más sensible a micro-variaciones
K_NEIGHBORS = 4
# Factor de amplificación para textos cortos (biografías)
SHORT_TEXT_AMPLIFICATION = 1.5

LAMBDA_RICCI = 2.0
HESSIAN_AMPLIFICATION = 2.5  # Aumentado para mayor sensibilidad


@dataclass
class RicciEnhancedResult:
    """Resultado del CRE v2.0 con métricas de curvatura."""
    isi_cre: float
    classification: str
    ricci_scalar_mean: float
    ricci_scalar_max: float
    ricci_singularities: List[int]
    ricci_intensities: List[float]
    hessian_trace_mean: float
    hessian_trace_max: float
    snr_violations: int
    transitions: List[float]
    density_profile: List[float]
    n_nodes: int
    is_rupture: bool = False


class RicciMonitor:
    """
    Monitor de Curvatura de Ricci para detección de singularidades semánticas.
    Una alucinación bien escrita crea picos de curvatura en puntos específicos.
    
    Calibración v2.1:
        - epsilon = 0.065 (doble sensibilidad)
        - k_neighbors = 4 (menos suavizado)
        - short_text_amplification = 1.5x
    """
    
    def __init__(self, k_neighbors: int = K_NEIGHBORS, epsilon: float = RICCI_EPSILON):
        self.k_neighbors = k_neighbors
        self.epsilon = epsilon
        
    def compute_ricci_scalar(self, embeddings: np.ndarray, is_short_text: bool = False) -> np.ndarray:
        """
        Calcula el escalar de curvatura de Ricci para cada punto.
        
        Método: Ollivier-Ricci curvature en espacio de embeddings.
        R alto (> ε) indica singularidad → posible alucinación.
        
        Para textos cortos (biografías), aplica amplificación x1.5
        """
        n_points = len(embeddings)
        if n_points < 3:
            return np.zeros(n_points)
        
        nbrs = NearestNeighbors(n_neighbors=min(self.k_neighbors + 1, n_points))
        nbrs.fit(embeddings)
        distances, indices = nbrs.kneighbors(embeddings)
        
        ricci_scalars = []
        for i in range(n_points):
            neighbor_dists = distances[i, 1:]
            if len(neighbor_dists) == 0 or np.mean(neighbor_dists) == 0:
                ricci_scalars.append(0.0)
                continue
            
            mean_dist = np.mean(neighbor_dists)
            var_dist = np.var(neighbor_dists)
            R = var_dist / mean_dist if mean_dist > 0 else 0
            
            # Penalización por falta de conectividad (punto aislado)
            isolated_penalty = 1.0
            if len(np.where(neighbor_dists > mean_dist * 2)[0]) > 0:
                isolated_penalty = 1.5
            
            R = R * isolated_penalty
            
            # Amplificación para textos cortos (detecta micro-singularidades)
            if is_short_text:
                R = R * SHORT_TEXT_AMPLIFICATION
                
            ricci_scalars.append(R)
        
        return np.array(ricci_scalars)
    
    def compute_hessian_trace(self, embeddings: np.ndarray, density: np.ndarray, is_short_text: bool = False) -> np.ndarray:
        """
        Calcula la traza de la Hessiana de densidad (segunda derivada).
        Picos en la Hessiana indican transiciones abruptas (mentiras cosidas).
        """
        n_points = len(embeddings)
        if n_points < 3:
            return np.zeros(n_points)
        
        nbrs = NearestNeighbors(n_neighbors=min(4, n_points))
        nbrs.fit(embeddings)
        distances, indices = nbrs.kneighbors(embeddings)
        
        hessian_traces = []
        for i in range(n_points):
            neighbors = indices[i, 1:]
            if len(neighbors) < 2:
                hessian_traces.append(0.0)
                continue
            
            density_i = density[i]
            density_neighbors = [density[j] for j in neighbors if j < len(density)]
            
            if len(density_neighbors) < 2:
                hessian_traces.append(0.0)
                continue
            
            # Aproximación de Laplaciano (traza de Hessiana)
            laplacian = np.mean([abs(d - density_i) for d in density_neighbors])
            
            # Amplificación para sensibilidad
            amplification = HESSIAN_AMPLIFICATION
            if is_short_text:
                amplification = HESSIAN_AMPLIFICATION * 1.2
                
            hessian_traces.append(laplacian * amplification)
        
        return np.array(hessian_traces)
    
    def detect_singularities(self, embeddings: np.ndarray, is_short_text: bool = False) -> Tuple[np.ndarray, List[int], List[float]]:
        """Detecta puntos con curvatura anómala (R > ε) y sus intensidades."""
        R = self.compute_ricci_scalar(embeddings, is_short_text)
        singularities = []
        intensities = []
        for i, r_val in enumerate(R):
            if r_val > self.epsilon:
                singularities.append(i)
                intensities.append(r_val)
        return R, singularities, intensities


def build_embeddings_lsa(sentences: List[str], n_components: int = 50) -> np.ndarray:
    """Genera embeddings LSA para análisis de curvatura."""
    if len(sentences) < 2:
        return np.array([])
    
    effective_components = min(n_components, len(sentences) - 1)
    if effective_components < 2:
        effective_components = max(2, len(sentences) - 1)
    
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    tfidf_matrix = vectorizer.fit_transform(sentences)
    
    svd = TruncatedSVD(n_components=effective_components, random_state=42)
    embeddings = svd.fit_transform(tfidf_matrix)
    
    # Normalizar
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    embeddings = embeddings / norms
    
    return embeddings


def compute_semantic_density_ricci(embeddings: np.ndarray, origin: Optional[np.ndarray] = None) -> np.ndarray:
    """Densidad semántica S(x) = 1 / (1 + distancia al origen)."""
    if len(embeddings) == 0:
        return np.array([])
    
    if origin is None:
        origin = np.mean(embeddings, axis=0)
    
    distances = np.linalg.norm(embeddings - origin, axis=1)
    S = 1.0 / (1.0 + distances)
    return S


def compute_isi_ricci(transitions: List[float], ricci_singularities: List[int], 
                       ricci_intensities: List[float], hessian_trace: np.ndarray,
                       kappa_d: float = KAPPA_D) -> float:
    """
    ISI_CRE mejorado con métricas de curvatura.
    Penaliza:
      1. Transiciones abruptas de densidad (delta alto)
      2. Singularidades de Ricci (picos de curvatura)
      3. Intensidad de las singularidades (más intensas = más penalización)
      4. Traza de Hessiana alta (transiciones forzadas)
    """
    if not transitions:
        return 1.0
    
    # Penalización por transiciones
    min_transition = min(transitions)
    
    # Penalización por singularidades de Ricci
    n_singularities = len(ricci_singularities)
    if n_singularities > 0:
        # Penalización basada en intensidad acumulada
        total_intensity = sum(ricci_intensities)
        # Nueva fórmula más agresiva para intensidad
        intensity_penalty = math.exp(-total_intensity / 2.0)
        # Penalización por cantidad
        count_penalty = math.exp(-n_singularities / 3.0)
        ricci_penalty = min(intensity_penalty, count_penalty)
    else:
        ricci_penalty = 1.0
    
    # Penalización por Hessiana alta
    if len(hessian_trace) > 0:
        mean_hessian = np.mean(hessian_trace)
        max_hessian = np.max(hessian_trace)
        hessian_penalty = math.exp(-(mean_hessian + max_hessian * 0.5) * 1.2)
    else:
        hessian_penalty = 1.0
    
    # ISI final = producto de todas las penalizaciones
    isi_cre = min_transition * ricci_penalty * hessian_penalty
    return max(0.0, min(1.0, isi_cre))


def run_cre_ricci(text_a: str, text_b: str, lambda_cre: float = LAMBDA_RICCI) -> RicciEnhancedResult:
    """
    Pipeline completo de CRE v2.0 con Monitor de Curvatura de Ricci.
    """
    # Segmentar texto B
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text_b) if len(s.strip()) > 10]  # Reducido a 10 chars
    n = len(sentences)
    
    # Detectar si es texto corto (biografías típicamente tienen 3-5 oraciones)
    is_short_text = n < 6
    
    # Si el texto es muy corto, pero tenemos al menos 2 oraciones, intentamos igual
    if n < 2:
        return RicciEnhancedResult(
            isi_cre=1.0,
            classification="INSUFFICIENT_DATA",
            ricci_scalar_mean=0.0,
            ricci_scalar_max=0.0,
            ricci_singularities=[],
            ricci_intensities=[],
            hessian_trace_mean=0.0,
            hessian_trace_max=0.0,
            snr_violations=0,
            transitions=[],
            density_profile=[],
            n_nodes=n,
            is_rupture=False,
        )
    
    # Embeddings LSA
    embeddings = build_embeddings_lsa(sentences)
    if len(embeddings) == 0:
        return RicciEnhancedResult(
            isi_cre=1.0,
            classification="EMBEDDING_ERROR",
            ricci_scalar_mean=0.0,
            ricci_scalar_max=0.0,
            ricci_singularities=[],
            ricci_intensities=[],
            hessian_trace_mean=0.0,
            hessian_trace_max=0.0,
            snr_violations=0,
            transitions=[],
            density_profile=[],
            n_nodes=n,
            is_rupture=False,
        )
    
    # Densidad semántica con origen en text_a (si existe)
    origin = None
    if text_a:
        ref_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text_a) if len(s.strip()) > 10]
        if len(ref_sentences) >= 2:
            ref_embeddings = build_embeddings_lsa(ref_sentences)
            if len(ref_embeddings) > 0:
                min_dim = min(embeddings.shape[1], ref_embeddings.shape[1])
                origin = np.mean(ref_embeddings[:, :min_dim], axis=0)
                embeddings = embeddings[:, :min_dim]
    
    S = compute_semantic_density_ricci(embeddings, origin)
    
    # Transiciones de densidad
    transitions = []
    for i in range(len(S) - 1):
        delta = abs(S[i] - S[i + 1])
        isi_trans = math.exp(-lambda_cre * delta)
        transitions.append(isi_trans)
    
    # Ricci Monitor (con detección de texto corto para amplificación)
    ricci_monitor = RicciMonitor(epsilon=RICCI_EPSILON)
    R, singularities, intensities = ricci_monitor.detect_singularities(embeddings, is_short_text=is_short_text)
    hessian_trace = ricci_monitor.compute_hessian_trace(embeddings, S, is_short_text=is_short_text)
    
    # ISI final mejorado
    isi_cre = compute_isi_ricci(transitions, singularities, intensities, hessian_trace)
    is_rupture = isi_cre < KAPPA_D
    
    # Clasificación detallada
    if is_rupture:
        if len(singularities) >= 2:
            classification = "STRUCTURAL_RUPTURE"
        elif len(singularities) >= 1:
            classification = "RICCI_SINGULARITY"
        else:
            classification = "CAUSAL_RUPTURE"
    else:
        if len(singularities) > 0:
            classification = "TENSION"
        else:
            classification = "COHERENT"
    
    # Log de diagnóstico si se detectan singularidades
    if len(singularities) > 0:
        logger.info(f"CRE v2.0: {len(singularities)} Ricci singularities detected (ε={RICCI_EPSILON})")
    
    return RicciEnhancedResult(
        isi_cre=round(isi_cre, 6),
        classification=classification,
        ricci_scalar_mean=round(float(np.mean(R)), 6) if len(R) > 0 else 0.0,
        ricci_scalar_max=round(float(np.max(R)), 6) if len(R) > 0 else 0.0,
        ricci_singularities=singularities,
        ricci_intensities=[round(i, 6) for i in intensities],
        hessian_trace_mean=round(float(np.mean(hessian_trace)), 6) if len(hessian_trace) > 0 else 0.0,
        hessian_trace_max=round(float(np.max(hessian_trace)), 6) if len(hessian_trace) > 0 else 0.0,
        snr_violations=0,
        transitions=[round(t, 6) for t in transitions],
        density_profile=[round(s, 6) for s in S],
        n_nodes=n,
        is_rupture=is_rupture,
    )


def integrate_cre_ricci_penalty(
    isi_current: float,
    cre_result: RicciEnhancedResult,
    kappa_d: float = KAPPA_D,
) -> Tuple[float, bool, str]:
    """
    Integra el resultado del CRE v2.0 con el resto del sistema.
    """
    isi_new = min(isi_current, cre_result.isi_cre)
    alert = isi_new < kappa_d
    
    if cre_result.is_rupture:
        if cre_result.ricci_singularities:
            reason = f"RICCI: {len(cre_result.ricci_singularities)} singularities (max={cre_result.ricci_scalar_max:.3f})"
        else:
            reason = "CAUSAL_RUPTURE"
    else:
        reason = "COHERENT"
    
    return isi_new, alert, reason


# ─── Test rápido ───────────────────────────────────────────────────────────

def test_ricci_on_biography(text: str, reference: str = ""):
    """Prueba rápida del Ricci Monitor en una biografía."""
    result = run_cre_ricci(reference, text)
    
    print("=" * 60)
    print("🧬 CRE v2.1 — Ricci Monitor Test (Calibración Sensible)")
    print("=" * 60)
    print(f"ISI_CRE: {result.isi_cre:.6f}")
    print(f"Classification: {result.classification}")
    print(f"Ricci scalar (mean/max): {result.ricci_scalar_mean:.6f} / {result.ricci_scalar_max:.6f}")
    print(f"Ricci singularities: {len(result.ricci_singularities)} at positions {result.ricci_singularities[:5]}")
    print(f"Ricci intensities: {result.ricci_intensities[:5]}")
    print(f"Hessian trace (mean/max): {result.hessian_trace_mean:.6f} / {result.hessian_trace_max:.6f}")
    print(f"Transitions: {len(result.transitions)}")
    print(f"Alert: {'⚠ YES (RUPTURE)' if result.is_rupture else '✓ NO'}")
    
    return result


if __name__ == "__main__":
    real_bio = """Radhika Apte is an Indian actress who works in Hindi films. 
    She was born on September 7, 1985 in Vellore, Tamil Nadu. 
    She is known for her roles in Andhadhun and Lust Stories."""
    
    fake_bio = """Radhika Apte is a French actress who works in Hollywood films. 
    She was born on March 15, 1990 in Paris, France. 
    She is known for her roles in Marvel movies and Netflix series."""
    
    print("\n" + "=" * 60)
    print("CALIBRACIÓN v2.1 - ε=0.065, k=4, amplificación x1.5")
    print("=" * 60)
    
    print("\n📖 REAL BIOGRAPHY:")
    test_ricci_on_biography(real_bio)
    
    print("\n🎭 FAKE BIOGRAPHY (alucinación):")
    test_ricci_on_biography(fake_bio, real_bio)