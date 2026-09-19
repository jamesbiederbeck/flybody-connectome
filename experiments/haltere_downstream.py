"""Where does haltere input go, and how many synapses from the wing muscles?

Motivated by a structural question: the pathway needs ~20 ms of sustained drive
(~4.4 wingbeats) before the motor pool produces a single spike, so something is
integrating slowly.  In *this* model it cannot be cell-type heterogeneity --
every one of the 166,700 neurons has the same 20 ms membrane and 5 ms synaptic
constant.  What the graph can show is topology: how many hops, how much
convergence, and how much of the signal is inhibitory.

Each synapse also costs 1.8 ms of delay, which is 141 degrees of phase at a 218
Hz wingbeat, so hop count is directly a phase-scrambling budget.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SYNAPTIC_DELAY_MS = 1.8
WINGBEAT_MS = 1000.0 / 218.0


def _targets(ptr, post, weight, src):
    """One hop: all postsynaptic partners of `src`, and the signed weight sum."""
    outs, w = [], []
    for i in src:
        lo, hi = ptr[i], ptr[i + 1]
        outs.append(post[lo:hi])
        w.append(weight[lo:hi])
    if not outs:
        return np.array([], dtype=np.int64), np.array([])
    return np.concatenate(outs), np.concatenate(w)


def run(*, dataset="malecns_v1", hops=4,
        out=ROOT / "outputs/haltere_downstream.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _clusters, _readouts

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    ptr, post, weight = brain.ptr, brain.post, brain.weight
    groups = _readouts(ann)
    wm = set(np.concatenate(list(groups.values())).tolist())
    superclass = ann.superclass.astype(str).to_numpy()

    report = {"dataset": dataset, "synaptic_delay_ms": SYNAPTIC_DELAY_MS,
              "wingbeat_ms": round(WINGBEAT_MS, 3), "sources": {}}

    sources = {"all_haltere": np.flatnonzero((ann.subclass == "haltere").to_numpy())}
    for name, (l, r) in _clusters(ann).items():
        sources[name] = np.concatenate([l, r])

    for name, seed in sources.items():
        frontier = np.asarray(seed, dtype=np.int64)
        seen = set(frontier.tolist())
        levels, first_motor = [], None
        for h in range(1, hops + 1):
            tgt, w = _targets(ptr, post, weight, frontier)
            if not len(tgt):
                break
            new = np.array(sorted(set(tgt.tolist()) - seen), dtype=np.int64)
            reached_motor = sorted(set(tgt.tolist()) & wm)
            if reached_motor and first_motor is None:
                first_motor = h
            comp = {}
            for sc, c in zip(*np.unique(superclass[new], return_counts=True)):
                comp[str(sc)] = int(c)
            levels.append({
                "hop": h,
                "synapses_traversed": int(len(tgt)),
                "new_cells": int(len(new)),
                "cumulative_cells": int(len(seen) + len(new)),
                "excitatory_fraction": round(float((w > 0).mean()), 3),
                "weight_sum": round(float(w.sum()), 1),
                "wing_motor_reached": len(reached_motor),
                "top_superclasses": dict(sorted(comp.items(), key=lambda x: -x[1])[:4]),
            })
            seen |= set(new.tolist())
            frontier = new
        report["sources"][name] = {
            "seed_cells": int(len(seed)),
            "first_hop_reaching_wing_motor": first_motor,
            "phase_rotation_deg_at_that_hop": (
                round(first_motor * SYNAPTIC_DELAY_MS / WINGBEAT_MS * 360, 0)
                if first_motor else None),
            "levels": levels,
        }

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hops", type=int, default=4)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_downstream.json"))
    a = p.parse_args()
    r = run(hops=a.hops, out=a.out)
    print(f"{'source':12s} {'seed':>5s} {'->wm hop':>9s} {'phase':>8s}  hop sizes")
    for k, v in r["sources"].items():
        sizes = " ".join(f"{l['new_cells']:>6d}" for l in v["levels"])
        ph = v["phase_rotation_deg_at_that_hop"]
        print(f"{k:12s} {v['seed_cells']:5d} {str(v['first_hop_reaching_wing_motor']):>9s} "
              f"{(str(int(ph)) + 'd') if ph else '-':>8s}  {sizes}")
