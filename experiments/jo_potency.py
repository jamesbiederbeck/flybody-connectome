"""Does Johnston's organ wind/gravity input reach the motor pools, and where?

The haltere equivalent of this run found that only 2 of 10 clusters move the
wing muscles at all.  Same question for JO, with three differences forced by the
tracing check (`jo_tracing_check.py`):

1. **Group by coarse array, not fine type.**  Fine types are structurally
   coherent (within/between target overlap 3.99, matching the haltere
   reference), but ~13% of wind_gravity cells have zero outputs and arbors are
   truncated, so small types would be dominated by reconstruction gaps.

2. **Split L/R on the pooled population, not per type.**  Median bilateral
   imbalance across JO types is 0.472 and 16 of 34 types are worse than 2:1, so
   a type is not a reliable bilateral pair the way a haltere type was.

3. **Read out every motor pool, not just the wings.**  Gravity and wind drive
   posture -- legs, neck, abdomen -- and reading only wing muscles would call a
   postural response silence.

Every result here is a **lower bound**: a silent group may be a group whose
axons were not reconstructed.  That is not a caveat to note and move past, it is
the main limit on what this run can conclude.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# vnc_motor subclasses, from flappy-haltere's fly_regions.py body map.
MOTOR_SUBCLASS = {"ad": "abdomen", "fl": "front_leg", "ml": "mid_leg",
                  "hl": "hind_leg", "wm": "wing", "nm": "neck",
                  "hm": "head", "xm": "other"}


def _motor_readouts(ann):
    motor = (ann.superclass.astype(str) == "vnc_motor").to_numpy()
    sub = ann.subclass.astype(str).to_numpy(dtype="U8")
    return {label: np.flatnonzero(motor & (sub == key)).astype(np.int32)
            for key, label in MOTOR_SUBCLASS.items()}


def _jo_groups(ann):
    """JO cells by coarse array (A, B, CA, CL, CM, ED, EV, ...), split by side."""
    types = ann.type.astype(str).to_numpy(dtype="U64")
    sub = ann.subclass.astype(str).to_numpy(dtype="U64")
    side = ann.rootSide.to_numpy()
    jo = np.flatnonzero(np.char.startswith(types, "JO-"))
    groups = {}
    for i in jo:
        arr = types[i][3:].split("-")[0].split("_")[0]
        arr = "".join(c for c in arr if c.isalpha()) or "unclear"
        groups.setdefault(f"JO-{arr}", []).append(int(i))
    out = {k: np.array(sorted(v), dtype=np.int32) for k, v in groups.items()}
    # Pooled populations are the ones the tracing check says to trust most.
    for sc in ("wind_gravity", "auditory"):
        ix = jo[sub[jo] == sc]
        out[f"pooled_{sc}"] = ix.astype(np.int32)
        for s in ("L", "R"):
            out[f"pooled_{sc}_{s}"] = ix[side[ix] == s].astype(np.int32)
    return out


def run(*, dataset="malecns_v1", currents=(8.0, 10.0, 12.0, 14.0, 20.0),
        duration_ms=500.0, out=ROOT / "outputs/jo_potency.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _reset

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    readouts = _motor_readouts(ann)
    groups = _jo_groups(ann)
    dark = np.zeros(len(brain.retina), dtype=np.float32)
    outdeg = np.diff(brain.ptr)

    # Baseline: no stimulation at all, so spontaneous motor activity is not read
    # as a response.
    _reset(brain)
    base_counts, _ = brain.step(dark, duration_ms, None)
    base = {k: int(base_counts[v].sum()) for k, v in readouts.items()}

    results, started = [], time.time()
    for name, idx in sorted(groups.items()):
        if not len(idx):
            continue
        row = {"group": name, "cells": int(len(idx)),
               "zero_output_cells": int((outdeg[idx] == 0).sum()),
               "median_out_degree": float(np.median(outdeg[idx])),
               "by_current": {}}
        for mv in currents:
            _reset(brain)
            c, _ = brain.step(dark, duration_ms, stimulation=(idx, mv))
            resp = {k: int(c[v].sum()) - base[k] for k, v in readouts.items()}
            row["by_current"][str(mv)] = {"total": sum(resp.values()), **resp}
        results.append(row)
        tot = {mv: row["by_current"][mv]["total"] for mv in row["by_current"]}
        print(f"{name:22s} n={len(idx):4d} zero={row['zero_output_cells']:3d}  " +
              " ".join(f"{mv}mV:{v:6d}" for mv, v in tot.items()), flush=True)

    report = {"dataset": dataset, "duration_ms": duration_ms,
              "currents_mV": list(currents),
              "unstimulated_baseline": base,
              "readout_cells": {k: int(len(v)) for k, v in readouts.items()},
              "caveat": "lower bound: ~13% of JO wind_gravity cells have zero "
                        "reconstructed outputs, so silence may be tracing",
              "groups": results, "wall_seconds": round(time.time() - started, 1)}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration-ms", type=float, default=500.0)
    p.add_argument("--out", default=str(ROOT / "outputs/jo_potency.json"))
    a = p.parse_args()
    r = run(duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['groups'])} groups in {r['wall_seconds']} s -> {a.out}")
