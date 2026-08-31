#!/usr/bin/env python3
"""
03_run_pilot_inference.py — Ejecuta SAS local sobre el piloto controlado.

No usa la API pública.
Llama directo a core/tribunal_multimetrico.py.

CHANGELOG DE CORRECCIONES APLICADAS
------------------------------------
[BLOCKER][interno H5 / Kimi H7]
    Los ítems que fallaban en tribunal.evaluar() se descartaban con
    `continue` y solo se imprimían por consola: no quedaba rastro
    persistente ni reconciliable. Ahora:
      - se acumulan en una lista `fallidos` con id y motivo del error
      - se escriben en results_pilot_A_failed.jsonl
      - al final se imprime la reconciliación explícita:
        input total vs procesados vs fallidos, y NO debe asumirse que
        "Total procesados" == "Total input" sin mirar este reporte.

[WARNING][interno H6 / Kimi H8]
    mapear_scores() y la extracción de módulos disparados dependían
    silenciosamente de nombres de atributos exactos del objeto `veredicto`.
    Ahora:
      - al cargar el tribunal se corre un smoke test con un ítem dummy y
        se valida con `hasattr` que existan los 7 atributos de score y el
        atributo modulos_disparados, fallando fuerte (exit) si falta algo,
        en vez de continuar silenciosamente con None.
      - la extracción de `m.nombre` usa getattr(m, "nombre", None) con
        fallback a str(m), y se cuenta cuántas veces se usó el fallback
        (indicador de desajuste de nombres en el core).

[BLOCKER][auditoría del core real]
    tribunal_multimetrico.py hace imports absolutos "from core.X import"
    dentro de cada _calcular_*, atrapados en try/except. Sin "core" en
    sys.path, esos imports fallan en silencio y 5 de 7 módulos degradan
    a valores por defecto sin ningún error visible — el hasattr() del
    smoke test anterior no lo detecta. Se agregó: (a) inserción del
    directorio padre de core/ en sys.path antes de cargar el módulo, y
    (b) verificar_submodulos_cargados(), que lee tribunal._modulos_cargados
    (expuesto por el propio core) y corta fuerte si algo no cargó.

[INFO][interno H13 / Kimi H11]
    CORE_PATH ya no está hardcodeado a "SAS/SAS/core/...". Se puede pasar
    por --core-path; si no se pasa, se intenta resolver relativo al
    directorio del script y, si no existe ahí, relativo al cwd.
"""

import argparse
import json
import sys
import importlib.util
from pathlib import Path

DEFAULT_CORE_RELATIVE = Path("SAS/SAS/core/tribunal_multimetrico.py")
PILOT_INPUT = Path("corpus_pilot_A_raw.jsonl")
OUTPUT = Path("results_pilot_A.jsonl")
FAILED_OUTPUT = Path("results_pilot_A_failed.jsonl")

MODULE_ORDER = [
    "lexical_baseline_score",
    "source_target_guard",
    "cre_isi",
    "flow_penalty",
    "negation_penalty",
    "arithmetic_penalty",
    "reference_penalty",
]


def resolver_core_path(core_path_arg):
    if core_path_arg:
        p = Path(core_path_arg)
        if p.exists():
            return p
        print(f"[ERROR] --core-path indicado no existe: {p}")
        sys.exit(1)

    candidatos = [
        Path(__file__).resolve().parent / DEFAULT_CORE_RELATIVE,
        Path.cwd() / DEFAULT_CORE_RELATIVE,
    ]
    for c in candidatos:
        if c.exists():
            return c

    print("[ERROR] No se encontró tribunal_multimetrico.py en ninguna ruta "
          "candidata:")
    for c in candidatos:
        print(f"  - {c}")
    print("Usá --core-path para indicar la ruta explícita.")
    sys.exit(1)


def cargar_tribunal(core_path: Path):
    """
    CORRECCIÓN (auditoría del core real, Hallazgo 1): tribunal_multimetrico.py
    hace imports absolutos tipo `from core.flow_coherence import ...` dentro
    de cada _calcular_*, envueltos en try/except. Si el paquete "core" no
    está en sys.path, esos imports fallan en SILENCIO (la excepción se
    traga) y 5 de los 7 módulos (flow, negation, cre_isi, arithmetic,
    reference) degradan a su valor por defecto ("no disponible", nunca
    disparan) sin lanzar ningún error visible. Por eso agregamos el
    directorio padre de core/ (ej. SAS/SAS/) a sys.path ANTES de cargar
    el módulo, para que esos imports absolutos puedan resolverse.
    """
    core_parent = core_path.parent.parent  # ej. .../SAS/SAS/ (padre de core/)
    if str(core_parent) not in sys.path:
        sys.path.insert(0, str(core_parent))

    spec = importlib.util.spec_from_file_location("tribunal_core", core_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["tribunal_core"] = module
    spec.loader.exec_module(module)
    return module.TribunalMultimetrico


def smoke_test_veredicto(tribunal):
    """
    Corre una evaluación dummy y verifica que el objeto veredicto tenga
    todos los atributos que este script espera leer. Si el core cambió de
    nombres, esto falla fuerte y explícito en vez de dejar todo en None
    silenciosamente durante las 70 evaluaciones reales.
    """
    try:
        v = tribunal.evaluar("Esto es una prueba.", "Esto es una prueba.")
    except Exception as e:
        print(f"[ERROR] Smoke test falló al llamar tribunal.evaluar(): {e}")
        sys.exit(1)

    atributos_esperados = MODULE_ORDER + ["isi_hard", "isi_final", "zona",
                                           "modulos_disparados"]
    faltantes = [a for a in atributos_esperados if not hasattr(v, a)]
    if faltantes:
        print("[ERROR] El objeto veredicto no tiene los atributos "
              "esperados. El core pudo haber cambiado de interfaz.")
        print(f"        Atributos faltantes: {faltantes}")
        sys.exit(1)

    print("[OK] Smoke test: interfaz del veredicto verificada.")


def verificar_submodulos_cargados(tribunal):
    """
    CORRECCIÓN (auditoría del core real, Hallazgo 1): el smoke test de
    interfaz (hasattr) NO detecta si los submódulos reales cargaron,
    porque los atributos existen igual con valores por defecto aunque
    el import haya fallado. El propio core expone
    tribunal._modulos_cargados (dict {nombre: bool}, poblado en
    _inicializar_modulos()) que SÍ dice la verdad. Lo leemos acá y
    cortamos fuerte si algo no cargó, en vez de dejar que el piloto
    corra 70 evaluaciones con la mayoría de las métricas mudas.
    """
    cargados = getattr(tribunal, "_modulos_cargados", None)
    if cargados is None:
        print("[ATENCIÓN] No se pudo inspeccionar tribunal._modulos_cargados "
              "(¿cambió la interfaz interna del core?). No se puede "
              "confirmar si los submódulos reales cargaron. Procedé con "
              "cautela y revisá los resultados a mano.")
        return

    print("\n[INFO] Estado de submódulos internos del core:")
    faltantes = []
    for nombre, ok in cargados.items():
        print(f"    {nombre:22s}: {'OK' if ok else 'NO CARGÓ'}")
        if not ok:
            faltantes.append(nombre)

    if faltantes:
        print(f"\n[ERROR] {len(faltantes)} submódulo(s) no cargaron: "
              f"{faltantes}")
        print("Con esto, las métricas correspondientes van a devolver "
              "'no disponible' (val=1.0, nunca disparan) para los 70 "
              "ítems, sin lanzar ningún error visible. El piloto daría "
              "resultados sin sentido. Revisá que 'core' esté "
              "correctamente resoluble como paquete antes de continuar.")
        sys.exit(1)

    print("[OK] Todos los submódulos internos del core cargaron "
          "correctamente.\n")


def mapear_scores(veredicto) -> dict:
    return {
        "lexical_baseline_score": getattr(veredicto, "lexical_baseline_score", None),
        "source_target_guard": getattr(veredicto, "source_target_guard", None),
        "cre_isi": getattr(veredicto, "cre_isi", None),
        "flow_penalty": getattr(veredicto, "flow_penalty", None),
        "negation_penalty": getattr(veredicto, "negation_penalty", None),
        "arithmetic_penalty": getattr(veredicto, "arithmetic_penalty", None),
        "reference_penalty": getattr(veredicto, "reference_penalty", None),
    }


def extraer_modulos_disparados(veredicto, contador_fallback):
    """
    Extrae los nombres de los módulos disparados con fallback robusto.

    CORRECCIÓN (auditoría Gemini, punto 2): el fallback anterior usaba
    str(m), que para un objeto sin __str__ custom produce algo tipo
    "<FlowPenaltyModule object at 0x7f...>" — inservible como clave y
    encima con una dirección de memoria que cambia entre corridas.
    Ahora se usa el nombre de la CLASE (m.__class__.__name__) como
    fallback, que es legible y estable.

    Ojo: aun con este fallback, es muy probable que el nombre de clase de
    Python (ej. "FlowPenaltyModule") NO coincida con el string en
    snake_case que espera MODULES (ej. "flow_penalty"). Por diseño, este
    fallback no pretende "adivinar" el nombre correcto — solo evita un
    string ilegible. Ese desajuste se cuenta y reporta (contador_fallback)
    y, si supera un umbral significativo del batch, el pipeline debe
    fallar fuerte al FINAL del reporte (ver main()), no a mitad de la
    corrida: matar el proceso en el ítem 3 de 70 tiraría por la borda la
    reconciliación de los 67 restantes que sí funcionan, que es
    exactamente lo que corregimos en el Hallazgo interno #5.
    """
    disparados = getattr(veredicto, "modulos_disparados", None) or []
    nombres = []
    for m in disparados:
        nombre = getattr(m, "nombre", None)
        if nombre is None:
            contador_fallback[0] += 1
            nombre = getattr(m, "name", None) or type(m).__name__
        nombres.append(nombre)
    return nombres


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--core-path", default=None,
        help="Ruta explícita a tribunal_multimetrico.py (opcional)."
    )
    args = parser.parse_args()

    if not PILOT_INPUT.exists():
        print(f"[ERROR] No se encontró {PILOT_INPUT}")
        sys.exit(1)

    core_path = resolver_core_path(args.core_path)
    TribunalCls = cargar_tribunal(core_path)

    # κR queda fijo en 0.15 porque no se está barriendo.
    tribunal = TribunalCls(kappa_d=0.56, kappa_r=0.15)

    smoke_test_veredicto(tribunal)
    verificar_submodulos_cargados(tribunal)

    items = []
    with PILOT_INPUT.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    resultados = []
    fallidos = []
    contador_fallback_nombre = [0]

    for i, item in enumerate(items, 1):
        try:
            v = tribunal.evaluar(item["source"], item["response"])
        except Exception as e:
            print(f"[ERROR] Falló {item.get('id', i)}: {e}")
            fallidos.append({
                "id": item.get("id", f"idx_{i}"),
                "domain": item.get("domain"),
                "expected_trigger": item.get("expected_trigger"),
                "error": str(e),
                "error_type": type(e).__name__,
            })
            continue

        scores = mapear_scores(v)
        modulos_disparados = extraer_modulos_disparados(
            v, contador_fallback_nombre
        )

        item["sas_result"] = {
            "isi_hard": v.isi_hard,
            "isi_final": v.isi_final,
            "verdict": v.zona,
            "module_scores": scores,
            "fired_modules": modulos_disparados,
        }

        resultados.append(item)

        if i % 10 == 0 or i == len(items):
            print(f"[{i}/{len(items)}] procesados")

    with OUTPUT.open("w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    if fallidos:
        with FAILED_OUTPUT.open("w", encoding="utf-8") as f:
            for r in fallidos:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ── Reconciliación explícita ─────────────────────────────────────────
    print(f"\n[OK] Resultados guardados en {OUTPUT}")
    print("\n" + "=" * 60)
    print("RECONCILIACIÓN DE INFERENCIA")
    print("=" * 60)
    print(f" Total input        : {len(items)}")
    print(f" Total procesados OK : {len(resultados)}")
    print(f" Total fallidos      : {len(fallidos)}")
    if fallidos:
        print(f" -> detalle en {FAILED_OUTPUT}")
        ids_fallidos = [f["id"] for f in fallidos]
        print(f" IDs fallidos: {ids_fallidos}")
    if contador_fallback_nombre[0] > 0:
        tasa_fallback = contador_fallback_nombre[0] / max(len(resultados), 1)
        print(f"\n[ATENCIÓN] Se usó fallback (nombre de clase) en vez de "
              f"m.nombre {contador_fallback_nombre[0]} veces "
              f"({tasa_fallback:.1%} de los ítems procesados). Esto "
              f"sugiere un desajuste entre el nombre de atributo esperado "
              f"y el que expone el core.")
        if tasa_fallback > 0.10:
            print("[ERROR] Más del 10% de los ítems dependieron del "
                  "fallback de nombre. Esto invalida la comparación contra "
                  "MODULES en 04_check_module_precision.py (los nombres de "
                  "clase casi seguro no coinciden con las claves esperadas "
                  "en snake_case). Revisá la interfaz del core antes de "
                  "confiar en las métricas de 04.")
            sys.exit(1)
    if len(resultados) != len(items):
        print("\n[ATENCIÓN] El total procesado NO coincide con el total de "
              "input. NO tratar 04_check_module_precision.py como si "
              "estuviera midiendo sobre el corpus completo sin revisar "
              "esta diferencia primero.")


if __name__ == "__main__":
    main()
