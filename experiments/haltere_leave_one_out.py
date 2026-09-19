"""Do the 198 individually-silent afferents contribute anything collectively?

The single-cell sweep found 198 of 205 haltere afferents produce zero motor
spikes when driven alone.  That does not prove they contribute nothing:
sub-threshold inputs sum at a shared target, so a population of individually
silent cells can still drive a pool that none of them could drive alone.  If
they do, the "interface is seven cells" conclusion is wrong and the
dimensionality analysis has to be redone on populations rather than individuals.

Four conditions at each current:

    all_205        every afferent
    potent_7       the seven that respond alone
    silent_198     all the rest -- the test
    all_minus_7    same as silent_198, stated separately as the leave-one-out

If silent_198 is ~0 while potent_7 ~= all_205, potency is carried by the seven
and nothing is lost by treating them as the interface.  If silent_198 is large,
sub-threshold summation matters and the seven-cell framing is an artifact of
testing cells one at a time.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

POTENT = ["101048", "136883", "946174", "808963", "809889", "801205", "810009"]


def run(*, dataset="malecns_v1", currents=(8.0, 14.0, 20.0), duration_ms=500.0,
        out=ROOT / "outputs/haltere_leave_one_out.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _readouts, _reset

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _readouts(ann)
    hal = np.flatnonzero((ann.subclass == "haltere").to_numpy()).astype(np.int32)
    ids = np.array([str(x) for x in brain.ids])
    potent = np.array([i for i in hal if ids[i] in POTENT], dtype=np.int32)
    silent = np.array([i for i in hal if ids[i] not in POTENT], dtype=np.int32)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    sets = {"all_205": hal, "potent_7": potent, "silent_198": silent}
    results = []
    for name, idx in sets.items():
        row = {"set": name, "cells": int(len(idx)), "by_current": {}}
        for mv in currents:
            _reset(brain)
            c, _ = brain.step(dark, duration_ms, stimulation=(idx, mv))
            resp = {k: int(c[v].sum()) for k, v in groups.items()}
            row["by_current"][str(mv)] = {"total": sum(resp.values()), **resp}
        results.append(row)
        print(f"{name:12s} n={len(idx):4d}  " +
              " ".join(f"{mv}mV:{row['by_current'][str(mv)]['total']:6d}" for mv in currents),
              flush=True)

    report = {"dataset": dataset, "duration_ms": duration_ms,
              "potent_body_ids": POTENT, "sets": results}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_leave_one_out.json"))
    a = p.parse_args()
    run(out=a.out)
