import json
d = json.load(open("reports/pairs_conditions_1800_seed42.json", encoding="utf-8"))
r = d["resultados"]

KAPPA_D = 0.56

# A_A: ¿cuántos cambios de zona tendría si NO hubiera short-circuit?
aa = [x for x in r if x["condicion"] == "A_A"]
aa_sin_sc = [x for x in aa if min(
    x["score_lexical_baseline_score"],
    x["score_source_target_guard"],
    x["score_cre_isi"]
) < KAPPA_D]
print("A_A: cambios de zona si quitamos short-circuit:", len(aa_sin_sc))

# A_App: cambios de zona actuales (con cre activo)
app = [x for x in r if x["condicion"] == "A_App"]
app_sin_cre = [x for x in app if min(
    x["score_lexical_baseline_score"],
    x["score_source_target_guard"]
) < KAPPA_D]
print("A_App: cambios de zona sin cre (solo lb+stg):", len(app_sin_cre))

# A_B para referencia
ab = [x for x in r if x["condicion"] == "A_B"]
ab_sin_cre = [x for x in ab if min(
    x["score_lexical_baseline_score"],
    x["score_source_target_guard"]
) < KAPPA_D]
print("A_B: cambios de zona sin cre:", len(ab_sin_cre))

# Distribución de score_cre_isi en A_A vs A_App (mismo ID)
from collections import defaultdict
por_id = defaultdict(dict)
for x in r:
    por_id[(x["suite"], x["id"])][x["condicion"]] = x

deltas = []
for key, conds in por_id.items():
    if "A_A" in conds and "A_App" in conds:
        deltas.append(conds["A_App"]["score_cre_isi"] - conds["A_A"]["score_cre_isi"])

deltas.sort()
print(f"Delta cre(A_App - A_A): mediana={deltas[len(deltas)//2]:.4f}  min={deltas[0]:.4f}  max={deltas[-1]:.4f}")