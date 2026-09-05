#!/usr/bin/env python3
"""scripts/72_verificar_5_pares_510.py — PARTE 2: verificación del split 0/510 con 5 pares al azar (seed=42)

Para cada uno de los 5 pares True→False muestreados:
  1. Texto completo de A y B.
  2. Oraciones que _split_sentences() extrajo de cada lado.
  3. Resultado de _align_sentences() — qué oración de A quedó emparejada
     con cuál de B (con score de similitud), o si ninguna alcanzó 0.10.
  4. Por qué, con ese alineamiento, no hay inversión detectada.
"""
import importlib.util
import json
import random
import sys
from pathlib import Path

BASE = Path(r"c:\Users\conno\Downloads\SAS-Semántico")
NEG_PATH = BASE / "SAS" / "SAS" / "core" / "negation_probe.py"
ANTES = BASE / "reports" / "regresion_1600_despues_v2.json"
DESPUES = BASE / "reports" / "regresion_1600_negation_v3.json"
CORPUS_DIR = BASE / "benchmark_corpus"
SUITES = [
    "codehalu", "halubench", "halueval_dialogue", "halueval_general",
    "halueval_qa", "halueval_summarization", "legal_hallucinations", "truthfulqa",
]


def cargar_negation():
    spec = importlib.util.spec_from_file_location("core.negation_probe", NEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["core.negation_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def cargar_pares_suite(suite, max_pairs=200, seed=42):
    suite_dir = CORPUS_DIR / suite
    if not suite_dir.exists():
        return []
    candidatos = []
    for clean_file in suite_dir.glob("*_A_clean.txt"):
        hall_file = clean_file.with_name(clean_file.name.replace("_A_clean.txt", "_B_hallucination.txt"))
        if not hall_file.exists():
            continue
        try:
            sz = clean_file.stat().st_size + hall_file.stat().st_size
        except OSError:
            continue
        if sz > 25000:
            continue
        candidatos.append((clean_file, hall_file))
    if not candidatos:
        return []
    n_muestra = min(max_pairs, len(candidatos))
    muestra = random.Random(seed).sample(candidatos, n_muestra)
    pares = []
    for clean_file, hall_file in muestra:
        base = clean_file.name.replace("_A_clean.txt", "")
        try:
            source = clean_file.read_text(encoding="utf-8", errors="replace").strip()
            response = hall_file.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        pares.append((source, response, f"{suite}/{base}"))
    return pares


def main():
    antes = json.loads(ANTES.read_text("utf-8"))
    despues = json.loads(DESPUES.read_text("utf-8"))
    mapa_antes = {a["pid"]: a for a in antes}
    mapa_despues = {d["pid"]: d for d in despues}

    # Identificar los 510 True→False
    bajan = []
    for pid in mapa_despues:
        a = mapa_antes.get(pid)
        if not a:
            continue
        fa = set(a["fired"])
        fd = set(mapa_despues[pid]["fired"])
        if "negation_penalty" in fa and "negation_penalty" not in fd:
            bajan.append(pid)
    print(f"Pares True→False: {len(bajan)}")

    # Cargar textos
    textos = {}
    for suite in SUITES:
        for src, rsp, pid in cargar_pares_suite(suite, 200, 42):
            textos[pid] = (src, rsp)

    # Muestrear 5 al azar (seed=42)
    rng = random.Random(42)
    muestra = rng.sample(bajan, 5)
    print(f"Muestra de 5 (seed=42): {muestra}")

    np_mod = cargar_negation()

    for i, pid in enumerate(muestra, 1):
        A, B = textos[pid]
        print("\n" + "=" * 90)
        print(f"[{i}] {pid}")
        print("=" * 90)

        print(f"\n── TEXTO A (completo) ──")
        print(A)
        print(f"\n── TEXTO B (completo) ──")
        print(B)

        sa = np_mod._split_sentences(A)
        sb = np_mod._split_sentences(B)
        print(f"\n── _split_sentences(A) → {len(sa)} oraciones ──")
        for j, s in enumerate(sa):
            neg = " [NEG]" if np_mod._tiene_negacion(s) else ""
            print(f"  A{j}: {s}{neg}")
        print(f"\n── _split_sentences(B) → {len(sb)} oraciones ──")
        for j, s in enumerate(sb):
            neg = " [NEG]" if np_mod._tiene_negacion(s) else ""
            print(f"  B{j}: {s}{neg}")

        # Alineación con scores
        print(f"\n── _align_sentences() (umbral 0.10) ──")
        combined = sa + sb
        vocab = np_mod._build_vocab(combined)
        vecs_a = [np_mod._bow_vector(s, vocab) for s in sa]
        vecs_b = [np_mod._bow_vector(s, vocab) for s in sb]
        used_b = set()
        pairs = []
        for ia, va in enumerate(vecs_a):
            best_j, best_sim = -1, -1.0
            for jb, vb in enumerate(vecs_b):
                if jb in used_b:
                    continue
                sim = np_mod._cosine(va, vb)
                if sim > best_sim:
                    best_sim = sim
                    best_j = jb
            if best_j >= 0 and best_sim > 0.10:
                pairs.append((ia, best_j, best_sim))
                used_b.add(best_j)
        if pairs:
            for ia, jb, sim in pairs:
                print(f"  A{ia} ↔ B{jb}  (sim={sim:.3f})")
                print(f"    A{ia}: {sa[ia][:100]}")
                print(f"    B{jb}: {sb[jb][:100]}")
        else:
            print("  (ninguna pareja alcanzó el umbral 0.10)")

        # Resultado del módulo
        r = np_mod.detect_inversions(A, B)
        print(f"\n── detect_inversions() → inv={r.inversion_count}, penalty={r.penalty} ──")
        print(f"  polarity_inverted={r.polarity_inverted}, quantifier_changed={r.quantifier_changed}")
        for d in r.details:
            print(f"  detail: {d.inversion_type} | {d.description}")

        # Explicación
        print(f"\n── POR QUÉ NO HAY INVERSIÓN ──")
        if not sa or not sb:
            print("  Algún lado no tiene oraciones ≥5 palabras → el módulo retorna sin inversión.")
        elif not pairs:
            print("  Ninguna oración de A alcanzó similitud >0.10 con una de B → sin pares alineados → sin inversión.")
        else:
            # Ver si alguna pareja alineada tiene polaridad opuesta
            inv_encontrada = False
            for ia, jb, sim in pairs:
                pol_a = np_mod._tiene_negacion(sa[ia])
                pol_b = np_mod._tiene_negacion(sb[jb])
                if pol_a != pol_b:
                    inv_encontrada = True
                    print(f"  ⚠️  A{ia} (neg={pol_a}) ↔ B{jb} (neg={pol_b}) — ¡polaridad opuesta alineada!")
            if not inv_encontrada:
                print("  Las parejas alineadas tienen la MISMA polaridad (o ninguna tiene negación) → no hay inversión.")
                for ia, jb, sim in pairs:
                    pol_a = np_mod._tiene_negacion(sa[ia])
                    pol_b = np_mod._tiene_negacion(sb[jb])
                    print(f"    A{ia} neg={pol_a} | B{jb} neg={pol_b} | sim={sim:.3f}")


if __name__ == "__main__":
    main()