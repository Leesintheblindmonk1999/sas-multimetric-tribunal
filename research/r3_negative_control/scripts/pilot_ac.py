"""
pilot_ac.py — Piloto de Control Negativo A->C (Paráfrasis)
═══════════════════════════════════════════════════════════════════════════════

Responde al Reviewer #1 (Prateek Srivastava):
  "Without evaluation on correct but non-identical responses, including
   paraphrases, summaries, and semantically equivalent reformulations,
   this conclusion remains premature."

Diseño conservador (n=100 piloto):
  1. Toma pares (source, clean_response) donde source != response
  2. Genera paráfrasis de la respuesta limpia por métodos livianos:
     a) Back-translation (EN -> ES -> EN) via deep_translator
     b) Synonym replacement via NLTK WordNet
  3. Evalúa (source, paráfrasis) con el tribunal
  4. Reporta distribución de zonas y falsos positivos

Uso:
  python pilot_ac.py --input prepared/pares_clean.json --output pilot_ac_results.json --n 100 --methods synonym backtranslation

Formato de entrada (prepared/pares_clean.json):
  [
    {"source": "...", "response": "...", "label": "sanity", "variant": "A->A_clean"},
    ...
  ]

Dependencias opcionales:
  pip install deep-translator nltk
"""

from __future__ import annotations

import json
import argparse
import sys
import random
import re
import warnings
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

# ── Detectar y agregar ruta del tribunal ──────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
if (SCRIPT_DIR / "core" / "tribunal_multimetrico.py").exists():
    sys.path.insert(0, str(SCRIPT_DIR))
elif (SCRIPT_DIR / "SAS" / "SAS" / "core" / "tribunal_multimetrico.py").exists():
    sys.path.insert(0, str(SCRIPT_DIR / "SAS" / "SAS"))
else:
    sys.path.insert(0, r"C:/Users/conno/Downloads/SAS-Semantico/SAS/SAS")

from core.tribunal_multimetrico import TribunalMultimetrico, KAPPA_D


# ════════════════════════════════════════════════════════════════════════════
# GENERADORES DE PARÁFRASIS
# ════════════════════════════════════════════════════════════════════════════

class Paraphraser:
    """Genera paráfrasis de texto usando múltiples métodos livianos."""

    def __init__(self):
        self.methods_available = []
        self._init_nltk()
        self._init_translator()

    def _init_nltk(self):
        """Inicializa recursos NLTK para synonym replacement."""
        try:
            import nltk
            from nltk.corpus import wordnet
            try:
                wordnet.synsets("test")
            except LookupError:
                nltk.download("wordnet", quiet=True)
                nltk.download("omw-1.4", quiet=True)
                nltk.download("averaged_perceptron_tagger_eng", quiet=True)
            self.wordnet = wordnet
            self.methods_available.append("synonym")
        except ImportError:
            warnings.warn("NLTK no instalado. Synonym replacement no disponible.")
            self.wordnet = None

    def _init_translator(self):
        """Inicializa deep_translator para back-translation."""
        try:
            from deep_translator import GoogleTranslator
            self.translator_en_es = GoogleTranslator(source="en", target="es")
            self.translator_es_en = GoogleTranslator(source="es", target="en")
            self.methods_available.append("backtranslation")
        except ImportError:
            warnings.warn("deep-translator no instalado. Back-translation no disponible.")
            self.translator_en_es = None

    def synonym_replace(self, text: str, replace_ratio: float = 0.3) -> str:
        """Reemplaza sinónimos usando WordNet."""
        if self.wordnet is None:
            return text

        import nltk
        words = nltk.word_tokenize(text)
        pos_tags = nltk.pos_tag(words)

        new_words = []
        for word, pos in pos_tags:
            wn_pos = None
            if pos.startswith("J"):
                wn_pos = self.wordnet.ADJ
            elif pos.startswith("V"):
                wn_pos = self.wordnet.VERB
            elif pos.startswith("N"):
                wn_pos = self.wordnet.NOUN
            elif pos.startswith("R"):
                wn_pos = self.wordnet.ADV

            if wn_pos and random.random() < replace_ratio:
                synsets = self.wordnet.synsets(word, pos=wn_pos)
                if synsets:
                    lemmas = [l.name().replace("_", " ") for l in synsets[0].lemmas()]
                    lemmas = [l for l in lemmas if l.lower() != word.lower()]
                    if lemmas:
                        new_words.append(random.choice(lemmas))
                        continue
            new_words.append(word)

        return " ".join(new_words)

    def back_translate(self, text: str) -> str:
        """EN -> ES -> EN via Google Translate."""
        if self.translator_en_es is None:
            return text
        try:
            es = self.translator_en_es.translate(text)
            en = self.translator_es_en.translate(es)
            return en
        except Exception as e:
            warnings.warn(f"Back-translation failed: {e}")
            return text

    def generate(self, text: str, methods: Optional[List[str]] = None) -> Dict[str, str]:
        """Genera paráfrasis por todos los métodos disponibles."""
        methods = methods or self.methods_available
        results = {}
        if "synonym" in methods and "synonym" in self.methods_available:
            results["synonym"] = self.synonym_replace(text)
        if "backtranslation" in methods and "backtranslation" in self.methods_available:
            results["backtranslation"] = self.back_translate(text)
        return results


# ════════════════════════════════════════════════════════════════════════════
# EVALUACIÓN A->C
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ACResult:
    source: str
    original_response: str
    paraphrase_method: str
    paraphrased_response: str
    isi_final: float
    zona: str
    codigo_zona: str
    fp: bool  # True si clasificó como F-S o B (falso positivo)


def run_pilot(pares: List[dict], n: int = 100,
              kappa_d: float = KAPPA_D, kappa_r: float = 0.15,
              methods: Optional[List[str]] = None) -> Dict:
    """Ejecuta el piloto A->C sobre n pares."""

    random.seed(42)

    # Filtrar solo pares donde source != response (excluir A->A tautologicos)
    valid_pares = [p for p in pares if p.get("source", "").strip() != p.get("response", "").strip()]

    print(f"    Pares validos (source != response): {len(valid_pares)}")

    if not valid_pares:
        print("    [ERROR] No hay pares validos para A->C")
        return {"error": "No valid pairs"}

    # Muestrear n pares aleatorios
    sample = random.sample(valid_pares, min(n, len(valid_pares)))

    para = Paraphraser()
    tribunal = TribunalMultimetrico(kappa_d=kappa_d, kappa_r=kappa_r)

    all_results = []
    summary = {}

    for method in (methods or para.methods_available):
        if method not in para.methods_available:
            print(f"  [SKIP] Metodo '{method}' no disponible")
            continue

        print(f"\n  Evaluando metodo: {method}")
        method_results = []
        fps = 0
        zones = {"A": 0, "B": 0, "F-S": 0}

        for i, par in enumerate(sample):
            source = par["source"]
            original = par["response"]

            # Generar paráfrasis
            para_dict = para.generate(original, methods=[method])
            paraphrased = para_dict.get(method, original)

            # Si la paráfrasis es identica al original, saltear (no aporta info)
            if paraphrased.strip() == original.strip():
                continue

            # Evaluar con tribunal
            v = tribunal.evaluar(source, paraphrased)

            is_fp = v.zona in ("COLAPSO_ESTRUCTURAL", "RUPTURA_RECUPERABLE")
            if is_fp:
                fps += 1
            zones[v.codigo_zona] = zones.get(v.codigo_zona, 0) + 1

            method_results.append(ACResult(
                source=source,
                original_response=original,
                paraphrase_method=method,
                paraphrased_response=paraphrased,
                isi_final=v.isi_final,
                zona=v.zona,
                codigo_zona=v.codigo_zona,
                fp=is_fp,
            ))

            if (i + 1) % 10 == 0:
                print(f"    Procesados {i+1}/{len(sample)} ...")

        all_results.extend([asdict(r) for r in method_results])
        n_eval = len(method_results)
        summary[method] = {
            "n_evaluated": n_eval,
            "false_positives": fps,
            "false_positive_rate": round(fps / n_eval, 4) if n_eval else 0.0,
            "zone_distribution": zones,
            "mean_isi": round(sum(r.isi_final for r in method_results) / n_eval, 4) if n_eval else 0.0,
        }
        print(f"    FP = {fps}/{n_eval} ({summary[method]['false_positive_rate']:.1%})")
        print(f"    Zonas: {zones}")

    return {
        "meta": {
            "n_pairs_sampled": len(sample),
            "n_pairs_valid": len(valid_pares),
            "kappa_d": kappa_d,
            "kappa_r": kappa_r,
            "methods_used": list(summary.keys()),
            "methods_available": para.methods_available,
        },
        "summary": summary,
        "detailed_results": all_results,
    }


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Piloto A->C — Paráfrasis")
    parser.add_argument("--input", required=True, help="JSON con pares limpios")
    parser.add_argument("--output", default="pilot_ac_results.json", help="Salida")
    parser.add_argument("--n", type=int, default=100, help="Numero de pares a muestrear")
    parser.add_argument("--kappa-d", type=float, default=KAPPA_D)
    parser.add_argument("--kappa-r", type=float, default=0.15)
    parser.add_argument("--methods", nargs="+", default=None,
                        help="Metodos: synonym backtranslation (default: todos disponibles)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        pares = json.load(f)

    print("=" * 70)
    print("PILOTO A->C — Control Negativo por Paráfrasis")
    print("=" * 70)
    print(f"Pares cargados: {len(pares)}")
    print(f"Muestreo: n={args.n}")
    print(f"kD = {args.kappa_d}, kR = {args.kappa_r}")

    result = run_pilot(
        pares, n=args.n,
        kappa_d=args.kappa_d, kappa_r=args.kappa_r,
        methods=args.methods,
    )

    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
        return

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"Resultados guardados en: {args.output}")
    print("\nRESUMEN POR METODO:")
    print(f"{'Metodo':<20} {'N':>5} {'FP':>5} {'FP%':>8} {'Mean ISI':>10} {'A':>5} {'B':>5} {'F-S':>5}")
    print("-" * 70)
    for method, s in result["summary"].items():
        z = s["zone_distribution"]
        print(f"{method:<20} {s['n_evaluated']:>5} {s['false_positives']:>5} "
              f"{s['false_positive_rate']:>7.1%} {s['mean_isi']:>10.4f} "
              f"{z.get('A', 0):>5} {z.get('B', 0):>5} {z.get('F-S', 0):>5}")

    print("\nNOTA: Un 'falso positivo' en A->C significa que una paráfrasis valida")
    print("fue clasificada como Ruptura (B) o Colapso (F-S). Esto es esperado")
    print("y deseable documentar, no ocultar.")


if __name__ == "__main__":
    main()