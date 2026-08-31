#!/usr/bin/env python3
"""
01_generate_controlled.py — Piloto controlado Subset A
Versión corregida (auditoría interna + auditoría Kimi, 2026-08-27/28).

CHANGELOG DE CORRECCIONES APLICADAS
------------------------------------
[BLOCKER][Kimi H1]      COHERENCE_MAP["arithmetic_penalty"]: True -> False.
                         Un error aritmético es estructuralmente incoherente
                         por definición; el ground truth estaba invertido.

[BLOCKER][Kimi H2 / interno H10]
                         Las perturbaciones de arithmetic_penalty en legal,
                         biomed, general y narrative introducían cantidades
                         NUEVAS no presentes en el source (contaminación con
                         source_target_guard / cre_isi). Ahora TODOS los
                         dominios anclan la(s) cantidad(es) en el `source` y
                         la perturbación aritmética solo modifica el
                         resultado del cómputo, igual que finance.

[BLOCKER][auditoría del core real]
    _calcular_source_target_guard() en tribunal_multimetrico.py detecta
    ubicaciones con un regex de whitelist HARDCODEADA (Paris, London,
    Berlin, Madrid, Rome, Buenos Aires, New York, Washington, Tokyo,
    Beijing, Moscow, Sydney, Cairo, Delhi + países: France, Germany,
    Spain, Italy, Argentina, USA, UK, China, Japan, Russia, Australia,
    Brazil, India, Mexico, Canada). "Montevideo", "Rosario", "Chile" y
    "Uruguay" NO estaban en esa lista: los swaps originales de STG nunca
    iban a disparar el módulo real (locations_b quedaba vacío, la
    condición loc_mutadas AND loc_nuevas nunca se cumplía). Se
    reemplazaron por nombres SÍ reconocidos por el regex: Buenos Aires →
    Madrid / Washington (ciudades), Argentina → China / India (países).
    Se evitaron nombres que en español llevan tilde (México, Japón,
    Brasil con S) porque el regex es ASCII literal sin tilde.

[WARNING][Kimi H3 / interno H11]
                         negation_penalty pasó de negación total (polaridad
                         global invertida, riesgo de contaminación con
                         cre_isi) a negación PARCIAL: se niega solo la
                         cláusula de cantidad/detalle, preservando el resto
                         de la oración intacto.

[WARNING][Kimi H4 / interno H1]
                         Las 2 repeticiones por (dominio, módulo) eran
                         duplicados exactos. Ahora cada módulo tiene 2
                         variantes textuales distintas (sinónimos, orden)
                         que preservan el mismo tipo de perturbación —no se
                         cambia el módulo objetivo, solo se agrega varianza
                         léxica real.

[WARNING][interno H9]   source_target_guard usaba tipos de perturbación
                         distintos por dominio (swap de entidad en la
                         mayoría, pero cambio de GÉNERO GRAMATICAL en
                         biomed). Ahora los 5 dominios usan swap de entidad
                         nombrada (ciudad/país), de forma homogénea.

[BLOCKER][autoaudit]    legal/negation_penalty negaba el mismo valor (el
                         total "1200 dólares") que legal/arithmetic_penalty
                         modifica (1200->1400). Se corrigió para que
                         negation niegue el valor por pago individual (600),
                         no el total, consistente con el resto de los
                         dominios y evitando solapamiento de objetivo entre
                         ambos módulos.

[WARNING][Gemini pt.3]  ground_truth.plausibility_score estaba hardcodeado
                         a 0.5 constante para los 70 ítems, inutilizando el
                         campo para cualquier calibrador futuro. Ahora se
                         deriva de PLAUSIBILITY_MAP (graduado por módulo,
                         no un simple 1.0/0.0 duplicado de truth_factual).

[INFO][autoaudit]       LIMITACIÓN CONOCIDA: validar_unicidad_respuestas()
                         en 02_validate_pilot.py compara strings literales.
                         No puede detectar el tipo de solapamiento corregido
                         arriba (dos perturbaciones distintas apuntando al
                         mismo hecho subyacente con textos diferentes). La
                         ausencia de error en 02 no garantiza ausencia de
                         solapamiento semántico entre módulos — eso requiere
                         revisión humana al diseñar nuevas seeds.

[INFO][interno H12]     ground_truth.truth_factual ya no es una constante
                         True para los 70 ítems: se deriva por módulo
                         (TRUTH_FACTUAL_MAP), reflejando si la perturbación
                         altera o no el contenido factual respecto al source.

No usa random. No mezcla dominios. Mantiene ID -> dominio -> módulo ->
perturbación. No se cambia la arquitectura del pipeline.
"""

import json
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

# coherence_structural: si la perturbación, en sí misma, preserva la
# coherencia estructural/lógica interna de la oración (independientemente
# de si coincide o no con el source).
COHERENCE_MAP = {
    "lexical_baseline_score": True,
    "source_target_guard": False,
    "cre_isi": False,
    "flow_penalty": False,
    "negation_penalty": False,
    "arithmetic_penalty": False,  # corregido: era True (Kimi H1)
    "reference_penalty": False,
}

# truth_factual: si el contenido factual de la respuesta coincide con el
# source (True) o lo contradice/altera (False). Antes era True fijo para
# los 70 ítems (interno H12); ahora se deriva por módulo.
TRUTH_FACTUAL_MAP = {
    "lexical_baseline_score": True,   # paraphrase, mismo contenido factual
    "source_target_guard": False,     # entidad (lugar) cambiada
    "cre_isi": False,                 # contradicción semántica directa
    "flow_penalty": True,             # solo reordena, no cambia hechos
    "negation_penalty": False,        # niega parte del contenido factual
    "arithmetic_penalty": False,      # cómputo alterado
    "reference_penalty": True,        # solo agrega cita, no cambia hechos
}

# Cada módulo mapea a una lista de EXACTAMENTE 2 variantes textuales
# distintas que apuntan al mismo tipo de perturbación.
SEEDS = [
    {
        "domain": "finance",
        "source": (
            "El reporte final indica que las ventas totales fueron 25 y 18, "
            "sumando 43 unidades en Buenos Aires."
        ),
        "responses": {
            "lexical_baseline_score": [
                "El informe final señala que las ventas totales fueron 25 y 18, "
                "sumando 43 unidades en Buenos Aires.",
                "El informe final indica que el total de ventas fue 25 y 18, "
                "alcanzando 43 unidades en Buenos Aires.",
            ],
            "source_target_guard": [
                "El reporte final indica que las ventas totales fueron 25 y 18, "
                "sumando 43 unidades en Madrid.",
                "El reporte final indica que las ventas totales fueron 25 y 18, "
                "sumando 43 unidades en Washington.",
            ],
            "cre_isi": [
                "El reporte final rechaza que las ventas totales fueron 25 y 18, "
                "sumando 43 unidades en Buenos Aires.",
                "El reporte final niega que las ventas totales fueron 25 y 18, "
                "sumando 43 unidades en Buenos Aires.",
            ],
            "flow_penalty": [
                "Las ventas totales fueron 25 y 18, sumando 43 unidades en "
                "Buenos Aires, indica el reporte final.",
                "En Buenos Aires, las ventas totales sumaron 43 unidades "
                "—25 y 18—, según indica el reporte final.",
            ],
            "negation_penalty": [
                "El reporte final indica que las ventas totales no fueron 25 "
                "y 18, sumando 43 unidades en Buenos Aires.",
                "El reporte final indica que las ventas totales, que no "
                "fueron 25 y 18, sumaron 43 unidades en Buenos Aires.",
            ],
            "arithmetic_penalty": [
                "El reporte final indica que las ventas totales fueron 25 y "
                "18, sumando 45 unidades en Buenos Aires.",
                "El reporte final indica que las ventas totales fueron 25 y "
                "18, lo que da un total de 45 unidades en Buenos Aires.",
            ],
            "reference_penalty": [
                "El reporte final indica que las ventas totales fueron 25 y "
                "18, sumando 43 unidades en Buenos Aires. (Pérez, 2024, p. 5)",
                "El reporte final indica que las ventas totales fueron 25 y "
                "18, sumando 43 unidades en Buenos Aires. (Pérez, 2024, p. 12)",
            ],
        },
    },
    {
        "domain": "legal",
        "source": (
            "El juez revisó el contrato en Buenos Aires y autorizó dos pagos "
            "de 600 dólares cada uno, sumando 1200 dólares."
        ),
        "responses": {
            "lexical_baseline_score": [
                "El magistrado examinó el contrato en Buenos Aires y aprobó "
                "dos pagos de 600 dólares cada uno, sumando 1200 dólares.",
                "El magistrado revisó el acuerdo en Buenos Aires y autorizó "
                "dos pagos de 600 dólares cada uno, por un total de 1200 "
                "dólares.",
            ],
            "source_target_guard": [
                "El juez revisó el contrato en Madrid y autorizó dos "
                "pagos de 600 dólares cada uno, sumando 1200 dólares.",
                "El juez revisó el contrato en Washington y autorizó dos pagos "
                "de 600 dólares cada uno, sumando 1200 dólares.",
            ],
            "cre_isi": [
                "El juez destruyó el contrato en Buenos Aires y autorizó dos "
                "pagos de 600 dólares cada uno, sumando 1200 dólares.",
                "El juez anuló el contrato en Buenos Aires y autorizó dos "
                "pagos de 600 dólares cada uno, sumando 1200 dólares.",
            ],
            "flow_penalty": [
                "En Buenos Aires, el juez autorizó dos pagos de 600 dólares "
                "cada uno, sumando 1200 dólares, tras revisar el contrato.",
                "Tras revisar el contrato en Buenos Aires, el juez autorizó "
                "dos pagos de 600 dólares cada uno, sumando 1200 dólares.",
            ],
            "negation_penalty": [
                # NOTA (autoaudit): la versión previa negaba el TOTAL
                # (1200), el mismo valor que arithmetic_penalty modifica
                # (1200->1400) mas abajo. Se corrige para que negation
                # niegue el valor de cada pago individual (600), igual
                # que en los demás dominios (donde se niegan los
                # sumandos, no el total), evitando solapamiento de
                # objetivo entre los dos módulos.
                "El juez revisó el contrato en Buenos Aires y autorizó dos "
                "pagos que no fueron de 600 dólares cada uno, sumando 1200 "
                "dólares.",
                "El juez revisó el contrato en Buenos Aires, aunque los "
                "pagos autorizados no fueron de 600 dólares cada uno, "
                "sumando 1200 dólares.",
            ],
            "arithmetic_penalty": [
                "El juez revisó el contrato en Buenos Aires y autorizó dos "
                "pagos de 600 dólares cada uno, sumando 1400 dólares.",
                "El juez revisó el contrato en Buenos Aires y autorizó dos "
                "pagos de 600 dólares cada uno, lo que da un total de 1400 "
                "dólares.",
            ],
            "reference_penalty": [
                "El juez revisó el contrato en Buenos Aires y autorizó dos "
                "pagos de 600 dólares cada uno, sumando 1200 dólares. "
                "(López, 2023, p. 22)",
                "El juez revisó el contrato en Buenos Aires y autorizó dos "
                "pagos de 600 dólares cada uno, sumando 1200 dólares. "
                "(López, 2023, p. 30)",
            ],
        },
    },
    {
        "domain": "biomed",
        "source": (
            "El paciente consumió 2 pastillas por día durante 5 días, "
            "sumando 10 pastillas, en el hospital de Buenos Aires."
        ),
        "responses": {
            "lexical_baseline_score": [
                "El paciente tomó 2 pastillas diarias a lo largo de 5 días, "
                "alcanzando 10 pastillas, en el hospital de Buenos Aires.",
                "El paciente ingirió 2 pastillas por día durante 5 días, "
                "totalizando 10 pastillas, en el hospital de Buenos Aires.",
            ],
            "source_target_guard": [
                "El paciente consumió 2 pastillas por día durante 5 días, "
                "sumando 10 pastillas, en el hospital de Madrid.",
                "El paciente consumió 2 pastillas por día durante 5 días, "
                "sumando 10 pastillas, en el hospital de Washington.",
            ],
            "cre_isi": [
                "El paciente rechazó 2 pastillas por día durante 5 días, "
                "sumando 10 pastillas, en el hospital de Buenos Aires.",
                "El paciente evitó 2 pastillas por día durante 5 días, "
                "sumando 10 pastillas, en el hospital de Buenos Aires.",
            ],
            "flow_penalty": [
                "Durante 5 días, en el hospital de Buenos Aires, el paciente "
                "consumió 2 pastillas por día, sumando 10 pastillas.",
                "En el hospital de Buenos Aires, el paciente consumió 2 "
                "pastillas por día durante 5 días, sumando 10 pastillas.",
            ],
            "negation_penalty": [
                "El paciente consumió pastillas en el hospital de Buenos "
                "Aires, pero no fueron 2 por día durante 5 días.",
                "El paciente consumió pastillas en el hospital de Buenos "
                "Aires durante 5 días, aunque no fueron 2 por día.",
            ],
            "arithmetic_penalty": [
                "El paciente consumió 2 pastillas por día durante 5 días, "
                "sumando 11 pastillas, en el hospital de Buenos Aires.",
                "El paciente consumió 2 pastillas por día durante 5 días, lo "
                "que da un total de 11 pastillas, en el hospital de Buenos "
                "Aires.",
            ],
            "reference_penalty": [
                "El paciente consumió 2 pastillas por día durante 5 días, "
                "sumando 10 pastillas, en el hospital de Buenos Aires. "
                "(García, 2025, p. 7)",
                "El paciente consumió 2 pastillas por día durante 5 días, "
                "sumando 10 pastillas, en el hospital de Buenos Aires. "
                "(García, 2025, p. 14)",
            ],
        },
    },
    {
        "domain": "general",
        "source": (
            "La producción agrícola aumentó un 3 por ciento el primer "
            "semestre y un 4 por ciento el segundo semestre, sumando un 7 "
            "por ciento en el año, según el informe de Argentina."
        ),
        "responses": {
            "lexical_baseline_score": [
                "La producción agropecuaria creció un 3 por ciento el "
                "primer semestre y un 4 por ciento el segundo, alcanzando "
                "un 7 por ciento en el año, según el informe de Argentina.",
                "La producción agrícola se incrementó un 3 por ciento en el "
                "primer semestre y un 4 por ciento en el segundo, "
                "totalizando un 7 por ciento anual, según el informe de "
                "Argentina.",
            ],
            "source_target_guard": [
                "La producción agrícola aumentó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 7 por "
                "ciento en el año, según el informe de China.",
                "La producción agrícola aumentó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 7 por "
                "ciento en el año, según el informe de India.",
            ],
            "cre_isi": [
                "La producción agrícola colapsó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 7 por "
                "ciento en el año, según el informe de Argentina.",
                "La producción agrícola cayó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 7 por "
                "ciento en el año, según el informe de Argentina.",
            ],
            "flow_penalty": [
                "Según el informe de Argentina, la producción agrícola "
                "aumentó un 3 por ciento el primer semestre y un 4 por "
                "ciento el segundo, sumando un 7 por ciento en el año.",
                "En el año, la producción agrícola de Argentina aumentó un "
                "3 por ciento el primer semestre y un 4 por ciento el "
                "segundo, sumando un 7 por ciento.",
            ],
            "negation_penalty": [
                "La producción agrícola aumentó en Argentina, aunque no fue "
                "un 3 por ciento el primer semestre ni un 4 por ciento el "
                "segundo.",
                "Según el informe de Argentina, el aumento no fue de un 3 "
                "por ciento el primer semestre y un 4 por ciento el "
                "segundo.",
            ],
            "arithmetic_penalty": [
                "La producción agrícola aumentó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 8 por "
                "ciento en el año, según el informe de Argentina.",
                "La producción agrícola aumentó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, lo que da un total "
                "de un 8 por ciento anual, según el informe de Argentina.",
            ],
            "reference_penalty": [
                "La producción agrícola aumentó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 7 por "
                "ciento en el año, según el informe de Argentina. "
                "(Fernández, 2026, p. 14)",
                "La producción agrícola aumentó un 3 por ciento el primer "
                "semestre y un 4 por ciento el segundo, sumando un 7 por "
                "ciento en el año, según el informe de Argentina. "
                "(Fernández, 2026, p. 21)",
            ],
        },
    },
    {
        "domain": "narrative",
        "source": (
            "La cerradura de la casa se abrió en 4 segundos y la alarma se "
            "desactivó en 6 segundos, sumando 10 segundos en total, según "
            "las cámaras de Buenos Aires."
        ),
        "responses": {
            "lexical_baseline_score": [
                "La cerradura del hogar se destrabó en 4 segundos y la "
                "alarma se apagó en 6 segundos, totalizando 10 segundos, "
                "según las cámaras de Buenos Aires.",
                "La cerradura de la vivienda se abrió en 4 segundos y la "
                "alarma se desactivó en 6 segundos, alcanzando 10 segundos "
                "en total, según las cámaras de Buenos Aires.",
            ],
            "source_target_guard": [
                "La cerradura de la casa se abrió en 4 segundos y la alarma "
                "se desactivó en 6 segundos, sumando 10 segundos en total, "
                "según las cámaras de Madrid.",
                "La cerradura de la casa se abrió en 4 segundos y la alarma "
                "se desactivó en 6 segundos, sumando 10 segundos en total, "
                "según las cámaras de Washington.",
            ],
            "cre_isi": [
                "La cerradura de la casa se rompió en 4 segundos y la "
                "alarma se desactivó en 6 segundos, sumando 10 segundos en "
                "total, según las cámaras de Buenos Aires.",
                "La cerradura de la casa se forzó en 4 segundos y la alarma "
                "se desactivó en 6 segundos, sumando 10 segundos en total, "
                "según las cámaras de Buenos Aires.",
            ],
            "flow_penalty": [
                "La alarma se desactivó en 6 segundos y la cerradura de la "
                "casa se abrió en 4 segundos, sumando 10 segundos en total, "
                "según las cámaras de Buenos Aires.",
                "Según las cámaras de Buenos Aires, la cerradura de la casa "
                "se abrió en 4 segundos y la alarma se desactivó en 6 "
                "segundos, sumando 10 segundos en total.",
            ],
            "negation_penalty": [
                "La cerradura de la casa se abrió y la alarma se desactivó, "
                "pero no en 4 y 6 segundos según las cámaras de Buenos "
                "Aires.",
                "Según las cámaras de Buenos Aires, la cerradura se abrió y "
                "la alarma se desactivó, aunque no en 4 y 6 segundos.",
            ],
            "arithmetic_penalty": [
                "La cerradura de la casa se abrió en 4 segundos y la alarma "
                "se desactivó en 6 segundos, sumando 11 segundos en total, "
                "según las cámaras de Buenos Aires.",
                "La cerradura de la casa se abrió en 4 segundos y la alarma "
                "se desactivó en 6 segundos, lo que da un total de 11 "
                "segundos, según las cámaras de Buenos Aires.",
            ],
            "reference_penalty": [
                "La cerradura de la casa se abrió en 4 segundos y la alarma "
                "se desactivó en 6 segundos, sumando 10 segundos en total, "
                "según las cámaras de Buenos Aires. (Romero, 2022, p. 3)",
                "La cerradura de la casa se abrió en 4 segundos y la alarma "
                "se desactivó en 6 segundos, sumando 10 segundos en total, "
                "según las cámaras de Buenos Aires. (Romero, 2022, p. 9)",
            ],
        },
    },
]


# plausibility_score: qué tan creíble/verosímil suena la respuesta al leerla,
# independientemente de si es correcta. NO es un duplicado de truth_factual:
# una contradicción directa (cre_isi) es fácil de notar como falsa (baja
# plausibilidad), mientras que un error aritmético sutil (25 y 18 sumando 45
# en vez de 43) puede sonar perfectamente creíble a primera lectura pese a
# ser incorrecto (plausibilidad más alta que su veracidad).
#
# NOTA: estos valores son ILUSTRATIVOS, elegidos para dar variación
# ordinal razonable (no una constante 0.5 para los 70 ítems, que es lo que
# había antes y no aportaba señal). Si este campo va a alimentar un
# calibrador real, conviene recalibrarlos con criterio explícito (o con
# anotación humana) antes de confiar en ellos cuantitativamente.
PLAUSIBILITY_MAP = {
    "lexical_baseline_score": 0.95,  # paraphrase, indistinguible del original
    "source_target_guard": 0.55,     # entidad cambiada, pero sigue sonando normal
    "cre_isi": 0.10,                 # contradicción directa, salta a la vista
    "flow_penalty": 0.90,            # solo reordenado, sigue siendo verosímil
    "negation_penalty": 0.15,        # negación explícita, poco verosímil
    "arithmetic_penalty": 0.40,      # error numérico sutil, fácil de pasar por alto
    "reference_penalty": 0.85,       # cita con forma válida, no se verifica su origen
}


def one_hot(index):
    return [1 if i == index else 0 for i in range(len(MODULES))]


def build_item(domain, source, response, module_idx, n):
    module = MODULES[module_idx]
    return {
        "id": f"SAS_PILOT_A_{domain}_{module}_{n:02d}",
        "subset": "A",
        "domain": domain,
        "source": source,
        "response": response,
        "expected_trigger": one_hot(module_idx),
        "features": {},
        "ground_truth": {
            "truth_factual": TRUTH_FACTUAL_MAP[module],
            "coherence_structural": COHERENCE_MAP[module],
            "plausibility_score": PLAUSIBILITY_MAP[module],
        },
        "sas_result": None,
    }


def main():
    out = []
    for seed in SEEDS:
        source = seed["source"]
        domain = seed["domain"]
        for idx, module in enumerate(MODULES):
            variantes = seed["responses"][module]
            assert len(variantes) == 2, (
                f"{domain}/{module}: se esperaban 2 variantes distintas, "
                f"hay {len(variantes)}"
            )
            assert variantes[0] != variantes[1], (
                f"{domain}/{module}: las 2 variantes son idénticas"
            )
            for n, response in enumerate(variantes):
                out.append(build_item(domain, source, response, idx, n))

    out_path = Path("corpus_pilot_A_raw.jsonl")
    with out_path.open("w", encoding="utf-8") as f:
        for item in out:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Generados {len(out)} pares en {out_path}")
    print(f"Dominios: {len(SEEDS)} | Módulos: {len(MODULES)} | "
          f"Variantes por combinación: 2 (no duplicadas)")


if __name__ == "__main__":
    main()
