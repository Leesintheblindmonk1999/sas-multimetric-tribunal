#!/usr/bin/env python3
"""
scripts/n1_control.py — Control N1: 4 condiciones sobre los mismos 1,800 IDs
═══════════════════════════════════════════════════════════════════════════════

Reusa EXACTAMENTE el muestreo de validacion_1800_stratified_v3.py:
sorted(glob) + seed=42, mismos 1,800 IDs, mismo orden.

4 condiciones por par:
  A_A   : A vs A           [identidad]
  A_Ap  : A vs A'          [respuesta correcta sola]
  A_B   : A vs B           [la publicada]
  A_App : A vs A''         [contexto + marcador + B, mismo formato distinto contenido]

Salida: reports/pairs_conditions_1800_seed42.json (7,200 objetos, 1,800 × 4)

Uso:
    python scripts/n1_control.py

Registry: EX-2026-18792778 (TAD, Argentina)
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Tuple, Optional

# ── Core ──────────────────────────────────────────────────────────────────
CORE_PARENT = Path(r"C:\Users\conno\Downloads\SAS-Semántico\SAS\SAS")
sys.path.insert(0, str(CORE_PARENT))

from core.tribunal_multimetrico import TribunalMultimetrico, KAPPA_D, COMBINER_WEIGHTS

# ── Rutas ─────────────────────────────────────────────────────────────────
CORPUS = Path(r"C:\ProgramData\benchmark_corpus")
SUITES = ["halueval_dialogue", "halueval_qa", "truthfulqa"]
N_PER_SUITE = 600
SEED = 42
KAPPA_R = 0.15
OUTPUT = Path(r"C:\Users\conno\Downloads\SAS-Semántico\reports\pairs_conditions_1800_seed42.json")

# ── Marcadores exactos (con espacio final, tal como aparecen en A) ────────
MARCADORES = {
    "halueval_dialogue": "Correct response: ",
    "halueval_qa": "Correct answer: ",
    "truthfulqa": "Correct answer: ",
}

# Patrón para detectar etiquetas prohibidas como A'
RE_ETIQUETA = re.compile(r'^(Dialogue|Knowledge|Question|Context)\s*:', re.IGNORECASE)


def partir_a(texto_a: str, suite: str) -> Tuple[Optional[str], Optional[str]]:
    """Divide A en (contexto, A').

    contexto = texto anterior al marcador (sin incluirlo)
    A' = texto posterior al marcador

    Si el marcador no aparece, devuelve (None, None).
    """
    marcador = MARCADORES[suite]
    idx = texto_a.find(marcador)
    if idx == -1:
        return None, None
    contexto = texto_a[:idx].rstrip()
    a_prime = texto_a[idx + len(marcador):].strip()
    return contexto, a_prime


def construir_a_pp(texto_a: str, suite: str, b: str) -> str:
    """Construye A'' = prefijo (texto hasta el marcador inclusive) + B.

    Preserva el separador original entre contexto y marcador.
    """
    marcador = MARCADORES[suite]
    idx = texto_a.find(marcador)
    if idx == -1:
        raise RuntimeError(f"Marcador '{marcador}' no encontrado en A (suite={suite})")
    prefijo = texto_a[:idx + len(marcador)]
    return prefijo + b


def cargar_muestra() -> Tuple[List[dict], List[str], List[str], List[str], List[str]]:
    """Carga los 1,800 pares con el mismo muestreo que validacion_1800_stratified_v3.py.

    Returns:
        metadatos:  lista de dicts con suite, id, archivo_a, archivo_b
        textos_a:   lista de textos A completos
        textos_b:   lista de textos B completos
        textos_ap:  lista de A' extraídos
        contextos:  lista de contextos (todo antes del marcador en A)
    """
    metadatos: List[dict] = []
    textos_a: List[str] = []
    textos_b: List[str] = []
    textos_ap: List[str] = []
    contextos: List[str] = []

    for suite in SUITES:
        suite_dir = CORPUS / suite
        if not suite_dir.exists():
            print(f"  [WARN] Suite no encontrada: {suite_dir}")
            continue

        clean_files = sorted(suite_dir.glob("*_A_clean.txt"))

        candidatos = []
        for cf in clean_files:
            hf = cf.with_name(cf.name.replace("_A_clean.txt", "_B_hallucination.txt"))
            if not hf.exists():
                continue
            try:
                a = cf.read_text(encoding="utf-8", errors="replace").strip()
                b = hf.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                continue
            if not a or not b:
                continue
            candidatos.append((cf, hf, a, b))

        rng = random.Random(SEED)
        muestra = rng.sample(candidatos, min(N_PER_SUITE, len(candidatos)))

        for cf, hf, a, b in muestra:
            pair_id = cf.name.replace("_A_clean.txt", "")
            ctx, ap = partir_a(a, suite)
            metadatos.append({
                "suite": suite,
                "id": pair_id,
                "archivo_a": str(cf),
                "archivo_b": str(hf),
            })
            textos_a.append(a)
            textos_b.append(b)
            textos_ap.append(ap)
            contextos.append(ctx)

    # ── Verificar contra isi_por_par_1800_seed42.json ───────────────────
    ids_ordenados = sorted(md["id"] for md in metadatos)
    hash_ids = hashlib.sha256("\n".join(ids_ordenados).encode()).hexdigest()
    print(f"  SHA-256 de IDs ordenados: {hash_ids}")

    ref_path = Path(r"C:\Users\conno\Downloads\SAS-Semántico\variado\sas-multimetric-tribunal\reports\isi_por_par_1800_seed42.json")
    if not ref_path.exists():
        print(f"  ❌ No se encontró {ref_path}")
        print(f"  ABORTANDO — el script necesita isi_por_par_1800_seed42.json para verificar el muestreo.")
        sys.exit(1)

    with open(ref_path, "r", encoding="utf-8") as f:
        ref_data = json.load(f)

    if not isinstance(ref_data, list) or len(ref_data) == 0:
        print(f"  ❌ {ref_path.name} no es una lista con al menos un elemento")
        print(f"  ABORTANDO.")
        sys.exit(1)

    if not isinstance(ref_data[0], dict) or "id" not in ref_data[0]:
        print(f"  ❌ Los elementos de {ref_path.name} no tienen campo 'id'")
        print(f"  Primer elemento: {str(ref_data[0])[:200]}")
        print(f"  ABORTANDO.")
        sys.exit(1)

    ref_ids = [item["id"] for item in ref_data]
    ref_ids_sorted = sorted(ref_ids)
    hash_ref = hashlib.sha256("\n".join(ref_ids_sorted).encode()).hexdigest()
    print(f"  SHA-256 de IDs en {ref_path.name}: {hash_ref}")

    if hash_ids != hash_ref:
        print(f"  ❌ LOS HASHES NO COINCIDEN — el muestreo difiere del de isi_por_par_1800_seed42.json")
        set_actual = set(ids_ordenados)
        set_ref = set(ref_ids_sorted)
        solo_actual = set_actual - set_ref
        solo_ref = set_ref - set_actual
        if solo_actual:
            print(f"  IDs solo en muestra actual (primeros 10): {sorted(solo_actual)[:10]}")
        if solo_ref:
            print(f"  IDs solo en referencia (primeros 10): {sorted(solo_ref)[:10]}")
        diff_count = 0
        for a, b in zip(ids_ordenados, ref_ids_sorted):
            if a != b:
                diff_count += 1
                if diff_count <= 10:
                    print(f"  Diff #{diff_count}: actual={a}  ref={b}")
        print(f"  ABORTANDO.")
        sys.exit(1)
    else:
        print(f"  ✅ IDs coinciden exactamente con {ref_path.name}")

    return metadatos, textos_a, textos_b, textos_ap, contextos


def validar_extraccion(metadatos, textos_a, textos_ap):
    """Valida A': imprime 5 ejemplos por suite, aborta si hay inválidos."""
    print("=" * 72)
    print("  VALIDACIÓN PREVIA — EXTRACCIÓN DE A'")
    print("=" * 72)

    abortar = False
    problemas = []

    for suite in SUITES:
        print(f"\n  ── {suite} ──")
        count = 0
        for md, a, ap in zip(metadatos, textos_a, textos_ap):
            if md["suite"] != suite:
                continue
            if count < 5:
                count += 1
                a_short = a[:80].replace("\n", "\\n")
                ap_short = (ap or "None")[:200].replace("\n", "\\n")
                print(f"    [{md['id']}]")
                print(f"      A (80 chars): {a_short}")
                print(f"      A' (completo): {ap_short}")
                print()

        for md, ap in zip(metadatos, textos_ap):
            if md["suite"] != suite:
                continue
            if ap is None:
                problemas.append((md["suite"], md["id"], "None (marcador no encontrado)"))
                abortar = True
            elif not ap:
                problemas.append((md["suite"], md["id"], "string vacío"))
                abortar = True
            elif RE_ETIQUETA.match(ap):
                problemas.append((md["suite"], md["id"], f"etiqueta: {ap[:60]}"))
                abortar = True

    if abortar:
        print("\n  ❌ VALIDACIÓN FALLÓ — IDs problemáticos:")
        for s, pid, razon in problemas:
            print(f"    [{s}/{pid}] {razon}")
        print("\n  ABORTANDO. Revisar los patrones de extracción.")
        sys.exit(1)
    else:
        print("  ✅ VALIDACIÓN PASÓ — todos los A' válidos")


def validar_identidad(tribunal, textos_a, metadatos):
    """Corre A→A y verifica que todos den ISI_final = 1.0000."""
    print("\n  ── Validación A→A (identidad) ──")
    for i, (md, a) in enumerate(zip(metadatos, textos_a)):
        v = tribunal.evaluar(a, a, request_id=f"{md['suite']}_{md['id']}_AA")
        if v.isi_final != 1.0:
            print(f"  ❌ [{md['suite']}/{md['id']}] ISI_final = {v.isi_final:.6f} (esperado 1.0000)")
            print(f"  ABORTANDO — A→A debe dar ISI_final = 1.0000 para todos los pares.")
            sys.exit(1)
        if (i + 1) % 600 == 0:
            print(f"    {i+1}/{len(textos_a)} OK")
    print(f"  ✅ {len(textos_a)}/{len(textos_a)} pares A→A con ISI_final = 1.0000")


def evaluar_condiciones(tribunal, textos_a, textos_b, textos_ap, contextos, metadatos):
    """Evalúa las 4 condiciones y devuelve lista plana de 7,200 objetos."""
    resultados = []
    t0 = time.time()

    for i, (md, a, b, ap, ctx) in enumerate(zip(metadatos, textos_a, textos_b, textos_ap, contextos)):
        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  Par {i+1}/{len(metadatos)} ({elapsed:.0f}s) ...")

        a_pp = construir_a_pp(a, md["suite"], b)

        pares = [
            ("A_A", a, a),
            ("A_Ap", a, ap),
            ("A_B", a, b),
            ("A_App", a, a_pp),
        ]

        for cond_name, src, rsp in pares:
            v = tribunal.evaluar(src, rsp, request_id=f"{md['suite']}_{md['id']}_{cond_name}")

            if not hasattr(v, "isi_hard"):
                raise RuntimeError(
                    f"v.isi_hard no existe en el objeto del tribunal. "
                    f"Versión del core incompatible. Atributos disponibles: "
                    f"{[a for a in dir(v) if not a.startswith('_')]}"
                )

            modulos_dict = {}
            modulos_disparados = []
            for ev in v.todas_las_evidencias:
                modulos_dict[f"score_{ev.nombre}"] = round(ev.valor, 6)
                if ev.disparo:
                    modulos_disparados.append(ev.nombre)

            # isi_avg = Σ(w_i × score_i) sobre los 7 módulos (pesos de Tabla 1)
            peso_map = {
                "lexical_baseline_score": "lexical_baseline",
                "source_target_guard": "source_target_guard",
                "flow_penalty": "flow_penalty",
                "negation_penalty": "negation_penalty",
                "cre_isi": "cre_isi",
                "arithmetic_penalty": "arithmetic_penalty",
                "reference_penalty": "reference_penalty",
            }
            isi_avg = 0.0
            for ev in v.todas_las_evidencias:
                wkey = peso_map.get(ev.nombre)
                if wkey and wkey in COMBINER_WEIGHTS:
                    isi_avg += COMBINER_WEIGHTS[wkey] * ev.valor
            isi_avg = round(isi_avg, 6)

            entry = {
                "suite": md["suite"],
                "id": md["id"],
                "condicion": cond_name,
                "isi_final": round(v.isi_final, 6),
                "isi_hard": round(v.isi_hard, 6),
                "isi_avg": isi_avg,
                "zona": v.codigo_zona,
                "modulos_disparados": modulos_disparados,
                **modulos_dict,
            }
            resultados.append(entry)

    return resultados


def mediana(vals):
    """Mediana de una lista de números. Para n par, promedio de los dos centrales."""
    vs = sorted(vals)
    n = len(vs)
    if n == 0:
        return 0.0
    if n % 2 == 1:
        return vs[n // 2]
    return (vs[n // 2 - 1] + vs[n // 2]) / 2


def reportar(resultados, metadatos, textos_ap, textos_b):
    """Reporte completo en stdout."""
    print("\n" + "=" * 72)
    print("  REPORTE CONTROL N1")
    print("=" * 72)

    # ── a) Estadísticas por suite y condición ─────────────────────────────
    print("\n  a) Estadísticas por suite y condición")
    print("-" * 72)
    for suite in SUITES:
        print(f"\n  ── {suite} ──")
        for cond in ["A_A", "A_Ap", "A_B", "A_App"]:
            vals = [r["isi_final"] for r in resultados
                    if r["suite"] == suite and r["condicion"] == cond]
            if not vals:
                continue
            n = len(vals)
            mdn = mediana(vals)
            media = sum(vals) / n
            vs = sorted(vals)
            p10 = vs[int(n * 0.1)]
            p90 = vs[int(n * 0.9)]
            print(f"    {cond}: n={n}  mediana={mdn:.4f}  media={media:.4f}  p10={p10:.4f}  p90={p90:.4f}")

    # ── b) ΔISI = isi_final(A_Ap) − isi_final(A_B) ───────────────────────
    print("\n  b) ΔISI = isi_final(A_Ap) − isi_final(A_B)")
    print("-" * 72)
    deltas_global = []
    for suite in SUITES:
        deltas = []
        ids_suite = set(r["id"] for r in resultados if r["suite"] == suite)
        for pid in ids_suite:
            ap_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_Ap"]
            b_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_B"]
            if ap_r and b_r:
                d = ap_r[0]["isi_final"] - b_r[0]["isi_final"]
                deltas.append(d)
                deltas_global.append(d)
        n_pos = sum(1 for d in deltas if d > 0)
        n_neg = sum(1 for d in deltas if d < 0)
        n_cero = sum(1 for d in deltas if d == 0)
        mdn = mediana(deltas)
        print(f"    {suite}: n={len(deltas)}  Δ>0={n_pos}  Δ<0={n_neg}  Δ=0={n_cero}  mediana_Δ={mdn:.4f}")

    # ── c) Matriz 2×2: A_Ap vs A_B, ambos vs κD ──────────────────────────
    print("\n  c) Matriz 2×2: A_Ap vs A_B (κD=0.56)")
    print("-" * 72)
    global_2x2 = {"ambos_marc": 0, "solo_Ap": 0, "solo_B": 0, "ninguno": 0}
    for suite in SUITES:
        suite_2x2 = {"ambos_marc": 0, "solo_Ap": 0, "solo_B": 0, "ninguno": 0}
        ids_suite = set(r["id"] for r in resultados if r["suite"] == suite)
        for pid in ids_suite:
            ap_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_Ap"]
            b_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_B"]
            if not ap_r or not b_r:
                continue
            ap_marc = ap_r[0]["isi_final"] < KAPPA_D
            b_marc = b_r[0]["isi_final"] < KAPPA_D
            if ap_marc and b_marc:
                suite_2x2["ambos_marc"] += 1
                global_2x2["ambos_marc"] += 1
            elif ap_marc and not b_marc:
                suite_2x2["solo_Ap"] += 1
                global_2x2["solo_Ap"] += 1
            elif not ap_marc and b_marc:
                suite_2x2["solo_B"] += 1
                global_2x2["solo_B"] += 1
            else:
                suite_2x2["ninguno"] += 1
                global_2x2["ninguno"] += 1
        t = sum(suite_2x2.values())
        print(f"    {suite}: total={t}")
        print(f"      Ap marcado & B marcado: {suite_2x2['ambos_marc']}")
        print(f"      Ap marcado & B NO:      {suite_2x2['solo_Ap']}")
        print(f"      Ap NO & B marcado:      {suite_2x2['solo_B']}")
        print(f"      Ap NO & B NO:           {suite_2x2['ninguno']}")

    tg = sum(global_2x2.values())
    print(f"\n    GLOBAL: total={tg}")
    print(f"      Ap marcado & B marcado: {global_2x2['ambos_marc']}")
    print(f"      Ap marcado & B NO:      {global_2x2['solo_Ap']}")
    print(f"      Ap NO & B marcado:      {global_2x2['solo_B']}")
    print(f"      Ap NO & B NO:           {global_2x2['ninguno']}")

    # ── d) 10 ejemplos por cada celda de (c) ─────────────────────────────
    print("\n  d) 10 ejemplos por celda de la matriz 2×2")
    print("-" * 72)

    ejemplos = {"ambos_marc": [], "solo_Ap": [], "solo_B": [], "ninguno": []}
    ids_global = set(r["id"] for r in resultados)
    for pid in ids_global:
        for suite in SUITES:
            ap_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_Ap"]
            b_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_B"]
            if not ap_r or not b_r:
                continue
            ap_marc = ap_r[0]["isi_final"] < KAPPA_D
            b_marc = b_r[0]["isi_final"] < KAPPA_D
            if ap_marc and b_marc and len(ejemplos["ambos_marc"]) < 10:
                ejemplos["ambos_marc"].append((suite, pid))
            elif ap_marc and not b_marc and len(ejemplos["solo_Ap"]) < 10:
                ejemplos["solo_Ap"].append((suite, pid))
            elif not ap_marc and b_marc and len(ejemplos["solo_B"]) < 10:
                ejemplos["solo_B"].append((suite, pid))
            elif not ap_marc and not b_marc and len(ejemplos["ninguno"]) < 10:
                ejemplos["ninguno"].append((suite, pid))

    for cat_key, cat_label in [("ambos_marc", "Ambos marcados"),
                                ("solo_Ap", "Solo A_Ap marcado"),
                                ("solo_B", "Solo A_B marcado"),
                                ("ninguno", "Ninguno marcado")]:
        print(f"\n    [{cat_label}]")
        for suite, pid in ejemplos[cat_key]:
            def get(suite, pid, cond):
                return [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == cond][0]
            r_a = get(suite, pid, "A_A")
            r_ap = get(suite, pid, "A_Ap")
            r_b = get(suite, pid, "A_B")
            r_app = get(suite, pid, "A_App")
            idx = next(i for i, md in enumerate(metadatos) if md["suite"] == suite and md["id"] == pid)
            ap_full = (textos_ap[idx] or "None")[:200]
            b_full = (textos_b[idx] or "None")[:200]
            print(f"      [{suite}/{pid}]")
            print(f"        A→A:   isi={r_a['isi_final']:.4f}  zona={r_a['zona']}")
            print(f"        A→A':  isi={r_ap['isi_final']:.4f}  zona={r_ap['zona']}  mods={r_ap['modulos_disparados']}")
            print(f"        A→B:   isi={r_b['isi_final']:.4f}  zona={r_b['zona']}  mods={r_b['modulos_disparados']}")
            print(f"        A→A'': isi={r_app['isi_final']:.4f}  zona={r_app['zona']}  mods={r_app['modulos_disparados']}")
            print(f"        A'={ap_full}")
            print(f"        B={b_full}")

    # ── e) A_App vs A_B ──────────────────────────────────────────────────
    print("\n  e) ΔISI = isi_final(A_App) − isi_final(A_B)")
    print("-" * 72)
    deltas_app_global = []
    for suite in SUITES:
        deltas = []
        ids_suite = set(r["id"] for r in resultados if r["suite"] == suite)
        for pid in ids_suite:
            app_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_App"]
            b_r = [r for r in resultados if r["suite"] == suite and r["id"] == pid and r["condicion"] == "A_B"]
            if app_r and b_r:
                d = app_r[0]["isi_final"] - b_r[0]["isi_final"]
                deltas.append(d)
                deltas_app_global.append(d)
        n_pos = sum(1 for d in deltas if d > 0)
        n_neg = sum(1 for d in deltas if d < 0)
        n_cero = sum(1 for d in deltas if d == 0)
        mdn = mediana(deltas)
        print(f"    {suite}: n={len(deltas)}  Δ>0={n_pos}  Δ<0={n_neg}  Δ=0={n_cero}  mediana_Δ={mdn:.4f}")

    # ── f) A_A vs A_Ap: cuántos pares tienen A_Ap marcado ────────────────
    print("\n  f) Comparación A_A vs A_Ap")
    print("-" * 72)
    marcados_ap = [r for r in resultados if r["condicion"] == "A_Ap" and r["zona"] != "A"]
    if marcados_ap:
        print(f"    {len(marcados_ap)} pares tienen A_Ap marcado (zona != A):")
        for r in marcados_ap[:20]:
            r_a = [x for x in resultados if x["suite"] == r["suite"] and x["id"] == r["id"] and x["condicion"] == "A_A"][0]
            print(f"      [{r['suite']}/{r['id']}] A_A: {r_a['zona']} isi={r_a['isi_final']:.4f}  |  A_Ap: {r['zona']} isi={r['isi_final']:.4f}  mods={r['modulos_disparados']}")
        if len(marcados_ap) > 20:
            print(f"      ... y {len(marcados_ap) - 20} más")
    else:
        print("    ✅ Ningún par tiene A_Ap marcado (todos zona=A)")

    # ── RESUMEN EJECUTIVO ─────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  RESUMEN EJECUTIVO")
    print("=" * 72)
    for cond in ["A_A", "A_Ap", "A_B", "A_App"]:
        vals = [r["isi_final"] for r in resultados if r["condicion"] == cond]
        n = len(vals)
        mdn = mediana(vals)
        print(f"  {cond}: n={n}  mediana_isi={mdn:.4f}")
    tg = sum(global_2x2.values())
    print(f"  Matriz 2×2 global: ambos={global_2x2['ambos_marc']}  solo_Ap={global_2x2['solo_Ap']}  solo_B={global_2x2['solo_B']}  ninguno={global_2x2['ninguno']}  (total={tg})")
    mdn_b = mediana(deltas_global)
    print(f"  Mediana ΔISI(A_Ap − A_B): {mdn_b:.4f}")
    mdn_e = mediana(deltas_app_global)
    print(f"  Mediana ΔISI(A_App − A_B): {mdn_e:.4f}")
    print(f"  Pares con A_Ap marcado (zona != A): {len(marcados_ap)}")


def main():
    print("=" * 72)
    print("  CONTROL N1 — 4 CONDICIONES SOBRE 1,800 IDs (seed=42)")
    print(f"  Suites: {', '.join(SUITES)}")
    print(f"  Muestra: {N_PER_SUITE} por suite, seed={SEED}")
    print(f"  κD={KAPPA_D}, κR={KAPPA_R}")
    print("=" * 72)

    t_start = time.time()

    # 1. Cargar muestra
    print("\n[1/5] Cargando muestra estratificada...")
    metadatos, textos_a, textos_b, textos_ap, contextos = cargar_muestra()
    print(f"  Total pares: {len(metadatos)}")

    # 2. Validar extracción de A'
    print("\n[2/5] Validando extracción de A'...")
    validar_extraccion(metadatos, textos_a, textos_ap)

    # 3. Verificar contextos
    print("\n[3/5] Verificando contextos...")
    ctx_none = [(md, ctx) for md, ctx in zip(metadatos, contextos) if ctx is None]
    if ctx_none:
        print(f"  ❌ {len(ctx_none)} contextos son None — ABORTANDO")
        for md, _ in ctx_none[:5]:
            print(f"    [{md['suite']}/{md['id']}]")
        sys.exit(1)
    print(f"  ✅ {len(metadatos) - len(ctx_none)} contextos válidos")

    # 4. Configurar tribunal
    print("\n[4/5] Configurando tribunal...")
    tribunal = TribunalMultimetrico(kappa_d=KAPPA_D, kappa_r=KAPPA_R)
    modulos = tribunal._modulos_cargados
    print(f"  Módulos cargados: {modulos}")

    # Mapeo: nombres del paper → nombres internos en _modulos_cargados
    MODULOS_PAPER = [
        "lexical_baseline_score",
        "source_target_guard",
        "flow_penalty",
        "negation_penalty",
        "cre_isi",
        "arithmetic_penalty",
        "reference_penalty",
    ]
    MAPEO_MODULOS = {
        "lexical_baseline_score": None,  # no requiere módulo externo
        "source_target_guard": None,
        "flow_penalty": "flow_coherence",
        "negation_penalty": "negation_probe",
        "cre_isi": "ricci_enhanced_cre",
        "arithmetic_penalty": "arithmetic_detector",
        "reference_penalty": "reference_check",
    }
    for nombre_paper in MODULOS_PAPER:
        nombre_interno = MAPEO_MODULOS.get(nombre_paper)
        if nombre_interno is None:
            continue  # módulo sin dependencia externa, siempre disponible
        if not modulos.get(nombre_interno, False):
            raise RuntimeError(
                f"Módulo del paper '{nombre_paper}' requiere '{nombre_interno}' "
                f"pero no está cargado. Módulos disponibles: {modulos}"
            )
    print(f"  ✅ Los 7 módulos del paper están disponibles")

    # 4d. Verificar que los 7 módulos producen evidencia en una evaluación real
    print("\n[4d/5] Verificando que los 7 módulos producen evidencia...")
    v_test = tribunal.evaluar(textos_a[0], textos_b[0], request_id="test_modulos")
    nombres_evidencia = {ev.nombre for ev in v_test.todas_las_evidencias}
    MODULOS_PAPER_SET = set(MODULOS_PAPER)
    faltantes = MODULOS_PAPER_SET - nombres_evidencia
    if faltantes:
        print(f"  ❌ Faltan {len(faltantes)} módulo(s) en la evidencia del tribunal:")
        for m in sorted(faltantes):
            print(f"      - {m}")
        print(f"  Nombres presentes ({len(nombres_evidencia)}): {sorted(nombres_evidencia)}")
        sys.exit(1)
    print(f"  ✅ Los 7 módulos producen evidencia en la evaluación")

    # 5. Validar identidad (A→A debe dar ISI_final = 1.0000)
    print("\n[4b/5] Validando condición A→A (identidad)...")
    validar_identidad(tribunal, textos_a, metadatos)

    # 5b. Verificar formato de A'' con 3 ejemplos
    print("\n[4c/5] Verificando formato de A'' (3 ejemplos)...")
    for i in range(min(3, len(metadatos))):
        md = metadatos[i]
        a = textos_a[i]
        b = textos_b[i]
        a_pp = construir_a_pp(a, md["suite"], b)
        marcador = MARCADORES[md["suite"]]
        idx_a = a.find(marcador)
        idx_app = a_pp.find(marcador)
        if idx_a == -1 or idx_app == -1:
            print(f"  ❌ [{md['suite']}/{md['id']}] Marcador '{marcador}' no encontrado en A o A''")
            sys.exit(1)
        # Verificar que el prefijo hasta el marcador sea idéntico
        prefijo_a = a[:idx_a + len(marcador)]
        prefijo_app = a_pp[:idx_app + len(marcador)]
        if prefijo_a != prefijo_app:
            print(f"  ❌ [{md['suite']}/{md['id']}] El prefijo hasta el marcador difiere")
            print(f"    A:   {prefijo_a[:100]}")
            print(f"    A'': {prefijo_app[:100]}")
            sys.exit(1)
        print(f"    [{md['suite']}/{md['id']}] ✅ formato coincide")
        print(f"      A (300 chars):   {a[:300]}")
        print(f"      A'' (300 chars): {a_pp[:300]}")
        print()
    print(f"  ✅ Formato de A'' verificado en {min(3, len(metadatos))} ejemplos")

    # 6. Evaluar 4 condiciones
    print("\n[5/5] Evaluando 4 condiciones por par...")
    resultados = evaluar_condiciones(tribunal, textos_a, textos_b, textos_ap, contextos, metadatos)

    # Ordenar por (suite, id, condicion)
    orden_cond = {"A_A": 0, "A_Ap": 1, "A_B": 2, "A_App": 3}
    resultados.sort(key=lambda r: (SUITES.index(r["suite"]) if r["suite"] in SUITES else 99,
                                    r["id"],
                                    orden_cond.get(r["condicion"], 99)))

    # Guardar JSON
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "experimento": "Control N1 — 4 condiciones sobre 1,800 IDs",
                "seed": SEED,
                "kappa_d": KAPPA_D,
                "kappa_r": KAPPA_R,
                "suites": SUITES,
                "n_per_suite": N_PER_SUITE,
                "total_pares": len(metadatos),
                "total_entradas": len(resultados),
                "condiciones": ["A_A", "A_Ap", "A_B", "A_App"],
                "fecha": "2026-10-09",
            },
            "resultados": resultados,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  Resultados guardados en: {OUTPUT}")
    print(f"  Total entradas: {len(resultados)} ({len(metadatos)} IDs × 4 condiciones)")

    # Reporte
    reportar(resultados, metadatos, textos_ap, textos_b)

    t_elapsed = time.time() - t_start
    print(f"\n  Tiempo total: {t_elapsed:.0f}s ({t_elapsed / 60:.1f}min)")

    print("\n" + "=" * 72)
    print("  CONTROL N1 COMPLETADO")
    print("=" * 72)


if __name__ == "__main__":
    main()