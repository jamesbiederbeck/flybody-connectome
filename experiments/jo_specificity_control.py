"""Is the JO response specific, or does injecting current anywhere do this?

`jo_potency.py` found that almost every Johnston's organ group drives thousands
of motor spikes, at 8 mV, with a response that barely changes from 8 to 20 mV.
That is not the haltere pattern (2 of 10 clusters, sharp threshold, graded) and
it is suspicious in a specific way: the downstream trace showed haltere input
reaching 97% of the brain in three hops, so stimulating *any* sufficiently large
population may simply ignite the network into a generic saturated state.

If so, "JO drives the motor pools" would mean nothing about JO.

The control: size-matched random sets of sensory cells that are neither JO nor
haltere, stimulated identically. If they produce a comparable response, the JO
result is a property of injecting current into N cells, not of Johnston's organ.
Several random draws per size, because a single draw could land on a potent
population by chance.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run(*, dataset="malecns_v1", sizes=(19, 50, 91, 176, 475), draws=3,
        currents=(8.0, 20.0), duration_ms=500.0, seed=0,
        out=ROOT / "outputs/jo_specificity_control.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _reset
    from experiments.jo_potency import _motor_readouts

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    readouts = _motor_readouts(ann)
    types = ann.type.astype(str).to_numpy(dtype="U64")
    sub = ann.subclass.astype(str).to_numpy(dtype="U64")
    sup = ann.superclass.astype(str).to_numpy(dtype="U64")

    # Candidate pool: sensory cells that are neither JO nor haltere. Sensory so
    # the comparison is like-for-like -- these are cells that also sit at the
    # input edge of the network.
    sensory = np.char.find(sup, "sensory") >= 0
    exclude = np.char.startswith(types, "JO-") | (sub == "haltere")
    pool = np.flatnonzero(sensory & ~exclude)
    rng = np.random.default_rng(seed)

    results, started = [], time.time()
    for n in sizes:
        if n > len(pool):
            continue
        for d in range(draws):
            idx = rng.choice(pool, size=n, replace=False).astype(np.int32)
            row = {"size": int(n), "draw": d, "by_current": {}}
            for mv in currents:
                _reset(brain)
                c, _ = brain.step(dark := np.zeros(len(brain.retina), np.float32),
                                  duration_ms, stimulation=(idx, mv))
                resp = {k: int(c[v].sum()) for k, v in readouts.items()}
                row["by_current"][str(mv)] = {"total": sum(resp.values()), **resp}
            results.append(row)
            tot = {mv: row["by_current"][mv]["total"] for mv in row["by_current"]}
            print(f"random n={n:4d} draw{d} " +
                  " ".join(f"{mv}mV:{v:6d}" for mv, v in tot.items()), flush=True)

    report = {"dataset": dataset, "duration_ms": duration_ms, "seed": seed,
              "candidate_pool_cells": int(len(pool)),
              "pool": "sensory superclass, excluding JO and haltere",
              "draws": results, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draws", type=int, default=3)
    p.add_argument("--out", default=str(ROOT / "outputs/jo_specificity_control.json"))
    a = p.parse_args()
    r = run(draws=a.draws, out=a.out)
    print(f"\n{len(r['draws'])} draws in {r['wall_seconds']} s -> {a.out}")
