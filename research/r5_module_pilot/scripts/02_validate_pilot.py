#!/usr/bin/env python3
"""
02_validate_pilot.py — Valida estructura y coherencia del piloto controlado.

No ejecuta SAS.
Solo chequea que el corpus generado sea internamente consistente.

CHANGELOG DE CORRECCIONES APLICADAS
------------------------------------
[BLOCKER][interno H3 / Kimi H5]
    Se agrega validar_id_coherente(): extrae el módulo codificado en el
    campo `id` y lo compara contra el módulo indicado por expected_trigger.
    Antes un error de mapeo módulo-perturbación en la generación pasaba
    completamente desapercibido.

[BLOCKER][interno H14 / Kimi H6]
    Se agrega validar_ground_truth(): chequea que truth_factual y
    coherence_structural sean bool, y que plausibility_score sea un float
    en [0, 1]. Antes solo se verificaba que la clave "ground_truth"
    existiera, sin mirar su contenido.

[WARNING][interno H2]
    validar_unicidad_respuestas() ahora distingue dos casos distintos:
      - "duplicado idéntico": mismo source+response Y mismo expected_trigger
        (antes esto NO se detectaba en absoluto).
      - "contaminación cruzada": mismo source+response con expected_trigger
        distinto (caso que ya se detectaba).
    Ambos se reportan, con etiquetas separadas.

[WARNING][autoaudit / Gemini pt.4]
    extraer_modulo_de_id() dependía de que `domain` no tuviera guiones
    bajos para poder recortar el prefijo con rsplit(). Se reescribió para
    comparar directamente contra la lista cerrada de MODULES, sin esa
    dependencia — robusto ante futuros dominios como "smart_contracts".

[INFO][interno H4]
    Se elimina la rama `elif trigger.index(1) < 0` en validar_estructura():
    es código muerto, ya que si `sum(trigger) == 1` entonces `.index(1)`
    siempre es >= 0.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

MODULES = [
    "lexical_baseline_score",
    "source_target_guard",
    "cre_isi",
    "flow_penalty",
    "negation_penalty",
    "arithmetic_penalty",
    "reference_penalty",
]

DOMAINS = {"finance", "legal", "biomed", "general", "narrative"}

INPUT_FILE = Path("corpus_pilot_A_raw.jsonl")


def cargar_items(path):
    items = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Línea {i}: JSON inválido: {e}")
                sys.exit(1)
            items.append(item)
    return items


def validar_estructura(item, idx):
    errores = []

    obligatorios = [
        "id", "subset", "domain", "source", "response",
        "expected_trigger", "features", "ground_truth", "sas_result"
    ]

    for campo in obligatorios:
        if campo not in item:
            errores.append(f"Falta campo {campo}")

    if not isinstance(item.get("source", ""), str) or not item["source"].strip():
        errores.append("source vacío o inválido")

    if not isinstance(item.get("response", ""), str) or not item["response"].strip():
        errores.append("response vacío o inválido")

    if item.get("subset") != "A":
        errores.append("subset debe ser A")

    if item.get("domain") not in DOMAINS:
        errores.append(f"dominio desconocido: {item.get('domain')}")

    trigger = item.get("expected_trigger")
    if not isinstance(trigger, list) or len(trigger) != len(MODULES):
        errores.append("expected_trigger inválido")
    elif sum(trigger) != 1:
        errores.append("expected_trigger debe ser one-hot")
    # (rama muerta `elif trigger.index(1) < 0` eliminada: si sum(trigger)==1
    #  entonces .index(1) siempre existe y es >= 0)

    return errores


def validar_ground_truth(item):
    """Chequea tipos dentro de ground_truth, no solo su presencia."""
    errores = []
    gt = item.get("ground_truth")

    if not isinstance(gt, dict):
        return ["ground_truth no es un objeto/dict"]

    if not isinstance(gt.get("truth_factual"), bool):
        errores.append(
            f"ground_truth.truth_factual no es bool "
            f"(valor: {gt.get('truth_factual')!r})"
        )

    if not isinstance(gt.get("coherence_structural"), bool):
        errores.append(
            f"ground_truth.coherence_structural no es bool "
            f"(valor: {gt.get('coherence_structural')!r})"
        )

    p = gt.get("plausibility_score")
    es_numero = isinstance(p, (int, float)) and not isinstance(p, bool)
    if not es_numero or not (0.0 <= float(p) <= 1.0):
        errores.append(
            f"ground_truth.plausibility_score no es float en [0,1] "
            f"(valor: {p!r})"
        )

    return errores


def extraer_modulo_de_id(item_id, domain):
    """
    Extrae el nombre del módulo codificado en el id, con el formato:
    SAS_PILOT_A_{domain}_{module}_{n:02d}

    CORRECCIÓN (auditoría Gemini, punto 4): la versión anterior recortaba
    el prefijo "SAS_PILOT_A_{domain}_" y usaba rsplit("_", 1) para separar
    el sufijo numérico, asumiendo que `domain` no contiene guiones bajos.
    Eso funciona hoy (finance/legal/biomed/general/narrative) pero se
    rompe en silencio si en el futuro se agrega un dominio como
    "smart_contracts" o "cyber_sec": el largo del prefijo se calcularía
    mal y toda la validación ID↔trigger colapsaría devolviendo None.

    Ahora, en vez de adivinar dónde termina el nombre del dominio, se
    prueba directamente contra la lista cerrada de MODULES (que es fija
    y conocida), sin depender de que domain esté libre de guiones bajos.
    """
    if not isinstance(item_id, str):
        return None

    for modulo in MODULES:
        prefix = f"SAS_PILOT_A_{domain}_{modulo}_"
        if item_id.startswith(prefix):
            resto = item_id[len(prefix):]
            if resto.isdigit():
                return modulo

    return None


def validar_id_coherente(item):
    """
    Verifica que el módulo codificado en el id coincida con el módulo
    indicado por expected_trigger. Antes NO existía ningún chequeo de esto:
    un error de mapeo módulo-perturbación en la generación pasaba
    desapercibido en la validación estructural.
    """
    trigger = item.get("expected_trigger")
    if not isinstance(trigger, list) or sum(trigger) != 1:
        return None  # ya reportado por validar_estructura

    modulo_esperado = MODULES[trigger.index(1)]
    modulo_en_id = extraer_modulo_de_id(item.get("id"), item.get("domain"))

    if modulo_en_id is None:
        return f"No se pudo extraer el módulo del id: {item.get('id')!r}"

    if modulo_en_id != modulo_esperado:
        return (
            f"Id/trigger inconsistentes: id indica '{modulo_en_id}' pero "
            f"expected_trigger apunta a '{modulo_esperado}'"
        )
    return None


def validar_unicidad_respuestas(items):
    """
    Dentro de cada dominio, detecta pares de ítems con exactamente el mismo
    source y response, distinguiendo dos casos:
      - mismo expected_trigger -> "duplicado idéntico" (antes indetectado)
      - distinto expected_trigger -> "contaminación cruzada"
    """
    por_dominio = defaultdict(list)
    for item in items:
        por_dominio[item["domain"]].append(item)

    problemas = []
    for dominio, lista in por_dominio.items():
        for i in range(len(lista)):
            for j in range(i + 1, len(lista)):
                a = lista[i]
                b = lista[j]
                if a["source"] != b["source"] or a["response"] != b["response"]:
                    continue

                if a["expected_trigger"] == b["expected_trigger"]:
                    modulo = MODULES[a["expected_trigger"].index(1)]
                    problemas.append(
                        f"{dominio}: DUPLICADO IDÉNTICO entre {a['id']} y "
                        f"{b['id']} (módulo {modulo}) — mismo source y "
                        f"response, sin varianza real"
                    )
                else:
                    problemas.append(
                        f"{dominio}: CONTAMINACIÓN CRUZADA entre "
                        f"{MODULES[a['expected_trigger'].index(1)]} y "
                        f"{MODULES[b['expected_trigger'].index(1)]} "
                        f"({a['id']} vs {b['id']})"
                    )
    return problemas


def validar_cobertura(items):
    conteo = Counter()
    for item in items:
        dominio = item["domain"]
        modulo = MODULES[item["expected_trigger"].index(1)]
        conteo[(dominio, modulo)] += 1

    errores = []
    for dominio in DOMAINS:
        for modulo in MODULES:
            n = conteo.get((dominio, modulo), 0)
            if n != 2:
                errores.append(f"{dominio}/{modulo}: {n} pares (esperado 2)")
    return errores


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] No existe {INPUT_FILE}")
        sys.exit(1)

    items = cargar_items(INPUT_FILE)
    total = len(items)
    print(f"[INFO] {total} pares cargados.")

    errores = []
    for idx, item in enumerate(items, 1):
        for e in validar_estructura(item, idx):
            errores.append(f"Ítem {idx} ({item.get('id')}): {e}")

        for e in validar_ground_truth(item):
            errores.append(f"Ítem {idx} ({item.get('id')}): {e}")

        e_id = validar_id_coherente(item)
        if e_id:
            errores.append(f"Ítem {idx} ({item.get('id')}): {e_id}")

    errores.extend(validar_unicidad_respuestas(items))
    errores.extend(validar_cobertura(items))

    if errores:
        print("\n[ERROR] Se encontraron inconsistencias:")
        for e in errores[:50]:
            print(" -", e)
        if len(errores) > 50:
            print(f" ... y {len(errores)-50} más.")
        sys.exit(1)

    dominios = sorted({item['domain'] for item in items})
    print("\n[OK] Validación estructural, de ground truth y de "
          "coherencia ID↔trigger superada.")
    print(f" Dominios: {len(dominios)}")
    for dominio in dominios:
        n = sum(1 for item in items if item['domain'] == dominio)
        print(f"   {dominio}: {n} pares")
    print(f" Módulos por dominio: {len(MODULES)}")
    print(f" Repeticiones por módulo: 2 (variantes distintas, no duplicadas)")


if __name__ == "__main__":
    main()
