#!/usr/bin/env python3
"""
04_check_module_precision.py — Mide precisión, recall y pureza de disparo
por módulo sobre el piloto controlado Subset A.

Lee results_pilot_A.jsonl y compara expected_trigger contra fired_modules.

CHANGELOG DE CORRECCIONES APLICADAS
------------------------------------
[BLOCKER][interno H7]
    La métrica llamada "precisión" en la versión original era en realidad
    RECALL (aciertos / total_esperado_para_ese_módulo). Ahora:
      - recall[m]    = TP[m] / esperado[m]           (lo que antes se
                        llamaba "precisión")
      - precision[m] = TP[m] / (TP[m] + FP[m])        (precisión real,
                        contando falsos positivos sobre TODOS los ítems,
                        no solo los que tenían a m como esperado)
    Ambas se reportan con su nombre correcto.

[BLOCKER][interno H8 / Kimi H9]
    Se agregan métricas de PUREZA, ausentes en la versión original:
      - puro[m]        = ítems donde fired_modules == {m} exactamente
                          (acierto sin ningún módulo extra)
      - pureza[m]       = puro[m] / esperado[m]
      - pureza_global    = sum(puro) / total_con_expected
    El veredicto final ahora exige precisión Y pureza, no solo recall.

[INFO][Kimi H10]
    Se agrega desglose por (módulo, dominio): un módulo puede tener buen
    recall global pero fallar sistemáticamente en un dominio específico,
    y eso quedaba enmascarado en el reporte agregado.

[INFO][Kimi H12]
    Se agrega un conteo de frecuencia de "extras" (Counter por par
    esperado->extra), en vez de solo listar qué módulos aparecieron sin
    contar cuántas veces, para poder distinguir un módulo "sucio"
    (dispara casi siempre) de contaminación esporádica.

[WARNING][autoaudit]
    "for m in fired: if m in MODULES: fired_total[m] += 1" descartaba en
    silencio cualquier nombre de módulo disparado que no coincidiera
    exactamente con MODULES (typos del core, distinto casing, o el
    fallback usado en 03 cuando falta el atributo .nombre). Eso es
    exactamente el tipo de fallo silencioso que se auditó en los otros 3
    scripts, colado en el propio script de métricas. Ahora se cuentan y
    reportan como "fired_no_reconocidos".

[WARNING][Gemini pt.1, mecanismo ajustado]
    Gemini señaló correctamente que excluir fired_no_reconocidos del
    cálculo infla precision_global artificialmente. Se evaluó (y se
    descartó) sumarlos directamente al denominador de FP global: eso
    mezclaría dos tipos de error distintos bajo un solo número — falla de
    CALIBRACIÓN del detector (FP real) vs. falla de INTERFAZ (nombre no
    mapeado) — y haría el número resultante ambiguo de interpretar. En su
    lugar: la fórmula de precisión queda como está (solo sobre nombres
    reconocidos), pero CUALQUIER fired_no_reconocidos no vacío bloquea
    automáticamente el veredicto final "piloto limpio", sin importar qué
    tan bien den las demás métricas.

[INFO][auditoría del core real]
    _calcular_source_target_guard() en el core también dispara ante
    CUALQUIER cambio de un número suelto en el texto (rama de "mutación
    de cantidades", cualquier número suelto en el texto), no solo ante cambios de ubicación.
    Como arithmetic_penalty funciona justamente cambiando un número, es
    ESPERABLE que source_target_guard aparezca como "extra" en casi
    todos los ítems de arithmetic_penalty — no es contaminación del
    diseño del corpus, es una característica real de cómo el core
    define "mutación de entidad" hoy. El reporte por módulo lo anota
    explícitamente para este par para no confundirlo con un hallazgo
    nuevo cada vez que se corra el piloto.

[INFO][interno H5]
    Reconciliación: si existen corpus_pilot_A_raw.jsonl y/o
    results_pilot_A_failed.jsonl, se reporta explícitamente cuántos ítems
    del corpus original NO llegaron a este análisis (por fallos de
    inferencia), en vez de calcular las métricas silenciosamente sobre lo
    que haya sobrevivido.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_FILE = Path("results_pilot_A.jsonl")
RAW_CORPUS_FILE = Path("corpus_pilot_A_raw.jsonl")
FAILED_FILE = Path("results_pilot_A_failed.jsonl")

MODULES = [
    "lexical_baseline_score",
    "source_target_guard",
    "cre_isi",
    "flow_penalty",
    "negation_penalty",
    "arithmetic_penalty",
    "reference_penalty",
]


def cargar_jsonl(path):
    if not path.exists():
        return None
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[ERROR] JSON inválido en {path}: {e}")
                sys.exit(1)
    return items


def extraer_modulo_esperado(item):
    trigger = item.get("expected_trigger")
    if not isinstance(trigger, list) or len(trigger) != len(MODULES):
        return None
    if sum(trigger) != 1:
        return None
    idx = trigger.index(1)
    return MODULES[idx]


def main():
    items = cargar_jsonl(RESULTS_FILE)
    if items is None:
        print(f"[ERROR] No existe {RESULTS_FILE}")
        sys.exit(1)
    total = len(items)

    # ── Reconciliación contra corpus original / fallidos ────────────────
    raw = cargar_jsonl(RAW_CORPUS_FILE)
    fallidos = cargar_jsonl(FAILED_FILE)
    if raw is not None and len(raw) != total:
        faltan = len(raw) - total - (len(fallidos) if fallidos else 0)
        print("=" * 64)
        print("[ATENCIÓN] RECONCILIACIÓN")
        print("=" * 64)
        print(f" Corpus original ({RAW_CORPUS_FILE}) : {len(raw)} ítems")
        print(f" Resultados analizados ({RESULTS_FILE}): {total} ítems")
        if fallidos:
            print(f" Fallidos registrados ({FAILED_FILE}) : {len(fallidos)}")
        if faltan != 0:
            print(f" [ERROR DE RECONCILIACIÓN] {faltan} ítems del corpus "
                  f"original no están ni en resultados ni en fallidos.")
        print()

    # ── Acumuladores ─────────────────────────────────────────────────────
    esperado = Counter()             # esperado[m] = veces que m era el módulo esperado
    fired_total = Counter()          # fired_total[m] = veces que m disparó, sobre TODOS los ítems
    tp = Counter()                   # tp[m] = m era esperado y m disparó
    puro = Counter()                 # puro[m] = tp[m] y ningún módulo extra disparó
    fallos = Counter()               # fallos[m] = m era esperado y NO disparó
    extras_por_esperado = defaultdict(Counter)  # extras_por_esperado[esperado][extra] = frecuencia
    por_dominio_modulo = defaultdict(lambda: {"esperado": 0, "aciertos": 0})

    items_con_extra = 0
    items_sin_expected = 0
    fired_no_reconocidos = Counter()

    for item in items:
        expected = extraer_modulo_esperado(item)
        sas = item.get("sas_result") or {}
        fired = set(sas.get("fired_modules") or [])

        for m in fired:
            if m in MODULES:
                fired_total[m] += 1
            else:
                fired_no_reconocidos[m] += 1

        if expected is None:
            items_sin_expected += 1
            continue

        esperado[expected] += 1
        dominio = item.get("domain", "?")
        por_dominio_modulo[(dominio, expected)]["esperado"] += 1

        if expected in fired:
            tp[expected] += 1
            por_dominio_modulo[(dominio, expected)]["aciertos"] += 1
        else:
            fallos[expected] += 1

        extras = fired - {expected}
        if extras:
            items_con_extra += 1
            for e in extras:
                if e in MODULES:
                    extras_por_esperado[expected][e] += 1
        else:
            if expected in fired:
                puro[expected] += 1

    total_con_expected = sum(esperado.values())

    if fired_no_reconocidos:
        print("=" * 64)
        print("[ATENCIÓN] MÓDULOS DISPARADOS NO RECONOCIDOS")
        print("=" * 64)
        print(" Estos nombres aparecieron en fired_modules pero NO están en")
        print(" MODULES. Se excluyen de todas las métricas de abajo. Esto")
        print(" puede indicar un desajuste de nombres en el core, un typo,")
        print(" o el fallback str(m) de 03 activándose:")
        for nombre, freq in sorted(fired_no_reconocidos.items(),
                                    key=lambda kv: -kv[1]):
            print(f"   - {nombre!r}: {freq} veces")
        print()

    # ── Reporte por módulo ─────────────────────────────────────────────
    print("=" * 64)
    print("RECALL / PRECISIÓN / PUREZA POR MÓDULO — SUBPILOT A")
    print("=" * 64)

    for modulo in MODULES:
        n_esperado = esperado.get(modulo, 0)
        n_tp = tp.get(modulo, 0)
        n_fallos = fallos.get(modulo, 0)
        n_puro = puro.get(modulo, 0)
        n_fired_total = fired_total.get(modulo, 0)
        n_fp = n_fired_total - n_tp  # veces que disparó sin ser el esperado

        if n_esperado == 0 and n_fired_total == 0:
            continue

        recall = (n_tp / n_esperado) if n_esperado else None
        precision = (n_tp / (n_tp + n_fp)) if (n_tp + n_fp) > 0 else None
        pureza = (n_puro / n_esperado) if n_esperado else None

        print(f"\n{modulo}")
        print(f"  Esperado (n)      : {n_esperado}")
        print(f"  Disparado (total) : {n_fired_total}  (TP={n_tp}, FP={n_fp})")
        print(f"  Faltantes         : {n_fallos}")
        print(f"  Recall            : {recall:.2%}" if recall is not None else "  Recall            : N/A")
        print(f"  Precisión         : {precision:.2%}" if precision is not None else "  Precisión         : N/A (nunca disparó)")
        print(f"  Pureza            : {pureza:.2%}" if pureza is not None else "  Pureza            : N/A")

        if extras_por_esperado.get(modulo):
            print("  Extras disparados cuando este módulo era el esperado:")
            for extra, freq in sorted(extras_por_esperado[modulo].items(),
                                       key=lambda kv: -kv[1]):
                nota = ""
                if modulo == "arithmetic_penalty" and extra == "source_target_guard":
                    nota = ("  [ESPERADO: STG dispara ante cualquier número "
                            "cambiado, ver nota en cabecera del script]")
                print(f"    - {extra}: {freq} veces{nota}")

    # ── Desglose por dominio ────────────────────────────────────────────
    print("\n" + "=" * 64)
    print("DESGLOSE POR (MÓDULO, DOMINIO) — recall")
    print("=" * 64)
    dominios = sorted({d for d, _ in por_dominio_modulo.keys()})
    for modulo in MODULES:
        fila = []
        for dominio in dominios:
            info = por_dominio_modulo.get((dominio, modulo))
            if not info or info["esperado"] == 0:
                fila.append(f"{dominio}=N/A")
                continue
            r = info["aciertos"] / info["esperado"]
            fila.append(f"{dominio}={r:.0%}")
        print(f"  {modulo:28s} " + "  ".join(fila))

    # ── Resumen global ──────────────────────────────────────────────────
    total_tp = sum(tp.values())
    total_fp = sum(fired_total.values()) - total_tp
    total_puro = sum(puro.values())
    total_extras_items = items_con_extra

    print("\n" + "=" * 64)
    print("RESUMEN GLOBAL DEL PILOTO")
    print("=" * 64)
    print(f" Ítems analizados          : {total}")
    print(f" Ítems con expected válido : {total_con_expected}")
    print(f" Ítems sin expected        : {items_sin_expected}")
    print(f" Disparos correctos (TP)   : {total_tp}")
    print(f" Disparos faltantes        : {sum(fallos.values())}")
    print(f" Falsos positivos (FP)     : {total_fp}")
    print(f" Ítems con disparo extra   : {total_extras_items}")

    if total_con_expected > 0:
        recall_global = total_tp / total_con_expected
        precision_global = (total_tp / (total_tp + total_fp)) if (total_tp + total_fp) > 0 else 0.0
        pureza_global = total_puro / total_con_expected

        print(f"\n Recall global (antes mal llamado 'precisión') : {recall_global:.2%}")
        print(f" Precisión global (TP / (TP+FP))               : {precision_global:.2%}")
        print(f" Pureza global (aciertos sin ningún extra)      : {pureza_global:.2%}")

        gate_ok = (recall_global >= 0.90 and precision_global >= 0.90
                   and pureza_global >= 0.90
                   and not fired_no_reconocidos)

        if gate_ok:
            print("\n[OK] El piloto está limpio.")
            print("Recall, precisión y pureza superan el umbral de 90%.")
            print("Podés escalar al corpus completo.")
        else:
            print("\n[ATENCIÓN] El piloto necesita ajuste.")
            if fired_no_reconocidos:
                print("Hay disparos con nombres de módulo no reconocidos "
                      "(ver arriba) — esto por sí solo invalida el "
                      "veredicto, independientemente de qué tan bien den "
                      "las demás métricas: no se puede confiar en un "
                      "recall/precisión calculado mientras haya disparos "
                      "que ni siquiera se están contando.")
            print("Revisá los módulos con recall, precisión o pureza < 90%.")
            print("No escales hasta corregir las perturbaciones o el core.")
    else:
        print("\n[ERROR] No se pudo calcular métricas: no hay expected "
              "triggers válidos.")


if __name__ == "__main__":
    main()
