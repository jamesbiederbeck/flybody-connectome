"""Is MaleCNS's Johnston's organ reconstruction good enough to build on?

Every one of the 672 JO cells is `RT Hard to trace` -- the dataset's lowest
confidence tier, with no Reviewed subset to fall back on.  That rules out the
stratification used for the haltere clusters (where all ten typed clusters were
Reviewed and only the SApp bulk was preliminary), so the check has to be
structural instead: does the reconstruction behave like something coherent?

Three proxies, each against the haltere afferents as a positive reference --
those are Reviewed for the typed clusters and known to produce sensible results.

1. **Out-degree.** A truncated arbor is the characteristic failure of hard
   tracing. If JO cells have systematically fewer outputs than a comparable
   sensory population, their downstream connectivity is being undercounted and
   every potency claim inherits that.

2. **Bilateral balance.** Types should have matched L/R counts; a type that is
   9-to-2 is more likely half-reconstructed than genuinely asymmetric.

3. **Within-type coherence.** Cells labelled the same type should project to
   overlapping targets. Measured as Jaccard overlap of downstream target sets,
   within type against between type. If within is no better than between, the
   type labels do not correspond to structural groups and clustering on them is
   meaningless -- regardless of what the tracing label says.

None of this validates the reconstruction. It can only fail it cheaply, and say
how much weight the next experiment can carry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _targets(brain, i):
    return set(brain.post[brain.ptr[i]:brain.ptr[i + 1]].tolist())


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def run(*, dataset="malecns_v1", min_cells=4,
        out=ROOT / "outputs/jo_tracing_check.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    types = ann.type.astype(str).to_numpy(dtype="U64")
    side = ann.rootSide.to_numpy()
    subclass = ann.subclass.astype(str).to_numpy(dtype="U64")

    jo = np.flatnonzero(np.char.startswith(types, "JO-"))
    hal = np.flatnonzero(subclass == "haltere")
    outdeg = np.diff(brain.ptr)

    report = {"dataset": dataset, "jo_cells": int(len(jo))}

    # 1. out-degree, JO against the haltere reference and the whole graph
    report["out_degree"] = {
        name: {"n": int(len(ix)), "median": float(np.median(outdeg[ix])),
               "mean": round(float(outdeg[ix].mean()), 1),
               "zero_output": int((outdeg[ix] == 0).sum())}
        for name, ix in [("johnstons_organ", jo), ("haltere_afferents", hal),
                         ("all_cells", np.arange(brain.n))]}
    # split JO by functional subclass, since wind_gravity is the population of
    # interest and may be reconstructed better or worse than the auditory one
    for sc in ("wind_gravity", "auditory", "grooming"):
        ix = jo[subclass[jo] == sc]
        if len(ix):
            report["out_degree"][f"jo_{sc}"] = {
                "n": int(len(ix)), "median": float(np.median(outdeg[ix])),
                "mean": round(float(outdeg[ix].mean()), 1),
                "zero_output": int((outdeg[ix] == 0).sum())}

    # 2. bilateral balance per type
    bal = []
    for t in sorted(set(types[jo])):
        ix = jo[types[jo] == t]
        l = int((side[ix] == "L").sum())
        r = int((side[ix] == "R").sum())
        if l + r:
            bal.append({"type": t, "L": l, "R": r,
                        "imbalance": round(abs(l - r) / (l + r), 3)})
    report["bilateral"] = {
        "types": bal,
        "median_imbalance": round(float(np.median([b["imbalance"] for b in bal])), 3),
        "types_worse_than_half": sum(1 for b in bal if b["imbalance"] > 0.5),
        "n_types": len(bal)}

    # 3. within-type vs between-type target overlap
    tset = {int(i): _targets(brain, int(i)) for i in jo}
    hset = {int(i): _targets(brain, int(i)) for i in hal}
    rng = np.random.default_rng(0)

    def coherence(cells, labels, sets):
        within, between = [], []
        by = {}
        for i in cells:
            by.setdefault(labels[i], []).append(int(i))
        for t, members in by.items():
            if len(members) < min_cells:
                continue
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    within.append(_jaccard(sets[members[a]], sets[members[b]]))
            others = [int(c) for c in cells if labels[c] != t]
            for m in members:
                for o in rng.choice(others, size=min(8, len(others)), replace=False):
                    between.append(_jaccard(sets[m], sets[int(o)]))
        return within, between

    for name, cells, sets in [("johnstons_organ", jo, tset),
                              ("haltere_afferents", hal, hset)]:
        w, b = coherence(cells, types, sets)
        report.setdefault("coherence", {})[name] = {
            "within_type_mean": round(float(np.mean(w)), 4) if w else None,
            "between_type_mean": round(float(np.mean(b)), 4) if b else None,
            "ratio": round(float(np.mean(w) / np.mean(b)), 2) if w and b and np.mean(b) else None,
            "pairs_within": len(w), "pairs_between": len(b)}

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=str(ROOT / "outputs/jo_tracing_check.json"))
    a = p.parse_args()
    r = run(out=a.out)
    print("out-degree:")
    for k, v in r["out_degree"].items():
        print(f"  {k:20s} n={v['n']:6d}  median={v['median']:6.1f}  mean={v['mean']:7.1f}  zero-output={v['zero_output']}")
    b = r["bilateral"]
    print(f"\nbilateral: median imbalance {b['median_imbalance']}, "
          f"{b['types_worse_than_half']}/{b['n_types']} types worse than 2:1")
    print("\ntarget-set overlap (Jaccard):")
    for k, v in r["coherence"].items():
        print(f"  {k:20s} within={v['within_type_mean']}  between={v['between_type_mean']}  ratio={v['ratio']}")
